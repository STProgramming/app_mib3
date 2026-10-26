"""Build the Java-8 candidate and a desktop/lab ZIP. No vehicle connection."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
GSON_VERSION = "2.14.0"
GSON_SHA256 = "2cbd119bf1961c28788310963dc80ba65f58cdeec1dd139c8bdb1240faa2c36f"
GSON_URL = f"https://repo.maven.apache.org/maven2/com/google/code/gson/gson/{GSON_VERSION}/gson-{GSON_VERSION}.jar"


def find_jdk(explicit: str | None = None) -> Path:
    candidates = [explicit, os.environ.get("JAVA_HOME")]
    if shutil.which("javac"):
        candidates.append(str(Path(shutil.which("javac")).resolve().parent.parent))
    candidates.append(r"C:\Program Files\Android\Android Studio\jbr")
    suffix = ".exe" if os.name == "nt" else ""
    for candidate in candidates:
        if candidate and (Path(candidate) / "bin" / ("javac" + suffix)).is_file():
            return Path(candidate)
    raise SystemExit("Serve un JDK 9+ per compilare: impostare JAVA_HOME o passare --jdk PERCORSO.")


def download(url: str, limit: int = 4 * 1024 * 1024) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "HelloGTE-build/0.1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        content = response.read(limit + 1)
    if len(content) > limit:
        raise SystemExit("Download più grande del limite previsto")
    return content


def build(jdk: Path) -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    deps = ROOT / ".deps"
    deps.mkdir(exist_ok=True)
    gson = deps / f"gson-{GSON_VERSION}.jar"
    if not gson.exists():
        content = download(GSON_URL)
        if hashlib.sha256(content).hexdigest() != GSON_SHA256:
            raise SystemExit("SHA-256 Gson non valido")
        gson.write_bytes(content)
    if hashlib.sha256(gson.read_bytes()).hexdigest() != GSON_SHA256:
        raise SystemExit("La copia locale di Gson non corrisponde al digest fissato")

    build_root = ROOT / "build"
    build_root.mkdir(exist_ok=True)
    output = ROOT / "dist" / "hello-gte"
    (output / "lib").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="compile-", dir=build_root) as temporary:
        work = Path(temporary).resolve()
        # The temporary directory is the only recursive cleanup target.
        assert work.is_relative_to(build_root.resolve())
        classes = work / "classes"
        classes.mkdir()
        sources = sorted(str(p) for p in (ROOT / "src").rglob("*.java"))
        subprocess.run([
            str(jdk / "bin" / ("javac" + suffix)), "--release", "8", "-encoding", "UTF-8",
            # Java 8 is deliberate; Gson's optional compile-only annotations are not needed at runtime.
            "-Xlint:all,-options,-classfile", "-cp", str(gson), "-d", str(classes), *sources,
        ], check=True)
        shutil.copy2(ROOT / "config" / "signals.json", classes / "signals.json")
        shutil.copy2(ROOT / "samples" / "gte-demo.json", classes / "gte-demo.json")
        manifest = work / "MANIFEST.MF"
        manifest.write_text(
            "Manifest-Version: 1.0\nMain-Class: it.mib3.hello.Main\n"
            f"Class-Path: lib/gson-{GSON_VERSION}.jar\n\n", encoding="ascii"
        )
        subprocess.run([
            str(jdk / "bin" / ("jar" + suffix)), "cfm", str(output / "hello-gte.jar"),
            str(manifest), "-C", str(classes), ".",
        ], check=True)

    shutil.copy2(gson, output / "lib" / gson.name)
    files = ["README.md", "run.ps1", "run.sh", "config/signals.json", "samples/gte-demo.json",
             "docs/accesso-mib3.md", "docs/schema-dati.md", "docs/logger.md", "docs/identificazione-5f.md",
             "probe/README.md", "probe/mib3-hello.sh", "tools/read_log.py"]
    for name in files:
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, destination)
    license_path = output / "lib" / "GSON-LICENSE.txt"
    with zipfile.ZipFile(gson) as archive:
        candidates = [n for n in archive.namelist() if n.upper().endswith("LICENSE")]
        license_content = archive.read(candidates[0]) if candidates else download(
            "https://raw.githubusercontent.com/google/gson/gson-parent-2.14.0/LICENSE")
    license_path.write_bytes(license_content)
    notice = output / "lib" / "NOTICE.txt"
    notice.write_text(
        f"Gson {GSON_VERSION}, Copyright 2008 Google Inc., Apache-2.0.\n"
        f"Source: https://github.com/google/gson/tree/gson-parent-{GSON_VERSION}\n"
        f"Artifact SHA-256: {GSON_SHA256}\n", encoding="utf-8"
    )
    archive_path = ROOT / "dist" / "hello-gte-desktop-lab.zip"
    packaged = files + ["hello-gte.jar", f"lib/{gson.name}", "lib/GSON-LICENSE.txt", "lib/NOTICE.txt"]
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in packaged:
            archive.write(output / name, "hello-gte/" + name)
    print(f"JDK: {jdk}")
    print(f"JAR (Java 8): {output / 'hello-gte.jar'}")
    print(f"Archivio desktop/laboratorio: {archive_path}")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jdk", help="Cartella JDK 9+ con bin/javac")
    arguments = parser.parse_args()
    build(find_jdk(arguments.jdk))
