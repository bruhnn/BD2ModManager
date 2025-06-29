import os
import re
import subprocess
from pathlib import Path

RESOURCES_PATH = Path(__file__).parent.parent / "src" / "resources"
MATERIAL_ICONS_PATH = RESOURCES_PATH / "assets" / "icons" / "material"

def update_resources():
    for source_file in RESOURCES_PATH.glob("**/*.qrc"):
        destination_file = source_file.with_name(source_file.stem + "_rc.py")

        cmd = ["pyside6-rcc", str(source_file), "-o", str(destination_file)]

        result = subprocess.run(cmd, capture_output=True)
        
        if result.returncode != 0:
            print(f"Error updating resource file {source_file}: {result.stderr.decode().strip()}")
            continue
        else:
            print(f"Resource file updated successfully: {destination_file}")

def update_icons() -> None:
    qrc = []
    qrc.append("<RCC>")
    qrc.append('    <qresource prefix="icons/material">')
    for icon_file in MATERIAL_ICONS_PATH.rglob("*.svg"):
        theme = icon_file.parent.name
        qrc.append(f'        <file alias="{theme}/{icon_file.name}">./{icon_file.relative_to(RESOURCES_PATH).as_posix()}</file>')
    qrc.append("    </qresource>")
    qrc.append("</RCC>")

    with open(RESOURCES_PATH / "icons.qrc", "w", encoding="UTF-8") as f:
        f.write("\n".join(qrc))
        
def update_all():
    update_icons()
    update_resources()

def recolor_svg_folder(folder_path, target_color_hex):
    svg_files = [f for f in os.listdir(folder_path) if f.endswith(".svg")]
    
    for svg_file in svg_files:
        full_path = os.path.join(folder_path, svg_file)
        
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()

        new_content, count = re.subn(
            r'fill="[^"]+"',
            f'fill="{target_color_hex}"',
            content,
            1
        )

        if count == 0:
            print(f"[Skipped] No fill found in: {svg_file}")
        else:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"[Updated] {svg_file} → Color: {target_color_hex}")

    print("\n✅ Done. All matching SVGs recolored.")


if __name__ == "__main__":
    update_all()

