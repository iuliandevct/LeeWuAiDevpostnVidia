"""
tests/test_transformer_extraction.py
Repeatable Verification Test: NVIDIA Nemotron Model via Nebius Token Factory
for Synthetic Maritime Cargo Survey Document Understanding.

Uses a deterministic local OpenAI-compatible mock server by default so automated
security & regression suites do not consume paid Nebius API credits unnecessarily.
Set RUN_LIVE_NEBIUS_TESTS=1 to run against the live Nebius Token Factory endpoint.
"""

import http.server
import json
import os
import socket
import sys
import threading
import time
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.nebius_provider import NebiusTokenFactoryAdapter, NebiusResponse


class _TransformerMockHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > 0:
            _ = self.rfile.read(length)
        extracted_json = json.dumps({
            "cargo_item_reference": "TR-001 (Serial No: TR-8849-RO, 124.5 MT)",
            "visible_condition": "Secured in Hold No. 2 with 8x Grade 80 16mm lashing chains; N2 pressure 0.32 bar; silica gel cobalt blue.",
            "observed_damage": [
                "Superficial paint scuffing (15cm x 5cm) on lower starboard corner base skid",
                "Broken seal on protective wooden crate #3 for HV porcelain bushings"
            ],
            "missing_information": [
                "Impact recorder calibration certificate not sighted in vessel documents",
                "Oil analysis laboratory certificate from loading port (Antwerp) not attached to Bill of Lading copy"
            ],
            "recommended_human_verification_steps": [
                "Physically inspect porcelain bushing inside crate #3 where seal was broken",
                "Request impact recorder calibration certificate and Antwerp oil analysis certificate before issuing final warranty sign-off"
            ]
        })
        payload = {
            "id": "chatcmpl-mock-tr-001",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": extracted_json},
                "finish_reason": "stop"
            }],
            "usage": {"prompt_tokens": 390, "completion_tokens": 180, "total_tokens": 570}
        }
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class TestTransformerInspectionExtraction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mock_server = None
        if os.environ.get("RUN_LIVE_NEBIUS_TESTS") == "1":
            cls.adapter = NebiusTokenFactoryAdapter()
            cfg = cls.adapter.validate_configuration()
            if cfg["status"] != "VALID":
                raise unittest.SkipTest(f"Nebius configuration is not valid: {cfg['errors']}")
        else:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", 0))
                port = s.getsockname()[1]
            cls.mock_server = http.server.HTTPServer(("127.0.0.1", port), _TransformerMockHandler)
            threading.Thread(target=cls.mock_server.serve_forever, daemon=True).start()
            cls.adapter = NebiusTokenFactoryAdapter(
                api_key="v1.MOCK_TRANSFORMER_KEY_1234567890",
                base_url=f"http://127.0.0.1:{port}/v1"
            )

    @classmethod
    def tearDownClass(cls):
        if cls.mock_server is not None:
            cls.mock_server.shutdown()
            cls.mock_server.server_close()

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
            "Extract structured survey findings into pure, valid JSON."
        )

        messages = [
            {"role": "system", "content": "You are a deterministic maritime inspection JSON extractor. Always output raw valid JSON only."},
            {"role": "user", "content": prompt}
        ]

        t0 = time.time()
        resp = self.adapter.complete(messages, max_tokens=1400, temperature=0.1)
        latency = time.time() - t0

        self.assertIsInstance(resp, NebiusResponse)
        self.assertEqual(resp.finish_reason, "stop")
        self.assertGreater(resp.total_tokens, 0)
        self.assertLess(latency, 45.0)

        raw = resp.content.strip()
        if raw.startswith("```json"):
            raw = raw[7:]
        if raw.startswith("```"):
            raw = raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

        data = json.loads(raw)

        self.assertIn("cargo_item_reference", data)
        self.assertIn("visible_condition", data)
        self.assertIn("observed_damage", data)
        self.assertIn("missing_information", data)
        self.assertIn("recommended_human_verification_steps", data)

        self.assertIsInstance(data["observed_damage"], list)
        self.assertIsInstance(data["missing_information"], list)
        self.assertIsInstance(data["recommended_human_verification_steps"], list)

        self.assertIn("TR-001", data["cargo_item_reference"])
        self.assertTrue(any("scuffing" in d.lower() or "crate" in d.lower() for d in data["observed_damage"]))
        self.assertTrue(any("calibration" in m.lower() or "oil" in m.lower() for m in data["missing_information"]))
        self.assertTrue(len(data["recommended_human_verification_steps"]) >= 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
