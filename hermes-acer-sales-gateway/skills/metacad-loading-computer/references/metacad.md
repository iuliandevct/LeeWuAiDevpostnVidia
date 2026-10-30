# MetaCAD reference

Verified against the MetaCAD English website on 2026-08-01:

- Product overview: https://metacad.io/en/
- Loading Computer: https://metacad.io/en/loading/computer/

Re-check the live site when exact current features, standards, tests, pricing or regulatory claims matter.

## Product boundary

MetaCAD describes itself as a browser-based naval-architecture and loading-calculation platform. Core calculations run client-side and can work offline; vessel inputs stay on the device unless the user invokes sharing or export.

MetaCAD explicitly states that it is for education, training and preliminary engineering unless vessel-specific approval applies. It is not an IACS-approved loading instrument. Never use it to replace the vessel's approved loading computer, stability booklet, instruments or command decision.

## Loading Computer input model

The loading table supports:

- lightship weight and LCG/VCG/TCG;
- ballast and consumable tanks with capacity, fill, density, volume, weight, LCG/VCG/TCG and FSM;
- cargo items or aggregates with weight and coordinates;
- constants, stores and personnel;
- hydrostatic tables and cross-curves;
- vessel dimensions, load-line and capacity limits.

Coordinate conventions and units are vessel-specific input facts. Record them explicitly.

## Review surfaces

The current interface exposes or advertises:

- loading table and cargo/bay/longitudinal views;
- port summary and loading sequence;
- strength, tank sounding and trim optimization;
- auto-balance and under-keel clearance;
- condition comparison and booklet/report export;
- aft/mid/forward drafts, trim, list, displacement and deadweight;
- freeboard, propeller immersion and bending-moment percentage;
- weight distribution and capacity budgets;
- LCG, VCG, TCG, KM, KG, uncorrected GM, FSM correction and corrected GM;
- TPC, MTC, KB, LCB, LCF, FWA and air draft;
- GZ curve, maximum GZ, vanishing angle and limiting KG;
- IMO IS Code criteria and RMRS selection;
- load-zone draft checks and icing-related analysis;
- a confidence/data-completeness assessment.

Feature presence does not establish vessel-specific approval or input validity.

## Interpretation rules

- Corrected GM is the relevant GM after free-surface correction.
- A positive GM alone does not prove compliance; evaluate every applicable GZ/area/angle/weather or vessel-specific criterion.
- A passed IMO criterion does not excuse another failed criterion.
- A negative limiting-KG margin means current KG exceeds the calculated limit for the selected basis.
- Draft and load-line compliance do not establish adequate stability or longitudinal/local strength.
- Global strength indicators do not prove local deck or tanktop loading under concentrated project cargo.
- A high confidence percentage is a data-completeness aid, not a safety approval.

## Evidence and reporting

Capture the MetaCAD condition identity, vessel dataset, input sources, units/datums, cargo and tank totals, FSM, warnings, full criterion table, GZ plot, limiting-KG margin, strength indicators and export timestamp. Preserve the original baseline and identify every modified what-if case.

For operational work, reconcile the preliminary result against the approved loading instrument and obtain the required Master/class/naval-architect/MWS acceptance.
