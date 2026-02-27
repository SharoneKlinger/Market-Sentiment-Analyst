from flask import Flask, jsonify, request
import math
import os
import requests

app = Flask(__name__)

ALPACA_API_KEY = os.getenv('ALPACA_API_KEY')
ALPACA_SECRET_KEY = os.getenv('ALPACA_SECRET_KEY')
BASE_URL = 'https://data.alpaca.markets/v2'

HEADERS = {
    'APCA-API-KEY-ID': ALPACA_API_KEY,
    'APCA-API-SECRET-KEY': ALPACA_SECRET_KEY,
}


def _norm_cdf(value):
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def _round_to_step(value, step=5):
    return int(round(value / step) * step)


def _estimate_short_delta(spot, strike, expected_move, option_type):
    """
    Delta approximation from a 1-day normal distribution where expected_move ~= 1 stdev.
    """
    sigma = max(expected_move, 1)
    z = (strike - spot) / sigma

    if option_type == 'call':
        # Prob(spot expires above strike)
        return max(0.01, min(0.99, 1 - _norm_cdf(z)))

    # Put delta magnitude approximated by Prob(spot expires below strike)
    return max(0.01, min(0.99, _norm_cdf(z)))


def _build_trade_plan(payload):
    required_fields = [
        'spx',
        'atm_straddle',
        'vix',
        'call_wall',
        'put_wall',
        'gamma_flip',
        'dealer_gamma',
        'account_size',
    ]
    missing_fields = [field for field in required_fields if field not in payload]
    if missing_fields:
        return {'error': f"Missing fields: {', '.join(missing_fields)}"}, 400

    spx = float(payload['spx'])
    atm_straddle = float(payload['atm_straddle'])
    vix = float(payload['vix'])
    call_wall = float(payload['call_wall'])
    put_wall = float(payload['put_wall'])
    gamma_flip = float(payload['gamma_flip'])
    dealer_gamma = str(payload['dealer_gamma']).lower()
    account_size = float(payload['account_size'])

    if dealer_gamma not in {'long', 'short'}:
        return {'error': "dealer_gamma must be 'long' or 'short'"}, 400

    expected_move = atm_straddle
    upper_expected = spx + expected_move
    lower_expected = spx - expected_move

    is_compression = vix < 14
    is_expansion = vix > 22

    # Structure and wing width logic.
    if dealer_gamma == 'short':
        # Wider and more directional-safe structure in unstable hedging regime.
        structure = 'iron fly (wide wings)'
        wing_width = 35 if is_expansion else 30
        body = _round_to_step(spx)
        short_call = body
        short_put = body
        long_call = _round_to_step(body + wing_width)
        long_put = _round_to_step(body - wing_width)
        net_credit = max(8.0, min(15.0, 0.22 * expected_move))
    else:
        structure = 'iron condor'
        if is_expansion:
            wing_width = 30
        elif is_compression:
            wing_width = 20
        else:
            wing_width = 25

        short_call = _round_to_step(min(call_wall - 10, upper_expected + expected_move * 0.2))
        short_put = _round_to_step(max(put_wall + 10, lower_expected - expected_move * 0.2))
        long_call = _round_to_step(short_call + wing_width)
        long_put = _round_to_step(short_put - wing_width)

        distance_call = max(short_call - spx, 5)
        distance_put = max(spx - short_put, 5)
        richness = max(0.8, min(1.2, expected_move / max((distance_call + distance_put) / 2, 1)))
        net_credit = round(1.4 + richness * (0.03 * wing_width), 2)

    short_call_delta = _estimate_short_delta(spx, short_call, expected_move, 'call')
    short_put_delta = _estimate_short_delta(spx, short_put, expected_move, 'put')

    pop = (1 - short_call_delta) * (1 - short_put_delta)
    pop = max(0.05, min(0.99, pop))

    width_risk = max(long_call - short_call, short_put - long_put)
    max_loss_per_contract = (width_risk * 100) - (net_credit * 100)

    risk_budget = account_size * 0.015
    contracts = max(1, int(risk_budget // max(max_loss_per_contract, 1)))
    capped_risk = min(risk_budget, account_size * 0.02)
    if contracts * max_loss_per_contract > capped_risk:
        contracts = max(1, int(capped_risk // max(max_loss_per_contract, 1)))

    total_credit = round(contracts * net_credit * 100, 2)
    total_max_loss = round(contracts * max_loss_per_contract, 2)

    lower_breakeven = round(short_put - net_credit, 2)
    upper_breakeven = round(short_call + net_credit, 2)

    target_buyback = round(net_credit * 0.4, 2)

    ev_per_contract = round((pop * net_credit - (1 - pop) * (max_loss_per_contract / 100)) * 100, 2)

    upside_break = spx > short_call
    downside_break = spx < short_put

    scenario = {
        'base_case': 'Pinning behavior inside walls supports theta decay.' if dealer_gamma == 'long' else 'Elevated movement likely; rely on wider tent and active hedging.',
        'upside_break': (
            f'If SPX > {short_call}, reduce call-side delta by buying back call spread at defined stop or roll up put side for net credit.'
        ),
        'downside_break': (
            f'If SPX < {short_put}, reduce put-side delta by buying back put spread at defined stop or roll down call side only if credit improves risk.'
        ),
        'flags': {
            'upside_tested': upside_break,
            'downside_tested': downside_break,
        },
    }

    return {
        'market_snapshot': {
            'spx': spx,
            'atm_straddle': atm_straddle,
            'expected_move': {
                'plus_minus': expected_move,
                'range': [round(lower_expected, 2), round(upper_expected, 2)],
            },
            'gamma_walls': {
                'call_wall': call_wall,
                'put_wall': put_wall,
                'gamma_flip': gamma_flip,
            },
            'dealer_positioning': 'long gamma' if dealer_gamma == 'long' else 'short gamma',
            'volatility_regime': 'compressed' if is_compression else ('expanded' if is_expansion else 'neutral'),
        },
        'trade': {
            'structure': structure,
            'strikes': {
                'short_call': short_call,
                'long_call': long_call,
                'short_put': short_put,
                'long_put': long_put,
            },
            'reasoning': [
                'Strikes anchored around expected move and gamma walls to harvest volatility premium with defined risk.',
                'Structure selection adapts to dealer gamma regime (long gamma favors condors, short gamma favors wider iron fly).',
                'Wing width scaled by VIX regime to control tail risk and preserve Sharpe stability.',
            ],
            'credit': {
                'per_contract': round(net_credit, 2),
                'total': total_credit,
            },
            'risk': {
                'max_loss_per_contract': round(max_loss_per_contract, 2),
                'total_max_loss': total_max_loss,
                'contracts': contracts,
                'account_risk_pct': round((total_max_loss / account_size) * 100, 2),
            },
            'breakevens': [lower_breakeven, upper_breakeven],
            'probability_of_profit': round(pop, 4),
            'expected_return_dollars': ev_per_contract * contracts,
            'exit_plan': {
                'profit_target_pct': 60,
                'profit_target_buyback_price': target_buyback,
                'hard_stop': 'Exit tested side if short strike delta > 0.25 or spread value reaches 2x entry credit.',
            },
            'adjustment_plan': scenario,
        },
        'risk_controls': {
            'no_directional_gambling': True,
            'defined_risk_only': True,
            'max_risk_per_structure_pct': 2,
            'event_filter': 'Avoid FOMC/CPI unless implied volatility is materially overpriced versus realized.',
        },
    }, 200


@app.route('/quote', methods=['GET'])
def get_quote():
    symbol = request.args.get('symbol', '')
    if not symbol:
        return jsonify({'error': 'Symbol required'}), 400
    url = f"{BASE_URL}/stocks/{symbol}/quotes/latest"
    response = requests.get(url, headers=HEADERS, timeout=10)
    return jsonify(response.json())


@app.route('/sentiment', methods=['GET'])
def get_sentiment():
    symbol = request.args.get('symbol', '')
    if not symbol:
        return jsonify({'error': 'Symbol required'}), 400
    quote_data = requests.get(f"{BASE_URL}/stocks/{symbol}/quotes/latest", headers=HEADERS, timeout=10).json()
    sentiment = 'bullish' if float(quote_data['quote']['askprice']) > float(quote_data['quote']['bidprice']) else 'bearish'
    return jsonify({'symbol': symbol, 'sentiment': sentiment, 'data': quote_data})


@app.route('/spx-0dte-plan', methods=['POST'])
def build_spx_0dte_plan():
    payload = request.get_json(silent=True) or {}
    response, status = _build_trade_plan(payload)
    return jsonify(response), status


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
