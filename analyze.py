"""Reproduce a fictional nonprofit outreach decision with exact decimal arithmetic."""

from __future__ import annotations

import argparse
from copy import deepcopy
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from html import escape
from itertools import product
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RATE_FIELDS = ("program_fit_rate", "booking_rate", "attendance_rate", "start_rate")
ZERO = Decimal("0")


def number(value, label):
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a number")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{label} must be a number") from exc
    if not result.is_finite() or result < 0:
        raise ValueError(f"{label} must be finite and nonnegative")
    return result


def integer(value, label):
    if type(value) is not int or value < 0:
        raise ValueError(f"{label} must be a nonnegative integer")
    return value


def validate(scenario):
    for field in ("duration_weeks", "cash_ceiling_cents", "fixed_setup_cost_cents",
                  "new_learner_seats", "support_reserve_per_seat_cents", "appointment_slots"):
        integer(scenario[field], field)
    for field in ("staff_hours_ceiling", "fixed_setup_hours", "appointment_hours",
                  "triage_hours_per_inquiry", "planning_start_ceiling"):
        number(scenario[field], field)
    if number(scenario["planning_start_ceiling"], "planning_start_ceiling") > scenario["new_learner_seats"]:
        raise ValueError("Planning starts cannot exceed learner seats")
    seen = set()
    combination_count = 1
    for channel in scenario["channels"]:
        if not channel["id"] or channel["id"] in seen:
            raise ValueError("Channel IDs must be unique and nonempty")
        seen.add(channel["id"])
        for field in ("max_units", "cost_per_unit_cents", "inquiries_per_unit"):
            integer(channel[field], field)
        number(channel["outreach_hours_per_unit"], "outreach_hours_per_unit")
        for field in RATE_FIELDS:
            if number(channel[field], field) > 1:
                raise ValueError(f"{field} must be between zero and one")
        combination_count *= channel["max_units"] + 1
    if not seen or combination_count > 100000:
        raise ValueError("Require a small, nonempty channel search space")
    sensitivity = scenario["sensitivity"]
    if sensitivity["channel_id"] not in seen:
        raise ValueError("Sensitivity must reference an existing channel")
    if number(sensitivity["attendance_rate"], "sensitivity attendance") > 1:
        raise ValueError("Sensitivity attendance must be between zero and one")


def evaluate(scenario, units):
    """Count scheduled appointment time even when expected attendance is lower."""
    channels = scenario["channels"]
    known = {c["id"] for c in channels}
    if set(units) - known:
        raise ValueError("Plan contains an unknown channel")
    totals = {key: ZERO for key in ("inquiries", "program_fit", "booked", "attended", "starts")}
    rows = []
    outreach_cost = 0
    staff_hours = number(scenario["fixed_setup_hours"], "fixed setup hours")
    for channel in channels:
        count = integer(units.get(channel["id"], 0), "unit count")
        if count > channel["max_units"]:
            raise ValueError("Plan exceeds a channel's pilot cap")
        inquiries = Decimal(count * channel["inquiries_per_unit"])
        program_fit = inquiries * number(channel["program_fit_rate"], "fit rate")
        booked = program_fit * number(channel["booking_rate"], "booking rate")
        attended = booked * number(channel["attendance_rate"], "attendance rate")
        starts = attended * number(channel["start_rate"], "start rate")
        hours = (count * number(channel["outreach_hours_per_unit"], "outreach hours")
                 + inquiries * number(scenario["triage_hours_per_inquiry"], "triage hours")
                 + booked * number(scenario["appointment_hours"], "appointment hours"))
        cost = count * channel["cost_per_unit_cents"]
        row = {"id": channel["id"], "name": channel["name"], "units": count,
               "outreach_cost_cents": cost, "staff_hours": hours, "inquiries": inquiries,
               "program_fit": program_fit, "booked": booked, "attended": attended, "starts": starts}
        rows.append(row)
        for key in totals:
            totals[key] += row[key]
        staff_hours += hours
        outreach_cost += cost
    reserve = scenario["new_learner_seats"] * scenario["support_reserve_per_seat_cents"]
    cash = scenario["fixed_setup_cost_cents"] + reserve + outreach_cost
    violations = []
    checks = ((cash, scenario["cash_ceiling_cents"], "cash"),
              (staff_hours, number(scenario["staff_hours_ceiling"], "staff ceiling"), "staff hours"),
              (totals["booked"], scenario["appointment_slots"], "appointment slots"),
              (totals["starts"], number(scenario["planning_start_ceiling"], "start ceiling"), "planning starts"),
              (totals["starts"], scenario["new_learner_seats"], "learner seats"))
    for value, limit, label in checks:
        if value > limit:
            violations.append(label)
    return {"units": {c["id"]: units.get(c["id"], 0) for c in channels}, "channels": rows,
            "funnel": totals, "outreach_cost_cents": outreach_cost,
            "setup_cost_cents": scenario["fixed_setup_cost_cents"], "support_reserve_cents": reserve,
            "cash_allocated_cents": cash, "cash_remaining_cents": scenario["cash_ceiling_cents"] - cash,
            "staff_hours": staff_hours,
            "staff_hours_remaining": number(scenario["staff_hours_ceiling"], "staff ceiling") - staff_hours,
            "appointment_slots_remaining": Decimal(scenario["appointment_slots"]) - totals["booked"],
            "learner_seat_headroom": Decimal(scenario["new_learner_seats"]) - totals["starts"],
            "allocated_dollars_per_expected_start": (Decimal(cash) / 100 / totals["starts"] if totals["starts"] else None),
            "feasible": not violations, "violations": violations}


def choose_plan(scenario):
    validate(scenario)
    candidates = []
    considered = 0
    channels = scenario["channels"]
    for counts in product(*(range(c["max_units"] + 1) for c in channels)):
        considered += 1
        result = evaluate(scenario, dict(zip((c["id"] for c in channels), counts)))
        if result["feasible"]:
            candidates.append(result)
    if not candidates:
        raise ValueError("No feasible plan, including fixed setup and reserve allocations")
    # Stable ties favor lower cash, then fewer hours, then channel-order unit counts.
    winner = min(candidates, key=lambda p: (-p["funnel"]["starts"], p["cash_allocated_cents"],
                                          p["staff_hours"], tuple(p["units"].values())))
    return winner, considered, len(candidates)


def model(scenario):
    selected, considered, feasible = choose_plan(scenario)
    stress = deepcopy(scenario)
    for channel in stress["channels"]:
        if channel["id"] == stress["sensitivity"]["channel_id"]:
            channel["attendance_rate"] = stress["sensitivity"]["attendance_rate"]
    stress_best, _, _ = choose_plan(stress)
    return {
        "scenario": scenario["scenario_name"], "status": scenario["status"],
        "method": "Enumerate integer channel units; maximize expected first-session starts subject to all planning limits.",
        "considered_plans": considered, "feasible_plans": feasible, "selected": selected,
        "comparisons": {name: evaluate(scenario, plan) for name, plan in scenario["comparison_plans"].items()},
        "sensitivity": {"change": scenario["sensitivity"], "original_mix": evaluate(stress, selected["units"]),
                        "reoptimized_mix": stress_best}
    }


def decimal_text(value):
    value = format(value, "f")
    return value.rstrip("0").rstrip(".") if "." in value else value


def serializable(value):
    if isinstance(value, Decimal):
        return decimal_text(value)
    if isinstance(value, dict):
        return {k: serializable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [serializable(v) for v in value]
    return value


def two(value):
    return f"{number(value, 'display value').quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,.2f}"


def dollars(cents):
    return "$" + two(Decimal(cents) / 100)


def percent(rate):
    return decimal_text(number(rate, "display rate") * 100) + "%"


def describe_plan(plan):
    labels = {"partner_referrals": ("partner activation", "partner activations"),
              "community_events": ("community event", "community events"),
              "paid_search": ("paid-search test", "paid-search tests"),
              "print_distribution": ("print round", "print rounds")}
    parts = []
    for channel, count in plan["units"].items():
        if count:
            singular, plural = labels.get(channel, (channel, channel))
            parts.append(f"{count} {singular if count == 1 else plural}")
    return ", ".join(parts) if parts else "no outreach units"


def report(scenario, result):
    selected = result["selected"]
    stressed = result["sensitivity"]["original_mix"]
    stress_best = result["sensitivity"]["reoptimized_mix"]
    sensitivity_channel = next(c for c in scenario["channels"] if c["id"] == scenario["sensitivity"]["channel_id"])
    rows = []
    for row in selected["channels"]:
        rows.append(f"| {row['name']} | {row['units']} | {dollars(row['outreach_cost_cents'])} | {two(row['staff_hours'])} | {two(row['starts'])} |")
    comparisons = []
    for label, plan in [("Selected mix", selected), *[(n.replace('_', ' ').capitalize(), p) for n, p in result["comparisons"].items()]]:
        comparisons.append(f"| {label} | {dollars(plan['cash_allocated_cents'])} | {two(plan['staff_hours'])} | {two(plan['funnel']['booked'])} | {two(plan['funnel']['starts'])} | {'Yes' if plan['feasible'] else 'No'} |")
    return f"""# Outreach decision brief

**Illustrative planning model. BridgePath Adult Learning is fictional. Every forecast below is calculated from invented assumptions, not historical Mercy Education Project results.**

## The decision

Test **{describe_plan(selected)}** over {scenario['duration_weeks']} weeks. The plan forecasts **{two(selected['funnel']['starts'])} first-session starts** and allocates **{dollars(selected['cash_allocated_cents'])}** of a {dollars(scenario['cash_ceiling_cents'])} ceiling. It reserves **{two(selected['staff_hours'])} of {scenario['staff_hours_ceiling']} staff hours**.

The calculation evaluates {result['considered_plans']} bounded channel combinations; {result['feasible_plans']} satisfy every planning limit. This is the best result within those assumptions and four options, not a claim about the best real-world marketing strategy.

## What the allocation buys

| Channel | Units | Outreach allocation | Staff hours | Expected starts |
| --- | ---: | ---: | ---: | ---: |
{chr(10).join(rows)}

Channel hours include inquiry triage and all booked intake time. Add the shared {scenario['fixed_setup_hours']}-hour setup allocation to reconcile to the total.

| Cash component | Allocation |
| --- | ---: |
| Outreach | {dollars(selected['outreach_cost_cents'])} |
| Shared setup | {dollars(selected['setup_cost_cents'])} |
| Learner-support reserve for all {scenario['new_learner_seats']} seats | {dollars(selected['support_reserve_cents'])} |
| Total allocated | {dollars(selected['cash_allocated_cents'])} |
| Unallocated cash | {dollars(selected['cash_remaining_cents'])} |

The learner-support reserve is held, not assumed spent. Existing staff wages and funded instructional delivery are outside the cash calculation.

## Follow the complete funnel

| Stage | Expected count | Definition |
| --- | ---: | --- |
| Unique inquiries | {two(selected['funnel']['inquiries'])} | Deduplicated first-time contacts assigned to one source |
| Program fit | {two(selected['funnel']['program_fit'])} | Inquiry matches the fictional service, learning goal and schedule |
| Booked intake | {two(selected['funnel']['booked'])} | Appointment confirmed with the learner |
| Attended intake | {two(selected['funnel']['attended'])} | Learner attends the appointment |
| First-session start | {two(selected['funnel']['starts'])} | Learner attends their first teaching session |

Fractional counts are expectations, not partial people. Booked intakes use {two(selected['funnel']['booked'])} of {scenario['appointment_slots']} planning slots, leaving only {two(selected['appointment_slots_remaining'])} slots of expected headroom. This is the plan's tightest operating constraint. Release outreach in stages and pause it if actual bookings consume the calendar. Rescheduling uses another slot and must fit the same cap. Actual starts must remain within {scenario['new_learner_seats']} available seats. The model's {scenario['planning_start_ceiling']}-start ceiling creates forecast headroom, not a statistical guarantee.

## The alternatives are close

| Plan | Total cash allocation | Staff hours | Expected bookings | Expected starts | Feasible |
| --- | ---: | ---: | ---: | ---: | --- |
{chr(10).join(comparisons)}

The event-led alternative uses {describe_plan(result['comparisons']['event_led_alternative'])}. The paid-search-heavier option uses {describe_plan(result['comparisons']['paid_search_heavier'])}. These are hypothetical allocations evaluated using the same inputs.

## One assumption can change the choice

If {sensitivity_channel['name'].lower()} intake attendance changes from {percent(sensitivity_channel['attendance_rate'])} to {percent(scenario['sensitivity']['attendance_rate'])}, the selected mix forecasts **{two(stressed['funnel']['starts'])} expected starts**. Rerunning the model selects **{describe_plan(stress_best)}**, forecasting **{two(stress_best['funnel']['starts'])} starts** with {dollars(stress_best['cash_allocated_cents'])} allocated and {two(stress_best['staff_hours'])} hours reserved.

This is a scenario comparison, not a confidence interval or causal estimate. Its purpose is to identify which assumptions need early measurement.

## What to measure before expansion

Track actual unique inquiries, booked appointments, attendance and starts by source. Review blocked appointment time even when learners do not attend. Investigate why people miss appointments before paying for more inquiries. Reserve confirmed seats individually and pause new outreach when the calendar cannot support follow-up.

The full rollout, learner messaging and review rules are in [the strategy memo](../strategy.md). Reproduce this brief with `python3 analyze.py`; verify saved outputs with `python3 analyze.py --check`.
"""


def svg(scenario, result):
    selected = result["selected"]
    stressed = result["sensitivity"]["original_mix"]
    stress_best = result["sensitivity"]["reoptimized_mix"]
    scale_max = max(Decimal("14"), max(row["starts"] for row in selected["channels"]))
    pieces = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="660" viewBox="0 0 1000 660" role="img" aria-labelledby="title desc">
<title id="title">Outreach tied to intake capacity</title>
<desc id="desc">Fictional BridgePath planning model. Selected mix forecasts {two(selected['funnel']['starts'])} first-session starts with {dollars(selected['cash_allocated_cents'])} allocated and {two(selected['staff_hours'])} staff hours. Lower partner attendance changes the preferred channel mix.</desc>
<rect width="1000" height="660" rx="20" fill="#f6f8f4"/>
<g font-family="Arial, sans-serif" fill="#193d35">
<text x="32" y="44" font-size="26" font-weight="700">Outreach tied to intake capacity</text>
<text x="32" y="72" font-size="15" fill="#52645a">BridgePath Adult Learning · Fictional eight-week planning exercise</text>''']
    cards = [(32, two(selected["funnel"]["starts"]), "Expected first-session starts"),
             (344, dollars(selected["cash_allocated_cents"]), "Allocated cash, including reserve"),
             (656, two(selected["staff_hours"]) + " h", "Outreach and intake staff time")]
    for x, big, label in cards:
        pieces.append(f'<rect x="{x}" y="100" width="288" height="104" rx="10" fill="#e3ebdf"/><text x="{x+18}" y="146" font-size="30" font-weight="700">{escape(big)}</text><text x="{x+18}" y="177" font-size="14">{escape(label)}</text>')
    pieces.append('<text x="32" y="246" font-size="18" font-weight="700">Expected starts by selected channel</text>')
    for i, row in enumerate(selected["channels"]):
        y = 280 + i * 53
        width = float(row["starts"] / scale_max * 590)
        pieces.append(f'<text x="32" y="{y+23}" font-size="16">{escape(row["name"])}</text><rect x="260" y="{y}" width="590" height="34" rx="5" fill="#e3e8e2"/>')
        if width:
            pieces.append(f'<rect x="260" y="{y}" width="{width:.3f}" height="34" rx="5" fill="#2d6a58"/>')
        pieces.append(f'<text x="870" y="{y+23}" font-size="16" font-weight="700">{two(row["starts"])}</text>')
    pieces.extend([
        f'<text x="32" y="509" font-size="13" fill="#52645a">Bar scale 0 to {decimal_text(scale_max)} starts · Intake uses {two(selected["funnel"]["booked"])} of {scenario["appointment_slots"]} planning slots.</text>',
        '<rect x="32" y="538" width="936" height="86" rx="10" fill="#f2e4ce"/>',
        '<text x="50" y="565" font-size="16" font-weight="700">A lower partner attendance assumption changes the recommendation</text>',
        f'<text x="50" y="590" font-size="15">Selected mix at {percent(scenario["sensitivity"]["attendance_rate"])} partner attendance: {two(stressed["funnel"]["starts"])} starts. Revised mix: {two(stress_best["funnel"]["starts"])}.</text>',
        '<text x="50" y="611" font-size="13">Illustrative forecasts only. Program delivery, retention and GED completion are outside this model.</text>',
        '</g></svg>\n'])
    return "\n".join(pieces)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check that committed outputs match the current inputs")
    args = parser.parse_args()
    scenario = json.loads((ROOT / "data/scenario.json").read_text())
    result = model(scenario)
    outputs = {"analysis.json": json.dumps(serializable(result), indent=2) + "\n",
               "decision-brief.md": report(scenario, result), "channel-plan.svg": svg(scenario, result)}
    directory = ROOT / "results"
    directory.mkdir(exist_ok=True)
    if args.check:
        stale = [name for name, content in outputs.items() if not (directory / name).exists() or (directory / name).read_text() != content]
        if stale:
            raise SystemExit("Stale generated outputs: " + ", ".join(stale))
        print("All three generated outputs match the scenario.")
    else:
        for name, content in outputs.items():
            (directory / name).write_text(content)
        print(f"Wrote three outputs. Expected starts {two(result['selected']['funnel']['starts'])}; allocated cash {dollars(result['selected']['cash_allocated_cents'])}; staff hours {two(result['selected']['staff_hours'])}.")


if __name__ == "__main__":
    main()
