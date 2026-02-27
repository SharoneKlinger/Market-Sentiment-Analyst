import unittest

from app import app


class TradePlanTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_trade_plan_success(self):
        payload = {
            'spx': 5020,
            'atm_straddle': 58,
            'vix': 15,
            'call_wall': 5080,
            'put_wall': 4960,
            'gamma_flip': 5005,
            'dealer_gamma': 'long',
            'account_size': 250000,
        }
        resp = self.client.post('/spx-0dte-plan', json=payload)
        self.assertEqual(resp.status_code, 200)

        body = resp.get_json()
        self.assertIn('trade', body)
        self.assertIn('probability_of_profit', body['trade'])
        self.assertGreater(body['trade']['probability_of_profit'], 0)
        self.assertLessEqual(body['trade']['risk']['account_risk_pct'], 2)

    def test_trade_plan_missing_fields(self):
        resp = self.client.post('/spx-0dte-plan', json={'spx': 5020})
        self.assertEqual(resp.status_code, 400)
        body = resp.get_json()
        self.assertIn('error', body)


if __name__ == '__main__':
    unittest.main()
