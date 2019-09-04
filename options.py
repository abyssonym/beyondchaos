from dataclasses import dataclass, field
from typing import List, Set
import string

from utils import utilrandom as random

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
    key1: str = ''
    key2: str = ''
    
    @property
    def is_cyphered(self):
        return self.key1 and self.key2

    def remove_from_string(self, s: str):
        name = self.name
        if self.is_cyphered:
            f = FourSquare(self.key1, self.key2)
            name = f.decypher(self.name)
        if name in s:
            return True, s.replace(name, '')
        return False, s
        

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
                if code in MAKEOVER_MODIFIER_CODES:
                    self.activate_code("makeover")
                if code in RESTRICTED_VANILLA_SPRITE_CODES:
                    self.activate_code("frenchvanilla")
                return

    def activate_flag(self, flag_name: str):
        for flag in ALL_FLAGS:
            if flag.name == flag_name:
                self.active_flags.add(flag)
                setattr(self, flag.attr, True)
                return

    def random_unused_code(self):
        candidates = [c for c in NORMAL_CODES
                      if c not in self.active_codes and c.name != "repairpalette"]
        
        i = random.randint(1,7)
        if i <= 2:
            secret_codes = [c for c in NORMAL_CODES if c.is_cyphered and not self.is_code_active(c)]
            if secret_codes:
                candidates = secret_codes
            
        elif i <= 4:
            new_codes = MAKEOVER_MODIFIER_CODES + [c for c in NORMAL_CODES if c.name in ["alasdraco"]]
            new_codes = [c for c in new_codes
                            if not self.is_code_active(c)]
            if new_codes:
                candidates = new_codes

        if not candidates:
            candidates = NORMAL_CODES + MAKEOVER_MODIFIER_CODES

        selected = random.choice(candidates)
        if selected.is_cyphered:
            f = FourSquare(selected.key1, selected.key2)
            return f.decypher(selected.name)
        return selected.name

ANCIENT_CAVE_PROHIBITED_CODES = [
    "airship",
    "alasdraco",
    "notawaiter",
    "strangejourney",
    "worringtriad",
    "QGWURNGNSEIMKTMDFBIX",
    "HAKCSBKC"
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
         description="Play the normal story up to Kefka at Narshe, with extra wackiness. Intended for racing.",
         forced_codes=["madworld"],
         prohibited_codes=["airship", "alasdraco", "worringtriad", "HAKCSBKC"],
         prohibited_flags=["d", "k", "r"]),
    Mode(name="dragonhunt",
         description="Kill all 8 dragons in the World of Ruin. Intended for racing.",
         forced_codes=["worringtriad"],
         prohibited_codes=["airship", "alasdraco", "QGWURNGNSEIMKTMDFBIX"])
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
    Code('alasdraco', "JAM UP YOUR OPERA MODE"),
    Code('bsiab', "UNBALANCED MONSTER CHESTS MODE"),
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
    #Code('sometimeszombies', "OLD CHARACTER PALETTE MODE"),
    Code('HAKCSBKC', 'ALTERNATE GOGO MODE', key1='application', key2='octetstream'),
    Code('QGWURNGNSEIMKTMDFBIX', 'DIVERGENT PATHS MODE', key1='power', key2='panda')
]

MAKEOVER_MODIFIER_CODES = [
    Code('novanilla', "COMPLETE MAKEOVER MODE"),
    Code('frenchvanilla', "EQUAL RIGHTS MAKEOVER MODE"),
    Code('cloneparty', "CLONE COSPLAY MAKEOVER MODE")
]
RESTRICTED_VANILLA_SPRITE_CODES = []
  
makeover_groups = ["boys", "girls", "kids", "pets", "potato"]
for mg in makeover_groups:
    no = Code('no'+mg, f"NO {mg.upper()} ALLOWED MODE")
    MAKEOVER_MODIFIER_CODES.extend([
        no,
        Code('hate'+mg, f"RARE {mg.upper()} MODE"),
        Code('like'+mg, f"COMMON {mg.upper()} MODE"),
        Code('love'+mg, f"{mg.upper()} WORLD MODE")])
    RESTRICTED_VANILLA_SPRITE_CODES.append(no)


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


TOP_SECRET_CODES = [
]

ALL_CODES = NORMAL_CODES + MAKEOVER_MODIFIER_CODES + CAVE_CODES + SPECIAL_CODES + TOP_SECRET_CODES

options_ = Options(ALL_MODES[0])


# This is a little silly, since anyone who knows a little python can very easily recover the plaintext, but knowing a little python you can easily subvert it all kinds of ways. This at least prevents people from seeing the plaintext (or something to easy decode in one's head like ROT13) directly in the code.
class FourSquare:
    def __init__(self, key1: str, key2: str):
        self.cyphertable1 = FourSquare.cyphertable_from_key(key1)
        self.cyphertable2 = FourSquare.cyphertable_from_key(key2)
        self.plaintable = string.ascii_lowercase.replace('j', '')

    @staticmethod
    def cyphertable_from_key(key: str):
        key = key.upper()
        key = key.replace('j', 'i')
        k = set(key)
        k_remainder = set(string.ascii_uppercase.replace('J', '')) - k
        return sorted(k, key=key.index) + sorted(k_remainder)
        
    def encypher(self, plaintext: str):
        plaintext = "".join([c for c in plaintext if c.isalpha()])
        plaintext = plaintext.lower()
        if len(plaintext) % 2 == 1:
            plaintext = plaintext + 'x'
        plaintext = plaintext.replace('j', 'i')
        
        cyphertext = ''
        for i in range(0, len(plaintext), 2):
            j = i+1
            i_index = self.plaintable.index(plaintext[i])
            i_row, i_col = divmod(i_index, 5)
            j_index = self.plaintable.index(plaintext[j])
            j_row, j_col = divmod(j_index, 5)
            
            cyphertext += self.cyphertable1[i_row*5 + j_col]
            cyphertext += self.cyphertable2[j_row*5 + i_col]
            
        return cyphertext
    
    def decypher(self, cyphertext:str):
        if len(cyphertext) % 2 == 1:
            raise ValueError
        if 'J' in cyphertext:
            raise ValueError
        
        plaintext = ''
        for i in range(0, len(cyphertext), 2):
            j = i+1
            i_index = self.cyphertable1.index(cyphertext[i])
            i_row, i_col = divmod(i_index, 5)
            j_index = self.cyphertable2.index(cyphertext[j])
            j_row, j_col = divmod(j_index, 5)
            
            plaintext += self.plaintable[i_row*5 + j_col]
            plaintext += self.plaintable[j_row*5 + i_col]

        return plaintext[:-1] if plaintext[-1] == 'x' else plaintext