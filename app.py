from flask import Flask, jsonify, request
from datetime import datetime, timedelta
import os
import logging
import requests
import pandas as pd
import numpy as np

from finviz_scanner import scrape_finviz_screener, get_available_presets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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


def detect_ema_break(symbol):
    """
    Detect whether a stock is breaking above or below the 8-week EMA.

    A "break" is a crossover event:
      - break_above: previous week closed below EMA, current week closed above
      - break_below: previous week closed above EMA, current week closed below
      - above: price is above EMA (no crossover this week)
      - below: price is below EMA (no crossover this week)

    Returns a dict with break info, or None if data is unavailable.
    """
    df = fetch_weekly_bars(symbol, weeks=20)
    if df.empty or len(df) < 3:
        return None

    df['ema_8'] = calculate_ema(df['c'], span=8)

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    close = float(latest['c'])
    ema_now = float(latest['ema_8'])
    prev_close = float(prev['c'])
    prev_ema = float(prev['ema_8'])

    ema_rising = ema_now > prev_ema
    distance_pct = ((close - ema_now) / ema_now) * 100

    was_below = prev_close < prev_ema
    was_above = prev_close >= prev_ema
    now_above = close >= ema_now
    now_below = close < ema_now

    if was_below and now_above:
        break_type = 'break_above'
    elif was_above and now_below:
        break_type = 'break_below'
    elif now_above:
        break_type = 'above'
    else:
        break_type = 'below'

    return {
        'symbol': symbol.upper(),
        'latest_close': round(close, 2),
        'ema_8_week': round(ema_now, 2),
        'distance_from_ema_pct': round(distance_pct, 2),
        'ema_rising': ema_rising,
        'break_type': break_type,
    }


@app.route('/scanner', methods=['GET'])
def scan_ema_breaks():
    """
    Scan for stocks breaking above or below the 8-week EMA.

    Uses Finviz screener to build a candidate list, then checks each
    symbol against Alpaca weekly data for 8-week EMA crossovers.

    Query params:
        preset: Finviz filter preset (default: momentum_leaders).
                Options: momentum_leaders, breakout_candidates,
                high_momentum, broad
        direction: Filter results — 'above', 'below', or 'all' (default: all)
        max_pages: Max Finviz pages to scan, 20 symbols each (default: 2)

    Returns list of symbols with their EMA break status.
    """
    preset = request.args.get('preset', 'momentum_leaders')
    direction = request.args.get('direction', 'all')
    max_pages = int(request.args.get('max_pages', 2))

    if max_pages < 1 or max_pages > 10:
        return jsonify({'error': 'max_pages must be between 1 and 10'}), 400

    try:
        symbols = scrape_finviz_screener(preset=preset, max_pages=max_pages)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Finviz request failed: {e}'}), 502

    if not symbols:
        return jsonify({
            'preset': preset,
            'candidates_scanned': 0,
            'results': [],
            'message': 'No symbols matched the Finviz pre-filter.',
        })

    results = []
    errors = []
    for sym in symbols:
        try:
            info = detect_ema_break(sym)
            if info is None:
                continue
            results.append(info)
        except Exception as e:
            errors.append({'symbol': sym, 'error': str(e)})
            logger.warning("Failed to analyze %s: %s", sym, e)

    # Filter by requested direction
    if direction == 'above':
        results = [r for r in results if r['break_type'] in ('break_above', 'above')]
    elif direction == 'below':
        results = [r for r in results if r['break_type'] in ('break_below', 'below')]

    # Sort: crossover events first, then by distance from EMA
    break_order = {'break_above': 0, 'break_below': 1, 'above': 2, 'below': 3}
    results.sort(key=lambda r: (break_order.get(r['break_type'], 9),
                                -abs(r['distance_from_ema_pct'])))

    breaks_above = [r for r in results if r['break_type'] == 'break_above']
    breaks_below = [r for r in results if r['break_type'] == 'break_below']

    return jsonify({
        'preset': preset,
        'candidates_scanned': len(symbols),
        'total_results': len(results),
        'breaks_above_count': len(breaks_above),
        'breaks_below_count': len(breaks_below),
        'results': results,
        'errors': errors if errors else None,
    })


@app.route('/scanner/presets', methods=['GET'])
def list_scanner_presets():
    """List all available Finviz scanner presets and their descriptions."""
    return jsonify(get_available_presets())


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
