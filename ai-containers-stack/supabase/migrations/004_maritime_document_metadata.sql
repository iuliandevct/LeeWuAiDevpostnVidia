update public.knowledge_documents
set metadata = metadata || jsonb_build_object(
  'document_type', 'commercial_offer',
  'topics', jsonb_build_array('stowage plan', 'centre of gravity', 'stability', 'deck strength', 'lashing plan', 'pricing'),
  'summary', 'Romanian commercial offer structured in three engineering stages: loading plan and actual CoG, stability/deck-strength calculations, and an IMO CSS Code Annex 13 lashing plan.'
)
where filename = 'Oferta Calcule de Stabilitate Project Cargo.docx';

update public.knowledge_documents
set metadata = metadata || jsonb_build_object(
  'document_type', 'research_paper',
  'topics', jsonb_build_array('IMO CSS Code', 'DNV 2024', 'lashing optimization', 'accelerations', 'securing forces'),
  'summary', '2025 research paper comparing international cargo-securing standards and optimizing lashing-line geometry. It identifies seven common layouts and highlights alpha 30 degrees / beta 10 degrees for minimum deck-space occupation.'
)
where filename like 'Optimizing Cargo Securing Layouts%';

update public.knowledge_documents
set metadata = metadata || jsonb_build_object(
  'document_type', 'vessel_particulars',
  'topics', jsonb_build_array('Caspian Harmony', 'MPP vessel', 'cranes', 'holds', 'tweendeck', 'heavy cargo'),
  'summary', 'Particulars for M/V Caspian Harmony (IMO 9766645), including dimensions, deadweight, hold and hatch geometry, deck arrangements, and crane capacities up to 500 t tandem lift.'
)
where filename = 'DOC-20260629-WA0035.pdf';

update public.knowledge_documents
set metadata = metadata || jsonb_build_object(
  'document_type', 'lashing_plan',
  'topics', jsonb_build_array('NR81.5 wind blades', 'lashing chains', 'D-rings', 'twistlocks', 'load spreading', 'welded stoppers'),
  'summary', 'Engineering lashing drawings for NR81.5 wind-turbine blades, including three- and four-blade stacks, MSL 10 t chains, twistlocks, HEB300 load-spreading beams, stoppers, rubber/dunnage and welding details.'
)
where filename like '30 BLADES NR81.5%';

update public.knowledge_documents
set metadata = metadata || jsonb_build_object(
  'document_type', 'stowage_plan',
  'topics', jsonb_build_array('Caspian Harmony', 'E-160 rotor blades', 'deck loading', 'hold loading', 'voyage 6806'),
  'summary', 'Stowage plan revision 00 for fifteen E-160 rotor-blade frames aboard Caspian Harmony, showing ship geometry, cargo positions and deck/tweendeck/tanktop loading limits.'
)
where filename like '6806 - Caspian Harmony%';

update public.knowledge_documents
set metadata = metadata || jsonb_build_object(
  'document_type', 'lashing_and_securing_plan',
  'topics', jsonb_build_array('Caspian Harmony', 'E-160 blades', 'chains', 'D-rings', 'bridge fittings', 'friction rubber', 'stoppers'),
  'summary', 'Detailed securing proposal for E-160 blade frames on Caspian Harmony, specifying chain/binder/D-ring quantities, tier-by-tier lashing patterns, bridge fittings, caulking, rubber friction layers, stoppers and welding requirements.'
)
where filename like 'Caspian Harmony , Lashing%';

update public.knowledge_documents
set metadata = metadata || jsonb_build_object(
  'document_type', 'cargo_manifest',
  'topics', jsonb_build_array('Duqm', 'Jebel Ali', 'turbines', 'generators', 'transformers', 'dimensions', 'weights', 'stackability'),
  'summary', 'Spreadsheet cargo list for power-generation equipment, including gross weight, dimensions, volume, freight tons, footprint and stackability. Major pieces include 334.7 t turbines, 308 t generators and 251 t transformers.'
)
where filename = '2. Duqm-Jebel Ali turbines.xlsx';

update public.knowledge_documents
set metadata = metadata || jsonb_build_object(
  'document_type', 'workflow_guidance',
  'topics', jsonb_build_array('MPP vessels', 'project cargo', 'IMO CSS', 'SOLAS', 'deck strength', 'MWS', 'insurance'),
  'summary', 'Romanian overview of regulatory and insurer requirements for oversized cargo on MPP vessels, from loading/CoG and stability through lashing calculations and Marine Warranty Survey approval.'
)
where filename like 'Incarcarea utilajelor agabaritice%';

update public.knowledge_documents
set metadata = metadata || jsonb_build_object(
  'document_type', 'technical_reference_book',
  'topics', jsonb_build_array('cargo stowage', 'cargo securing', 'IMO CSS', 'rule of thumb', 'advanced calculation', 'dunnage', 'friction', 'lashings'),
  'summary', 'North of England P&I reference on cargo stowage and securing, covering forces and accelerations, dunnage, friction, securing equipment, practical rules and advanced calculation methods for non-standard cargo.'
)
where filename = '00-Cargo-Stowage-and-Securing-North-of-England.pdf';
