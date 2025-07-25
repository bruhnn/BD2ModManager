import json
import xml.etree.ElementTree as ET
from pathlib import Path

TRANSLATIONS_DIR = Path("src/translations")
TRANSLATIONS_JSON = Path("scripts/translations.json")

def load_translations(json_path: Path):
    with open(json_path, encoding="utf-8") as f:
        return json.load(f)

def update_ts_file(ts_path: Path, translation_data: dict):
    tree = ET.parse(ts_path)
    root = tree.getroot()
    changed = False

    for context in root.findall("context"):
        context_name = context.findtext("name", default=None)
        if context_name not in translation_data:
            continue

        context_translations = translation_data[context_name]

        for message in context.findall("message"):
            source_text = message.findtext("source", default=None)
            if not source_text or source_text not in context_translations:
                continue

            translated_text = context_translations[source_text]
            translation = message.find("translation")
            if translation is not None:
                if translation.text != translated_text:
                    translation.text = translated_text
                    translation.attrib.pop("type", None)  # Remove type="unfinished" if exists
                    changed = True

    if changed:
        tree.write(ts_path, encoding="utf-8", xml_declaration=True)
        print(f"Updated: {ts_path.name}")
    else:
        print(f"No changes in: {ts_path.name}")

def main():
    all_translations = load_translations(TRANSLATIONS_JSON)

    for lang_code, translations in all_translations.items():
        ts_file = TRANSLATIONS_DIR / f"{lang_code}.ts"
        if not ts_file.exists():
            print(f"Missing file: {ts_file}")
            continue

        update_ts_file(ts_file, translations)

if __name__ == "__main__":
    main()
