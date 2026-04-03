import unittest
from unittest.mock import patch, MagicMock
import json
import pandas as pd
import numpy as np
from app import app, calculate_ema, analyze_8week_ema_momentum


def make_weekly_bars(closes, start_date='2025-01-06'):
    """Helper to create mock weekly bar data from a list of closing prices."""
    dates = pd.date_range(start=start_date, periods=len(closes), freq='W-FRI')
    bars = []
    for i, (date, close) in enumerate(zip(dates, closes)):
        bars.append({
            't': date.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'o': close * 0.99,
            'h': close * 1.02,
            'l': close * 0.97,
            'c': close,
            'v': 1000000,
        })
    return bars


class TestCalculateEMA(unittest.TestCase):
    def test_ema_basic(self):
        series = pd.Series([10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0])
        ema = calculate_ema(series, span=8)
        self.assertEqual(len(ema), 8)
        # EMA should be less than or equal to last value in uptrend
        self.assertLess(ema.iloc[-1], 17.0)
        # EMA should be rising
        self.assertGreater(ema.iloc[-1], ema.iloc[-2])

    def test_ema_single_value(self):
        series = pd.Series([50.0])
        ema = calculate_ema(series, span=8)
        self.assertAlmostEqual(ema.iloc[0], 50.0)

    def test_ema_constant_series(self):
        series = pd.Series([100.0] * 20)
        ema = calculate_ema(series, span=8)
        for val in ema:
            self.assertAlmostEqual(val, 100.0)


class TestMomentumEndpoint(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        app.config['TESTING'] = True

    def test_missing_symbol(self):
        response = self.app.get('/momentum')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)

    @patch('app.fetch_weekly_bars')
    def test_bullish_signal(self, mock_fetch):
        # Steadily rising prices -> bullish
        closes = [100, 102, 104, 106, 108, 110, 112, 114, 116, 118, 120]
        bars = make_weekly_bars(closes)
        df = pd.DataFrame(bars)
        df['t'] = pd.to_datetime(df['t'])
        df = df.sort_values('t').reset_index(drop=True)
        mock_fetch.return_value = df

        response = self.app.get('/momentum?symbol=AAPL')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['symbol'], 'AAPL')
        self.assertIn(data['signal'], ['bullish', 'extended'])
        self.assertTrue(data['ema_rising'])
        self.assertGreater(data['distance_from_ema_pct'], 0)

    @patch('app.fetch_weekly_bars')
    def test_bearish_signal(self, mock_fetch):
        # Steadily declining prices -> bearish
        closes = [120, 118, 116, 114, 112, 110, 108, 106, 104, 102, 100]
        bars = make_weekly_bars(closes)
        df = pd.DataFrame(bars)
        df['t'] = pd.to_datetime(df['t'])
        df = df.sort_values('t').reset_index(drop=True)
        mock_fetch.return_value = df

        response = self.app.get('/momentum?symbol=AAPL')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['signal'], 'bearish')
        self.assertFalse(data['ema_rising'])
        self.assertLess(data['distance_from_ema_pct'], 0)

    @patch('app.fetch_weekly_bars')
    def test_no_data(self, mock_fetch):
        mock_fetch.return_value = pd.DataFrame()
        response = self.app.get('/momentum?symbol=FAKE')
        self.assertEqual(response.status_code, 404)

    @patch('app.fetch_weekly_bars')
    def test_extended_signal(self, mock_fetch):
        # Price stretched far above EMA
        closes = [100, 102, 104, 106, 108, 110, 112, 114, 116, 118, 150]
        bars = make_weekly_bars(closes)
        df = pd.DataFrame(bars)
        df['t'] = pd.to_datetime(df['t'])
        df = df.sort_values('t').reset_index(drop=True)
        mock_fetch.return_value = df

        response = self.app.get('/momentum?symbol=AAPL')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['signal'], 'extended')
        self.assertGreater(data['distance_from_ema_pct'], 10)

    @patch('app.fetch_weekly_bars')
    def test_weekly_history_in_response(self, mock_fetch):
        closes = [100, 102, 104, 106, 108, 110, 112, 114, 116, 118, 120]
        bars = make_weekly_bars(closes)
        df = pd.DataFrame(bars)
        df['t'] = pd.to_datetime(df['t'])
        df = df.sort_values('t').reset_index(drop=True)
        mock_fetch.return_value = df

        response = self.app.get('/momentum?symbol=AAPL')
        data = json.loads(response.data)
        self.assertIn('weekly_history', data)
        self.assertEqual(len(data['weekly_history']), 8)
        for entry in data['weekly_history']:
            self.assertIn('date', entry)
            self.assertIn('close', entry)
            self.assertIn('ema_8', entry)


class TestExistingEndpoints(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        app.config['TESTING'] = True

    def test_quote_missing_symbol(self):
        response = self.app.get('/quote')
        self.assertEqual(response.status_code, 400)

    def test_sentiment_missing_symbol(self):
        response = self.app.get('/sentiment')
        self.assertEqual(response.status_code, 400)


if __name__ == '__main__':
    unittest.main()
