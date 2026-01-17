import yfinance as yf
import pandas as pd
import pandas_ta as ta
import json
import requests
from datetime import datetime

# --- 核心配置 ---
TICKERS = {
    'Crypto': ['BTC-USD', 'ETH-USD', 'SOL-USD', 'BNB-USD', 'DOGE-USD', 'XRP-USD'],
    'Stock': ['SPY', 'QQQ', 'NVDA', 'TSLA', 'COIN', 'MSTR', 'AAPL', 'AMD', 'MSFT', 'AMZN']
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
    print("Fetching market data...")
    all_tickers = TICKERS['Crypto'] + TICKERS['Stock']
    
    # 下载数据
    data = yf.download(all_tickers, period="1mo", interval="1d", group_by='ticker', auto_adjust=True)
    
    signals = []
    total_rsi = 0
    valid_count = 0
    
    for symbol in all_tickers:
        try:
            # 数据清洗
            df = data[symbol].copy()
            df.dropna(inplace=True)
            
            if df.empty or len(df) < 20: 
                continue
            
            # --- 1. 计算指标 (防弹版写法) ---
            # 直接赋值，不使用 append=True，防止版本冲突
            df['RSI_14'] = df.ta.rsi(length=14)
            
            # 布林带会返回3列，我们需要分别处理
            bbands = df.ta.bbands(length=20, std=2)
            # pandas_ta 的列名通常是 BBL_20_2.0, BBM_20_2.0, BBU_20_2.0
            # 我们动态获取列名以防万一
            if bbands is not None:
                df = pd.concat([df, bbands], axis=1)
                
            df['VOL_SMA'] = df['Volume'].rolling(20).mean()
            
            # 再次清洗空值（因为计算指标会产生NaN）
            df.dropna(inplace=True)
            
            if len(df) < 7: continue

            # 获取数据点
            curr = df.iloc[-1]
            prev = df.iloc[-2]
            
            # 动态获取布林带上轨列名
            bbu_col = [c for c in df.columns if c.startswith('BBU')][0]
            
            # --- 2. 提取数据 ---
            price = curr['Close']
            rsi = curr['RSI_14']
            vol_sma = curr['VOL_SMA']
            vol_ratio = curr['Volume'] / vol_sma if vol_sma > 0 else 1.0
            
            # 提取走势 (最后7天)
            sparkline = df['Close'].tail(7).tolist()
            
            # --- 3. 信号逻辑 ---
            signal_type = "WATCHING"
            action = "HOLD"
            score = 50
            detail = "Neutral"
            
            # 策略 A: 巨鲸
            if vol_ratio > 2.0:
                if price > prev['Close']:
                    signal_type = "WHALE_INFLOW"
                    action = "BUY"
                    score = 90
                    detail = f"Vol Spike: {vol_ratio:.1f}x"
                else:
                    signal_type = "WHALE_DUMP"
                    action = "SELL"
                    score = 85
                    detail = f"Panic Sell: {vol_ratio:.1f}x"
            
            # 策略 B: RSI
            elif rsi > 75:
                signal_type = "OVERBOUGHT"
                action = "SELL"
                score = 80
                detail = f"RSI Peak: {rsi:.0f}"
            elif rsi < 25:
                signal_type = "OVERSOLD"
                action = "BUY"
                score = 85
                detail = f"RSI Bottom: {rsi:.0f}"
            
            # 策略 C: 突破
            elif price > curr[bbu_col]:
                signal_type = "BREAKOUT"
                action = "BUY"
                score = 75
                detail = "Breakout"
            
            clean_symbol = symbol.replace("-USD", "")
            
            signals.append({
                "id": f"{clean_symbol}_{int(datetime.now().timestamp())}",
                "symbol": clean_symbol,
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
            
            total_rsi += rsi
            valid_count += 1
            
        except Exception as e:
            # 打印错误但不中断整个脚本
            print(f"Skipping {symbol}: {e}")
            continue

    # 汇总
    mood = int(total_rsi / valid_count) if valid_count > 0 else 50
    signals.sort(key=lambda x: x['score'], reverse=True)
    
    top_sig = signals[0] if signals else None
    headline = f"Focus: {top_sig['symbol']}" if top_sig else "Market Choppy"
    body = "Institutional activity detected." if top_sig else "Low volume."

    output = {
        "meta": {"updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
        "dashboard": {
            "crypto_fear_index": fear_val,
            "crypto_fear_label": fear_label,
            "stock_market_mood": mood,
            "market_summary_headline": headline,
            "market_summary_body": body
        },
        "signals": signals
    }
    
    with open('data.json', 'w') as f:
        json.dump(output, f, indent=2)
    print("Success: data.json created")

if __name__ == "__main__":
    fear_val, fear_label = get_crypto_fear()
    analyze_market()
