import json
import tempfile
import unittest
from pathlib import Path

from funds_manager import (
    add_fund_and_save,
    calculate_holding_metrics,
    normalize_fund_items,
    update_fund_holding_and_save,
)


class FundsManagerTests(unittest.TestCase):
    def test_add_fund_and_save_preserves_existing_holding(self):
        existing_funds = [
            {
                "code": "110022",
                "name": "示例基金",
                "holding": {"units": 100.5, "cost_amount": 120.0},
            }
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "funds.json"
            updated = add_fund_and_save(existing_funds, "161725", config_path)

            self.assertEqual(updated[0]["holding"]["units"], 100.5)
            self.assertEqual(updated[0]["holding"]["cost_amount"], 120.0)

            payload = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["funds"][0]["holding"]["units"], 100.5)
            self.assertEqual(payload["funds"][0]["holding"]["cost_amount"], 120.0)
            self.assertEqual(payload["funds"][1]["code"], "161725")

    def test_update_fund_holding_and_save_writes_normalized_values(self):
        existing_funds = [{"code": "110022"}]

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "funds.json"
            updated = update_fund_holding_and_save(existing_funds, "110022", 256.75, 300.5, config_path)

            self.assertEqual(updated[0]["holding"]["units"], 256.75)
            self.assertEqual(updated[0]["holding"]["cost_amount"], 300.5)

            payload = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(
                payload,
                {
                    "funds": [
                        {
                            "code": "110022",
                            "holding": {"units": 256.75, "cost_amount": 300.5},
                        }
                    ]
                },
            )

    def test_calculate_holding_metrics_returns_daily_and_total_profit(self):
        metrics = calculate_holding_metrics(
            units=100.0,
            cost_amount=110.0,
            current_nav=1.25,
            previous_nav=1.20,
        )

        self.assertAlmostEqual(metrics["market_value"], 125.0)
        self.assertAlmostEqual(metrics["total_profit"], 15.0)
        self.assertAlmostEqual(metrics["total_profit_pct"], 13.6363636363, places=6)
        self.assertAlmostEqual(metrics["daily_profit"], 5.0)
        self.assertAlmostEqual(metrics["daily_profit_pct"], 4.1666666666, places=6)

    def test_calculate_holding_metrics_handles_missing_previous_nav(self):
        metrics = calculate_holding_metrics(
            units=100.0,
            cost_amount=110.0,
            current_nav=1.25,
            previous_nav=None,
        )

        self.assertAlmostEqual(metrics["market_value"], 125.0)
        self.assertAlmostEqual(metrics["total_profit"], 15.0)
        self.assertIsNone(metrics["daily_profit"])
        self.assertIsNone(metrics["daily_profit_pct"])

    def test_normalize_fund_items_ignores_invalid_holding_when_requested(self):
        normalized = normalize_fund_items(
            [{"code": "110022", "holding": {"units": 1}}],
            ignore_invalid_holding=True,
        )

        self.assertEqual(normalized, [{"code": "110022"}])


if __name__ == "__main__":
    unittest.main()
