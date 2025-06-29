from pathlib import Path
from pathlib import PurePath
from hashlib import sha256
from typing import Union, Any
import logging
import shutil

from py7zr import pack_7zarchive, unpack_7zarchive

try:
    shutil.register_archive_format(
        "7zip", pack_7zarchive, description="7zip archive")
    shutil.register_unpack_format("7zip", [".7z"], unpack_7zarchive)
except shutil.RegistryError:
    pass  # already registred I hope

logger = logging.getLogger(__name__)
COMPRESSED_EXTENSIONS = {".7z", ".zip", ".rar", ".tar", ".gz", ".bz2", ".xz"}


def get_folder_hash(path: Path) -> str:
    hash = sha256()

    for file in sorted(path.rglob("*")):
        if file.is_file():
            relative_path = str(file.relative_to(path))
            hash.update(relative_path.encode())

            # Stream file contents in chunks
            with file.open("rb") as f:
                while chunk := f.read(8192):
                    hash.update(chunk)

    return hash.hexdigest()


def get_file_hash(path: Path) -> str:
    hash = sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hash.update(chunk)
    return hash.hexdigest()


def get_data_hash(data: Any) -> str:
    hash = sha256()
    hash.update(data)
    return hash.hexdigest()


def is_filename_valid(filename: str) -> bool:
    return PurePath(filename).name == filename


def is_compressed_file(path: Path) -> bool:
    return path.suffix.lower() in COMPRESSED_EXTENSIONS


def extract_file(source_path: Union[str, Path], output_path: Union[str, Path]) -> None:
    source_path = Path(source_path)
    output_path = Path(output_path)

    if not source_path.exists():
        raise FileNotFoundError(f"Source archive not found: {source_path}")

    # Create output directory if it doesn't exist
    output_path.mkdir(parents=True, exist_ok=True)

    logger.info("Extracting archive: %s", source_path)
    try:
        shutil.unpack_archive(str(source_path), str(output_path))
        logger.info("Successfully extracted to: %s", output_path)
    except Exception as e:
        logger.error("Failed to extract %s: %s", source_path, e)
        raise


def remove_folder(path: Path) -> None:
    try:
        if path.is_symlink():
            logger.debug("Removing symlink at %s", path)
            if path.is_dir():
                path.rmdir()
            else:
                path.unlink()
        elif path.is_dir():
            logger.debug("Removing directory and its contents at %s", path)
            shutil.rmtree(path)
        else:
            if not path.exists():
                logger.debug(
                    "Path %s does not exist. Nothing to remove.", path)
            else:
                logger.warning(
                    "Path %s is a file, not a directory. Skipping removal.", path
                )
    except (OSError, PermissionError) as error:
        logger.error("Failed to remove path %s: %s", path, error)
        raise


def are_folders_identical(directory_one: Union[str, Path], directory_two: Union[str, Path]) -> bool:
    directory_one = Path(directory_one)
    directory_two = Path(directory_two)

    if not directory_one.exists() or not directory_two.exists():
        return False

    # Get relative file paths
    files_one = {
        file.relative_to(directory_one)
        for file in directory_one.rglob("*")
        if file.is_file()
    }
    files_two = {
        file.relative_to(directory_two)
        for file in directory_two.rglob("*")
        if file.is_file()
    }

    # Compare structure first
    if files_one != files_two:
        return False

    for rel_path in files_one:
        file_one = directory_one / rel_path
        file_two = directory_two / rel_path

        if file_one.stat().st_size != file_two.stat().st_size:
            return False

    return get_folder_hash(directory_one) == get_folder_hash(directory_two)


def cleanup_empty_parent_dirs(child_path: Path, root_path: Path) -> None:
    current_dir = child_path.parent

    while current_dir.is_relative_to(root_path) and current_dir != root_path:
        try:
            if not any(current_dir.iterdir()):
                logger.info("Removing empty parent directory: %s", current_dir)
                current_dir.rmdir()
                current_dir = current_dir.parent
            else:
                logger.debug(
                    "Parent directory '%s' is not empty. Stopping cleanup.", current_dir
                )
                break
        except (OSError, PermissionError) as e:
            logger.error(
                "Could not remove empty parent directory '%s': %s", current_dir, e)
            break
