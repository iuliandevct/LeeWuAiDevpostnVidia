# LEEWU AI — MARITIME DEMO VALIDATION & PROVENANCE REPORT

**Demo Identifier:** `LW-DEMO-001`  
**Cargo Unit:** Heavy Industrial 110kV Power Transformer (`TR-001`, 124.5 MT)  
**Vessel:** `MV DEMO CARRIER` (IMO: 9482184)  
**Location:** Port of Constanta (Berth 120 / Dana 52)  
**Evaluation Mode:** Complete 10-Step Workflow Validation  

---

## 1. END-TO-END WORKFLOW EXECUTION

| Step | Operation | Endpoint | Status | Output Evidence |
|---|---|---|---|---|
| **1** | Initialize Demo Survey | Database bootstrap | **PASS** | Survey record `LW-DEMO-001` loaded in draft state. |
| **2** | Identify Vessel & Cargo | `GET /api/surveys/LW-DEMO-001` | **PASS** | Verified vessel IMO, cargo weight (124.5 MT), and berth. |
| **3** | Record Scope of Inspection | Survey console state | **PASS** | Nitrogen seal, shock recorder, and lashing scope configured. |
| **4** | Upload Photographic Evidence | `POST /api/surveys/.../upload` | **PASS** | Evidence file `evidence_LW-DEMO-001_TR001_*.jpg` saved. |
| **5** | Verify SHA-256 Checksum | `hashlib.sha256()` | **PASS** | Checksum verified: `cbfd090e07a67ab20818c3e113fa6276ad37f3ba9da9479528fdf4dc2e0464b7`. |
| **6** | Execute AI Assessment | `POST /api/surveys/.../ai-inspect` | **PASS** | NVIDIA Nemotron 30B generated 4-part structured engineering notes. |
| **7** | Review AI Findings | Survey console review UI | **PASS** | N2 positive pressure (0.24 bar), shock logs (<0.8G) reviewed. |
| **8** | Human Surveyor Sign-off | `POST /api/surveys/.../approve` | **PASS** | Status updated to `APPROVED`; cryptographic seal generated. |
| **9** | Render Statutory Export | `GET /api/surveys/.../export` | **PASS** | HTML report rendered with XSS escaping and demo disclosures. |
| **10** | Document Integrity Audit | Document verification gate | **PASS** | Seal hash matches record payload: SHA-256 data integrity confirmed. |

---

## 2. EVIDENCE PROVENANCE & CLAIMS INTEGRITY

The platform strictly classifies all evidence according to source provenance:

| Category | Classification | Description | Disclosure Rule |
|---|---|---|---|
| **Photographic Proof** | `OBSERVED & MEASURED` | Physical camera capture and EXIF metadata. | Accompanied by SHA-256 file checksum and resolution. |
| **Sensor Telemetry** | `DOCUMENTED` | Nitrogen gauge readings (0.24 bar) and impact recorder logs (<0.8G). | Recorded as surveyor-provided sensor readings. |
| **AI Evaluation** | `AI_INFERRED` | NVIDIA Nemotron 30B technical synthesis and CSS Code evaluation. | Visibly marked with AI_INFERRED tag; distinguished from physical observations. |
| **Surveyor Approval** | `HUMAN_APPROVED` | Manual sign-off by attending surveyor. | Requires authenticated reviewer name, license, and timestamp. |
| **Cryptographic Seal** | `INTEGRITY_CHECKSUM` | SHA-256 record hash over survey metadata. | **Explicit Disclosure:** Cryptographic file integrity checksum; not an eIDAS statutory electronic signature. |
| **Dataset Nature** | `SYNTHETIC_DEMO` | Demo survey record `LW-DEMO-001`. | **Explicit Disclosure:** Displayed on all report exports: *Demonstration workflow — synthetic dataset for hackathon evaluation only.* |
