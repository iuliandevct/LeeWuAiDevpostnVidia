---
name: sea-fastening-survey
description: Prepare and review project-cargo and heavy-lift sea-fastening calculations, drawings, evidence packs and pre-departure survey checklists. Use for non-standard cargo, wind components, transformers, modules, machinery, welded stoppers/bracing/pad-eyes, CSS Code Annex 13 force balance, MSL/CS checks, friction/sliding/tipping checks, and Marine Warranty Survey readiness. Do not issue approvals or a Certificate of Approval and do not replace physical survey, NDT, structural verification or the appointed MWS.
---

# Sea Fastening Survey

Read [references/sea-fastening.md](references/sea-fastening.md) before selecting a calculation basis or stating compliance.

## Workflow

1. Define parties, voyage, vessel, cargo unit, insurer/MWS requirements and governing documents. Distinguish CSM-standardized securing from project-specific sea fastening.
2. Collect verified cargo weight, dimensions, CoG, support footprint, allowable loads, lifting/lashing points and transport frame data.
3. Collect vessel Lpp, breadth, GM/loading condition, speed, stow position, deck/tanktop limits, structural framing, fastening-point capacities and approved CSM information.
4. Establish route/environment and design acceleration basis. Confirm whether IMO CSS Annex 13 is accepted or whether DNV-ST-N001, class, flag, client or MWS requirements govern.
5. Calculate design forces and moments in all required directions, including applicable wind/sea effects. Keep input coefficients and corrections auditable.
6. Check sliding and tipping using defensible friction and geometry. Do not count friction without verified contact material, condition, normal force and governing-method permission.
7. Check each restraint by direction and load path: chains/wires/webbing, MSL/CS, angles, pretension assumptions, D-rings/pad-eyes, bridge fittings, stoppers, braces, welds, foundations and supporting vessel structure.
8. Check load spreading and local/global deck strength. A lashing force balance does not prove weld, pad-eye, stopper or deck capacity.
9. Review drawings for dimensions, item IDs, material grades, weld symbols/sizes/lengths, NDT, strong-point alignment, installation/removal sequence and inspection access.
10. Build a pre-departure evidence pack: approved drawings/calculations, certificates, welder qualifications, WPS/PQR, NDT, material certificates, torque/tension records, photographs, punch list and close-out.
11. Submit preliminary calculations/drawings to the appointed MWS and close comments. The MWS/underwriter process—not Hermes or MetaCAD—controls any Certificate of Approval.

## MetaCAD use

Use `https://metacad.io/en/commercial/sea-fastening-survey/` for preliminary CSS Annex 13 calculations and checklist/report generation. Confirm every default and coefficient. MetaCAD currently describes DNV-ST-N001 route-aware override as a roadmap feature; do not label an Annex 13 result as DNV-ST-N001 compliance.

## Output

Return:

- scope, voyage and governing basis;
- verified inputs and missing/assumed data;
- design forces/moments and load combinations;
- sliding/tipping and restraint utilization checks;
- weld/steel/deck checks as VERIFIED, FAILED or NOT VERIFIED;
- drawing and survey punch lists;
- required MWS/class/flag/owner actions;
- a clear preliminary-status disclaimer.

Never claim that a report is `MWS approved` merely because it is formatted for MWS submission.
