"""Lab checks for the standalone shell probe, never a vehicle compatibility test."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "probe" / "mib3-hello.sh"
GIT_SH = Path(r"C:\Program Files\Git\usr\bin\sh.exe")
SHELL = str(GIT_SH) if os.name == "nt" and GIT_SH.is_file() else shutil.which("sh")


@unittest.skipUnless(SHELL, "Serve una shell POSIX per i test di laboratorio")
class ProbeTest(unittest.TestCase):
    def run_probe(self, *args):
        return subprocess.run(
            [SHELL, str(SCRIPT), *map(str, args)], capture_output=True, timeout=15,
            encoding="utf-8", errors="replace",
        )

    def shell_path(self, path):
        # Git sh expects its own absolute path, rather than a Win32 drive prefix.
        resolved = path.resolve().as_posix()
        if os.name == "nt":
            return "/" + resolved[0].lower() + resolved[2:]
        return resolved

    def test_lab_report_with_spaces_and_no_overwrite(self):
        with tempfile.TemporaryDirectory(prefix="mib probe ") as tmp:
            output = Path(tmp) / "USB with spaces"
            output.mkdir()
            result = self.run_probe("--lab", "--output-dir", self.shell_path(output))
            self.assertEqual(result.returncode, 0, result.stderr)
            report = output / "hello.txt"
            content = report.read_bytes()
            self.assertTrue(content.startswith(b"Ciao mondo\n"))
            self.assertIn(b"context=LAB_NOT_VEHICLE_VERIFICATION\n", content)
            self.assertIn(b"vehicle_signals=not_collected\n", content)
            self.assertTrue(content.endswith(b"report_complete=yes\n"))
            self.assertLess(len(content), 16384)
            self.assertEqual([p.name for p in output.iterdir()], ["hello.txt"])
            second = self.run_probe("--lab", "--output-dir", self.shell_path(output))
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual(report.read_bytes(), content)

    def test_invalid_arguments_do_not_create_reports(self):
        with tempfile.TemporaryDirectory(prefix="mib-probe-") as tmp:
            parent = Path(tmp)
            for args in [[], ["--lab"], ["--lab", "--output-dir"],
                         ["--lab", "--output-dir", "relative"],
                         ["--lab", "--output-dir", self.shell_path(parent / "missing")],
                         ["--unknown"]]:
                with self.subTest(args=args):
                    self.assertNotEqual(self.run_probe(*args).returncode, 0)
            self.assertEqual(list(parent.iterdir()), [])

    def test_pc_not_mistaken_for_mib3(self):
        if Path("/lge/app_ro").is_dir() and Path("/vw").is_dir():
            self.skipTest("Questo controllo richiede un host senza struttura MOI3")
        with tempfile.TemporaryDirectory(prefix="mib-probe-") as tmp:
            output = Path(tmp)
            result = self.run_probe("--output-dir", self.shell_path(output))
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(list(output.iterdir()), [])

    def test_shell_syntax_and_help(self):
        result = subprocess.run([SHELL, "-n", str(SCRIPT)], capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.run_probe("--help").returncode, 0)


class ProbePackageTest(unittest.TestCase):
    def test_package_has_lf_script_and_no_fake_result(self):
        from tools.package_probe import package

        archive_path = package()
        with zipfile.ZipFile(archive_path) as archive:
            names = archive.namelist()
            self.assertEqual(len(names), 5)
            self.assertFalse(any(name.endswith("hello.txt") for name in names))
            content = archive.read("mib3-hello-probe/mib3-hello.sh")
            self.assertTrue(content.startswith(b"#!/bin/sh\n"))
            self.assertNotIn(b"\r", content)
            for name in names:
                if not name.endswith(".md"):
                    continue
                for link in re.findall(r"\]\(([^)]+)\)", archive.read(name).decode("utf-8")):
                    if "://" not in link:
                        self.assertIn(str(Path(name).parent / link).replace("\\", "/"), names)
            for line in archive.read("mib3-hello-probe/SHA256SUMS.txt").decode("ascii").splitlines():
                digest, name = line.split("  ", 1)
                self.assertEqual(hashlib.sha256(archive.read("mib3-hello-probe/" + name)).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()
