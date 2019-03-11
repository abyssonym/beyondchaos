from dataclasses import dataclass, field
from typing import List

@dataclass
class Mode:
    name: str
    description: str
    forced_codes: List[str] = field(default_factory=list)
    prohibited_codes: List[str] = field(default_factory=list)

ancient_cave_prohibited_codes=[
    "airship",
    "notawaiter",
    "strangejourney",
    "worringtriad"
]

ALL_MODES = [
    Mode(name="normal", description="Play through the game with things randomized."),
    Mode(name="ancientcave",
         description="Play through a long randomized dungeon.",
         forced_codes=["ancientcave"],
         prohibited_codes=ancient_cave_prohibited_codes),
    Mode(name="speedcave",
         description="Play through a medium-sized randomized dungeon.",
         forced_codes=["speedcave"],
         prohibited_codes=ancient_cave_prohibited_codes),
    Mode(name="racecave",
         description="Play through a short randomized dungeon.",
         forced_codes=["racecave"],
         prohibited_codes=ancient_cave_prohibited_codes),
]