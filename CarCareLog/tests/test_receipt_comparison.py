"""Checks for the local-versus-hosted receipt comparison tool (no network, no model)."""

import io
import json
import re
from pathlib import Path
import sys
import unittest
from contextlib import redirect_stdout
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import compare_receipt_runtimes as cmp  # noqa: E402
import evaluate_receipts as ev  # noqa: E402
from backend import receipt_runtime  # noqa: E402


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def responses_reply(draft, status="completed", usage=(120, 60, 20)):
    return {"status": status, "output": [
        {"type": "reasoning", "summary": []},
        {"type": "message", "content": [{"type": "output_text", "text": json.dumps(draft)}]}],
        "usage": {"input_tokens": usage[0], "output_tokens": usage[1],
                  "output_tokens_details": {"reasoning_tokens": usage[2]}}}


class ReceiptComparisonTests(unittest.TestCase):
    def setUp(self):
        quiet = redirect_stdout(io.StringIO())
        quiet.__enter__()
        self.addCleanup(quiet.__exit__, None, None, None)

    @classmethod
    def setUpClass(cls):
        cls.samples = ev.load_samples()
        cls.ideal = {s["text"]: s["ideal_draft"] for s in cls.samples}

    def opener_for(self, reply_for):
        sent = []

        def opener(request, timeout):
            body = json.loads(request.data)
            sent.append((request, body, timeout))
            reply = reply_for(body)
            if isinstance(reply, Exception):
                raise reply
            return FakeResponse(json.dumps(reply).encode())
        return opener, sent

    def test_hosted_request_uses_the_same_prompt_and_a_strict_nullable_schema(self):
        text = self.samples[0]["text"]
        opener, sent = self.opener_for(lambda body: responses_reply(self.ideal[text]))
        draft = cmp.hosted_drafter("test-key", opener)(text)
        self.assertEqual(draft, self.ideal[text])
        request, body, timeout = sent[0]
        self.assertEqual(request.full_url, "https://api.openai.com/v1/responses")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
        self.assertEqual((body["model"], body["store"], body["reasoning"]), ("gpt-6.1-sol", False, {"effort": "low"}))
        self.assertEqual(body["input"], receipt_runtime.build_request(text, "x")["prompt"])
        fmt = body["text"]["format"]
        self.assertTrue(fmt["strict"])
        self.assertEqual(set(fmt["schema"]["required"]), set(receipt_runtime.DRAFT_FIELDS))
        self.assertFalse(fmt["schema"]["additionalProperties"])
        self.assertEqual(fmt["schema"]["properties"]["service_item"]["type"], ["string", "null"])
        self.assertNotIn("temperature", body)
        self.assertGreaterEqual(body["max_output_tokens"], 1024)
        self.assertEqual(timeout, cmp.DEADLINE)

    def test_incomplete_malformed_and_http_errors_are_runtime_failures(self):
        text = self.samples[0]["text"]
        cases = [responses_reply(self.ideal[text], status="incomplete"),
                 {"status": "completed", "output": [{"type": "message", "content": [
                     {"type": "output_text", "text": '{"service_date": "2026-11-16"}'}]}]},
                 HTTPError("u", 401, "Unauthorized", {}, None)]
        for reply in cases:
            with self.subTest(reply=type(reply).__name__):
                opener, _ = self.opener_for(lambda body, reply=reply: reply)
                with self.assertRaises(receipt_runtime.ReceiptRuntimeUnavailable):
                    cmp.hosted_drafter("k", opener)(text)

    def test_measure_records_usage_and_cost_and_stops_on_a_bad_key(self):
        opener, _ = self.opener_for(lambda body: responses_reply(
            self.ideal[json.loads(body["input"].rsplit("Receipt text (JSON string): ", 1)[1])]))
        drafter = cmp.hosted_drafter("k", opener)
        run = cmp.measure(self.samples, drafter)
        self.assertEqual((run["completed"], run["field_accuracy"], run["wrong_values_unflagged"]),
                         (len(self.samples), 1.0, 0))
        cost = cmp.hosted_cost(drafter.usage)
        self.assertEqual(cost["input_tokens"], 120 * len(self.samples))
        self.assertAlmostEqual(cost["estimated_usd"], len(self.samples) * (120 * 2 + 60 * 10) / 1e6, places=4)

        opener, _ = self.opener_for(lambda body: HTTPError("u", 401, "Unauthorized", {}, None))
        with self.assertRaises(SystemExit):
            cmp.measure(self.samples, cmp.hosted_drafter("bad", opener))

    def test_e5_value_runs_from_two_seconds_to_the_timeout(self):
        self.assertEqual(cmp.e5_value(1.5), 1.0)
        self.assertEqual(cmp.e5_value(2), 1.0)
        self.assertAlmostEqual(cmp.e5_value(15.978), (60 - 15.978) / 58)
        self.assertEqual(cmp.e5_value(60), 0.0)
        self.assertEqual(cmp.e5_value(75), 0.0)
        self.assertIsNone(cmp.e5_value(None))

    def test_sample_digest_ignores_line_endings(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            unix, windows = Path(folder) / "a.jsonl", Path(folder) / "b.jsonl"
            unix.write_bytes(b'{"id": 1}\n{"id": 2}\n')
            windows.write_bytes(b'{"id": 1}\r\n{"id": 2}\r\n')
            self.assertEqual(cmp.samples_digest(unix), cmp.samples_digest(windows))

    def test_report_puts_both_runs_side_by_side(self):
        local = cmp.measure(self.samples, lambda text: dict(self.ideal[text]))
        local.update(ollama_version="0.40.16", started_utc="2026-11-22T00:00:00+00:00", samples_sha256="a" * 64)
        opener, _ = self.opener_for(lambda body: responses_reply(
            self.ideal[json.loads(body["input"].rsplit("Receipt text (JSON string): ", 1)[1])]))
        drafter = cmp.hosted_drafter("k", opener)
        hosted = cmp.measure(self.samples, drafter)
        hosted.update(model="gpt-6.1-sol", endpoint=cmp.HOSTED_ENDPOINT, reasoning_effort="low",
                      started_utc="2026-11-22T00:10:00+00:00", samples_sha256="a" * 64,
                      cost=cmp.hosted_cost(drafter.usage))
        text = cmp.render_report(local, hosted)
        self.assertIn("qwen2.5:3b-instruct-q4_K_M", text)
        self.assertIn("gpt-6.1-sol", text)
        self.assertIn("Wrong values shown as found", text)
        self.assertEqual(len(re.findall(r"^\| R\d\d \|", text, re.M)), len(self.samples))


if __name__ == "__main__":
    unittest.main()
