import unittest
from unittest.mock import patch, MagicMock
import json
import pandas as pd
import numpy as np
from app import app, detect_ema_break
from finviz_scanner import (
    _parse_screener_page,
    get_available_presets,
    SCAN_PRESETS,
)


def make_weekly_df(closes, start_date='2025-01-06'):
    """Build a DataFrame mimicking fetch_weekly_bars output."""
    dates = pd.date_range(start=start_date, periods=len(closes), freq='W-FRI')
    rows = []
    for date, close in zip(dates, closes):
        rows.append({
            't': date,
            'o': close * 0.99,
            'h': close * 1.02,
            'l': close * 0.97,
            'c': close,
            'v': 1000000,
        })
    return pd.DataFrame(rows)


# --- Finviz HTML parsing tests ---

SAMPLE_FINVIZ_HTML = """
<html><body>
<table>
  <tr><td><a href="quote.ashx?t=NVDA">NVDA</a></td></tr>
  <tr><td><a href="quote.ashx?t=AAPL">AAPL</a></td></tr>
  <tr><td><a href="quote.ashx?t=TSLA">TSLA</a></td></tr>
  <tr><td><a href="quote.ashx?t=META">META</a></td></tr>
  <tr><td><a href="somewhere_else">Not a ticker</a></td></tr>
  <tr><td><a href="quote.ashx?t=TOOLONG&extra=1">TOOLONG</a></td></tr>
</table>
</body></html>
"""


class TestFinvizParser(unittest.TestCase):
    def test_parse_screener_page(self):
        symbols = _parse_screener_page(SAMPLE_FINVIZ_HTML)
        self.assertEqual(symbols, ['NVDA', 'AAPL', 'TSLA', 'META'])

    def test_parse_empty_page(self):
        symbols = _parse_screener_page('<html><body></body></html>')
        self.assertEqual(symbols, [])

    def test_filters_non_ticker_links(self):
        html = '<a href="quote.ashx?t=OK">OK</a><a href="other.ashx?t=NO">NO</a>'
        symbols = _parse_screener_page(html)
        self.assertEqual(symbols, ['OK'])

    def test_rejects_lowercase_tickers(self):
        html = '<a href="quote.ashx?t=bad">bad</a>'
        symbols = _parse_screener_page(html)
        self.assertEqual(symbols, [])


class TestScanPresets(unittest.TestCase):
    def test_all_presets_have_descriptions(self):
        presets = get_available_presets()
        for name in SCAN_PRESETS:
            self.assertIn(name, presets)
            self.assertTrue(len(presets[name]) > 0)

    def test_all_presets_have_filters(self):
        for name, config in SCAN_PRESETS.items():
            self.assertIn('filters', config)
            self.assertIn('v', config['filters'])
            self.assertIn('f', config['filters'])


# --- EMA break detection tests ---

class TestDetectEmaBreak(unittest.TestCase):

    @patch('app.fetch_weekly_bars')
    def test_break_above(self, mock_fetch):
        # Price was below EMA, then jumps above
        closes = [100, 102, 104, 103, 101, 99, 97, 95, 93, 91, 89, 88, 86, 84, 82, 80, 78, 100]
        mock_fetch.return_value = make_weekly_df(closes)
        result = detect_ema_break('TEST')
        self.assertIsNotNone(result)
        self.assertEqual(result['break_type'], 'break_above')
        self.assertEqual(result['symbol'], 'TEST')

    @patch('app.fetch_weekly_bars')
    def test_break_below(self, mock_fetch):
        # Price was above EMA, then drops below
        closes = [80, 82, 84, 86, 88, 90, 92, 94, 96, 98, 100, 102, 104, 106, 108, 110, 112, 80]
        mock_fetch.return_value = make_weekly_df(closes)
        result = detect_ema_break('TEST')
        self.assertIsNotNone(result)
        self.assertEqual(result['break_type'], 'break_below')

    @patch('app.fetch_weekly_bars')
    def test_steady_above(self, mock_fetch):
        # Price consistently above EMA, no crossover
        closes = [100, 102, 104, 106, 108, 110, 112, 114, 116, 118, 120]
        mock_fetch.return_value = make_weekly_df(closes)
        result = detect_ema_break('TEST')
        self.assertEqual(result['break_type'], 'above')

    @patch('app.fetch_weekly_bars')
    def test_steady_below(self, mock_fetch):
        # Price consistently below EMA (downtrend)
        closes = [120, 118, 116, 114, 112, 110, 108, 106, 104, 102, 100]
        mock_fetch.return_value = make_weekly_df(closes)
        result = detect_ema_break('TEST')
        self.assertEqual(result['break_type'], 'below')

    @patch('app.fetch_weekly_bars')
    def test_insufficient_data(self, mock_fetch):
        mock_fetch.return_value = make_weekly_df([100, 102])
        result = detect_ema_break('TEST')
        self.assertIsNone(result)

    @patch('app.fetch_weekly_bars')
    def test_empty_data(self, mock_fetch):
        mock_fetch.return_value = pd.DataFrame()
        result = detect_ema_break('TEST')
        self.assertIsNone(result)


# --- Scanner endpoint tests ---

class TestScannerEndpoint(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        app.config['TESTING'] = True

    @patch('app.detect_ema_break')
    @patch('app.scrape_finviz_screener')
    def test_scanner_returns_results(self, mock_scrape, mock_detect):
        mock_scrape.return_value = ['AAPL', 'NVDA']
        mock_detect.side_effect = [
            {
                'symbol': 'AAPL', 'latest_close': 195.0, 'ema_8_week': 190.0,
                'distance_from_ema_pct': 2.63, 'ema_rising': True,
                'break_type': 'break_above',
            },
            {
                'symbol': 'NVDA', 'latest_close': 880.0, 'ema_8_week': 870.0,
                'distance_from_ema_pct': 1.15, 'ema_rising': True,
                'break_type': 'above',
            },
        ]

        response = self.app.get('/scanner?preset=momentum_leaders')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['candidates_scanned'], 2)
        self.assertEqual(data['total_results'], 2)
        self.assertEqual(data['breaks_above_count'], 1)
        # break_above should sort first
        self.assertEqual(data['results'][0]['symbol'], 'AAPL')

    @patch('app.detect_ema_break')
    @patch('app.scrape_finviz_screener')
    def test_scanner_direction_filter_above(self, mock_scrape, mock_detect):
        mock_scrape.return_value = ['AAPL', 'TSLA']
        mock_detect.side_effect = [
            {
                'symbol': 'AAPL', 'latest_close': 195.0, 'ema_8_week': 190.0,
                'distance_from_ema_pct': 2.63, 'ema_rising': True,
                'break_type': 'break_above',
            },
            {
                'symbol': 'TSLA', 'latest_close': 150.0, 'ema_8_week': 180.0,
                'distance_from_ema_pct': -16.67, 'ema_rising': False,
                'break_type': 'break_below',
            },
        ]

        response = self.app.get('/scanner?direction=above')
        data = json.loads(response.data)
        self.assertEqual(data['total_results'], 1)
        self.assertEqual(data['results'][0]['symbol'], 'AAPL')

    @patch('app.detect_ema_break')
    @patch('app.scrape_finviz_screener')
    def test_scanner_direction_filter_below(self, mock_scrape, mock_detect):
        mock_scrape.return_value = ['TSLA']
        mock_detect.side_effect = [
            {
                'symbol': 'TSLA', 'latest_close': 150.0, 'ema_8_week': 180.0,
                'distance_from_ema_pct': -16.67, 'ema_rising': False,
                'break_type': 'below',
            },
        ]

        response = self.app.get('/scanner?direction=below')
        data = json.loads(response.data)
        self.assertEqual(data['total_results'], 1)

    @patch('app.scrape_finviz_screener')
    def test_scanner_no_symbols(self, mock_scrape):
        mock_scrape.return_value = []
        response = self.app.get('/scanner')
        data = json.loads(response.data)
        self.assertEqual(data['candidates_scanned'], 0)

    def test_scanner_invalid_max_pages(self):
        response = self.app.get('/scanner?max_pages=99')
        self.assertEqual(response.status_code, 400)

    @patch('app.scrape_finviz_screener')
    def test_scanner_invalid_preset(self, mock_scrape):
        mock_scrape.side_effect = ValueError("Unknown preset 'fake'")
        response = self.app.get('/scanner?preset=fake')
        self.assertEqual(response.status_code, 400)

    @patch('app.detect_ema_break')
    @patch('app.scrape_finviz_screener')
    def test_scanner_handles_individual_failures(self, mock_scrape, mock_detect):
        mock_scrape.return_value = ['AAPL', 'BAD']
        mock_detect.side_effect = [
            {
                'symbol': 'AAPL', 'latest_close': 195.0, 'ema_8_week': 190.0,
                'distance_from_ema_pct': 2.63, 'ema_rising': True,
                'break_type': 'above',
            },
            Exception("API error"),
        ]

        response = self.app.get('/scanner')
        data = json.loads(response.data)
        self.assertEqual(data['total_results'], 1)
        self.assertEqual(len(data['errors']), 1)
        self.assertEqual(data['errors'][0]['symbol'], 'BAD')


class TestPresetsEndpoint(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        app.config['TESTING'] = True

    def test_list_presets(self):
        response = self.app.get('/scanner/presets')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('momentum_leaders', data)
        self.assertIn('breakout_candidates', data)
        self.assertIn('high_momentum', data)
        self.assertIn('broad', data)


if __name__ == '__main__':
    unittest.main()
