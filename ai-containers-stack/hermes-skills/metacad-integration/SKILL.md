---
name: metacad-integration
description: Route MetaCAD requests to the dedicated loading-computer, stability, or sea-fastening skills. Use when a request mentions MetaCAD generally or spans several MetaCAD maritime workflows and the correct specialist skill must be selected.
---

# MetaCAD Integration Router

Select the smallest applicable specialist skill:

- Use `metacad-loading-computer` for complete loading conditions, tanks, ballast, cargo distribution, trim, drafts, strength indicators and preliminary loadicator reports.
- Use `metacad-stability` for GM, free-surface correction, KN/GZ curves, intact-stability criteria, weather criterion, limiting KG and SGISC screening.
- Use `sea-fastening-survey` for project cargo, CSS Annex 13, restraint capacity, friction/sliding/tipping, welded fastening, survey evidence and MWS readiness.

Load more than one specialist skill when the request crosses boundaries. For example, a heavy deck cargo may require loading/stability plus sea fastening.

MetaCAD exposes a browser interface; do not claim a public automation API unless current official documentation explicitly provides one. Do not use `scripts/metacad_helper.py` to validate engineering criteria: its report function only formats caller-supplied values and performs no stability calculation.

All MetaCAD results remain preliminary unless supported by vessel-specific approval. Never replace the approved loading instrument, stability booklet, Cargo Securing Manual, Master, class, flag, naval architect or appointed MWS.
