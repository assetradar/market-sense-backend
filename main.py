import yfinance as yf
import pandas as pd
import pandas_ta as ta
import json
import requests
from datetime import datetime

# --- 配置区 ---
TICKERS = {
    'Crypto': ['BTC-USD', 'ETH-USD', 'SOL-USD', 'BNB-USD', 'DOGE-USD'],
    'Stock': ['SPY', 'QQQ', 'NVDA', 'TSLA', 'COIN', 'MSTR', 'AAPL', 'AMD']
}

def get_crypto_fear():
    try:
        url = "https://api.alternative.me/fng/?limit=1"
        response = requests.get(url, timeout=10)
        data = response.json()
        return int(data['data'][0]['value']), data['data'][0]['value_classification']
    except:
        return 50, "Neutral"

def analyze_market():
    all_tickers = TICKERS['Crypto'] + TICKERS['Stock']
    # 下载数据：足够计算指标 + 画 7 天走势图
    data = yf.download(all_tickers, period="1mo", interval="1d", group_by='ticker')
    
    signals = []
    dashboard_mood = 50
    valid_count = 0
    total_rsi = 0
    
    for symbol in all_tickers:
        try:
            df = data[symbol].copy()
            if df.empty or len(df) < 20: continue
            
            # 1. 计算指标
            df.ta.rsi(length=14, append=True)
            df.ta.bbands(length=20, std=2, append=True)
            df['VOL_SMA'] = df['Volume'].rolling(20).mean()
            
            curr = df.iloc[-1]
            prev = df.iloc[-2]
            
            # 2. 提取关键数据
            rsi = curr['RSI_14']
            price = curr['Close']
            # --- 关键升级：提取过去 7 天的收盘价 (用于 App 画迷你图) ---
            # 取最后 7 个点，转为列表
            sparkline = df['Close'].tail(7).tolist()
            
            # 3. 信号逻辑 (保持商业级逻辑)
            signal_type = "NEUTRAL"
            action = "HOLD"
            score = 50
            detail = "Watching"
            
            # A. 巨鲸逻辑
            if curr['Volume'] > (curr['VOL_SMA'] * 2.0):
                if price > prev['Close']:
                    signal_type = "WHALE_INFLOW"
                    action = "BUY"
                    score = 90
                    detail = "High Vol Accumulation"
                else:
                    signal_type = "WHALE_DUMP"
                    action = "SELL"
                    score = 85
                    detail = "Panic Selling Detected"
            
            # B. RSI 逻辑
            elif rsi > 75:
                signal_type = "OVERBOUGHT"
                action = "SELL"
                score = 80
                detail = f"RSI Peak: {rsi:.1f}"
            elif rsi < 25:
                signal_type = "OVERSOLD"
                action = "BUY"
                score = 85
                detail = f"RSI Bottom: {rsi:.1f}"
            
            # 只有高价值信号才推送到前台，或者如果不属于高价值，但也保留基础数据供查询
            # 为了让 App 列表丰富，我们这次把所有数据都保留，但在 App 端过滤
            clean_symbol = symbol.replace("-USD", "")
            
            signals.append({
                "id": f"{clean_symbol}_{datetime.now().timestamp()}",
                "symbol": clean_symbol,
                "price": f"{price:.2f}",
                "signal_type": signal_type,
                "action": action,
                "value_display": detail,
                "score": score,
                "sparkline": sparkline, # <--- 新增字段：走势数组
                "stats": { # <--- 新增字段：详情页用的数据
                    "rsi": f"{rsi:.1f}",
                    "vol_ratio": f"{curr['Volume']/curr['VOL_SMA']:.1f}x",
                    "high_24h": f"{curr['High']:.2f}",
                    "low_24h": f"{curr['Low']:.2f}"
                }
            })
            
            total_rsi += rsi
            valid_count += 1
            
        except Exception as e:
            continue

    if valid_count > 0:
        dashboard_mood = int(total_rsi / valid_count)
        
    # 按分数排序
    signals.sort(key=lambda x: x['score'], reverse=True)
    
    return signals, dashboard_mood

def main():
    fear_val, fear_label = get_crypto_fear()
    generated_signals, stock_mood = analyze_market()
    
    top_sig = generated_signals[0] if generated_signals else None
    headline = f"Focus: {top_sig['symbol']}" if top_sig else "Market Choppy"
    body = "Institutional volume anomalies detected." if top_sig else "Low liquidity environment."

    output = {
        "meta": {"updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
        "dashboard": {
            "crypto_fear_index": fear_val,
            "crypto_fear_label": fear_label,
            "stock_market_mood": stock_mood,
            "market_summary_headline": headline,
            "market_summary_body": body
        },
        "signals": generated_signals
    }
    
    with open('data.json', 'w') as f:
        json.dump(output, f, indent=2)

if __name__ == "__main__":
    main()
