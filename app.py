from flask import Flask, render_template, jsonify, request
from auth import auth_bp
from portfolio import portfolio_bp

import requests
import numpy as np
import pandas as pd
from datetime import datetime

app = Flask(__name__)
app.secret_key = "your-very-secret-key"

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(portfolio_bp)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/analyze", methods=["GET"])
def analyze():
    symbol = request.args.get("symbol")
    if not symbol:
        return jsonify({"error": "No symbol provided"}), 400

    api_key = "YOUR_API_KEY"
    url = f"https://api.polygon.io/v2/aggs/ticker/{symbol.upper()}/range/1/day/2023-01-01/2023-12-31?adjusted=true&sort=asc&limit=120&apiKey={api_key}"

    response = requests.get(url)
    if response.status_code != 200:
        return jsonify({"error": "Failed to fetch data"}), 400

    data = response.json()
    if "results" not in data or not data["results"]:
        return jsonify({"error": "No data found"}), 400

    closes = [item["c"] for item in data["results"]]
    dates = [datetime.utcfromtimestamp(item["t"]/1000).strftime("%Y-%m-%d") for item in data["results"]]
    closes_array = np.array(closes)

    # RSI Calculation
    def calculate_rsi(prices, period=14):
        deltas = np.diff(prices)
        seed = deltas[:period]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        rs = up / down if down != 0 else 0
        rsi = np.zeros_like(prices)
        rsi[:period] = 100. - 100. / (1. + rs)
        for i in range(period, len(prices)):
            delta = deltas[i - 1]
            if delta > 0:
                upval = delta
                downval = 0.
            else:
                upval = 0.
                downval = -delta
            up = (up * (period - 1) + upval) / period
            down = (down * (period - 1) + downval) / period
            rs = up / down if down != 0 else 0
            rsi[i] = 100. - 100. / (1. + rs)
        return rsi

    rsi_series = calculate_rsi(closes_array).tolist()
    rsi_value = rsi_series[-1]
    moving_avg = closes_array[-20:].mean()

    # MACD Calculation
    def calculate_macd(prices, slow=26, fast=12, signal=9):
        exp1 = pd.Series(prices).ewm(span=fast, adjust=False).mean()
        exp2 = pd.Series(prices).ewm(span=slow, adjust=False).mean()
        macd_line = exp1 - exp2
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        return macd_line.tolist(), signal_line.tolist()

    macd_line, signal_line = calculate_macd(closes_array)

    recommendation = (
        "Buy (Oversold)" if rsi_value < 30 else
        "Sell (Overbought)" if rsi_value > 70 else
        "Hold"
    )

    return jsonify({
        "symbol": symbol.upper(),
        "latest_price": closes_array[-1],
        "rsi": round(rsi_value, 2),
        "moving_average_20": round(moving_avg, 2),
        "recommendation": recommendation,
        "dates": dates,
        "closes": closes,
        "rsi_series": rsi_series,
        "macd_line": macd_line,
        "signal_line": signal_line
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
