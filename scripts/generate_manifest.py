import hashlib
import json
from pathlib import Path

DATA_DIR = Path("src/data")
MANIFEST_PATH = Path("src/manifest.json")

FILES = ["characters.csv", "authors.csv", "datings.csv"]

def sha256sum(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def generate_manifest():
    if not MANIFEST_PATH.exists():
        print(f"❌ Manifest not found at {MANIFEST_PATH}")
        return

    with MANIFEST_PATH.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    if "data" not in manifest:
        manifest["data"] = {}

    for filename in FILES:
        file_path = DATA_DIR / filename
        if not file_path.exists():
            print(f"⚠️  File not found: {file_path}")
            continue

        key = filename.removesuffix(".csv")
        file_hash = sha256sum(file_path)

        if key not in manifest["data"]:
            manifest["data"][key] = {}

        manifest["data"][key]["hash"] = file_hash
        print(f"✅ Updated hash for '{key}'")

    print(json.dumps(manifest, indent=4))

if __name__ == "__main__":
    generate_manifest()
