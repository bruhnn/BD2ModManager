import hashlib
import json
from pathlib import Path
from packaging.version import parse

DATA_DIR = Path("src/data")
MANIFEST_PATH = Path("src/manifest_v2.json")

FILES = ["characters.csv", "authors.csv", "npcs.csv", "datings.csv"]

def sha256sum(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def generate_manifest():
    if not MANIFEST_PATH.exists():
        print(f"- Manifest not found at {MANIFEST_PATH}")
        return

    with MANIFEST_PATH.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    if "data" not in manifest:
        manifest["data"] = {}

    for filename in FILES:
        file_path = DATA_DIR / filename
        if not file_path.exists():
            print(f"- File not found: {file_path}")
            continue

        key = filename
        file_hash = sha256sum(file_path)

        if key not in manifest["data"]:
            manifest["data"][key] = {}
            
        mhash = manifest["data"][key].get("hash", "v0.0.0")
        
        def bump_version(version: str) -> str:
            v = parse(version.lstrip("v"))
            major, minor, patch = map(int, str(v).split("."))
            patch += 1
            return f"{major}.{minor}.{patch}"

        if mhash != file_hash:
            v = manifest["data"][key]["version"]
            manifest["data"][key]["hash"] = file_hash
            manifest["data"][key]["version"] = str(bump_version(v))
            print(f"- Updated hash for '{key}'")

    print(json.dumps(manifest, indent=4))

if __name__ == "__main__":
    generate_manifest()
