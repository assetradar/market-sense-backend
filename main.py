import yfinance as yf
import pandas as pd
import pandas_ta as ta
import json
import requests
import time
from datetime import datetime

# --- 1. 双核资产配置 ---
# 币安符号 (必须是 USDT 交易对)
CRYPTO_SYMBOLS = [
    'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'DOGEUSDT', 
    'XRPUSDT', 'ADAUSDT', 'SHIBUSDT', 'PEPEUSDT', 'WIFUSDT',
    'LINKUSDT', 'AVAXUSDT', 'NEARUSDT', 'FETUSDT', 'RNDRUSDT'
]

# 美股符号 (Yahoo Finance 格式)
STOCK_SYMBOLS = [
    'SPY', 'QQQ', 'DIA', '^VIX', # 指数
    'NVDA', 'TSLA', 'AAPL', 'MSFT', 'AMZN', 'GOOGL', 'META', 
    'AMD', 'COIN', 'MSTR', 'IBIT', 'MARA', 'PLTR', 'GME'
]

def get_crypto_fear_standard():
    """获取行业标准的加密恐惧指数"""
    try:
        url = "https://api.alternative.me/fng/?limit=1"
        response = requests.get(url, timeout=10)
        data = response.json()
        val = int(data['data'][0]['value'])
        # 简单汉化
        if val < 25: label = "极度恐慌"
        elif val < 45: label = "恐慌"
        elif val > 75: label = "极度贪婪"
        elif val > 55: label = "贪婪"
        else: label = "中性"
        return val, label
    except:
        return 50, "中性"

def fetch_binance_candles(symbol):
    """
    [核心升级] 直连币安 API 获取 K 线数据
    无需 API Key，完全免费
    """
    url = "https://api.binance.com/api/v3/klines"
    params = {
        'symbol': symbol,
        'interval': '1d',  # 日线
        'limit': 50        # 获取过去50天数据用于计算指标
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        # 币安返回的是列表，需要转成 DataFrame
        # 格式: [Open Time, Open, High, Low, Close, Volume, ...]
        df = pd.DataFrame(data, columns=[
            'Open Time', 'Open', 'High', 'Low', 'Close', 'Volume', 
            'Close Time', 'Quote Asset Volume', 'Number of Trades', 
            'Taker Buy Base Asset Volume', 'Taker Buy Quote Asset Volume', 'Ignore'
        ])
        
        # 数据类型转换 (字符串 -> 浮点数)
        numeric_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        df[numeric_cols] = df[numeric_cols].astype(float)
        
        return df
    except Exception as e:
        print(f"Binance API Error [{symbol}]: {e}")
        return pd.DataFrame()

def analyze_market():
    print("启动双核分析引擎 (Binance + Yahoo)...")
    
    signals = []
    
    # ---------------------------
    # 引擎 1: 加密货币 (Binance)
    # ---------------------------
    print(f"正在连接币安节点 ({len(CRYPTO_SYMBOLS)} Assets)...")
    for symbol in CRYPTO_SYMBOLS:
        try:
            df = fetch_binance_candles(symbol)
            if df.empty or len(df) < 30: continue
            
            # --- 技术指标计算 (通用逻辑) ---
            process_technical_analysis(df, symbol, 'Crypto', signals)
            
            # 避免 API 速率限制 (虽然币安额度很高，但安全起见)
            time.sleep(0.1)
            
        except Exception as e:
            print(f"Error Crypto {symbol}: {e}")

    # ---------------------------
    # 引擎 2: 美股 (Yahoo)
    # ---------------------------
    print(f"正在连接美股节点 ({len(STOCK_SYMBOLS)} Assets)...")
    try:
        # 批量下载美股数据
        stock_data = yf.download(STOCK_SYMBOLS, period="3mo", interval="1d", group_by='ticker', auto_adjust=True, threads=True)
        
        # 计算美股大盘情绪 (VIX)
        try:
            vix_price = stock_data['^VIX']['Close'].iloc[-1]
            # VIX > 30 恐慌(0分), VIX < 15 贪婪(100分)
            stock_mood = int(max(0, min(100, 100 - (vix_price - 15) * 4)))
        except:
            stock_mood = 50

        for symbol in STOCK_SYMBOLS:
            if symbol == '^VIX': continue # VIX 只用于计算情绪，不作为个股展示
            
            try:
                df = stock_data[symbol].copy()
                df = df.ffill() # 填充
                df.dropna(inplace=True)
                if len(df) < 30: continue
                
                process_technical_analysis(df, symbol, 'Stock', signals)
            except:
                continue
                
    except Exception as e:
        print(f"Yahoo API Error: {e}")
        stock_mood = 50

    # ---------------------------
    # 汇总输出
    # ---------------------------
    crypto_val, crypto_label = get_crypto_fear_standard()
    
    # 排序：高分优先
    signals.sort(key=lambda x: x['score'], reverse=True)
    
    # 生成简报
    top_sig = signals[0] if signals else None
    if top_sig and top_sig['score'] >= 85:
        headline = f"主力异动: {top_sig['symbol']}"
        body = f"双核引擎在 {top_sig['symbol']} 监测到 {top_sig['signal_type']}。成交量激增 {top_sig['stats']['vol_ratio']}，趋势反转确立。"
    else:
        headline = "市场清洗筹码"
        body = "多空双方博弈激烈，暂无确定性主升浪信号，建议保持观望。"

    output = {
        "meta": {"updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
        "dashboard": {
            "crypto_fear_index": crypto_val,
            "crypto_fear_label": crypto_label,
            "stock_market_mood": stock_mood,
            "market_summary_headline": headline,
            "market_summary_body": body
        },
        "signals": signals
    }
    
    with open('data.json', 'w') as f:
        json.dump(output, f, indent=2)
    print("Success: Hybrid Data Generated.")

def process_technical_analysis(df, raw_symbol, asset_type, signals_list):
    """
    通用技术分析内核 (处理 DF -> Signal)
    """
    # 1. 计算指标
    df['RSI'] = df.ta.rsi(length=14)
    
    # MACD
    macd = df.ta.macd(fast=12, slow=26, signal=9)
    if macd is not None:
        df = pd.concat([df, macd], axis=1)
        
    # 布林带
    bbands = df.ta.bbands(length=20, std=2)
    if bbands is not None:
        df = pd.concat([df, bbands], axis=1)
        
    df['VOL_SMA'] = df['Volume'].rolling(20).mean()
    
    df.dropna(inplace=True)
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    # 动态获取列名
    bbu_col = [c for c in df.columns if c.startswith('BBU')][0]
    macd_col = [c for c in df.columns if c.startswith('MACD_')][0]
    macds_col = [c for c in df.columns if c.startswith('MACDs_')][0]
    
    # 提取数值
    price = curr['Close']
    rsi = curr['RSI']
    vol_ratio = (curr['Volume'] / curr['VOL_SMA']) if curr['VOL_SMA'] > 0 else 1.0
    sparkline = df['Close'].tail(7).tolist()
    
    macd_val = curr[macd_col]
    macd_sig = curr[macds_col]
    
    # --- 智能判定逻辑 ---
    signal_type = "观察中"
    action = "持有"
    score = 50
    detail = "趋势震荡"
    
    # 1. 底部共振 (RSI低位 + MACD金叉 + 巨量)
    if rsi < 35:
        if macd_val > macd_sig and vol_ratio > 1.5:
            signal_type = "底部爆发"
            action = "强力买入"
            score = 98
            detail = "金叉+放量+超卖"
        elif macd_val > macd_sig:
            signal_type = "趋势反转"
            action = "买入"
            score = 85
            detail = "底部金叉确认"
        else:
            signal_type = "严重超卖"
            action = "关注"
            score = 75
            detail = "等待启动信号"
            
    # 2. 顶部风险
    elif rsi > 75:
        if macd_val < macd_sig:
            signal_type = "顶部死叉"
            action = "强力卖出"
            score = 90
            detail = "动能衰竭"
        else:
            signal_type = "极度狂热"
            action = "减仓"
            score = 80
            detail = f"RSI高位: {rsi:.0f}"
            
    # 3. 巨鲸异动 (不看 RSI，只看量)
    elif vol_ratio > 3.0:
        if price > prev['Close']:
            signal_type = "巨鲸抢筹"
            action = "买入"
            score = 92
            detail = f"爆量上涨 {vol_ratio:.1f}x"
        else:
            signal_type = "恐慌出逃"
            action = "卖出"
            score = 88
            detail = f"爆量砸盘 {vol_ratio:.1f}x"
            
    # 净化名称 (BTCUSDT -> BTC)
    clean_symbol = raw_symbol.replace("USDT", "").replace("-USD", "")
    
    signals_list.append({
        "id": f"{clean_symbol}_{int(datetime.now().timestamp())}",
        "symbol": clean_symbol,
        "asset_type": asset_type,
        "price": f"{price:.2f}",
        "signal_type": signal_type,
        "action": action,
        "value_display": detail,
        "score": score,
        "sparkline": sparkline,
        "stats": {
            "rsi": f"{rsi:.1f}",
            "vol_ratio": f"{vol_ratio:.1f}x",
            "high_24h": f"{curr['High']:.2f}",
            "low_24h": f"{curr['Low']:.2f}"
        }
    })

if __name__ == "__main__":
    analyze_market()
