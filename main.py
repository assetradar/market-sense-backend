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
    print("开始获取市场数据...")
    all_tickers = TICKERS['Crypto'] + TICKERS['Stock']
    
    # 下载数据
    data = yf.download(all_tickers, period="1mo", interval="1d", group_by='ticker', auto_adjust=True)
    
    signals = []
    total_rsi = 0
    valid_count = 0
    
    for symbol in all_tickers:
        try:
            df = data[symbol].copy()
            df.dropna(inplace=True)
            if df.empty or len(df) < 20: continue
            
            # --- 计算指标 ---
            df['RSI_14'] = df.ta.rsi(length=14)
            
            # 布林带计算
            bbands = df.ta.bbands(length=20, std=2)
            if bbands is not None:
                df = pd.concat([df, bbands], axis=1)
                
            df['VOL_SMA'] = df['Volume'].rolling(20).mean()
            
            # 再次清洗空值
            df.dropna(inplace=True)
            
            if len(df) < 7: continue

            # 获取数据点
            curr = df.iloc[-1]
            prev = df.iloc[-2]
            
            # 动态获取布林带上轨列名
            bbu_col = [c for c in df.columns if c.startswith('BBU')][0]
            
            # --- 提取核心数据 ---
            price = curr['Close']
            rsi = curr['RSI_14']
            vol_sma = curr['VOL_SMA']
            vol_ratio = curr['Volume'] / vol_sma if vol_sma > 0 else 1.0
            sparkline = df['Close'].tail(7).tolist()
            
            # --- 3. 信号逻辑 (全中文版) ---
            signal_type = "观察中"
            action = "持有"
            score = 50
            detail = "趋势不明朗"
            
            # 策略 A: 巨鲸异动 (成交量突增)
            if vol_ratio > 2.0:
                if price > prev['Close']:
                    signal_type = "巨鲸吸筹"
                    action = "买入"
                    score = 90
                    detail = f"放量上涨: {vol_ratio:.1f}倍"
                else:
                    signal_type = "恐慌抛售"
                    action = "卖出"
                    score = 85
                    detail = f"放量下跌: {vol_ratio:.1f}倍"
            
            # 策略 B: RSI 极端反转
            elif rsi > 75:
                signal_type = "严重超买"
                action = "卖出"
                score = 80
                detail = f"RSI 触顶: {rsi:.0f}"
            elif rsi < 25:
                signal_type = "严重超卖"
                action = "买入"
                score = 85
                detail = f"RSI 触底: {rsi:.0f}"
            
            # 策略 C: 布林带突破
            elif price > curr[bbu_col]:
                signal_type = "突破上轨"
                action = "买入"
                score = 75
                detail = "布林带突破"
            
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
            print(f"Skipping {symbol}: {e}")
            continue

    # 计算整体市场情绪
    mood = int(total_rsi / valid_count) if valid_count > 0 else 50
    signals.sort(key=lambda x: x['score'], reverse=True)
    
    # 生成中文市场简报 (头部大字)
    top_sig = signals[0] if signals else None
    if top_sig and top_sig['score'] >= 80:
        headline = f"重点关注: {top_sig['symbol']}"
        body = f"检测到 {top_sig['signal_type']} 信号。机构资金正在{top_sig['action']}，成交量异常放大。"
    else:
        headline = "市场横盘震荡"
        body = "暂无高胜率信号，流动性较低，建议观望。"

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
    print("Success: data.json created (Chinese Version)")

if __name__ == "__main__":
    fear_val, fear_label = get_crypto_fear()
    analyze_market()
