import argparse
import re
import subprocess
from pathlib import Path

RESOURCES_PATH = Path(__file__).resolve().parent.parent / "src" / "resources"
ASSETS_PATH = RESOURCES_PATH / "assets"
ICON_ASSETS_PATH = ASSETS_PATH / "icons" / "material"
CHARACTER_ASSETS_PATH = ASSETS_PATH / "characters"

def generate_qrc_file(
    asset_base_path: Path,
    qresource_prefix: str,
    file_glob: str,
    output_filename: str,
    alias_generator,
) -> None:
    print(f"Generating {output_filename}...")
    qrc_lines = [
        "<RCC>",
        f'    <qresource prefix="{qresource_prefix}">',
    ]

    found_files = sorted(list(asset_base_path.rglob(file_glob)))
    if not found_files:
        print(f"  -> No files found matching '{file_glob}' in {asset_base_path}")
        return

    for asset_file in found_files:
        alias = alias_generator(asset_file)
        relative_path = asset_file.relative_to(RESOURCES_PATH).as_posix()
        qrc_lines.append(f'        <file alias="{alias}">{relative_path}</file>')

    qrc_lines.extend(["    </qresource>", "</RCC>", ""])

    output_path = RESOURCES_PATH / output_filename
    output_path.write_text("\n".join(qrc_lines), encoding="UTF-8")
    print(f"Successfully generated {output_path}")


def compile_resources() -> None:
    print("\nCompiling all .qrc files...")
    qrc_files = list(RESOURCES_PATH.glob("**/*.qrc"))
    
    if not qrc_files:
        print("  -> No .qrc files found to compile.")
        return

    for source_file in qrc_files:
        destination_file = source_file.with_name(f"{source_file.stem}_rc.py")
        cmd = ["pyside6-rcc", str(source_file), "-o", str(destination_file)]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"Error compiling {source_file}:\n{result.stderr.strip()}")
        else:
            print(f"Compiled {source_file} -> {destination_file}")


def recolor_svgs(folder_path: Path, color: str) -> None:
    print(f"\nRecoloring SVGs in {folder_path} to {color}...")

    fill_pattern = re.compile(r'fill\s*=\s*([\'"])[^"]+\1')
    
    svg_files = list(folder_path.glob("*.svg"))

    if not svg_files:
        print("  -> No SVG files found in this folder.")
        return

    for svg_file in svg_files:
        content = svg_file.read_text(encoding="utf-8")
        
        new_content, count = fill_pattern.subn(f'fill="{color}"', content, count=1)

        if count > 0:
            svg_file.write_text(new_content, encoding="utf-8")
            print(f"[Updated] {svg_file.name}")
        else:
            print(f"[Skipped] No 'fill' attribute found in: {svg_file.name}")
    
    print("\nDone. All matching SVGs recolored.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="A helper script to manage and update project assets."
    )
    parser.add_argument(
        "action",
        choices=["update", "recolor", "all"],
        help="The action to perform: 'update' resources, 'recolor' SVGs, or 'all'.",
    )
    parser.add_argument(
        "--color",
        default="#FFFFFF",
        help="The target hex color for SVG recoloring (e.g., '#FF5733').",
    )
    parser.add_argument(
        "--svg-dir",
        type=Path,
        default=ICON_ASSETS_PATH / "filled",
        help="The directory containing SVG files to recolor.",
    )

    args = parser.parse_args()

    if args.action in ["update", "all"]:

        generate_qrc_file(
            asset_base_path=ICON_ASSETS_PATH,
            qresource_prefix="icons/material",
            file_glob="*.svg",
            output_filename="icons.qrc",
            alias_generator=lambda p: f"{p.parent.name}/{p.name}",
        )
        
        generate_qrc_file(
            asset_base_path=CHARACTER_ASSETS_PATH,
            qresource_prefix="characters",
            file_glob="*.png",
            output_filename="characters.qrc",
            alias_generator=lambda p: p.stem,
        )

        compile_resources()

    if args.action in ["recolor", "all"]:
        if not args.svg_dir.is_dir():
            print(f"Error: SVG directory not found at '{args.svg_dir}'")
        else:
            recolor_svgs(args.svg_dir, args.color)

    print("\nScript finished.")