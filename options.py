from dataclasses import dataclass, field
from typing import List

@dataclass
class Mode:
    name: str
    description: str
    forced_codes: List[str] = field(default_factory=list)
    prohibited_codes: List[str] = field(default_factory=list)
    prohibited_flags: List[str] = field(default_factory=list)

@dataclass(order=True)
class Flag:
    name: str
    description: str

    def __post_init__(self):
        self.name = self.name[0]
        
ANCIENT_CAVE_PROHIBITED_CODES = [
    "airship",
    "notawaiter",
    "strangejourney",
    "worringtriad"
]

ANCIENT_CAVE_PROHIBITED_FLAGS = [
"d",
"k",
"r",
]

ALL_MODES = [
    Mode(name="normal", description="Play through the game with things randomized."),
    Mode(name="ancientcave",
         description="Play through a long randomized dungeon.",
         forced_codes=["ancientcave"],
         prohibited_codes=ANCIENT_CAVE_PROHIBITED_CODES,
         prohibited_flags=ANCIENT_CAVE_PROHIBITED_FLAGS),
    Mode(name="speedcave",
         description="Play through a medium-sized randomized dungeon.",
         forced_codes=["speedcave"],
         prohibited_codes=ANCIENT_CAVE_PROHIBITED_CODES,
         prohibited_flags=ANCIENT_CAVE_PROHIBITED_FLAGS),
    Mode(name="racecave",
         description="Play through a short randomized dungeon.",
         forced_codes=["racecave"],
         prohibited_codes=ANCIENT_CAVE_PROHIBITED_CODES,
         prohibited_flags=ANCIENT_CAVE_PROHIBITED_FLAGS),
]

ALL_FLAGS = [
    Flag('o', "Shuffle characters' in-battle commands"),
    Flag('w', 'Generate new commands for characters, replacing old commands.'),
    Flag('z', 'Always have "Sprint Shoes" effect.'),
    Flag('b', 'Make the game more balanced by removing exploits such as Joker Doom, '
                'Vanish/Doom, and the Evade/Mblock bug.'),
    Flag('m', 'Randomize enemy stats.'),
    Flag('c', 'Randomize palettes and names of various things.'),
    Flag('i', 'Randomize the stats of equippable items.'),
    Flag('q', 'Randomize what equipment each character can wear and character stats.'),
    Flag('e', 'Randomize esper spells and levelup bonuses.'),
    Flag('t', 'Randomize treasure, including chests, colosseum, shops, and enemy drops.'),
    Flag('u', 'Umaro risk. (Random character will be berserk)'),
    Flag('l', 'Randomize blitz inputs.'),
    Flag('n', 'Randomize window background colors.'),
    Flag('f', 'Randomize enemy formations.'),
    Flag('s', 'Swap character graphics around.'),
    Flag('p', 'Randomize the palettes of spells and weapon animations.'),
    Flag('d', 'Randomize final dungeon.'),
    Flag('g', 'Randomize dances'),
    Flag('k', 'Randomize the clock in Zozo'),
    Flag('r', 'Randomize character locations in the world of ruin.'),
]