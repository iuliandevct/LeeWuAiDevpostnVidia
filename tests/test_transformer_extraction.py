"""
tests/test_transformer_extraction.py
Repeatable Verification Test: NVIDIA Nemotron Model via Nebius Token Factory
for Synthetic Maritime Cargo Survey Document Understanding.
"""

import os
import sys
import json
import time
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.nebius_provider import NebiusTokenFactoryAdapter, NebiusResponse


class TestTransformerInspectionExtraction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adapter = NebiusTokenFactoryAdapter()
        # Verify valid configuration before starting
        cfg = cls.adapter.validate_configuration()
        if cfg["status"] != "VALID":
            raise unittest.SkipTest(f"Nebius configuration is not valid: {cfg['errors']}")

    def test_synthetic_transformer_extraction(self):
        """Sends a synthetic industrial transformer inspection note and verifies structured JSON output."""
        synthetic_note = (
            "PORT OF CONSTANTA - BERTH 120\n"
            "PRE-DISCHARGE SURVEY NOTE\n"
            "Vessel: MV DEMO CARRIER | Voyage: 2026/04\n"
            "Cargo Item: Industrial Power Transformer Unit TR-001 (Serial No: TR-8849-RO, 124.5 MT)\n"
            "Stowage: Hold No. 2, Tanktop, center line.\n\n"
            "Visual Findings:\n"
            "- Transformer main tank body is secured with 8x Grade 80 lashing chains (16mm) with turnbuckles.\n"
            "- Shock recorder mounted on upper transformer frame shows readings: Longitudinal 0.28G, Transverse 0.34G, Vertical 0.19G.\n"
            "- Nitrogen blanket positive pressure gauge currently reads 0.32 bar. Bleed valve seal #4928 intact.\n"
            "- Observed slight superficial paint scuffing (approx 15cm x 5cm) on lower starboard corner base skid, no deformation to load-bearing flanges.\n"
            "- Porcelain HV bushings (4x) inspected under protective wooden crates: crates show no external crushing, but seal on crate #3 was broken during ocean passage.\n"
            "- Desiccant breather silica gel crystals show uniform dark cobalt blue hue.\n\n"
            "Note: Impact recorder calibration certificate not sighted in vessel documents. Oil analysis laboratory certificate from loading port (Antwerp) not attached to Bill of Lading copy."
        )

        prompt = (
            "You are LeeWu AI, Senior Marine Warranty Surveyor (MWS) intelligence system.\n"
            f"Analyze the following synthetic inspection note for an industrial transformer:\n\n"
            f'"""{synthetic_note}"""\n\n'
            "Extract structured survey findings into pure, valid JSON with exact keys:\n"
            "{\n"
            '  "cargo_item_reference": "string",\n'
            '  "visible_condition": "string",\n'
            '  "observed_damage": ["string"],\n'
            '  "missing_information": ["string"],\n'
            '  "recommended_human_verification_steps": ["string"]\n'
            "}\n\n"
            "Rules:\n"
            "- observed_damage must be a JSON array of strings.\n"
            "- missing_information must be a JSON array of strings.\n"
            "- recommended_human_verification_steps must be a JSON array of strings.\n"
            "- Output ONLY the raw JSON object, without backticks, markdown fences, or conversational text."
        )

        messages = [
            {"role": "system", "content": "You are a deterministic maritime inspection JSON extractor. Always output raw valid JSON only."},
            {"role": "user", "content": prompt}
        ]

        t0 = time.time()
        resp = self.adapter.complete(messages, max_tokens=1400, temperature=0.1)
        latency = time.time() - t0

        # Assert response object properties
        self.assertIsInstance(resp, NebiusResponse)
        self.assertEqual(resp.finish_reason, "stop")
        self.assertGreater(resp.total_tokens, 0)
        self.assertLess(latency, 45.0)

        # Parse and validate JSON content
        raw = resp.content.strip()
        if raw.startswith("```json"):
            raw = raw[7:]
        if raw.startswith("```"):
            raw = raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

        data = json.loads(raw)

        # Verify required keys and types
        self.assertIn("cargo_item_reference", data)
        self.assertIn("visible_condition", data)
        self.assertIn("observed_damage", data)
        self.assertIn("missing_information", data)
        self.assertIn("recommended_human_verification_steps", data)

        self.assertIsInstance(data["observed_damage"], list)
        self.assertIsInstance(data["missing_information"], list)
        self.assertIsInstance(data["recommended_human_verification_steps"], list)

        # Semantic content verification
        self.assertIn("TR-001", data["cargo_item_reference"])
        self.assertTrue(any("scuffing" in d.lower() or "crate" in d.lower() for d in data["observed_damage"]))
        self.assertTrue(any("calibration" in m.lower() or "oil" in m.lower() for m in data["missing_information"]))
        self.assertTrue(len(data["recommended_human_verification_steps"]) >= 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
