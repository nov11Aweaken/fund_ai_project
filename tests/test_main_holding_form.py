import types
import unittest

from main import FletApp


class HoldingFormValueTests(unittest.TestCase):
    def test_read_holding_form_values_falls_back_to_cached_state(self):
        dummy_app = types.SimpleNamespace(
            _holding_form_state={"units": "123.45", "cost_amount": "678.90"},
            _holding_units_field=types.SimpleNamespace(value=""),
            _holding_cost_field=types.SimpleNamespace(value=""),
        )

        values = FletApp._read_holding_form_values(dummy_app)

        self.assertEqual(values, ("123.45", "678.90"))


if __name__ == "__main__":
    unittest.main()
