import yfinance as yf
import pandas as pd
import pandas_ta as ta
import json
import requests
from datetime import datetime

# --- 资产配置 ---
# 格式: (显示名称, Yahoo代码)
# 注意: 加密货币在 Yahoo 是 "BTC-USD" 格式
ASSETS = [
    ('BTC', 'BTC-USD'), ('ETH', 'ETH-USD'), ('SOL', 'SOL-USD'),
    ('BNB', 'BNB-USD'), ('DOGE', 'DOGE-USD'), ('XRP', 'XRP-USD'),
    ('PEPE', 'PEPE-USD'), ('SHIB', 'SHIB-USD'), ('WIF', 'WIF-USD'),
    ('SPY', 'SPY'), ('QQQ', 'QQQ'), ('NVDA', 'NVDA'),
    ('TSLA', 'TSLA'), ('AAPL', 'AAPL'), ('MSFT', 'MSFT'),
    ('COIN', 'COIN'), ('MSTR', 'MSTR'), ('^VIX', '^VIX')
]

def get_crypto_fear():
    try:
        url = "https://api.alternative.me/fng/?limit=1"
        response = requests.get(url, timeout=10)
        data = response.json()
        val = int(data['data'][0]['value'])
        if val < 25: label = "极度恐慌"
        elif val < 45: label = "恐慌"
        elif val > 75: label = "极度贪婪"
        elif val > 55: label = "贪婪"
        else: label = "中性"
        return val, label
    except:
        return 50, "中性"

def analyze_market():
    print("启动策略计算引擎 (Yahoo Core)...")
    
    signals = []
    tickers = [x[1] for x in ASSETS]
    
    # 1. 批量下载数据 (稳定)
    try:
        data = yf.download(tickers, period="3mo", interval="1d", group_by='ticker', auto_adjust=True, threads=True)
    except Exception as e:
        print(f"Yahoo Download Error: {e}")
        return

    # 2. 计算 VIX 情绪
    try:
        vix_price = data['^VIX']['Close'].dropna().iloc[-1]
        stock_mood = int(max(0, min(100, 100 - (vix_price - 15) * 4)))
    except:
        stock_mood = 50

    # 3. 遍历分析
    for symbol_display, symbol_yahoo in ASSETS:
        if symbol_display == '^VIX': continue
        
        try:
            # 区分类型
            asset_type = 'Crypto' if '-USD' in symbol_yahoo else 'Stock'
            
            df = data[symbol_yahoo].copy()
            df = df.ffill()
            df.dropna(inplace=True)
            
            if len(df) < 30: continue
            
            # --- 技术指标计算 ---
            df['RSI'] = df.ta.rsi(length=14)
            
            macd = df.ta.macd(fast=12, slow=26, signal=9)
            if macd is not None:
                df = pd.concat([df, macd], axis=1)
                
            df['VOL_SMA'] = df['Volume'].rolling(20).mean()
            
            bbands = df.ta.bbands(length=20, std=2)
            if bbands is not None:
                df = pd.concat([df, bbands], axis=1)
            
            df.dropna(inplace=True)
            if len(df) < 2: continue

            curr = df.iloc[-1]
            prev = df.iloc[-2]
            
            # 动态列名
            macd_col = [c for c in df.columns if c.startswith('MACD_')][0]
            macds_col = [c for c in df.columns if c.startswith('MACDs_')][0]
            bbu_col = [c for c in df.columns if c.startswith('BBU')][0]
            
            # 提取数据
            price = curr['Close']
            rsi = curr['RSI']
            vol_ratio = (curr['Volume'] / curr['VOL_SMA']) if curr['VOL_SMA'] > 0 else 1.0
            sparkline = df['Close'].tail(7).tolist()
            
            macd_val = curr[macd_col]
            macd_sig = curr[macds_col]
            
            # --- 信号逻辑 ---
            signal_type = "观察中"
            action = "持有"
            score = 50
            detail = "趋势震荡"
            
            # 策略 A: 底部金叉
            if rsi < 35 and macd_val > macd_sig:
                signal_type = "底部金叉"
                action = "买入"
                score = 90
                detail = "超卖反转"
            # 策略 B: 顶部风险
            elif rsi > 75:
                signal_type = "严重超买"
                action = "卖出"
                score = 80
                detail = f"RSI高位: {rsi:.0f}"
            # 策略 C: 量能异动
            elif vol_ratio > 2.5:
                if price > prev['Close']:
                    signal_type = "主力抢筹"
                    action = "买入"
                    score = 88
                    detail = f"放量 {vol_ratio:.1f}x"
                else:
                    signal_type = "恐慌抛售"
                    action = "卖出"
                    score = 85
                    detail = f"放量下跌 {vol_ratio:.1f}x"
            # 策略 D: 突破布林
            elif price > curr[bbu_col]:
                signal_type = "突破上轨"
                action = "买入"
                score = 75
                detail = "趋势增强"

            signals.append({
                "id": f"{symbol_display}_{int(datetime.now().timestamp())}",
                "symbol": symbol_display,
                "asset_type": asset_type,
                "price": f"{price:.2f}", # 这个价格只是参考，前端会覆盖成实时价格
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
            continue

    # 汇总
    crypto_val, crypto_label = get_crypto_fear()
    signals.sort(key=lambda x: x['score'], reverse=True)
    
    top = signals[0] if signals else None
    headline = f"关注: {top['symbol']}" if top else "市场震荡"
    body = f"{top['symbol']} 出现 {top['signal_type']} 信号。" if top else "暂无高确定性机会。"

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
    print("Strategy Calculation Complete.")

if __name__ == "__main__":
    analyze_market()
