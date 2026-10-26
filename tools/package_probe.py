"""Package the shell probe; no compilation, download or vehicle connection."""
from __future__ import annotations

import hashlib
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "probe/mib3-hello.sh": "mib3-hello.sh",
    "probe/README.md": "README.md",
    "docs/identificazione-5f.md": "docs/identificazione-5f.md",
    "docs/accesso-mib3.md": "docs/accesso-mib3.md",
}


def package() -> Path:
    folder = ROOT / "dist" / "mib3-hello-probe"
    folder.mkdir(parents=True, exist_ok=True)
    archive_path = ROOT / "dist" / "mib3-hello-probe.zip"
    entries = {}
    for source, destination in FILES.items():
        # LF and no BOM are necessary when an archive is extracted onto a USB drive.
        source_text = (ROOT / source).read_text(encoding="utf-8-sig").replace("\r\n", "\n")
        if source == "probe/README.md":
            # The standalone README sits at the archive root, next to docs/.
            source_text = source_text.replace("](../docs/", "](docs/")
        content = source_text.encode("utf-8")
        target = folder / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        entries[destination] = content
    entries["SHA256SUMS.txt"] = "".join(
        f"{hashlib.sha256(content).hexdigest()}  {name}\n"
        for name, content in entries.items()
    ).encode("ascii")
    (folder / "SHA256SUMS.txt").write_bytes(entries["SHA256SUMS.txt"])
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            item = zipfile.ZipInfo("mib3-hello-probe/" + name)
            item.create_system = 3
            item.external_attr = (0o100755 if name.endswith(".sh") else 0o100644) << 16
            item.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(item, content)
    print(f"Sonda (richiede accesso gia disponibile): {archive_path}")
    return archive_path


if __name__ == "__main__":
    package()
