import yfinance as yf
import pandas as pd
import pandas_ta as ta
import json
import requests
import time
from datetime import datetime

# --- Asset Configuration ---
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
        response = requests.get(url, timeout=5)
        data = response.json()
        val = int(data['data'][0]['value'])
        # Translate fear labels to English
        if val < 25: label = "Extreme Fear"
        elif val < 45: label = "Fear"
        elif val > 75: label = "Extreme Greed"
        elif val > 55: label = "Greed"
        else: label = "Neutral"
        return val, label
    except:
        return 50, "Neutral"

def generate_analysis_report(symbol, price, rsi, macd_val, macd_sig, vol_ratio, close_price, lower_band, upper_band):
    """
    [Core Upgrade] Generate traceable logic analysis report (in English)
    """
    report_parts = []
    
    # 1. Trend Analysis (MACD)
    if macd_val > macd_sig:
        report_parts.append("MACD is above signal line, indicating a bullish trend.")
    else:
        report_parts.append("MACD momentum is weakening, potential pullback ahead.")
        
    # 2. Sentiment Analysis (RSI)
    if rsi < 30:
        report_parts.append(f" RSI dropped to {rsi:.1f}, entering [Oversold] zone. Rebound likely.")
    elif rsi > 70:
        report_parts.append(f" RSI reached {rsi:.1f}, entering [Overbought] zone. Caution advised.")
    else:
        report_parts.append(f" RSI ({rsi:.1f}) is in neutral zone.")
        
    # 3. Volume Analysis
    if vol_ratio > 2.0:
        direction = "institutional buying" if price > close_price else "panic selling"
        report_parts.append(f" Abnormal volume detected ({vol_ratio:.1f}x avg), showing {direction}.")
    elif vol_ratio < 0.6:
        report_parts.append(" Volume is extremely low, market is waiting for direction.")
        
    # 4. Pattern Analysis (Bollinger Bands)
    if price < lower_band:
        report_parts.append(" Price broke below Bollinger Lower Band. Mean reversion expected.")
    elif price > upper_band:
        report_parts.append(" Price broke above Bollinger Upper Band. Strong momentum.")
        
    # Combine
    full_report = " ".join(report_parts)
    return full_report

def analyze_market():
    print("Starting Logic Analysis Engine...")
    
    signals = []
    tickers = [x[1] for x in ASSETS]
    
    try:
        data = yf.download(tickers, period="3mo", interval="1d", group_by='ticker', auto_adjust=True, threads=True)
    except Exception as e:
        print(f"Data Error: {e}")
        return

    # VIX Logic
    try:
        vix_price = data['^VIX']['Close'].dropna().iloc[-1]
        # Simple inversion: Low VIX = High Stock Mood
        stock_mood = int(max(0, min(100, 100 - (vix_price - 15) * 4)))
    except:
        stock_mood = 50

    for symbol_display, symbol_yahoo in ASSETS:
        if symbol_display == '^VIX': continue
        
        try:
            asset_type = 'Crypto' if '-USD' in symbol_yahoo else 'Stock'
            df = data[symbol_yahoo].copy()
            df = df.ffill()
            df.dropna(inplace=True)
            
            if len(df) < 30: continue
            
            # Indicators
            df['RSI'] = df.ta.rsi(length=14)
            macd = df.ta.macd(fast=12, slow=26, signal=9)
            if macd is not None: df = pd.concat([df, macd], axis=1)
            
            df['VOL_SMA'] = df['Volume'].rolling(20).mean()
            bbands = df.ta.bbands(length=20, std=2)
            if bbands is not None: df = pd.concat([df, bbands], axis=1)
            
            df.dropna(inplace=True)
            curr = df.iloc[-1]
            prev = df.iloc[-2]
            
            # Column mapping
            macd_col = [c for c in df.columns if c.startswith('MACD_')][0]
            macds_col = [c for c in df.columns if c.startswith('MACDs_')][0]
            bbl_col = [c for c in df.columns if c.startswith('BBL')][0]
            bbu_col = [c for c in df.columns if c.startswith('BBU')][0]
            
            price = curr['Close']
            rsi = curr['RSI']
            vol_ratio = (curr['Volume'] / curr['VOL_SMA']) if curr['VOL_SMA'] > 0 else 1.0
            
            macd_val = curr[macd_col]
            macd_sig = curr[macds_col]
            
            # --- Decision Logic (English Keys) ---
            signal_type = "Watching"
            action = "Watch"
            score = 50
            detail = "Choppy"
            
            if rsi < 35 and macd_val > macd_sig:
                signal_type = "Golden Cross"
                action = "Buy"
                score = 88
                detail = "Oversold Reversal"
            elif rsi > 75:
                signal_type = "Severe Overbought"
                action = "Sell"
                score = 80
                detail = f"High RSI: {rsi:.0f}"
            elif vol_ratio > 2.5:
                if price > prev['Close']:
                    signal_type = "Whale Buy"
                    action = "Buy"
                    score = 85
                    detail = "Volume Spike"
                else:
                    signal_type = "Panic Sell"
                    action = "Sell"
                    score = 82
                    detail = "Volume Dump"
            elif price > curr[bbu_col]:
                signal_type = "Breakout"
                action = "Hold"
                score = 70
                detail = "Strong Trend"
            
            # --- [Core] Generate AI Analysis Report (English) ---
            ai_analysis_text = generate_analysis_report(
                symbol_display, price, rsi, macd_val, macd_sig, vol_ratio, prev['Close'], curr[bbl_col], curr[bbu_col]
            )

            signals.append({
                "id": f"{symbol_display}_{int(datetime.now().timestamp())}",
                "symbol": symbol_display,
                "asset_type": asset_type,
                "price": f"{price:.2f}",
                "signal_type": signal_type,
                "action": action, # Now returns "Buy", "Sell", "Watch", "Hold"
                "value_display": detail,
                "score": score,
                "ai_analysis": ai_analysis_text, # English text
                "sparkline": df['Close'].tail(7).tolist(),
                "stats": {
                    "rsi": f"{rsi:.1f}",
                    "vol_ratio": f"{vol_ratio:.1f}x",
                    "high_24h": f"{curr['High']:.2f}",
                    "low_24h": f"{curr['Low']:.2f}"
                }
            })
            
        except Exception as e:
            continue

    crypto_val, crypto_label = get_crypto_fear()
    signals.sort(key=lambda x: x['score'], reverse=True)
    
    output = {
        "meta": {"updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
        "dashboard": {
            "crypto_fear_index": crypto_val,
            "crypto_fear_label": crypto_label, # Now in English
            "stock_market_mood": stock_mood,
            "market_summary_headline": f"Opportunity: {signals[0]['symbol']}" if signals else "Market Flat",
            "market_summary_body": "AI Strategy Engine has completed a full market scan. Volatility detected in key sectors. Check detailed signals below."
        },
        "signals": signals
    }
    
    with open('data.json', 'w') as f:
        json.dump(output, f, indent=2)
    print("Logic Analysis Complete (English).")

if __name__ == "__main__":
    analyze_market()
