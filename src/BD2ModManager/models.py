from enum import Enum
from dataclasses import dataclass
from typing import Union, Optional
from pathlib import Path
import re
import logging

from .errors import ModInvalidError

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class BD2ModType(Enum):
    IDLE = 0
    CUTSCENE = 1
    SCENE = 2
    NPC = 3
    DATING = 4

    @property
    def display_name(self):
        if self.value in (3,): # NPC
            return self.name.upper()
        
        return self.name.capitalize()
    
@dataclass
class BD2Mod:
    type: Optional[BD2ModType]
    name: str
    character_id: Optional[str]
    scene_id: Optional[str]
    npc_id: Optional[str]
    dating_id: Optional[str]
    
    @classmethod
    def from_mod_path(cls, path: Union[str, Path]):
        if not isinstance(path, Path):
            path = Path(path)

        modfile = next(path.glob("*.modfile"), None)
        if modfile is None:
            logger.error("No .modfile found in %s", path)
            raise ModInvalidError(f"No .modfile found in {path}")

        type_patterns = {
            BD2ModType.IDLE: re.compile(r"^char(\d+)\.modfile$", re.I),
            BD2ModType.CUTSCENE: re.compile(r"cutscene_char(\d+)\.modfile$", re.I),
            BD2ModType.SCENE: re.compile(r"(?:specialillust|illust_special|storypack)(\d+)(?:_?\d+)?\.modfile$", re.I),
            BD2ModType.NPC: re.compile(r"^npc(\d+)\.modfile$", re.I),
            BD2ModType.DATING: re.compile(r"^illust_dating(\d+)\.modfile$", re.I),
        }

        mod_type = None
        mod_id = None

        for mtype, pattern in type_patterns.items():
            match = pattern.match(modfile.name)
            if match:
                mod_type = mtype
                mod_id = match.group(1)
                break

        if mod_type is None:
            logger.warning("Unknown mod type for file: %s", path.name)

        return cls(
            type=mod_type,
            name=path.name,
            character_id=mod_id if mod_type in (BD2ModType.IDLE, BD2ModType.CUTSCENE) else None,
            scene_id=mod_id if mod_type == BD2ModType.SCENE else None,
            npc_id=mod_id if mod_type == BD2ModType.NPC else None,
            dating_id=mod_id if mod_type == BD2ModType.DATING else None,
        )

@dataclass
class Character:
    id: str
    character: str
    costume: str
    
    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            id=data["id"],
            character=data["character"],
            costume=data["costume"]
        )
    
    def full_name(self, separator: Optional[str] = None):
        return f"{self.character} {self.costume}" if not separator else f"{self.character} {separator} {self.costume}"

@dataclass
class Scene:
    id: str
    name: str

@dataclass
class NPC:
    id: str
    name: str

@dataclass
class BD2ModEntry:
    mod: BD2Mod
    path: str
    author: str
    enabled: bool
    character: Optional[Character] = None
    scene: Optional[Scene] = None
    npc: Optional[NPC] = None