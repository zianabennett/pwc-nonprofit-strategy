from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import unittest

from analyze import choose_plan, evaluate, model, validate


class PlanningRulesTests(unittest.TestCase):
    def setUp(self):
        self.scenario = json.loads((Path(__file__).parent / "data/scenario.json").read_text())

    def test_no_show_still_consumes_booked_appointment_time(self):
        plan = {"partner_referrals": 1}
        original = evaluate(self.scenario, plan)
        changed = deepcopy(self.scenario)
        changed["channels"][0]["attendance_rate"] = "0"
        no_shows = evaluate(changed, plan)
        self.assertEqual(no_shows["staff_hours"], original["staff_hours"])
        self.assertEqual(no_shows["funnel"]["booked"], Decimal("7.2"))
        self.assertEqual(no_shows["funnel"]["starts"], Decimal("0"))

    def test_cash_includes_setup_and_reserve_for_all_seats(self):
        plan = evaluate(self.scenario, {"partner_referrals": 1})
        self.assertEqual(plan["cash_allocated_cents"], 12000 + 20000 + 24 * 2000)
        self.assertEqual(plan["support_reserve_cents"], 48000)

    def test_resource_limits_are_inclusive_and_independent(self):
        units = {"partner_referrals": 1}
        base = evaluate(self.scenario, units)
        at_limit = deepcopy(self.scenario)
        at_limit["cash_ceiling_cents"] = base["cash_allocated_cents"]
        at_limit["staff_hours_ceiling"] = str(base["staff_hours"])
        at_limit["planning_start_ceiling"] = str(base["funnel"]["starts"])
        self.assertTrue(evaluate(at_limit, units)["feasible"])
        for field, value, violation in (("cash_ceiling_cents", base["cash_allocated_cents"] - 1, "cash"),
                                        ("staff_hours_ceiling", str(base["staff_hours"] - Decimal("0.01")), "staff hours"),
                                        ("appointment_slots", 7, "appointment slots"),
                                        ("planning_start_ceiling", "4", "planning starts")):
            changed = deepcopy(self.scenario)
            changed[field] = value
            self.assertIn(violation, evaluate(changed, units)["violations"])

    def test_zero_starts_has_no_cost_per_start(self):
        zero = evaluate(self.scenario, {})
        self.assertIsNone(zero["allocated_dollars_per_expected_start"])
        self.assertEqual(zero["staff_hours"], Decimal("6"))

    def test_invalid_rates_duplicate_channels_and_fractional_units_are_rejected(self):
        invalid_rate = deepcopy(self.scenario)
        invalid_rate["channels"][0]["attendance_rate"] = "1.01"
        with self.assertRaises(ValueError):
            validate(invalid_rate)
        duplicate = deepcopy(self.scenario)
        duplicate["channels"][1]["id"] = duplicate["channels"][0]["id"]
        with self.assertRaises(ValueError):
            validate(duplicate)
        with self.assertRaises(ValueError):
            evaluate(self.scenario, {"partner_referrals": 0.5})

    def test_insufficient_cash_for_fixed_allocations_has_no_feasible_plan(self):
        self.scenario["cash_ceiling_cents"] = 67999
        with self.assertRaisesRegex(ValueError, "No feasible plan"):
            choose_plan(self.scenario)

    def test_attendance_sensitivity_changes_channel_choice(self):
        result = model(self.scenario)
        self.assertEqual(result["selected"]["units"], {"partner_referrals": 3, "community_events": 0, "paid_search": 1, "print_distribution": 1})
        stressed = result["sensitivity"]
        self.assertLess(stressed["original_mix"]["funnel"]["starts"], stressed["reoptimized_mix"]["funnel"]["starts"])
        self.assertEqual(stressed["reoptimized_mix"]["units"], {"partner_referrals": 2, "community_events": 1, "paid_search": 0, "print_distribution": 2})


if __name__ == "__main__":
    unittest.main()
