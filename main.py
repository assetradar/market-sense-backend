import yfinance as yf
import pandas as pd
import pandas_ta as ta
import json
import requests
from datetime import datetime

# --- 1. 扩充核心资产池 (覆盖主流美股与加密货币) ---
TICKERS_CONFIG = {
    'Crypto': [
        'BTC-USD', 'ETH-USD', 'SOL-USD', 'BNB-USD', 'DOGE-USD', 
        'XRP-USD', 'ADA-USD', 'PEPE-USD', 'SHIB-USD'
    ],
    'Stock': [
        'SPY', 'QQQ', 'NVDA', 'TSLA', 'AAPL', 'MSFT', 'AMZN', 
        'GOOGL', 'META', 'COIN', 'MSTR', 'AMD', 'GME', 'PLTR'
    ]
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
    print("正在启动 AI 深度分析引擎...")
    
    # 扁平化列表用于下载
    all_tickers = TICKERS_CONFIG['Crypto'] + TICKERS_CONFIG['Stock']
    
    # 下载数据 (auto_adjust=True 修复股票除权问题)
    try:
        data = yf.download(all_tickers, period="1mo", interval="1d", group_by='ticker', auto_adjust=True, threads=True)
    except Exception as e:
        print(f"Data download error: {e}")
        return

    signals = []
    total_rsi = 0
    valid_count = 0
    
    for symbol in all_tickers:
        try:
            # 确定资产类型
            asset_type = 'Crypto' if symbol in TICKERS_CONFIG['Crypto'] else 'Stock'
            
            # 提取数据
            df = data[symbol].copy()
            
            # --- 深度数据清洗 (针对美股周末空缺进行填充) ---
            # 如果是股票，周末可能是 NaN，我们用前值填充 (Forward Fill)
            df = df.ffill() 
            df.dropna(inplace=True)
            
            if df.empty or len(df) < 20: 
                print(f"Skipping {symbol}: Not enough data")
                continue
            
            # --- 计算核心指标 ---
            df['RSI_14'] = df.ta.rsi(length=14)
            bbands = df.ta.bbands(length=20, std=2)
            if bbands is not None:
                df = pd.concat([df, bbands], axis=1)
            df['VOL_SMA'] = df['Volume'].rolling(20).mean()
            
            # 再次清洗 (计算指标后会有 NaN)
            df.dropna(inplace=True)
            
            if len(df) < 7: continue

            curr = df.iloc[-1]
            prev = df.iloc[-2]
            
            # 动态获取布林带列名
            bbu_col = [c for c in df.columns if c.startswith('BBU')][0]
            
            # 提取数值
            price = curr['Close']
            rsi = curr['RSI_14']
            vol_sma = curr['VOL_SMA']
            # 防止除以0
            vol_ratio = (curr['Volume'] / vol_sma) if (vol_sma > 0) else 1.0
            
            # 生成 Sparkline (走势图数据)
            sparkline = df['Close'].tail(7).tolist()
            
            # --- 信号判定逻辑 ---
            signal_type = "观察中"
            action = "持有"
            score = 50
            detail = "趋势不明朗"
            
            # 1. 巨鲸异动
            if vol_ratio > 2.0:
                if price > prev['Close']:
                    signal_type = "巨鲸吸筹"
                    action = "买入"
                    score = 90
                    detail = f"放量上涨 {vol_ratio:.1f}x"
                else:
                    signal_type = "恐慌抛售"
                    action = "卖出"
                    score = 85
                    detail = f"放量下跌 {vol_ratio:.1f}x"
            
            # 2. RSI 极端
            elif rsi > 75:
                signal_type = "严重超买"
                action = "卖出"
                score = 80
                detail = f"RSI 高位: {rsi:.0f}"
            elif rsi < 25:
                signal_type = "严重超卖"
                action = "买入"
                score = 85
                detail = f"RSI 低位: {rsi:.0f}"
            
            # 3. 突破策略
            elif price > curr[bbu_col]:
                signal_type = "突破上轨"
                action = "买入"
                score = 75
                detail = "布林带突破"
            
            # 净化名称 (去掉 -USD 以便 App 显示)
            clean_symbol = symbol.replace("-USD", "")
            
            signals.append({
                "id": f"{clean_symbol}_{int(datetime.now().timestamp())}",
                "symbol": clean_symbol,
                "asset_type": asset_type, # <--- 新增字段：资产类型
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
            print(f"Error processing {symbol}: {e}")
            continue

    # 市场综合情绪
    mood = int(total_rsi / valid_count) if valid_count > 0 else 50
    # 按分数排序
    signals.sort(key=lambda x: x['score'], reverse=True)
    
    # 生成简报
    top_sig = signals[0] if signals else None
    if top_sig and top_sig['score'] >= 80:
        headline = f"关注: {top_sig['symbol']}"
        body = f"AI 在 {top_sig['asset_type']} 市场检测到 {top_sig['signal_type']} 信号。成交量放大 {top_sig['stats']['vol_ratio']}。"
    else:
        headline = "市场波动收窄"
        body = "美股与加密市场均处于震荡整理阶段，建议等待明确方向。"

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
    print("Success: Analysis complete.")

if __name__ == "__main__":
    fear_val, fear_label = get_crypto_fear()
    analyze_market()
