"""Recording correctness: unrecognized data, failures, byte recovery and bounded storage."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import test_app
from tools.build import ROOT, find_jdk
from tools.read_log import response_bytes, summarize


class DiagnosticLoggingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.java = find_jdk() / "bin" / ("java.exe" if os.name == "nt" else "java")
        cls.jar = ROOT / "dist" / "hello-gte" / "hello-gte.jar"

    def run_app(self, *args, data=None):
        return subprocess.run([str(self.java), "-Djava.awt.headless=true", "-jar", str(self.jar), *args],
                              input=data, capture_output=True, timeout=20)

    def records(self, directory):
        return [json.loads(line) for file in sorted(Path(directory).glob("*.jsonl"))
                for line in file.read_text(encoding="utf-8").splitlines()]

    def test_complete_unknown_payload_is_retained_and_fields_are_discoverable(self):
        with tempfile.TemporaryDirectory(prefix="hello-gte-log-") as temporary:
            directory = Path(temporary)
            payload = test_app.AppTests().snapshot(unmapped={"pack_voltage": 357.2, "state": "ready"})
            with test_app.AppTests().server(payload) as (url, calls):
                result = self.run_app("--url", url, "--json", "--log-dir", str(directory))
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            self.assertFalse(json.loads(result.stdout)["simulation"])
            records = self.records(directory)
            self.assertEqual([r["event"] for r in records], ["session_start", "source_read", "session_end"])
            reading = records[1]
            self.assertEqual(json.loads(response_bytes(reading["response"])), payload)
            self.assertEqual(reading["http_status"], 200)
            self.assertIsNotNone(reading["http_response_headers"])
            self.assertEqual(reading["stage"], "done")
            self.assertGreaterEqual(reading["elapsed_ms"], 0)
            self.assertEqual(calls, [("GET", "/snapshot")])
            summary = summarize(directory, fields=True)
            self.assertIn("/unmapped/pack_voltage", summary["observed_json_paths"])
            self.assertEqual(summary["unclosed_sessions"], 0)

    def test_non_snapshot_response_is_kept_even_when_interpretation_fails(self):
        with tempfile.TemporaryDirectory(prefix="hello-gte-log-schema-") as temporary:
            body = b'{"unmapped_service":{"batteryPack":{"soc":62}}}'
            with test_app.AppTests().server(body) as (url, _):
                result = self.run_app("--url", url, "--json", "--log-dir", temporary)
            self.assertEqual(result.returncode, 1)
            reading = self.records(temporary)[1]
            self.assertEqual(reading["stage"], "parse")
            self.assertEqual(response_bytes(reading["response"]), body)
            self.assertTrue(reading["response"]["complete"])
            self.assertEqual(reading["interpreted"]["freshness"], "error")

    def test_http_error_body_and_status_are_recorded(self):
        with tempfile.TemporaryDirectory(prefix="hello-gte-log-http-") as temporary:
            body = b'{"service":"carif","message":"not ready"}'
            with test_app.AppTests().server(body, status=503) as (url, _):
                result = self.run_app("--url", url, "--json", "--log-dir", temporary)
            self.assertEqual(result.returncode, 1)
            reading = self.records(temporary)[1]
            self.assertEqual(reading["http_status"], 503)
            self.assertEqual(response_bytes(reading["response"]), body)
            self.assertIsNotNone(reading["error_type"])
            self.assertEqual(reading["interpreted"]["error"], "HTTP 503")

    def test_non_utf8_and_malformed_bytes_can_be_recovered_exactly(self):
        with tempfile.TemporaryDirectory(prefix="hello-gte-log-binary-") as temporary:
            directory = Path(temporary)
            body = b'\xff\x00invalid\r\n{json'
            original = directory / "source.bin"
            original.write_bytes(body)
            logs = directory / "logs"
            result = self.run_app("--file", str(original), "--json", "--log-dir", str(logs))
            self.assertEqual(result.returncode, 1)
            response = self.records(logs)[1]["response"]
            self.assertEqual(response["encoding"], "base64")
            self.assertEqual(response_bytes(response), body)
            destination = directory / "recovered"
            summarize(logs, extract=destination)
            self.assertEqual(next(destination.glob("*/response-*.bin")).read_bytes(), body)

    def test_oversize_response_is_preserved_to_the_limit_and_marked_partial(self):
        with tempfile.TemporaryDirectory(prefix="hello-gte-log-size-") as temporary:
            directory = Path(temporary)
            original = directory / "large.bin"
            original.write_bytes(b"z" * 300000)
            logs = directory / "logs"
            result = self.run_app("--file", str(original), "--json", "--log-dir", str(logs))
            self.assertEqual(result.returncode, 1)
            response = self.records(logs)[1]["response"]
            self.assertEqual(response["bytes_captured"], 262144)
            self.assertTrue(response["truncated"])
            self.assertFalse(response["complete"])
            self.assertEqual(response_bytes(response), b"z" * 262144)

    def test_stream_is_lossless_across_chunk_boundaries_and_rotated_files(self):
        with tempfile.TemporaryDirectory(prefix="hello-gte-log-stream-") as temporary:
            directory = Path(temporary)
            logs = directory / "logs"
            # Mix binary bytes and multibyte text, enough to cross the 4 MiB rotation boundary.
            body = (bytes(range(256)) * 20480) + "fine stream è €\r\n".encode()
            result = self.run_app("--capture-stdin", "--log-dir", str(logs), data=body)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            files = sorted(logs.glob("*.jsonl"))
            self.assertGreater(len(files), 1)
            self.assertTrue(all(p.stat().st_size <= 4 * 1024 * 1024 for p in files))
            records = self.records(logs)
            self.assertEqual([r["sequence"] for r in records], list(range(1, len(records) + 1)))
            summary = summarize(logs, extract=directory / "recovered")
            self.assertEqual(summary["bytes_captured"], len(body))
            self.assertEqual(summary["streams_without_eof"], 0)
            self.assertEqual(summary["missing_sequences"], 0)
            self.assertEqual(next((directory / "recovered").glob("*/stream.bin")).read_bytes(), body)

    def test_session_limit_stops_acquisition_with_a_terminal_event(self):
        with tempfile.TemporaryDirectory(prefix="hello-gte-log-limit-") as temporary:
            result = self.run_app("--capture-stdin", "--log-dir", temporary,
                                  "--log-max-mib", "1", data=b"x" * (2 * 1024 * 1024))
            self.assertEqual(result.returncode, 2)
            records = self.records(temporary)
            self.assertEqual(records[-1]["event"], "session_limit_reached")
            self.assertTrue(records[-1]["capture_stopped"])
            self.assertLessEqual(sum(f.stat().st_size for f in Path(temporary).glob("*.jsonl")), 1024 * 1024)
            summary = summarize(Path(temporary))
            self.assertEqual(summary["streams_without_eof"], 1)

    def test_session_names_are_unique_and_existing_logs_are_not_overwritten(self):
        with tempfile.TemporaryDirectory(prefix="hello-gte-log-restart-") as temporary:
            for _ in range(2):
                result = self.run_app("--demo", "--json", "--log-dir", temporary)
                self.assertEqual(result.returncode, 0)
            self.assertEqual(len(list(Path(temporary).glob("*.jsonl"))), 2)
            self.assertEqual(summarize(Path(temporary))["sessions"], 2)

    def test_bounded_polling_records_the_requested_number_of_reads(self):
        with tempfile.TemporaryDirectory(prefix="hello-gte-log-count-") as temporary:
            result = self.run_app("--demo", "--watch", "--count", "3", "--interval-ms", "100",
                                  "--log-dir", temporary)
            self.assertEqual(result.returncode, 0)
            summary = summarize(Path(temporary))
            self.assertEqual(summary["events"]["source_read"], 3)
            self.assertEqual(summary["events"]["session_end"], 1)

    def test_log_creation_failure_is_reported_before_reading(self):
        with tempfile.TemporaryDirectory(prefix="hello-gte-log-failure-") as temporary:
            invalid = Path(temporary) / "not-a-directory"
            invalid.write_text("keep this file", encoding="utf-8")
            result = self.run_app("--demo", "--json", "--log-dir", str(invalid))
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, b"")
            self.assertEqual(invalid.read_text(), "keep this file")

    def test_log_reader_reports_corruption_instead_of_exporting_it(self):
        with tempfile.TemporaryDirectory(prefix="hello-gte-log-corrupt-") as temporary:
            result = self.run_app("--demo", "--json", "--log-dir", temporary)
            self.assertEqual(result.returncode, 0)
            file = next(Path(temporary).glob("*.jsonl"))
            records = self.records(temporary)
            records[1]["response"]["sha256"] = "0" * 64
            file.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
            result = subprocess.run([sys.executable, str(ROOT / "tools" / "read_log.py"), str(file)],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 2)
            self.assertIn("SHA-256", result.stderr)


if __name__ == "__main__":
    unittest.main()
