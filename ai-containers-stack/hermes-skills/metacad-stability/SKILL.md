---
name: metacad-stability
description: Prepare and review preliminary ship-stability calculations with MetaCAD, including displacement and moments, corrected GM, KN/GZ curves, area criteria, weather criterion, limiting KG/GM, vanishing angle, icing, flooding and SGISC screening. Use when explaining stability results, comparing loading cases, diagnosing failed IMO/class criteria, or preparing an auditable preliminary report. Never use MetaCAD as a substitute for a vessel-approved loading instrument or stability booklet.
---

# MetaCAD Stability

Read [references/stability.md](references/stability.md) before calculation or interpretation.

## Procedure

1. Identify the vessel, loading condition, voyage stage, applicable criteria and intended decision.
2. Establish the approved data basis: lightship, hydrostatics, KN/cross-curves, tank tables, downflooding/opening data, load lines and operational limits.
3. Reconcile all weights and moments. Require weight, LCG, VCG and TCG for each item; require density and FSM for slack tanks.
4. Verify units, axes, longitudinal datum, sign conventions, water density and interpolation range.
5. Use the full vessel dataset when available. Treat express `L, B, T, KG` mode and template vessels as demonstrations or rough screening only.
6. Calculate displacement/current trim, combined KG and corrected GM, then build the GZ curve from vessel-specific KN data.
7. Check every applicable criterion separately. Record actual value, requirement, margin and source. Include areas under GZ, maximum GZ/angle, initial GM, range/vanishing angle, weather criterion and vessel-specific criteria.
8. Check limiting KG/GM and sensitivities to cargo VCG, ballast, consumables, FSM, icing, flooding or voyage-stage changes.
9. If classic criteria pass but dynamic vulnerability matters, identify the need for SGISC Level 2/3 or another approved assessment; do not infer dynamic safety from intact-static compliance.
10. Preserve baseline and what-if cases. Export inputs, ShowMath/formulas, criteria table, GZ chart, assumptions and signature block.

## Diagnosis order

When a result fails, check source-data completeness and datum/unit errors first. Then assess negative/low GM, FSM, high KG, transverse imbalance, downflooding angle, inadequate GZ areas/range and criterion-specific environmental effects.

Offer candidate adjustments as reversible what-if cases. Do not order cargo or ballast movement without verifying local/global strength, tank restrictions, draft/load-line limits, propeller/rudder immersion, cargo securing and operational constraints.

## Output

Return the calculation basis, missing inputs, reconciled displacement/moments, corrected GM, GZ summary, criterion table, limiting KG margin, sensitivity cases, unresolved risks and approval path. Mark outputs `PRELIMINARY — VERIFY WITH APPROVED VESSEL DOCUMENTATION/INSTRUMENT`.
