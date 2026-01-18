import yfinance as yf
import pandas as pd
import pandas_ta as ta
import json
import requests
import time
from datetime import datetime

# --- 资产配置 ---
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
        if val < 25: label = "极度恐慌"
        elif val < 45: label = "恐慌"
        elif val > 75: label = "极度贪婪"
        elif val > 55: label = "贪婪"
        else: label = "中性"
        return val, label
    except:
        return 50, "中性"

def generate_analysis_report(symbol, price, rsi, macd_val, macd_sig, vol_ratio, close_price, lower_band, upper_band):
    """
    [核心升级] 生成可溯源的逻辑推演文案
    """
    report_parts = []
    
    # 1. 趋势判断 (MACD)
    if macd_val > macd_sig:
        trend = "多头主导"
        report_parts.append("MACD 指标在零轴上方运行，市场处于多头主导趋势。")
    else:
        trend = "空头主导"
        report_parts.append("MACD 动能转弱，短期面临回调压力。")
        
    # 2. 情绪判断 (RSI)
    if rsi < 30:
        report_parts.append(f"RSI 指标降至 {rsi:.1f}，进入【严重超卖】区间，市场恐慌情绪过度释放，反弹一触即发。")
    elif rsi > 70:
        report_parts.append(f"RSI 指标高达 {rsi:.1f}，进入【严重超买】区间，需警惕获利盘回吐。")
    else:
        report_parts.append(f"RSI 指标 ({rsi:.1f}) 处于中性区域，多空双方力量均衡。")
        
    # 3. 资金面判断 (量能)
    if vol_ratio > 2.0:
        report_parts.append(f"监测到异常交易量（{vol_ratio:.1f}x 平均量），显示有主力资金正在{'抢筹' if price > close_price else '出逃'}。")
    elif vol_ratio < 0.6:
        report_parts.append("成交量极度萎缩，市场观望情绪浓厚，变盘在即。")
        
    # 4. 形态判断 (布林带)
    if price < lower_band:
        report_parts.append("价格已跌破布林带下轨，属于非理性下跌，回归均值的概率极大。")
    elif price > upper_band:
        report_parts.append("价格突破布林带上轨，单边上涨行情确立，但需防范插针回调。")
        
    # 汇总
    full_report = "".join(report_parts)
    return full_report

def analyze_market():
    print("启动逻辑溯源分析引擎...")
    
    signals = []
    tickers = [x[1] for x in ASSETS]
    
    try:
        data = yf.download(tickers, period="3mo", interval="1d", group_by='ticker', auto_adjust=True, threads=True)
    except Exception as e:
        print(f"Data Error: {e}")
        return

    # VIX
    try:
        vix_price = data['^VIX']['Close'].dropna().iloc[-1]
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
            
            # 指标计算
            df['RSI'] = df.ta.rsi(length=14)
            macd = df.ta.macd(fast=12, slow=26, signal=9)
            if macd is not None: df = pd.concat([df, macd], axis=1)
            
            df['VOL_SMA'] = df['Volume'].rolling(20).mean()
            bbands = df.ta.bbands(length=20, std=2)
            if bbands is not None: df = pd.concat([df, bbands], axis=1)
            
            df.dropna(inplace=True)
            curr = df.iloc[-1]
            prev = df.iloc[-2]
            
            # 获取列名
            macd_col = [c for c in df.columns if c.startswith('MACD_')][0]
            macds_col = [c for c in df.columns if c.startswith('MACDs_')][0]
            bbl_col = [c for c in df.columns if c.startswith('BBL')][0]
            bbu_col = [c for c in df.columns if c.startswith('BBU')][0]
            
            price = curr['Close']
            rsi = curr['RSI']
            vol_ratio = (curr['Volume'] / curr['VOL_SMA']) if curr['VOL_SMA'] > 0 else 1.0
            
            macd_val = curr[macd_col]
            macd_sig = curr[macds_col]
            
            # --- 决策逻辑 ---
            signal_type = "观察中"
            action = "持有"
            score = 50
            detail = "趋势震荡"
            
            if rsi < 35 and macd_val > macd_sig:
                signal_type = "底部金叉"
                action = "买入"
                score = 88
                detail = "超卖反转"
            elif rsi > 75:
                signal_type = "严重超买"
                action = "卖出"
                score = 80
                detail = f"RSI高位: {rsi:.0f}"
            elif vol_ratio > 2.5:
                if price > prev['Close']:
                    signal_type = "主力抢筹"
                    action = "买入"
                    score = 85
                    detail = "放量上涨"
                else:
                    signal_type = "恐慌抛售"
                    action = "卖出"
                    score = 82
                    detail = "放量下跌"
            elif price > curr[bbu_col]:
                signal_type = "突破上轨"
                action = "持有"
                score = 70
                detail = "强势延续"
            
            # --- [核心] 生成溯源分析报告 ---
            ai_analysis_text = generate_analysis_report(
                symbol_display, price, rsi, macd_val, macd_sig, vol_ratio, prev['Close'], curr[bbl_col], curr[bbu_col]
            )

            signals.append({
                "id": f"{symbol_display}_{int(datetime.now().timestamp())}",
                "symbol": symbol_display,
                "asset_type": asset_type,
                "price": f"{price:.2f}",
                "signal_type": signal_type,
                "action": action,
                "value_display": detail,
                "score": score,
                "ai_analysis": ai_analysis_text, # ✅ 新增字段
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
            "crypto_fear_label": crypto_label,
            "stock_market_mood": stock_mood,
            "market_summary_headline": f"机会: {signals[0]['symbol']}" if signals else "市场平淡",
            "market_summary_body": "AI 策略引擎已完成全市场扫描，请查看下方详细分析。"
        },
        "signals": signals
    }
    
    with open('data.json', 'w') as f:
        json.dump(output, f, indent=2)
    print("Logic Analysis Complete.")

if __name__ == "__main__":
    analyze_market()
