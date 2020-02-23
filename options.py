from dataclasses import dataclass, field
from typing import List, Set, Union

@dataclass(frozen=True)
class Mode:
    name: str
    description: str
    forced_codes: List[str] = field(default_factory=list)
    prohibited_codes: List[str] = field(default_factory=list)
    prohibited_flags: Set[str] = field(default_factory=set)


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
    long_description: str
    category: str
    key1: str = ''
    key2: str = ''

    def remove_from_string(self, s: str):
        name = self.name
        if name in s:
            return True, s.replace(name, '')
        return False, s


@dataclass
class Options:
    mode: Mode
    active_flags: Set[Flag] = field(default_factory=set)
    active_codes: Set[Code] = field(default_factory=set)
    shuffle_commands: bool = field(init=False, default=False)
    replace_commands: bool = field(init=False, default=False)
    sprint: bool = field(init=False, default=False)
    fix_exploits: bool = field(init=False, default=False)
    random_enemy_stats: bool = field(init=False, default=False)
    random_palettes_and_names: bool = field(init=False, default=False)
    random_items: bool = field(init=False, default=False)
    random_character_stats: bool = field(init=False, default=False)
    random_espers: bool = field(init=False, default=False)
    random_treasure: bool = field(init=False, default=False)
    random_zerker: bool = field(init=False, default=False)
    random_blitz: bool = field(init=False, default=False)
    random_window: bool = field(init=False, default=False)
    random_formations: bool = field(init=False, default=False)
    swap_sprites: bool = field(init=False, default=False)
    random_animation_palettes: bool = field(init=False, default=False)
    random_final_dungeon: bool = field(init=False, default=False)
    random_dances: bool = field(init=False, default=False)
    random_clock: bool = field(init=False, default=False)
    shuffle_wor: bool = field(init=False, default=False)
    randomize_forest: bool = field(init=False, default=False)
    randomize_magicite: bool = field(init=False, default=False)

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

    def activate_flag(self, flag: Flag):
        self.active_flags.add(flag)
        setattr(self, flag.attr, True)

    def activate_from_string(self, flag_string):
        for code in self.mode.forced_codes:
            self.activate_code(code)

        s = ""
        flags, codes = read_options_from_string(flag_string, self.mode)
        for code in codes:
            if code.name in self.mode.prohibited_codes:
                s += f"SECRET CODE: '{code.description}' is not compatible with {self.mode.name} mode.\n"
                continue
            s += f"SECRET CODE: {code.description} ACTIVATED\n"
            self.activate_code(code.name)

        if self.is_code_active('strangejourney'):
            self.activate_code('notawaiter')

        flags -= self.mode.prohibited_flags
        if not flags:
            flags = {f for f in ALL_FLAGS if f not in self.mode.prohibited_flags}

        for flag in flags:
            self.activate_flag(flag)

        return s


def read_options_from_string(flag_string: str, mode: Union[Mode, str]):
    flags = set()
    codes = set()

    if isinstance(mode, str):
        mode = [m for m in ALL_MODES if m.name == mode][0]

    for code in NORMAL_CODES + MAKEOVER_MODIFIER_CODES:
        found, flag_string = code.remove_from_string(flag_string)
        if found:
            codes.add(code)

    if '-' in flag_string:
        print("NOTE: Using all flags EXCEPT the specified flags.")
        flags = {f for f in ALL_FLAGS if f.name not in flag_string}
    else:
        flags = {f for f in ALL_FLAGS if f.name in flag_string}

    flags -= mode.prohibited_flags
    if not flags:
        flags = {f for f in ALL_FLAGS if f not in mode.prohibited_flags}

    return flags, codes

ANCIENT_CAVE_PROHIBITED_CODES = [
    "airship",
    "alasdraco",
    "notawaiter",
    "strangejourney",
    "worringtriad",
    "thescenarionottaken",
    "mimetime"
]


ANCIENT_CAVE_PROHIBITED_FLAGS = {
    "d",
    "k",
    "r",
    "j",
}

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
         prohibited_codes=["airship", "alasdraco", "worringtriad", "mimetime"],
         prohibited_flags={"d", "k", "r"}),
    Mode(name="dragonhunt",
         description="Kill all 8 dragons in the World of Ruin. Intended for racing.",
         forced_codes=["worringtriad"],
         prohibited_codes=["airship", "alasdraco", "thescenarionottaken"],
         prohibited_flags={"j"}),
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
    Flag('j', 'randomize_forest', 'Randomize the phantom forest.'),
    Flag('y', 'randomize_magicite', 'Shuffle magicite locations.'),
]


NORMAL_CODES = [
    Code('airship', "AIRSHIP MODE", "The party will have access to the airship immediately after leaving Narshe. Chocobo stables can also be used to acquire the airship. Doing events out of order can cause softlocks.", "gamebreaking"),
    Code('alasdraco', "JAM UP YOUR OPERA MODE", "Randomizes the sprites of Maria, Draco, Ralse, the Impresario, the flowers Maria throws from the balcony, and the weight Ultros drops, as well as the singing voices and the names of the factions.", "aesthetic"),
    Code('allcombos', "ALL COMBOS MODE", "All skills that get replaced with something are replaced with combo skills.", "minor"),
    Code('bingoboingo', "BINGO BONUS", "Generates a Bingo table with spells, items, equipment, and enemy squares to check off. Players can set victory requirements like achieving a line, or acquiring a certain number of points. The ROM does not interact with the bingo card.", "aesthetic"),
    Code('bravenudeworld', "TINA PARTY MODE", "All characters use the Esper Terra sprite.", "aesthetic"),
    Code('bsiab', "UNBALANCED MONSTER CHESTS MODE", "Reverts the monster-in-a-box selection algorithm to be (mostly) the same as versions prior to EX v3.", "minor"),
    Code('canttouchthis', "INVINCIBILITY", "All characters have 255 Defense and 255 Magic Defense, as well as 128 Evasion and Magic Evasion.", "major"),
    Code('capslockoff', "Mixed Case Names Mode", "Names use whatever capitalization is in the name lists instead of all caps.", "aesthetic"),
    Code('collateraldamage', "ITEM BREAK MODE", "All pieces of equipment break for spells. Characters only have the Fight and Item commands, and enemies will use items drastically more often than usual.", "major"),
    Code('dancingmaduin', "RESTRICTED ESPERS MODE", "Restricts Esper usage such that most Espers can only be equipped by one character. Also usually changes what spell the Paladin Shld teaches.", "major"),
    Code('darkworld', "SLASHER'S DELIGHT MODE", "Drastically increases the difficulty of the seed, akin to a hard mode. Mostly meant to be used in conjunction with the madworld code.", "major"),
    Code('dearestmolulu', "ENCOUNTERLESS MODE", "No random encounters occur. All encounters yield 3x EXP. Wearing a Moogle Charm or a piece of equipment with the Moogle Charm effect will cause a battle to occur on every step when encounters can be occur.", "major"),
    Code('easymodo', "EASY MODE", "All enemies have 1 HP.", "major"),
    Code('electricboogaloo', "WILD ITEM BREAK MODE", "Increases the list of spells that items can break and proc for. Items can break for potentially any spell, and weapons can potentially proc any spell excluding SwdTechs, Blitzes, Slots, and a couple other skills.", "minor"),
    Code('endless9', "ENDLESS NINE MODE", "All R-[skills] are automatically changed to 9x[skills]. W-[skills] will become 8x[skills].", "major"),
    Code('equipanything', "EQUIP ANYTHING MODE", "Items that are not equippable normally can now be equipped as weapons or shields. These often give strange defensive stats or weapon animations.", "gamebreaking"),
    Code('fightclub', "MORE LIKE COLI-DON'T-SEE-'EM", "Does not allow you to see the coliseum rewards before betting, but you can often run from the coliseum battles to keep your item.", "minor"),
    Code('johnnydmad', "MUSIC REPLACEMENT MODE", "Randomizes music with regard to what would make sense in a given location.", "aesthetic"),
    Code('johnnyachaotic', "MUSIC MANGLING MODE", "Randomizes music with no regard to what would make sense in a given location.", "aesthetic"),
    Code('kupokupo', "MOOGLE MODE", "All party members are moogles except Mog. With partyparty, all characters are moogles, except Mog, Esper Terra, and Imps.", "aesthetic"),
    Code('llg', "LOW LEVEL GAME MODE", "Stands for Low Level Game. No encounters will yield any Experience Points.", "major"),
    Code('madworld', "TIERS FOR FEARS MODE", 'Creates a "true tierless" seed, with enemies having a higher degree of randomization and shops being very randomized as well.', "major"),
    Code('makeover', "SPRITE REPLACEMENT MODE", "Some sprites are replaced with new ones (like Cecil or Zero Suit Samus).", "aesthetic"),
    Code('masseffect', "WILD EQUIPMENT EFFECT MODE", "Increases the number of rogue effects on equipment by a large amount.", "major"),
    Code('metronome', "R-CHAOS MODE", "All characters have Fight, R-Chaos, Magic, and Item as their skillset, except for the Mime, who has Mimic instead of Fight. Berserker also only has R-Chaos.", "major"),
    Code('mimetime', 'ALTERNATE GOGO MODE', "Gogo will be hidden somewhere in the world of ruin disguised as another character. Bring that character to him to recruit him.", "minor"),
    Code('naturalmagic', "NATURAL MAGIC MODE", "No Espers or equipment will teach spells. The only way to learn spells is through Natural Magic.", "major"),
    Code('naturalstats', "NATURAL STATS MODE", "No Espers will grant stat bonuses upon leveling up.", "minor"),
    Code('norng', "NO RNG MODE", "Calls to the RNG are not made. Attacks are always critical hits, everything targets the lead character when applicable, and all attacks hit if they are able to except Instant Death. Many more additional effects occur. Cannot currently be completed without cheat codes.", "experimental"),
    Code('notawaiter', "CUTSCENE SKIPS", "Up to Kefka at Narshe, the vast majority of mandatory cutscenes are completely removed. Optional cutscenes are not removed.", "aesthetic"),
    Code('partyparty', "CRAZY PARTY MODE", "Kefka, Trooper, Banon, Leo, Ghost, Merchant, Esper Terra, and Soldier are mixed into the sprites that can be acquired by playable characters. Those sprites are also randomized themselves, allowing Leo to look like Edgar, for example.", "aesthetic"),
    Code('playsitself', "AUTOBATTLE MODE", "All characters will act automatically, in a manner similar to when Coliseum fights are fought.", "major"),
    Code('quikdraw', "QUIKDRAW MODE", "All characters look like imperial soldiers, and none of them have Gau's Rage skill.", "minor"),
    Code('randomboost', "RANDOM BOOST MODE", "Prompts you for a randomness multiplier, which changes the range of items that can be in chests, etc. Choosing a randomness multiplier of 0(or leaving it blank) will allow any item to appear in any treasure chest.", "major"),
    Code('randombosses', "RANDOM BOSSES MODE", "Causes boss skills to be randomized similarly to regular enemy skills. Boss skills can change to similarly powerful skills.", "minor"),
    Code('repairpalette', "PALETTE REPAIR", "Used for testing changes to palette randomization. Not intended for actual play. Cannot proceed past Banon's scenario.", "experimental"),
    Code('replaceeverything', "REPLACE ALL SKILLS MODE", "All vanilla skills that can be replaced, are replaced.", "minor"),
    Code('rushforpower', "OLD VARGAS FIGHT MODE", "Reverts the Vargas fight to the way it was before Beyond Chaos EX.", "minor"),
    Code('strangejourney', "BIZARRE ADVENTURE", "A prototype entrance randomizer, similar to the ancientcave mode. Includes all maps and event tiles, and is usually extremely hard to beat by itself.", "experimental"),
    Code('supernatural', "SUPER NATURAL MAGIC MODE", "Makes it so that any character with the Magic command will have natural magic.", "minor"),
    Code('suplexwrecks', "SUPLEX MODE", "All characters use the Sabin sprite, as well as having a name similar to Sabin. All characters have the Blitz and Suplex commands, and every enemy can be hit by Suplex.", "major"),
    Code('thescenarionottaken', 'DIVERGENT PATHS MODE', "Changes the way the 3 scenarios are split up.", "major"),
    Code('worringtriad', "START IN WOR", "The player will start in the World of Ruin, with all of the World of Balance treasure chests, along with a guaranteed set of items, and more Lores.", "major"),
]

MAKEOVER_MODIFIER_CODES = [
    Code('novanilla', "COMPLETE MAKEOVER MODE", "Same as 'makeover' except sprites from the vanilla game are guaranteed not to appear.", "aesthetic"),
    Code('frenchvanilla', "EQUAL RIGHTS MAKEOVER MODE", "Same as 'makeover' except sprites from the vanilla game are selected with equal weight to new sprites rather than some being guaranteed to appear.", "aesthetic"),
    Code('cloneparty', "CLONE COSPLAY MAKEOVER MODE", "Same as 'makeover' except instead of avoiding choosing different versions of the same character, it actively tries to do so.", "aesthetic")
]
RESTRICTED_VANILLA_SPRITE_CODES = []

makeover_groups = ["boys", "girls", "kids", "pets", "potato"]
for mg in makeover_groups:
    no = Code('no'+mg, f"NO {mg.upper()} ALLOWED MODE", f"Do not select {mg} sprites.", "aesthetic")
    MAKEOVER_MODIFIER_CODES.extend([
        no,
        Code('hate'+mg, f"RARE {mg.upper()} MODE", f"Reduce probability of selecting {mg} sprites.", "aesthetic"),
        Code('like'+mg, f"COMMON {mg.upper()} MODE", f"Increase probability of selecting {mg} sprites.", "aesthetic"),
        Code('love'+mg, f"{mg.upper()} WORLD MODE", f"Select only {mg} sprites.", "aesthetic")])
    RESTRICTED_VANILLA_SPRITE_CODES.append(no)


# TODO: do this a better way
CAVE_CODES = [
    Code('ancientcave', "ANCIENT CAVE MODE", "", "cave"),
    Code('speedcave', "SPEED CAVE MODE", "", "cave"),
    Code('racecave', "RACE CAVE MODE", "", "cave"),
]


SPECIAL_CODES = [
    Code('christmas', 'CHIRSTMAS MODE', '', 'holiday'),
    Code('halloween', "ALL HALLOWS' EVE MODE", '', 'holiday')
]


ALL_CODES = NORMAL_CODES + MAKEOVER_MODIFIER_CODES + CAVE_CODES + SPECIAL_CODES

options_ = Options(ALL_MODES[0])
