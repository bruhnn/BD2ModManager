import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def extract_unfinished_translations(ts_path: Path):
    tree = ET.parse(ts_path)
    root = tree.getroot()
    unfinished = []

    for context in root.findall("context"):
        context_name = context.findtext("name", default="(UnknownContext)")
        for message in context.findall("message"):
            source = message.findtext("source", default="")
            translation = message.find("translation")

            if translation is not None and translation.get("type") == "unfinished":
                unfinished.append({
                    "context": context_name,
                    "source": source.strip(),
                    "translation": translation.text or ""
                })

    return unfinished


def main():
    translations_dir = Path("src/translations")
    ts_files = sorted(translations_dir.glob("*.ts"))

    if not ts_files:
        print("No .ts files found in src/translations/")
        sys.exit(1)

    for ts_file in ts_files:
        lang_code = ts_file.stem 
        results = extract_unfinished_translations(ts_file)

        if not results:
            continue

        print(f"# Language: {lang_code}")
        print(f"Translate the following from English to {lang_code}:\n")

        for item in results:
            print(f"Context: {item['context']}")
            print(f"Source: {item['source']}")
            print(f"Current Translation: {item['translation']}")
            print()

        print("#" * 80)
        print()


if __name__ == "__main__":
    main()
