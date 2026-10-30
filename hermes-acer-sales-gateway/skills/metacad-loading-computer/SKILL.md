---
name: metacad-loading-computer
description: Prepare, enter, review, and explain vessel loading conditions with the browser-based MetaCAD Loading Computer. Use for stability, trim, drafts, ballast and tank states, cargo weight/CG placement, free-surface correction, GZ and IMO criteria, limiting KG, load-line checks, hull-strength indicators, and preliminary loading reports. Use only for education, training, and preliminary engineering; never represent MetaCAD output as approval for an operational loading condition.
---

# MetaCAD Loading Computer

Use MetaCAD as a transparent preliminary calculation and review surface. Keep the approved stability booklet, Cargo Securing Manual, class-approved loading instrument, Master, naval architect, and Marine Warranty Surveyor authoritative.

Read [references/metacad.md](references/metacad.md) before using MetaCAD or interpreting its output.

## Workflow

1. Define the task: new loading condition, review, what-if comparison, troubleshooting, or report interpretation.
2. Collect vessel-specific inputs. Require source documents for lightship, hydrostatics/cross-curves, tanks, load lines, permissible strength limits, and coordinate conventions.
3. Collect every variable load: cargo, ballast, fuel, lubricants, fresh water, stores, constants and personnel. Record weight, LCG, VCG and TCG; record tank fill, density and FSM.
4. Normalize units and axes before entry. State the longitudinal datum, sign conventions and density basis. Never infer a missing coordinate from a drawing without marking it provisional.
5. Open `https://metacad.io/en/loading/computer/`. Prefer import or a verified vessel dataset over a generic preset. Save a named baseline before changes.
6. Enter or import the loading condition. Reconcile category subtotals and total displacement against the source data.
7. Inspect data confidence before conclusions. Treat missing hydrostatics, cross-curves, dimensions, cargo items, FSM or out-of-range drafts as blockers.
8. Review drafts, trim, list, displacement, deadweight, freeboard, propeller immersion, CG, FSM correction, corrected GM, GZ curve, IMO criteria, limiting KG and available strength indicators.
9. Investigate every failure from inputs to physics: source-data validity, unit/datum errors, missing weights, tank slackness/FSM, high VCG cargo, transverse imbalance, longitudinal distribution, draft-table range, then criterion-specific margins.
10. Create reversible what-if cases. Explain the expected effect of lowering or relocating cargo, redistributing ballast, reducing slack tanks, or changing consumables. Do not prescribe transfers without checking tank, structural, operational and environmental constraints.
11. Export or capture a report containing the input basis, condition name/time, warnings, failed criteria, margins and assumptions. Label it `PRELIMINARY — NOT AN APPROVED LOADING INSTRUMENT OUTPUT`.

## Required response structure

Return:

- purpose and calculation basis;
- source data received and missing;
- input reconciliation and assumptions;
- key results with units;
- each criterion as PASS/FAIL/NOT VERIFIED with actual value, requirement and margin;
- limiting risks and sensitivity;
- candidate what-if improvements;
- required approval/verification path.

Do not report an overall `safe` result merely because one metric passes. If MetaCAD and approved vessel documentation disagree, stop and escalate the discrepancy.

## Project-cargo use

For heavy-lift or oversized cargo, pair the loading review with deck/tanktop load limits, local load spreading, lifting sequence, crane-induced heel, lashing calculations and voyage-specific accelerations. These are not proven by an intact-stability pass alone. If a local maritime-knowledge search tool is available, use it to retrieve supporting vessel particulars, stowage plans and securing references with page citations.
