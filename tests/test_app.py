"""Exercise the built JAR, its input boundaries, and the HTTP method on the wire."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import threading
import unittest
import zipfile

from tools.build import ROOT, find_jdk


class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.java = find_jdk() / "bin" / ("java.exe" if os.name == "nt" else "java")
        cls.jar = ROOT / "dist" / "hello-gte" / "hello-gte.jar"
        if not cls.jar.exists():
            raise RuntimeError("Compilare prima: python tools/build.py")

    def run_app(self, *args):
        return subprocess.run([str(self.java), "-Djava.awt.headless=true", "-jar", str(self.jar), *args],
                              capture_output=True, text=True, encoding="utf-8", timeout=12)

    def snapshot(self, **changes):
        result = {
            "schema_version": 1,
            "simulation": False,
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "signals": {
                "battery_soc": {"value": 62, "unit": "%"},
                "speed": {"value": 0, "unit": "km/h"},
            },
        }
        result.update(changes)
        return result

    def from_file(self, data, *extra):
        with tempfile.TemporaryDirectory(prefix="hello-gte-test-") as directory:
            path = Path(directory) / "input.json"
            path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
            result = self.run_app("--file", str(path), "--json", *extra)
            return result, json.loads(result.stdout)

    @contextmanager
    def server(self, content, status=200, redirect=False):
        calls = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(inner):
                calls.append((inner.command, inner.path))
                inner.send_response(status)
                if redirect:
                    inner.send_header("Location", "/must-not-follow")
                inner.send_header("Content-Type", "application/json")
                inner.end_headers()
                inner.wfile.write(content if isinstance(content, bytes) else json.dumps(content).encode())
            def do_POST(inner):
                calls.append((inner.command, inner.path))
                inner.send_error(405)
            def log_message(inner, *args):
                pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}/snapshot", calls
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_source_is_explicit_not_automatic_demo(self):
        result = self.run_app("--json")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")

    def test_hello_world_and_demo_marker(self):
        result = self.run_app("--demo")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Ciao mondo", result.stdout)
        self.assertIn("DATI SIMULATI", result.stdout)
        self.assertIn("Batteria GTE: 64 %", result.stdout)

    def test_imported_demo_cannot_lose_simulation_marker(self):
        result = self.run_app("--file", str(ROOT / "samples" / "gte-demo.json"), "--json")
        frame = json.loads(result.stdout)
        self.assertTrue(frame["simulation"])
        self.assertEqual(frame["transport"], "file")
        self.assertEqual(frame["freshness"], "demo")

    def test_values_missing_fields_and_real_zero_are_distinct(self):
        result, frame = self.from_file(self.snapshot())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(frame["simulation"])
        self.assertEqual(frame["freshness"], "recent")
        self.assertEqual(frame["signals"]["battery_soc"]["value"], 62)
        self.assertEqual(frame["signals"]["speed"]["value"], 0)
        self.assertIsNone(frame["signals"]["battery_temperature"]["value"])
        self.assertEqual(frame["signals"]["battery_temperature"]["state"], "unavailable")

    def test_units_number_types_and_ranges_are_validated(self):
        for reading in [{"value": 65, "unit": "V"}, {"value": "65", "unit": "%"},
                        {"value": 101, "unit": "%"}, {"value": -1, "unit": "%"},
                        {"value": 1e309, "unit": "%"}]:
            with self.subTest(reading=reading):
                _, frame = self.from_file(self.snapshot(signals={"battery_soc": reading}))
                self.assertIsNone(frame["signals"]["battery_soc"]["value"])
                # Non-JSON Infinity can reject the entire snapshot, which is also correct.
                self.assertIn(frame["signals"]["battery_soc"]["state"], {"invalid", "unavailable"})

    def test_timestamps_do_not_turn_download_time_into_sample_time(self):
        cases = [
            (None, "unknown_age"),
            ((datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(), "stale"),
            ((datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat(), "future_timestamp"),
        ]
        for timestamp, freshness in cases:
            with self.subTest(freshness=freshness):
                _, frame = self.from_file(self.snapshot(observed_at=timestamp))
                self.assertEqual(frame["freshness"], freshness)

    def test_bad_or_oversize_input_never_falls_back_to_demo(self):
        for payload in ["{invalid", "x" * 262145, '{"schema_version": 1}',
                        json.dumps(self.snapshot(observed_at="yesterday"))]:
            with self.subTest(size=len(payload)):
                result, frame = self.from_file(payload)
                self.assertEqual(result.returncode, 1)
                self.assertFalse(frame["simulation"])
                self.assertEqual(frame["freshness"], "error")
                self.assertTrue(all(r["value"] is None for r in frame["signals"].values()))

    def test_explicit_http_endpoint_uses_only_get(self):
        with self.server(self.snapshot()) as (url, calls):
            result = self.run_app("--url", url, "--json")
            frame = json.loads(result.stdout)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(frame["signals"]["battery_soc"]["value"], 62)
            self.assertEqual(calls, [("GET", "/snapshot")])

    def test_http_redirect_is_not_followed(self):
        with self.server({}, status=302, redirect=True) as (url, calls):
            result = self.run_app("--url", url, "--json")
            frame = json.loads(result.stdout)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(frame["error"], "HTTP 302")
            self.assertEqual(calls, [("GET", "/snapshot")])
            self.assertFalse(frame["simulation"])

    def test_http_failure_has_no_invented_vehicle_values(self):
        with self.server({}, status=503) as (url, calls):
            result = self.run_app("--url", url, "--json")
            frame = json.loads(result.stdout)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(frame["error"], "HTTP 503")
            self.assertTrue(all(r["value"] is None for r in frame["signals"].values()))

    def test_custom_json_pointer_handles_arrays_and_escaped_names(self):
        with tempfile.TemporaryDirectory(prefix="hello-gte-config-test-") as directory:
            definitions = json.loads((ROOT / "config" / "signals.json").read_text(encoding="utf-8"))
            definitions[0]["path"] = "/raw/0/a~1b/~0soc"
            config = Path(directory) / "signals.json"
            config.write_text(json.dumps(definitions), encoding="utf-8")
            _, frame = self.from_file(self.snapshot(raw=[{"a/b": {"~soc": {"value": 77, "unit": "%"}}}]),
                                      "--config", str(config))
            self.assertEqual(frame["signals"]["battery_soc"]["value"], 77)

    def test_candidate_uses_java8_bytecode(self):
        with zipfile.ZipFile(self.jar) as archive:
            bytecode = archive.read("it/mib3/hello/Main.class")
        self.assertEqual(struct.unpack(">H", bytecode[6:8])[0], 52)

    def test_distribution_runs_outside_the_repository(self):
        package = ROOT / "dist" / "hello-gte-desktop-lab.zip"
        with tempfile.TemporaryDirectory(prefix="hello-gte-distribution-test-") as directory:
            with zipfile.ZipFile(package) as archive:
                archive.extractall(directory)
            jar = Path(directory) / "hello-gte" / "hello-gte.jar"
            result = subprocess.run([str(self.java), "-jar", str(jar), "--demo", "--json"],
                                    cwd=directory, capture_output=True, encoding="utf-8", timeout=12)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)["simulation"])
            self.assertTrue((jar.parent / "lib" / "GSON-LICENSE.txt").is_file())

    def test_desktop_renderer_produces_requested_size(self):
        with tempfile.TemporaryDirectory(prefix="hello-gte-render-test-") as directory:
            target = Path(directory) / "preview.png"
            result = self.run_app("--demo", "--render", str(target), "--width", "960", "--height", "540")
            self.assertEqual(result.returncode, 0, result.stderr)
            image = target.read_bytes()
            self.assertEqual(image[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(struct.unpack(">II", image[16:24]), (960, 540))


if __name__ == "__main__":
    unittest.main()
