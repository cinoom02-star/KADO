"""Create a source+compiled-dashboard release without runtime data or secrets."""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    destination = args.destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    excluded = {".venv", "venv", "node_modules", "data", ".git", "__pycache__", ".pytest_cache", ".mypy_cache"}
    entries = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(part in excluded for part in rel.parts) or path.is_symlink() or not path.is_file():
            continue
        if path.resolve() == destination or path.name == "MANIFEST.sha256" or path.suffix in {".zip", ".pyc", ".log"}:
            continue
        if path.name.startswith(".env") and path.name != ".env.example":
            continue
        entries.append((path, rel.as_posix()))
    manifest = []
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path, relative in entries:
            data = path.read_bytes()
            archive.writestr("KADO-AI-COMPANY/" + relative, data)
            manifest.append(hashlib.sha256(data).hexdigest() + "  " + relative)
        archive.writestr("KADO-AI-COMPANY/MANIFEST.sha256", "\n".join(manifest) + "\n")
    with zipfile.ZipFile(destination) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
        assert len(names) == len(set(names)), "Duplicate archive entries"
        for entry in manifest:
            expected, relative = entry.split("  ", 1)
            assert hashlib.sha256(archive.read("KADO-AI-COMPANY/" + relative)).hexdigest() == expected
        assert all("/data/" not in n and "/node_modules/" not in n for n in names)
        assert all(not n.endswith("/.env") and "api-token.txt" not in n for n in names)
    print(f"Release: {len(entries)} files; {destination.stat().st_size} bytes; SHA256 {hashlib.sha256(destination.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
