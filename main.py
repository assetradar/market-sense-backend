import yfinance as yf
import pandas as pd
import pandas_ta as ta
import json
import requests
from datetime import datetime


# 1. 获取加密货币恐慌指数 (免费 API)
def get_crypto_fear():
    try:
        url = "https://api.alternative.me/fng/?limit=1"
        response = requests.get(url)
        data = response.json()
        value = int(data['data'][0]['value'])
        label = data['data'][0]['value_classification']
        return value, label
    except Exception as e:
        print(f"Error getting fear index: {e}")
        return 50, "Neutral"


# 2. 获取资产数据并计算指标 (Yahoo Finance)
def analyze_assets():
    # 我们关注的核心资产列表
    tickers = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'NVDA', 'TSLA', 'AAPL', 'SPY']

    signals = []
    top_movers = []

    # 下载数据 (最近 1 个月，1 天级别)
    data = yf.download(tickers, period="1mo", interval="1d", group_by='ticker')

    for symbol in tickers:
        try:
            # 提取单个资产的数据
            df = data[symbol].copy()

            # 确保数据非空
            if df.empty:
                continue

            # 计算 RSI (14天)
            # pandas_ta 会自动添加一列 RSI_14
            df.ta.rsi(length=14, append=True)

            current_price = df['Close'].iloc[-1]
            prev_price = df['Close'].iloc[-2]
            current_rsi = df['RSI_14'].iloc[-1]

            # 计算 24h 涨跌幅
            change_percent = ((current_price - prev_price) / prev_price) * 100

            # 添加到异动榜逻辑 (绝对值 > 3% 算异动)
            if abs(change_percent) > 3.0:
                mover_type = "crypto" if "-USD" in symbol else "stock"
                display_name = symbol.replace("-USD", "")
                top_movers.append({
                    "symbol": display_name,
                    "name": display_name,
                    "price": f"${current_price:.2f}",
                    "change_24h": f"{change_percent:+.2f}%",
                    "type": mover_type
                })

            # 生成信号逻辑 (RSI 策略)
            display_name = symbol.replace("-USD", "")
            if current_rsi > 70:
                signals.append({
                    "id": f"sig_{symbol}_overbought",
                    "symbol": display_name,
                    "signal_type": "RSI_OVERBOUGHT",
                    "value_display": f"RSI: {current_rsi:.1f}",
                    "action": "SELL",
                    "score": 80
                })
            elif current_rsi < 30:
                signals.append({
                    "id": f"sig_{symbol}_oversold",
                    "symbol": display_name,
                    "signal_type": "RSI_OVERSOLD",
                    "value_display": f"RSI: {current_rsi:.1f}",
                    "action": "BUY",
                    "score": 80
                })

        except Exception as e:
            print(f"Error analyzing {symbol}: {e}")
            continue

    # 按涨跌幅排序 Top Movers
    top_movers.sort(key=lambda x: float(x['change_24h'].strip('%')), reverse=True)

    return top_movers[:3], signals


# 主函数
def main():
    print("Starting data analysis...")

    fear_value, fear_label = get_crypto_fear()
    movers, generated_signals = analyze_assets()

    # 构建最终 JSON
    output_data = {
        "meta": {
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "success"
        },
        "dashboard": {
            "crypto_fear_index": fear_value,
            "crypto_fear_label": fear_label,
            "stock_market_mood": 60,  # 暂时写死，后续加逻辑
            "market_summary_headline": f"Crypto is in {fear_label} mode.",
            "market_summary_body": "Automated analysis based on RSI and Volume data."
        },
        "top_movers": movers,
        "signals": generated_signals
    }

    # 写入文件
    with open('data.json', 'w') as f:
        json.dump(output_data, f, indent=2)

    print("Success! data.json generated.")


if __name__ == "__main__":
    main()