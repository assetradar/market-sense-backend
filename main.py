import yfinance as yf
import pandas as pd
import pandas_ta as ta # 必须确保安装了 pandas_ta
import json
import requests
from datetime import datetime

# --- 配置区 ---
TICKERS = {
    'Crypto': ['BTC-USD', 'ETH-USD', 'SOL-USD', 'BNB-USD', 'DOGE-USD'],
    'Stock': ['SPY', 'QQQ', 'NVDA', 'TSLA', 'COIN', 'MSTR']
}

# 1. 获取恐慌指数 (保持不变)
def get_crypto_fear():
    try:
        url = "https://api.alternative.me/fng/?limit=1"
        response = requests.get(url, timeout=10)
        data = response.json()
        value = int(data['data'][0]['value'])
        label = data['data'][0]['value_classification']
        return value, label
    except:
        return 50, "Neutral"

# 2. 核心算法：生成高级信号
def analyze_market():
    all_tickers = TICKERS['Crypto'] + TICKERS['Stock']
    
    # 下载更多数据以便计算 MACD 和 布林带
    data = yf.download(all_tickers, period="3mo", interval="1d", group_by='ticker')
    
    signals = []
    dashboard_mood = 50 # 默认分
    valid_tickers_count = 0
    total_rsi = 0
    
    for symbol in all_tickers:
        try:
            df = data[symbol].copy()
            if df.empty or len(df) < 30: continue
            
            # --- A. 计算技术指标 ---
            # 1. RSI (相对强弱)
            df.ta.rsi(length=14, append=True)
            # 2. Bollinger Bands (布林带 - 衡量波动)
            df.ta.bbands(length=20, std=2, append=True)
            # 3. MACD (趋势)
            df.ta.macd(fast=12, slow=26, signal=9, append=True)
            # 4. Volume SMA (成交量均线 - 用于抓巨鲸)
            df['VOL_SMA_20'] = df['Volume'].rolling(window=20).mean()
            
            # 获取最新一行数据
            curr = df.iloc[-1]
            prev = df.iloc[-2]
            
            # 动态列名 (pandas_ta 自动生成的列名)
            rsi_val = curr['RSI_14']
            upper_band = curr['BBU_20_2.0']
            lower_band = curr['BBL_20_2.0']
            macd = curr['MACD_12_26_9']
            macd_signal = curr['MACDs_12_26_9']
            vol_avg = curr['VOL_SMA_20']
            curr_vol = curr['Volume']
            close_price = curr['Close']
            
            # 累加用于计算整体市场情绪
            total_rsi += rsi_val
            valid_tickers_count += 1
            
            clean_symbol = symbol.replace("-USD", "")
            
            # --- B. 商业级信号逻辑 (The Alpha) ---
            
            # 策略 1: 巨鲸异动 (Whale Alert)
            # 逻辑: 成交量是 20日均线的 2.5倍 + 价格变动
            if curr_vol > (vol_avg * 2.5):
                signal_type = "WHALE_INFLOW" if close_price > prev['Close'] else "WHALE_DUMP"
                action = "BUY" if close_price > prev['Close'] else "SELL"
                score = 95 # 高权重
                signals.append({
                    "id": f"whale_{clean_symbol}",
                    "symbol": clean_symbol,
                    "signal_type": signal_type,
                    "value_display": f"Vol: {int(curr_vol/vol_avg)}x Avg",
                    "action": action,
                    "score": score
                })

            # 策略 2: 极度超买/超卖 + 布林带突破 (Reversal Setup)
            # 逻辑: RSI > 75 且 价格突破布林上轨 -> 极大概率回调
            elif rsi_val > 75 and close_price > upper_band:
                signals.append({
                    "id": f"top_{clean_symbol}",
                    "symbol": clean_symbol,
                    "signal_type": "BLOW_OFF_TOP", # 冲高回落预警
                    "value_display": f"RSI: {rsi_val:.0f} + Breakout",
                    "action": "TAKE PROFIT",
                    "score": 90
                })
            
            # 逻辑: RSI < 25 且 价格跌破布林下轨 -> 黄金坑
            elif rsi_val < 25 and close_price < lower_band:
                signals.append({
                    "id": f"btm_{clean_symbol}",
                    "symbol": clean_symbol,
                    "signal_type": "OVERSOLD_BOUNCE",
                    "value_display": f"RSI: {rsi_val:.0f} + Support",
                    "action": "STRONG BUY",
                    "score": 90
                })
                
            # 策略 3: MACD 金叉 (Trend Reversal)
            # 逻辑: MACD 刚刚上穿 Signal 线
            elif macd > macd_signal and prev['MACD_12_26_9'] <= prev['MACDs_12_26_9']:
                 signals.append({
                    "id": f"macd_{clean_symbol}",
                    "symbol": clean_symbol,
                    "signal_type": "MOMENTUM_UP",
                    "value_display": "MACD Crossover",
                    "action": "BUY",
                    "score": 70
                })

        except Exception as e:
            print(f"Skipping {symbol}: {e}")
            continue

    # 计算整体市场情绪 (基于所有资产的平均 RSI)
    if valid_tickers_count > 0:
        avg_rsi = total_rsi / valid_tickers_count
        # 映射: RSI 50 -> Mood 50. RSI 80 -> Mood 90.
        dashboard_mood = int(avg_rsi) 

    # 排序信号：高分在前
    signals.sort(key=lambda x: x['score'], reverse=True)
    
    return signals[:10], dashboard_mood # 只返回前10个最强信号

def main():
    print("Running Advanced Analysis...")
    fear_val, fear_label = get_crypto_fear()
    generated_signals, stock_mood = analyze_market()
    
    # 生成 "AI 总结" (伪装成 AI，其实是规则引擎)
    # 这部分文案要写得极其唬人
    top_signal = generated_signals[0] if generated_signals else None
    if top_signal:
        headline = f"Market Focus: {top_signal['symbol']}"
        body = f"Detected {top_signal['signal_type'].replace('_', ' ')} pattern on {top_signal['symbol']}. Institutional volume suggests a {top_signal['action']} setup."
    else:
        headline = "Market is Choppy"
        body = "No high-confidence signals detected. Liquidity is low. Stay on sidelines."

    output = {
        "meta": {"updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
        "dashboard": {
            "crypto_fear_index": fear_val,
            "crypto_fear_label": fear_label,
            "stock_market_mood": stock_mood,
            "market_summary_headline": headline,
            "market_summary_body": body
        },
        "signals": generated_signals,
        "top_movers": [] # 暂时不需要这个，信号才是重点
    }
    
    with open('data.json', 'w') as f:
        json.dump(output, f, indent=2)
    print("Analysis Complete.")

if __name__ == "__main__":
    main()
