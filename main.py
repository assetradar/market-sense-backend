import yfinance as yf
import pandas as pd
import pandas_ta as ta
import json
import requests
from datetime import datetime

# --- 核心资产配置 ---
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
    
    # 抓取足够多的数据用于画图 (1个月数据)
    data = yf.download(all_tickers, period="1mo", interval="1d", group_by='ticker', auto_adjust=True)
    
    signals = []
    total_rsi = 0
    valid_count = 0
    
    for symbol in all_tickers:
        try:
            # 提取单个资产数据
            df = data[symbol].copy()
            
            # 数据清洗：去除空值，确保数据量足够
            df.dropna(inplace=True)
            if df.empty or len(df) < 20: 
                continue
            
            # --- 1. 计算技术指标 ---
            df.ta.rsi(length=14, append=True)
            df.ta.bbands(length=20, std=2, append=True)
            df['VOL_SMA'] = df['Volume'].rolling(20).mean()
            
            # 获取最新一行和前一行
            curr = df.iloc[-1]
            prev = df.iloc[-2]
            
            # --- 2. 提取关键数据 ---
            price = curr['Close']
            rsi = curr['RSI_14']
            vol_ratio = curr['Volume'] / curr['VOL_SMA'] if curr['VOL_SMA'] > 0 else 1.0
            
            # 关键：提取过去 7 天收盘价用于画图 (转为列表)
            sparkline = df['Close'].tail(7).tolist()
            
            # --- 3. 信号判定逻辑 (商业级) ---
            signal_type = "WATCHING"
            action = "HOLD"
            score = 50
            detail = "Neutral Trend"
            
            # 策略 A: 巨鲸异动 (量比 > 2.0)
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
            
            # 策略 B: RSI 极端反转
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
            
            # 策略 C: 趋势跟随 (MACD/均线逻辑可后续加，这里简化)
            elif price > curr['BBU_20_2.0']: # 突破布林上轨
                signal_type = "BREAKOUT"
                action = "BUY"
                score = 75
                detail = "Upper Band Break"
            
            # 清理代码名称
            clean_symbol = symbol.replace("-USD", "")
            
            # 构造数据对象
            signals.append({
                "id": f"{clean_symbol}_{int(datetime.now().timestamp())}",
                "symbol": clean_symbol,
                "price": f"{price:.2f}",
                "signal_type": signal_type,
                "action": action,
                "value_display": detail,
                "score": score,
                "sparkline": sparkline, # <--- 核心新增：走势数据
                "stats": {              # <--- 核心新增：详情统计
                    "rsi": f"{rsi:.1f}",
                    "vol_ratio": f"{vol_ratio:.1f}x",
                    "high_24h": f"{curr['High']:.2f}",
                    "low_24h": f"{curr['Low']:.2f}"
                }
            })
            
            total_rsi += rsi
            valid_count += 1
            
        except Exception as e:
            print(f"Error processing {symbol}: {e}")
            continue

    # 计算市场情绪分
    dashboard_mood = int(total_rsi / valid_count) if valid_count > 0 else 50
    
    # 排序：高分信号排前面
    signals.sort(key=lambda x: x['score'], reverse=True)
    
    # 生成头部文案
    top_sig = signals[0] if signals else None
    if top_sig and top_sig['score'] >= 80:
        headline = f"Focus: {top_sig['symbol']} Move"
        body = f"Detected {top_sig['signal_type'].replace('_',' ')} pattern. Institutional volume suggests {top_sig['action']} setup."
    else:
        headline = "Market is Choppy"
        body = "No high-confidence signals detected. Liquidity is low. Exercise caution."

    output = {
        "meta": {"updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
        "dashboard": {
            "crypto_fear_index": fear_val,
            "crypto_fear_label": fear_label,
            "stock_market_mood": dashboard_mood,
            "market_summary_headline": headline,
            "market_summary_body": body
        },
        "signals": signals # 返回所有信号，App端决定显示多少
    }
    
    with open('data.json', 'w') as f:
        json.dump(output, f, indent=2)
    print("Analysis Complete. data.json generated.")

if __name__ == "__main__":
    fear_val, fear_label = get_crypto_fear()
    analyze_market()
