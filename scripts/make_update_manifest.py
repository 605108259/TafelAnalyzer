from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Create TAFSQ update manifest.")
    parser.add_argument("--version", required=True)
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--notes", default="")
    parser.add_argument("--mandatory", action="store_true")
    parser.add_argument("--output", default="release/update.json", type=Path)
    args = parser.parse_args()

    artifact = args.artifact.resolve()
    if not artifact.is_file():
        raise SystemExit(f"artifact not found: {artifact}")

    base_url = args.base_url.rstrip("/")
    payload = {
        "version": args.version,
        "url": f"{base_url}/{artifact.name}",
        "filename": artifact.name,
        "sha256": sha256_file(artifact),
        "size": artifact.stat().st_size,
        "mandatory": bool(args.mandatory),
        "notes": args.notes,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
