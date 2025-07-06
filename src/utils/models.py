from enum import Enum
from dataclasses import dataclass
from typing import Union, Optional
from pathlib import Path
import re
import logging

from src.utils.errors import ModInvalidError

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
        if self is BD2ModType.NPC:  # NPC
            return self.name.upper()

        return self.name.capitalize()


@dataclass
class BD2Mod:
    name: str
    display_name: str
    type: Optional[BD2ModType]
    character_id: Optional[str]
    scene_id: Optional[str]
    npc_id: Optional[str]
    dating_id: Optional[str]
    path: str

    @classmethod
    def from_mod_path(cls, path: Union[str, Path], staging_path: Path):
        if not isinstance(path, Path):
            path = Path(path)

        modfile = next(path.glob("*.modfile"), None)
        if modfile is None:
            logger.error("No .modfile found in %s", path)
            raise ModInvalidError(f"No .modfile found in {path}")

        type_patterns = {
            BD2ModType.IDLE: re.compile(r"^char(\d+)\.modfile$", re.I),
            BD2ModType.CUTSCENE: re.compile(r"cutscene_char(\d+)\.modfile$", re.I),
            BD2ModType.SCENE: re.compile(
                r"(?:specialillust|illust_special|storypack)(\d+)(?:_?\d+)?\.modfile$",
                re.I,
            ),
            BD2ModType.NPC: re.compile(r"^(npc(\d+)|illust_talk(\d+))\.modfile$", re.I),
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

        kwargs = {
            "type": mod_type,
            "name": str(path.relative_to(staging_path).as_posix()),
            "display_name": path.name,
            "path": str(path.resolve()),
            "character_id": None,
            "scene_id": None,
            "npc_id": None,
            "dating_id": None,
        }

        if mod_id:
            if mod_type in (BD2ModType.IDLE, BD2ModType.CUTSCENE):
                kwargs["character_id"] = mod_id
            elif mod_type == BD2ModType.SCENE:
                kwargs["scene_id"] = mod_id
            elif mod_type == BD2ModType.NPC:
                kwargs["npc_id"] = mod_id
            elif mod_type == BD2ModType.DATING:
                kwargs["dating_id"] = mod_id

        return cls(**kwargs)


@dataclass
class Character:
    id: str
    character: str
    costume: str

    @classmethod
    def from_dict(cls, data: dict):
        return cls(id=data["id"], character=data["character"], costume=data["costume"])

    def full_name(self, separator: Optional[str] = None):
        return (
            f"{self.character} {self.costume}"
            if not separator
            else f"{self.character} {separator} {self.costume}"
        )


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
    author: Optional[str] = None
    enabled: bool = False
    character: Optional[Character] = None
    scene: Optional[Scene] = None
    npc: Optional[NPC] = None
    has_conflict: bool = False

    @property
    def name(self) -> str:
        return self.mod.name
    
    @property
    def display_name(self) -> str:
        return self.mod.display_name

    @property
    def path(self):
        return self.mod.path

    @classmethod
    def create_from_mod(cls, mod: BD2Mod, game_data: "BD2GameData", **kwargs) -> "BD2ModEntry":
        entry = cls(mod=mod, **kwargs)

        if (
            mod.type in (BD2ModType.CUTSCENE, BD2ModType.IDLE)
            and mod.character_id is not None
        ):
            entry.character = game_data.get_character_by_id(
                mod.character_id
            )
        elif mod.type == BD2ModType.DATING and mod.dating_id is not None:
            entry.character = game_data.get_character_by_dating_id(
                mod.dating_id
            )
        elif mod.type == BD2ModType.NPC and mod.npc_id is not None:
            entry.npc = game_data.get_npc_by_id(mod.npc_id)
        elif mod.type == BD2ModType.SCENE and mod.scene_id is not None:
            entry.scene = game_data.get_scene_by_id(mod.scene_id)
            
        return entry
