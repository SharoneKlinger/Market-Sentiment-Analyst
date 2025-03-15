from flask import Flask, jsonify, request
import os
import requests

app = Flask(__name__)

ALPACA_API_KEY = os.getenv('ALPACA_API_KEY')
ALPACA_SECRET_KEY = os.getenv('ALPACA_SECRET_KEY')
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
    quote_data = requests.get(f"{BASE_URL}/stocks/{symbol}/quotes/latest", headers=HEADERS).json()
    sentiment = 'bullish' if float(quote_data['quote']['askprice']) > float(quote_data['quote']['bidprice']) else 'bearish'
    return jsonify({'symbol': symbol, 'sentiment': sentiment, 'data': quote_data})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

web: python app.py
```
