from dataclasses import dataclass, field
from typing import List, Set

@dataclass(frozen=True)
class Mode:
    name: str
    description: str
    forced_codes: List[str] = field(default_factory=list)
    prohibited_codes: List[str] = field(default_factory=list)
    prohibited_flags: List[str] = field(default_factory=list)


@dataclass(order=True, frozen=True)
class Flag:
    name: str
    attr: str
    description: str

    def __post_init__(self):
        object.__setattr__(self, 'name', self.name[0])


@dataclass(frozen=True)
class Code:
    name: str
    description: str


@dataclass
class Options:
    mode: Mode
    active_flags: Set[Flag] = field(default_factory=set)
    active_codes: Set[Code] = field(default_factory=set)
    

    def __post_init__(self):
        for flag in ALL_FLAGS:
            setattr(self, flag.attr, False)
            
    def is_code_active(self, code_name: str):
        for code in self.active_codes:
            if code.name == code_name:
                return True
        return False
        
    def is_any_code_active(self, code_names: List[str]):
        for code in self.active_codes:
            if code.name in code_names:
                return True
        return False

    def is_flag_active(self, flag_name: str):
        for flag in self.active_flags:
            if flag.name == flag_name:
                return True
        return False

    def activate_code(self, code_name: str):
        for code in ALL_CODES:
            if code.name == code_name:
                self.active_codes.add(code)
                return

    def activate_flag(self, flag_name: str):
        for flag in ALL_FLAGS:
            if flag.name == flag_name:
                self.active_flags.add(flag)
                setattr(self, flag.attr, True)
                return


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
    Mode(name="normal", description="Play through the normal story."),
    Mode(name="ancientcave",
         description="Play through a long randomized dungeon.",
         forced_codes=["ancientcave"],
         prohibited_codes=ANCIENT_CAVE_PROHIBITED_CODES,
         prohibited_flags=ANCIENT_CAVE_PROHIBITED_FLAGS),
    Mode(name="speedcave",
         description="Play through a medium-sized randomized dungeon.",
         forced_codes=["speedcave", "ancientcave"],
         prohibited_codes=ANCIENT_CAVE_PROHIBITED_CODES,
         prohibited_flags=ANCIENT_CAVE_PROHIBITED_FLAGS),
    Mode(name="racecave",
         description="Play through a short randomized dungeon.",
         forced_codes=["racecave", "speedcave", "ancientcave"],
         prohibited_codes=ANCIENT_CAVE_PROHIBITED_CODES,
         prohibited_flags=ANCIENT_CAVE_PROHIBITED_FLAGS),
    Mode(name="katn",
         description="",
         forced_codes=["madworld"],
         prohibited_codes=["airship", "worringtriad"],
         prohibited_flags=["d", "k", "r"])
]

ALL_FLAGS = [
    Flag('o', 'shuffle_commands', "Shuffle characters' in-battle commands"),
    Flag('w', 'replace_commands', 'Generate new commands for characters, replacing old commands.'),
    Flag('z', 'sprint', 'Always have "Sprint Shoes" effect.'),
    Flag('b', 'fix_exploits', 'Make the game more balanced by removing exploits such as Joker Doom, '
              'Vanish/Doom, and the Evade/Mblock bug.'),
    Flag('m', 'random_enemy_stats', 'Randomize enemy stats.'),
    Flag('c', 'random_palettes_and_names', 'Randomize palettes and names of various things.'),
    Flag('i', 'random_items', 'Randomize the stats of equippable items.'),
    Flag('q', 'random_character_stats', 'Randomize what equipment each character can wear and character stats.'),
    Flag('e', 'random_espers', 'Randomize esper spells and levelup bonuses.'),
    Flag('t', 'random_treasure', 'Randomize treasure, including chests, colosseum, shops, and enemy drops.'),
    Flag('u', 'random_zerker', 'Umaro risk. (Random character will be berserk)'),
    Flag('l', 'random_blitz', 'Randomize blitz inputs.'),
    Flag('n', 'random_window', 'Randomize window background colors.'),
    Flag('f', 'random_formations', 'Randomize enemy formations.'),
    Flag('s', 'swap_sprites', 'Swap character graphics around.'),
    Flag('p', 'random_animation_palettes', 'Randomize the palettes of spells and weapon animations.'),
    Flag('d', 'random_final_dungeon', 'Randomize final dungeon.'),
    Flag('g', 'random_dances', 'Randomize dances'),
    Flag('k', 'random_clock', 'Randomize the clock in Zozo'),
    Flag('r', 'shuffle_wor', 'Randomize character locations in the world of ruin.'),
]


NORMAL_CODES = [
    Code('airship', "AIRSHIP MODE"),
    Code('partyparty', "CRAZY PARTY MODE"),
    Code('bravenudeworld', "TINA PARTY MODE"),
    Code('suplexwrecks', "SUPLEX MODE"),
    Code('strangejourney', "BIZARRE ADVENTURE"),
    Code('dearestmolulu', "ENCOUNTERLESS MODE"),
    Code('canttouchthis', "INVINCIBILITY"),
    Code('easymodo', "EASY MODE"),
    Code('norng', "NO RNG MODE"),
    Code('endless9', "ENDLESS NINE MODE"),
    Code('equipanything', "EQUIP ANYTHING MODE"),
    Code('collateraldamage', "ITEM BREAK MODE"),
    Code('repairpalette', "PALETTE REPAIR"),
    Code('llg', "LOW LEVEL GAME MODE"),
    Code('naturalmagic', "NATURAL MAGIC MODE"),
    Code('naturalstats', "NATURAL STATS MODE"),
    Code('playsitself', "AUTOBATTLE MODE"),
    Code('bingoboingo', "BINGO BONUS"),
    Code('worringtriad', "START IN WOR"),
    Code('metronome', "R-CHAOS MODE"),
    Code('quikdraw', "QUIKDRAW MODE"),
    Code('makeover', "SPRITE REPLACEMENT MODE"),
    Code('kupokupo', "MOOGLE MODE"),
    Code('capslockoff', "Mixed Case Names Mode"),
    Code('replaceeverything', "REPLACE ALL SKILLS MODE"),
    Code('allcombos', "ALL COMBOS MODE"),
    Code('randomboost', "RANDOM BOOST MODE"),
    Code('dancingmaduin', "RESTRICTED ESPERS MODE"),
    Code('masseffect', "WILD EQUIPMENT EFFECT MODE"),
    Code('darkworld', "SLASHER'S DELIGHT MODE"),
    Code('supernatural', "SUPER NATURAL MAGIC MODE"),
    Code('madworld', "TIERS FOR FEARS MODE"),
    Code('randombosses', "RANDOM BOSSES MODE"),
    Code('electricboogaloo', "WILD ITEM BREAK MODE"),
    Code('notawaiter', "CUTSCENE SKIPS"),
    Code('rushforpower', "OLD VARGAS FIGHT MODE"),
    Code('johnnydmad', "MUSIC REPLACEMENT MODE"),
    Code('johnnyachaotic', "MUSIC MANGLING MODE"),
]


# TODO: do this a better way
CAVE_CODES = [
    Code('ancientcave', "ANCIENT CAVE MODE"),
    Code('speedcave', "SPEED CAVE MODE"),
    Code('racecave', "RACE CAVE MODE"),
]


SPECIAL_CODES = [
    Code('christmas', 'CHIRSTMAS MODE'),
    Code('halloween', "ALL HALLOWS' EVE MODE")
]


ALL_CODES = NORMAL_CODES + CAVE_CODES + SPECIAL_CODES

options = Options(ALL_MODES[0])