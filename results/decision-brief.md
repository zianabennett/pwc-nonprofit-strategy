# Outreach decision brief

**Illustrative planning model. BridgePath Adult Learning is fictional. Every forecast below is calculated from invented assumptions, not historical Mercy Education Project results.**

## The decision

Test **3 partner activations, 1 paid-search test, 1 print round** over 8 weeks. The plan forecasts **17.74 first-session starts** and allocates **$1,440.00** of a $1,500.00 ceiling. It reserves **53.73 of 60 staff hours**.

The calculation evaluates 144 bounded channel combinations; 43 satisfy every planning limit. This is the best result within those assumptions and four options, not a claim about the best real-world marketing strategy.

## What the allocation buys

| Channel | Units | Outreach allocation | Staff hours | Expected starts |
| --- | ---: | ---: | ---: | ---: |
| Partner referrals | 3 | $360.00 | 31.20 | 13.82 |
| Community events | 0 | $0.00 | 0.00 | 0.00 |
| Paid search test | 1 | $300.00 | 10.05 | 2.63 |
| Local print outreach | 1 | $100.00 | 6.48 | 1.29 |

Channel hours include inquiry triage and all booked intake time. Add the shared 6-hour setup allocation to reconcile to the total.

| Cash component | Allocation |
| --- | ---: |
| Outreach | $760.00 |
| Shared setup | $200.00 |
| Learner-support reserve for all 24 seats | $480.00 |
| Total allocated | $1,440.00 |
| Unallocated cash | $60.00 |

The learner-support reserve is held, not assumed spent. Existing staff wages and funded instructional delivery are outside the cash calculation.

## Follow the complete funnel

| Stage | Expected count | Definition |
| --- | ---: | --- |
| Unique inquiries | 64.00 | Deduplicated first-time contacts assigned to one source |
| Program fit | 42.20 | Inquiry matches the fictional service, learning goal and schedule |
| Booked intake | 29.64 | Appointment confirmed with the learner |
| Attended intake | 22.51 | Learner attends the appointment |
| First-session start | 17.74 | Learner attends their first teaching session |

Fractional counts are expectations, not partial people. Booked intakes use 29.64 of 30 planning slots, leaving only 0.36 slots of expected headroom. This is the plan's tightest operating constraint. Release outreach in stages and pause it if actual bookings consume the calendar. Rescheduling uses another slot and must fit the same cap. Actual starts must remain within 24 available seats. The model's 18-start ceiling creates forecast headroom, not a statistical guarantee.

## The alternatives are close

| Plan | Total cash allocation | Staff hours | Expected bookings | Expected starts | Feasible |
| --- | ---: | ---: | ---: | ---: | --- |
| Selected mix | $1,440.00 | 53.73 | 29.64 | 17.74 | Yes |
| Event led alternative | $1,470.00 | 57.35 | 29.13 | 17.46 | Yes |
| Paid search heavier | $1,500.00 | 42.98 | 20.64 | 11.16 | Yes |

The event-led alternative uses 2 partner activations, 1 community event, 2 print rounds. The paid-search-heavier option uses 1 partner activation, 2 paid-search tests, 1 print round. These are hypothetical allocations evaluated using the same inputs.

## One assumption can change the choice

If partner referrals intake attendance changes from 80% to 60%, the selected mix forecasts **14.29 expected starts**. Rerunning the model selects **2 partner activations, 1 community event, 2 print rounds**, forecasting **15.16 starts** with $1,470.00 allocated and 57.35 hours reserved.

This is a scenario comparison, not a confidence interval or causal estimate. Its purpose is to identify which assumptions need early measurement.

## What to measure before expansion

Track actual unique inquiries, booked appointments, attendance and starts by source. Review blocked appointment time even when learners do not attend. Investigate why people miss appointments before paying for more inquiries. Reserve confirmed seats individually and pause new outreach when the calendar cannot support follow-up.

The full rollout, learner messaging and review rules are in [the strategy memo](../strategy.md). Reproduce this brief with `python3 analyze.py`; verify saved outputs with `python3 analyze.py --check`.
