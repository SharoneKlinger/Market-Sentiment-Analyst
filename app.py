from urllib import request
from flask import Flask, jsonify # type: ignore
import requests

app = Flask(__name__)

ALPACA_API_KEY = 'CKYXN92ADFIYOVGTHVAV'
ALPACA_SECRET_KEY = 'e8Dbo9gvS8fbgkWajW8mme1BIrlup20cqfEcvZ2G'
BASE_URL = 'https://data.alpaca.markets/v2'

HEADERS = {
    'APCA-API-KEY-ID': ALPACA_API_KEY,
    'APCA-API-SECRET-KEY': ALPACA_SECRET_KEY
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
    # Here you could add your own logic for sentiment analysis
    quote_data = requests.get(f"{BASE_URL}/stocks/{symbol}/quotes/latest", headers=HEADERS).json()
    # Placeholder sentiment logic:
    sentiment = 'bullish' if float(quote_data['quote']['askprice']) > float(quote_data['quote']['bidprice']) else 'bearish'
    return jsonify({'symbol': symbol, 'sentiment': sentiment, 'data': quote_data})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
