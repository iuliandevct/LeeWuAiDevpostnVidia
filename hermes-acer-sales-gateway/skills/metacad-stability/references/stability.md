# MetaCAD stability reference

Source checked 2026-08-01: https://metacad.io/en/stability/

Re-check the live page and governing official standards when exact current features or criteria matter.

## Core relationships shown by MetaCAD

- Corrected initial stability: `GMcorr = KM - KG - ΣFSM / Δ`.
- Righting arm from cross-curves: `GZ(θ) = KN(θ, Δ) - KG × sin(θ)` under the assumptions of the selected method.
- IMO criteria include required areas under portions of the GZ curve; MetaCAD shows formula substitution through ShowMath.

These compact relationships do not replace vessel-specific hydrostatics, cross-curves, downflooding data, corrections or special criteria.

## MetaCAD surfaces

The stability suite advertises vessel library/import, express inputs, GZ and dynamic righting arms, area integration, IMO IS Code/class checks, weather criterion, limiting KG/GM, icing, flooding/damage tools, case comparison, reports and SGISC Level 2/3 tools.

## Guardrails

- MetaCAD states that it is educational/training/preliminary software and is not an IACS-approved loading instrument.
- Positive GM is necessary in common intact cases but does not prove compliance.
- A generic/template hull cannot validate a real vessel.
- Correct FSM and actual KG are critical; missing slack-tank effects can materially overstate stability.
- Damage stability, grain, timber, lifting, towing and offshore operations can invoke additional or different criteria.
- SGISC screening addresses dynamic failure modes that classic GM/GZ checks may not capture.
- Operational acceptance remains with the approved instrument/documents and responsible Master/class/naval architect/authority.
