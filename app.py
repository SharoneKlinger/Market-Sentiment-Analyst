from flask import Flask, jsonify, request
from datetime import datetime, timedelta
import os
import requests
import pandas as pd
import numpy as np

app = Flask(__name__)

ALPACA_API_KEY = os.getenv('ALPACA_API_KEY')
ALPACA_SECRET_KEY = os.getenv('ALPACA_SECRET_KEY')
BASE_URL = 'https://data.alpaca.markets/v2'

HEADERS = {
    'APCA-API-KEY-ID': ALPACA_API_KEY,
    'APCA-API-SECRET-KEY': ALPACA_SECRET_KEY
}


def fetch_weekly_bars(symbol, weeks=52):
    """Fetch weekly bar data from Alpaca for the given symbol."""
    end = datetime.utcnow()
    start = end - timedelta(weeks=weeks)
    url = f"{BASE_URL}/stocks/{symbol}/bars"
    params = {
        'start': start.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'end': end.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'timeframe': '1Week',
        'limit': weeks,
    }
    response = requests.get(url, headers=HEADERS, params=params)
    response.raise_for_status()
    data = response.json()
    bars = data.get('bars', [])
    if not bars:
        return pd.DataFrame()
    df = pd.DataFrame(bars)
    df['t'] = pd.to_datetime(df['t'])
    df = df.sort_values('t').reset_index(drop=True)
    return df


def calculate_ema(series, span):
    """Calculate Exponential Moving Average for a given span."""
    return series.ewm(span=span, adjust=False).mean()


def analyze_8week_ema_momentum(symbol):
    """
    Analyze a stock's momentum using the 8-week EMA.

    Returns the current price vs 8-week EMA relationship, trend direction,
    and a momentum signal based on institutional-quality criteria.
    """
    df = fetch_weekly_bars(symbol, weeks=52)
    if df.empty:
        return None

    df['ema_8'] = calculate_ema(df['c'], span=8)

    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else latest

    close = float(latest['c'])
    ema_8 = float(latest['ema_8'])
    prev_ema_8 = float(prev['ema_8'])

    # Distance from price to 8-week EMA as a percentage
    distance_pct = ((close - ema_8) / ema_8) * 100

    # EMA slope: rising or falling
    ema_rising = ema_8 > prev_ema_8

    # Determine momentum signal
    if close > ema_8 and ema_rising:
        if distance_pct > 10:
            signal = 'extended'
            description = ('Price is stretched far above the 8-week EMA. '
                           'Momentum is strong but risk of mean reversion is elevated.')
        else:
            signal = 'bullish'
            description = ('Price is above a rising 8-week EMA. '
                           'Institutional support is intact and momentum is healthy.')
    elif close > ema_8 and not ema_rising:
        signal = 'weakening'
        description = ('Price is above the 8-week EMA but the EMA is flattening or declining. '
                       'Momentum is cooling; watch for a weekly close below the EMA.')
    elif close < ema_8 and ema_rising:
        signal = 'pullback'
        description = ('Price has dipped below the 8-week EMA while it is still rising. '
                       'Could be a buyable dip if the EMA holds as support on a closing basis.')
    else:
        signal = 'bearish'
        description = ('Price is below a declining 8-week EMA. '
                       'Momentum has broken down; institutions are likely distributing.')

    # Build weekly EMA history for the response
    ema_history = []
    for _, row in df.tail(8).iterrows():
        ema_history.append({
            'date': row['t'].strftime('%Y-%m-%d'),
            'close': round(float(row['c']), 2),
            'ema_8': round(float(row['ema_8']), 2),
        })

    return {
        'symbol': symbol.upper(),
        'latest_close': round(close, 2),
        'ema_8_week': round(ema_8, 2),
        'distance_from_ema_pct': round(distance_pct, 2),
        'ema_rising': ema_rising,
        'signal': signal,
        'description': description,
        'weekly_history': ema_history,
    }


@app.route('/quote', methods=['GET'])
def get_quote():
    symbol = request.args.get('symbol', '')
    if not symbol:
        return jsonify({'error': 'Symbol required'}), 400
    url = f"{BASE_URL}/stocks/{symbol}/quotes/latest"
    response = requests.get(url, headers=HEADERS)
    return jsonify(response.json())


@app.route('/sentiment', methods=['GET'])
def get_sentiment():
    symbol = request.args.get('symbol', '')
    if not symbol:
        return jsonify({'error': 'Symbol required'}), 400
    quote_data = requests.get(
        f"{BASE_URL}/stocks/{symbol}/quotes/latest", headers=HEADERS
    ).json()
    ask = float(quote_data['quote']['askprice'])
    bid = float(quote_data['quote']['bidprice'])
    sentiment = 'bullish' if ask > bid else 'bearish'
    return jsonify({'symbol': symbol, 'sentiment': sentiment, 'data': quote_data})


@app.route('/momentum', methods=['GET'])
def get_momentum():
    """
    Analyze a stock's 8-week EMA momentum.

    Query params:
        symbol (required): Stock ticker symbol

    Returns momentum signal: bullish, extended, weakening, pullback, or bearish.
    """
    symbol = request.args.get('symbol', '')
    if not symbol:
        return jsonify({'error': 'Symbol required'}), 400

    try:
        result = analyze_8week_ema_momentum(symbol)
    except requests.exceptions.HTTPError as e:
        return jsonify({'error': f'Failed to fetch data: {e}'}), 502

    if result is None:
        return jsonify({'error': f'No weekly bar data available for {symbol}'}), 404

    return jsonify(result)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
