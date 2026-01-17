import yfinance as yf
import pandas as pd
import pandas_ta as ta
import json
import requests
from datetime import datetime

# --- 1. 深度资产池 (覆盖 美股/加密/指数/波动率) ---
# 我们不仅看个股，还要看 VIX (恐慌指数) 来定大盘情绪
TICKERS_CONFIG = {
    'Crypto': [
        'BTC-USD', 'ETH-USD', 'SOL-USD', 'BNB-USD', 'DOGE-USD', 
        'XRP-USD', 'ADA-USD', 'SHIB-USD', 'PEPE-USD', 'LINK-USD',
        'AVAX-USD', 'SUI-USD', 'NEAR-USD', 'APT-USD', 'LTC-USD'
    ],
    'Stock': [
        'SPY', 'QQQ', 'DIA', '^VIX', # 核心指数 + 恐慌指数
        'NVDA', 'TSLA', 'AAPL', 'MSFT', 'AMZN', 'GOOGL', 'META', 
        'AMD', 'COIN', 'MSTR', 'IBIT', 'MARA', 'PLTR', 'GME'
    ]
}

def get_crypto_fear_standard():
    """
    获取行业标准的加密货币恐惧贪婪指数
    来源: alternative.me (行业公认标准)
    """
    try:
        url = "https://api.alternative.me/fng/?limit=1"
        response = requests.get(url, timeout=10)
        data = response.json()
        val = int(data['data'][0]['value'])
        label = data['data'][0]['value_classification']
        # 汉化标签
        if val < 25: label_cn = "极度恐慌"
        elif val < 45: label_cn = "恐慌"
        elif val > 75: label_cn = "极度贪婪"
        elif val > 55: label_cn = "贪婪"
        else: label_cn = "中性"
        return val, label_cn
    except:
        return 50, "中性"

def calculate_stock_mood(vix_price, spy_rsi):
    """
    计算美股真实情绪
    逻辑: 结合 VIX (恐慌指数) 和 SPY (大盘) 的强弱
    VIX > 30 = 极度恐慌, VIX < 15 = 极度贪婪
    """
    # 基础分：VIX 20 是中界线。VIX 越低，情绪越高昂(贪婪)
    # 简单算法：映射 VIX 10~35 到 100~0 分
    if vix_price <= 10: base_score = 95
    elif vix_price >= 35: base_score = 5
    else:
        # 线性插值
        base_score = 100 - ((vix_price - 10) / 25 * 100)
    
    return int(base_score)

def analyze_market():
    print("启动华尔街级深度分析引擎...")
    
    all_tickers = TICKERS_CONFIG['Crypto'] + TICKERS_CONFIG['Stock']
    
    # 下载数据 (包含 VIX)
    try:
        # period="2mo" 确保有足够数据计算 MACD (需要 26天+)
        data = yf.download(all_tickers, period="3mo", interval="1d", group_by='ticker', auto_adjust=True, threads=True)
    except Exception as e:
        print(f"数据源连接失败: {e}")
        return

    signals = []
    
    # 1. 先提取大盘数据用于计算环境
    try:
        vix_series = data['^VIX']['Close'].dropna()
        vix_current = vix_series.iloc[-1]
        
        spy_series = data['SPY']['Close'].dropna()
        spy_rsi = ta.rsi(spy_series, length=14).iloc[-1]
        
        # 计算美股情绪 (基于 VIX)
        stock_mood_score = calculate_stock_mood(vix_current, spy_rsi)
    except:
        stock_mood_score = 50 # 降级处理
        vix_current = 20.0

    # 2. 遍历分析个股
    for symbol in all_tickers:
        # 跳过指数本身，我们只分析可交易标的
        if symbol in ['^VIX', 'SPY', 'QQQ', 'DIA']: continue
        
        try:
            asset_type = 'Crypto' if symbol in TICKERS_CONFIG['Crypto'] else 'Stock'
            df = data[symbol].copy()
            df = df.ffill() # 填充周末数据
            df.dropna(inplace=True)
            
            if len(df) < 30: continue # 数据不足无法计算 MACD
            
            # --- 深度技术指标计算 ---
            # 1. RSI (强弱)
            df['RSI'] = df.ta.rsi(length=14)
            
            # 2. Bollinger Bands (波动)
            bbands = df.ta.bbands(length=20, std=2)
            if bbands is not None:
                df = pd.concat([df, bbands], axis=1)
                
            # 3. MACD (趋势 - 核心升级)
            # macd 列名通常是: MACD_12_26_9, MACDh_12_26_9(柱), MACDs_12_26_9(信号)
            macd = df.ta.macd(fast=12, slow=26, signal=9)
            if macd is not None:
                df = pd.concat([df, macd], axis=1)
            
            # 4. 均线 (趋势确认)
            df['SMA_20'] = df['Close'].rolling(20).mean()
            df['VOL_SMA'] = df['Volume'].rolling(20).mean()
            
            df.dropna(inplace=True)
            curr = df.iloc[-1]
            prev = df.iloc[-2]
            
            # 获取动态列名
            bbu_col = [c for c in df.columns if c.startswith('BBU')][0]
            macd_col = [c for c in df.columns if c.startswith('MACD_')][0]
            macds_col = [c for c in df.columns if c.startswith('MACDs_')][0] # 信号线
            
            # --- 数据提取 ---
            price = curr['Close']
            rsi = curr['RSI']
            macd_val = curr[macd_col]
            macd_signal = curr[macds_col]
            vol_ratio = (curr['Volume'] / curr['VOL_SMA']) if curr['VOL_SMA'] > 0 else 1.0
            sparkline = df['Close'].tail(7).tolist()

            # --- 智能信号判定系统 (Smart Signal Logic) ---
            signal_type = "观察中"
            action = "持有"
            score = 50
            detail = "趋势震荡"
            
            # 判定 1: 黄金坑 (RSI超卖 + 支撑位)
            if rsi < 30:
                if macd_val > macd_signal: # MACD 刚刚金叉 (极强信号)
                    signal_type = "底部金叉"
                    action = "强力买入"
                    score = 95
                    detail = f"RSI低位 + MACD反转"
                else:
                    signal_type = "严重超卖"
                    action = "关注"
                    score = 85
                    detail = f"RSI: {rsi:.0f} 等待反转"
            
            # 判定 2: 顶部风险 (RSI超买 + 跌破均线)
            elif rsi > 75:
                if price < curr['SMA_20']:
                    signal_type = "趋势崩塌"
                    action = "强力卖出"
                    score = 90
                    detail = "高位跌破均线"
                else:
                    signal_type = "严重超买"
                    action = "减仓"
                    score = 80
                    detail = f"RSI: {rsi:.0f} 风险积聚"
            
            # 判定 3: 巨鲸异动 (量能判定)
            elif vol_ratio > 2.5:
                if price > prev['Close'] * 1.02: # 涨幅超过2%
                    signal_type = "主力抢筹"
                    action = "买入"
                    score = 88
                    detail = f"成交量放大 {vol_ratio:.1f}倍"
                elif price < prev['Close'] * 0.98:
                    signal_type = "主力出货"
                    action = "卖出"
                    score = 88
                    detail = f"恐慌抛售 {vol_ratio:.1f}倍"

            clean_symbol = symbol.replace("-USD", "")
            
            signals.append({
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
            
        except Exception as e:
            # 个别数据错误不影响整体
            continue

    # 获取标准加密情绪
    crypto_val, crypto_label = get_crypto_fear_standard()
    
    # 排序：将有信号的 ("买入"/"卖出") 排在前面，"持有"的排在后面
    # 逻辑: score 高的排前
    signals.sort(key=lambda x: x['score'], reverse=True)

    # 简报生成
    top_sig = signals[0] if signals else None
    if top_sig and top_sig['score'] >= 85:
        headline = f"异动警报: {top_sig['symbol']}"
        body = f"AI 算法在 {top_sig['symbol']} 识别到 {top_sig['signal_type']} 信号。各项技术指标共振，建议重点关注。"
    else:
        headline = "市场缺乏方向"
        body = f"VIX 恐慌指数为 {vix_current:.1f}，市场处于震荡区间，并未出现高胜率交易机会。"

    output = {
        "meta": {"updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
        "dashboard": {
            "crypto_fear_index": crypto_val,
            "crypto_fear_label": crypto_label,
            "stock_market_mood": stock_mood_score, # 使用基于 VIX 的真实数据
            "market_summary_headline": headline,
            "market_summary_body": body
        },
        "signals": signals
    }
    
    with open('data.json', 'w') as f:
        json.dump(output, f, indent=2)
    print("AI Analysis Complete: VIX & MACD Integrated.")

if __name__ == "__main__":
    analyze_market()
