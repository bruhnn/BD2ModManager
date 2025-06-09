from pathlib import Path
from pathlib import PurePath
from hashlib import sha256
from typing import Union
import logging
import shutil
from py7zr import pack_7zarchive, unpack_7zarchive

shutil.register_archive_format('7zip', pack_7zarchive, description='7zip archive')
shutil.register_unpack_format('7zip', ['.7z'], unpack_7zarchive)

logger = logging.getLogger(__name__)

def get_folder_hash(path: Path) -> str:
    """Compute sha256 hash of all files under a directory."""
    hash = sha256()
    for file in sorted(path.rglob("*")):
        if file.is_file():
            hash.update(file.read_bytes())
    return hash.hexdigest()

def is_filename_valid(filename: str):
    return PurePath(filename).name == filename

def is_compressed_file(path: Path):
    extensions = [
        '.7z',
        '.zip',
        '.rar',
        '.tar',
        '.gz',
        '.bz2',
        '.xz'
    ]
    
    return path.suffix.lower() in extensions

def extract_file(source_path: Union[str, Path], output_path: Union[str, Path]):
    # if rarfile.is_rarfile(source_path): # Path(source_path).suffix == ".rar"
    #     # use 7z.exe tool to extract
    #     with rarfile.RarFile(source_path) as rar_file:
    #         rar_file.extractall(output_path)
    #     return
    logger.info(f"Extracting archive: {source_path}")
    shutil.unpack_archive(str(source_path), str(output_path))
    logger.info(f"Successfully extracted to: {output_path}")
    # source_path, output_path = Path(source_path), Path(output_path)
    
    # result = subprocess.run([SEVENZIP_BINARY_PATH, "x", source_path, f"-o{output_path}"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    # if result.returncode != 0:
    #     raise UnsupportedArchiveFormatError(f"{source_path.name}: {source_path.suffix} is not supported.")