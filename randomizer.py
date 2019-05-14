#!/usr/bin/env python3

from time import time, sleep, gmtime
from sys import argv, exit
from shutil import copyfile
import os
from hashlib import md5
from utils import (ESPER_TABLE,
                   CHAR_TABLE, COMMAND_TABLE, LOCATION_TABLE,
                   LOCATION_PALETTE_TABLE, CHARACTER_PALETTE_TABLE,
                   EVENT_PALETTE_TABLE, MALE_NAMES_TABLE, FEMALE_NAMES_TABLE,
                   FINAL_BOSS_AI_TABLE, SHOP_TABLE, WOB_TREASURE_TABLE,
                   WOR_ITEMS_TABLE, WOB_EVENTS_TABLE, SPRITE_REPLACEMENT_TABLE, RIDING_SPRITE_TABLE,
                   MOOGLE_NAMES_TABLE, SKIP_EVENTS_TABLE, DANCE_NAMES_TABLE,
                   Substitution, shorttexttable, name_to_bytes,
                   hex2int, int2bytes, read_multi, write_multi,
                   generate_swapfunc, shift_middle, get_palette_transformer,
                   battlebg_palettes, shuffle_char_hues, generate_character_palette, set_randomness_multiplier,
                   mutate_index, utilrandom as random, open_mei_fallback,
                   dialogue_to_bytes)
from skillrandomizer import (SpellBlock, CommandBlock, SpellSub, ComboSpellSub,
                             RandomSpellSub, MultipleSpellSub, ChainSpellSub,
                             get_ranked_spells, get_spell)
from monsterrandomizer import (MonsterGraphicBlock, get_monsters,
                               get_metamorphs, get_ranked_monsters,
                               shuffle_monsters, get_monster, read_ai_table)
from itemrandomizer import (reset_equippable, get_ranked_items, get_item,
                            reset_special_relics, reset_rage_blizzard,
                            reset_cursed_shield, unhack_tintinabar)
from esperrandomizer import (EsperBlock, allocate_espers)
from shoprandomizer import (ShopBlock, buy_owned_breakable_tools)
from namerandomizer import generate_name
from formationrandomizer import (get_formations, get_fsets,
                                 get_formation, get_fset)
from locationrandomizer import (EntranceSet,
                                get_locations, get_location, get_zones)
from chestrandomizer import mutate_event_items, get_event_items
from towerrandomizer import randomize_tower
from musicrandomizer import randomize_music
from menufeatures import (improve_item_display, improve_gogo_status_menu, improve_rage_menu, show_original_names, improve_dance_menu)
from decompress import Decompressor


VERSION = "2"
BETA = False
VERSION_ROMAN = "II"
if BETA:
    VERSION_ROMAN += " BETA"
TEST_ON = False
TEST_SEED = "44.abcefghijklmnopqrstuvwxyz-partyparty.42069"
TEST_FILE = "program.rom"
seed, flags = None, None
seedcounter = 1
sourcefile, outfile = None, None
fout = None


NEVER_REPLACE = ["fight", "item", "magic", "row", "def", "magitek", "lore",
                 "jump", "mimic", "xmagic", "summon", "morph", "revert"]
RESTRICTED_REPLACE = ["throw", "steal"]
ALWAYS_REPLACE = ["leap", "possess", "health", "shock"]
FORBIDDEN_COMMANDS = ["leap", "possess"]

CHARSTATNAMES = ["hp", "mp", "vigor", "speed", "stamina", "m.power",
                 "attack", "defense", "m.def", "evade", "mblock"]

MD5HASH = "e986575b98300f721ce27c180264d890"

# Dummied Umaro, Dummied Kefka, Colossus, CzarDragon, ???, ???
REPLACE_ENEMIES = [0x10f, 0x136, 0x137]
# Guardian x4, Broken Dirt Drgn, Kefka + Ice Dragon
REPLACE_FORMATIONS = [0x20e, 0x1ca, 0x1e9, 0x1fa]
KEFKA_EXTRA_FORMATION = 0x1FF  # Fake Atma
NOREPLACE_FORMATIONS = [0x232, 0x1c5, 0x1bb, 0x230, KEFKA_EXTRA_FORMATION]


TEK_SKILLS = (# [0x18, 0x6E, 0x70, 0x7D, 0x7E] +
              list(range(0x86, 0x8B)) +
              [0xA7, 0xB1] +
              list(range(0xB4, 0xBA)) +
              [0xBF, 0xCD, 0xD1, 0xD4, 0xD7, 0xDD, 0xE3])


secret_codes = {}
activated_codes = set([])
namelocdict = {}
changed_commands = set([])

randlog = {}


def log(text, section):
    global randlog
    if section not in randlog:
        randlog[section] = []
    if "\n" in text:
        text = text.split("\n")
        text = "\n".join([line.rstrip() for line in text])
    text = text.strip()
    randlog[section].append(text)


def get_logstring(ordering=None):
    global randlog
    s = ""
    if ordering is None:
        ordering = sorted([o for o in randlog.keys() if o is not None])
    ordering = [o for o in ordering if o is not None]

    for d in randlog[None]:
        s += d + "\n"

    s += "\n"
    for sectnum, section in enumerate(ordering):
        sectnum += 1
        s += "-{0:02d}- {1}\n".format(
            sectnum, " ".join([word.capitalize() for word in section.split()]))

    for sectnum, section in enumerate(ordering):
        sectnum += 1
        s += "\n" + "=" * 60 + "\n"
        s += "-{0:02d}- {1}\n".format(sectnum, section.upper())
        s += "-" * 60 + "\n"
        datas = sorted(randlog[section])
        newlines = False
        if any("\n" in d for d in datas):
            s += "\n"
            newlines = True
        for d in datas:
            s += d.strip() + "\n"
            if newlines:
                s += "\n"
    return s.strip()


def log_chests():
    areachests = {}
    event_items = get_event_items()
    for l in get_locations():
        if not l.chests:
            continue
        if l.area_name not in areachests:
            areachests[l.area_name] = ""
        areachests[l.area_name] += l.chest_contents + "\n"
    for area_name in event_items:
        if area_name not in areachests:
            areachests[area_name] = ""
        areachests[area_name] += "\n".join([e.description for e in event_items[area_name]])
    for area_name in sorted(areachests):
        chests = areachests[area_name]
        chests = "\n".join(sorted(chests.strip().split("\n")))
        chests = area_name.upper() + "\n" + chests.strip()
        log(chests, section="treasure chests")


def log_break_learn_items():
    items = sorted(get_ranked_items(), key=lambda i: i.itemid)
    breakable = [i for i in items if not i.is_consumable and i.itemtype & 0x20]
    s = "BREAKABLE ITEMS\n"
    for i in breakable:
        spell = get_spell(i.features['breakeffect'])
        indestructible = not i.features['otherproperties'] & 0x08
        s2 = "{0:13}  {1}".format(i.name + ":", spell.name)
        if indestructible:
            s2 += " (indestructible)"
        s += s2 + "\n"
    log(s, "item magic")
    s = "SPELL-TEACHING ITEMS\n"
    learnable = [i for i in items if i.features['learnrate'] > 0]
    for i in learnable:
        spell = get_spell(i.features['learnspell'])
        rate = i.features['learnrate']
        s += "{0:13}  {1} x{2}\n".format(i.name + ":", spell.name, rate)
    log(s, "item magic")


def rngstate():
    state = sum(random.getstate()[1])
    print(state)
    return state


def reseed():
    global seedcounter
    random.seed(seed + seedcounter)
    seedcounter += (seedcounter * 2) + 1


def rewrite_title(text):
    while len(text) < 20:
        text += ' '
    text = text[:20]
    fout.seek(0xFFC0)
    fout.write(bytes(text, encoding='ascii'))
    fout.seek(0xFFDB)
    fout.write(bytes([int(VERSION)]))


def rewrite_checksum(filename=None):
    if filename is None:
        filename = outfile
    MEGABIT = 0x20000
    f = open(filename, 'r+b')
    subsums = [sum(f.read(MEGABIT)) for _ in range(32)]
    checksum = sum(subsums) & 0xFFFF
    f.seek(0xFFDE)
    write_multi(f, checksum, length=2)
    f.seek(0xFFDC)
    write_multi(f, checksum ^ 0xFFFF, length=2)
    f.close()


class AutoLearnRageSub(Substitution):
    def __init__(self, require_gau):
        self.require_gau = require_gau

    @property
    def bytestring(self):
        # NOTE: This must be placed at a location called from C2/5EE5
        bs = []
        if self.require_gau:
            bs += [0xAD, 0x0B, 0x30, 0x30, 0x03]
        bs += [0x20, 0x07, 0x4A, 0xAD, 0x0A, 0x30, 0x60]
        return bytes(bs)

    def write(self, filename):
        learn_leap_sub = Substitution()
        learn_leap_sub.bytestring = bytes([0xEA] * 7)
        learn_leap_sub.set_location(0x2543E)
        learn_leap_sub.write(filename)

        vict_sub = Substitution()
        vict_sub.bytestring = bytes([0x20]) + int2bytes(self.location, length=2)
        vict_sub.set_location(0x25EE5)
        vict_sub.write(filename)

        super(AutoLearnRageSub, self).write(filename)


class AutoRecruitGauSub(Substitution):
    @property
    def bytestring(self):
        return bytes([0x50, 0xBC, 0x59, 0x10, 0x3F, 0x0B, 0x01, 0xD4, 0xFB, 0xFE])

    def write(self, filename):
        sub_addr = self.location - 0xa0000
        call_recruit_sub = Substitution()
        call_recruit_sub.bytestring = bytes([0xB2]) + int2bytes(sub_addr, length=3)
        call_recruit_sub.set_location(0xBC19C)
        call_recruit_sub.write(filename)
        gau_stays_wor_sub = Substitution()
        gau_stays_wor_sub.bytestring = bytes([0xD4, 0xFB])
        gau_stays_wor_sub.set_location(0xA5324)
        gau_stays_wor_sub.write(filename)
        gau_cant_appear_sub = Substitution()
        gau_cant_appear_sub.bytestring = bytes([0x80, 0x0C])
        gau_cant_appear_sub.set_location(0x22FB5)
        gau_cant_appear_sub.write(filename)
        REPLACE_ENEMIES.append(0x172)
        super(AutoRecruitGauSub, self).write(filename)


class EnableEsperMagicSub(Substitution):
    @property
    def bytestring(self):
        return bytes([0xA9, 0x20, 0xA6, 0x00, 0x95, 0x79, 0xE8, 0xA9, 0x24, 0x60])

    def write(self, filename):
        jsr_sub = Substitution()
        jsr_sub.bytestring = bytes([0x20]) + int2bytes(self.location, length=2) + bytes([0xEA])
        jsr_sub.set_location(0x34D3D)
        jsr_sub.write(filename)
        super(EnableEsperMagicSub, self).write(filename)


class FreeBlock:
    def __init__(self, start, end):
        self.start = start
        self.end = end

    @property
    def size(self):
        return self.end - self.start

    def unfree(self, start, length):
        end = start + length
        if start < self.start:
            raise Exception("Used space out of bounds (left)")
        elif end > self.end:
            raise Exception("Used space out of bounds (right)")
        newfree = []
        if self.start != start:
            newfree.append(FreeBlock(self.start, start))
        if end != self.end:
            newfree.append(FreeBlock(end, self.end))
        self.start, self.end = None, None
        return newfree


def get_appropriate_freespace(freespaces, size):
    candidates = [c for c in freespaces if c.size >= size]
    if not candidates:
        raise Exception("Not enough free space")

    candidates = sorted(candidates, key=lambda f: f.size)
    return candidates[0]


def determine_new_freespaces(freespaces, myfs, size):
    freespaces.remove(myfs)
    fss = myfs.unfree(myfs.start, size)
    freespaces.extend(fss)
    return freespaces


equip_offsets = {"weapon": 15,
                 "shield": 16,
                 "helm": 17,
                 "armor": 18,
                 "relic1": 19,
                 "relic2": 20}


class CharacterBlock:
    def __init__(self, address, name):
        self.address = hex2int(address)
        self.name = name.lower().capitalize()
        self.newname = self.name.upper()
        self.battle_commands = [0x00, None, None, None]
        self.id = None
        self.beserk = False
        self.original_appearance = None
        self.new_appearance = None
        self.natural_magic = None
        self.palette = None

    def __repr__(self):
        s = "{0:02d}. {1}".format(self.id+1, self.newname) + "\n"
        command_names = []
        for c in self.command_objs:
            if c is not None:
                command_names.append(c.name.lower())
        s += "Commands: "
        s += ", ".join(command_names) + "\n"
        if self.original_appearance and self.new_appearance:
            s += "Looks like: %s\n" % self.new_appearance
            s += "Originally: %s\n" % self.original_appearance

        from utils import make_table
        statblurbs = {}
        for name in CHARSTATNAMES:
            blurb = "{0:8} {1}".format(name.upper() + ":", self.stats[name])
            statblurbs[name] = blurb
        column1 = [statblurbs[n] for n in ["hp", "mp", "evade", "mblock"]]
        column2 = [statblurbs[n] for n in ["vigor", "m.power", "speed", "stamina"]]
        column3 = [statblurbs[n] for n in ["attack", "defense", "m.def"]]
        s += make_table([column1, column2, column3]) + "\n"
        if self.id < 14:
            s += "Notable equipment: "
            s += ", ".join([n.name for n in self.get_notable_equips()])
            s += "\n"
        if self.natural_magic is not None:
            s += "Has natural magic.\n"
            for level, spell in self.natural_magic:
                s += "  LV %s - %s\n" % (level, spell.name)
        return s.strip()

    def get_notable_equips(self):
        items = [i for i in get_ranked_items() if
                 i.equippable & (1 << self.id) and not i.imp_only]
        weapons = [i for i in items if i.is_weapon]
        rare = [i for i in items if not i.is_weapon and
                bin(i.equippable).count('1') <= 5 and
                i.rank() > 4000]
        rare.extend([w for w in weapons if w.rank() > 50000])
        if self.id == 12:
            rare = [r for r in rare if not r.features['special1'] & 0x7C]
        notable = []
        if weapons:
            weapons = sorted(weapons, key=lambda w: w.rank(), reverse=True)
            notable.extend(weapons[:2])
        if rare:
            rare = sorted(rare, key=lambda r: r.rank(), reverse=True)
            notable.extend(rare[:8])
        notable = set(notable)
        return sorted(notable, key=lambda n: n.itemid)

    def associate_command_objects(self, commands):
        self.command_objs = []
        for c in self.battle_commands:
            command = [cmd for cmd in commands if cmd.id == c]
            if not command:
                command = None
            else:
                command = command[0]
            self.command_objs.append(command)

    def set_battle_command(self, slot, command=None, command_id=None):
        if command:
            command_id = command.id
        self.battle_commands[slot] = command_id
        if self.id == 12:
            self.battle_commands[0] = 0x12

    def write_battle_commands(self, fout):
        for i, command in enumerate(self.battle_commands):
            if command is None:
                if i == 0:
                    command = 0
                else:
                    continue
            fout.seek(self.address + 2 + i)
            fout.write(bytes([command]))

    def write_default_equipment(self, fout, equipid, equiptype):
        fout.seek(self.address + equip_offsets[equiptype])
        fout.write(bytes([equipid]))

    def mutate_stats(self, fout, read_only=False):

        def mutation(base):
            while True:
                value = max(base // 2, 1)
                if self.beserk:
                    value += 1

                value += random.randint(0, value) + random.randint(0, value)
                while random.randint(1, 10) == 10:
                    value = max(value // 2, 1)
                    value += random.randint(0, value) + random.randint(0, value)
                value = max(1, min(value, 0xFE))

                if not self.beserk:
                    break
                elif value >= base:
                    break

            return value

        self.stats = {}
        fout.seek(self.address)
        hpmp = bytes(fout.read(2))
        if not read_only:
            hpmp = bytes([mutation(v) for v in hpmp])
            fout.seek(self.address)
            fout.write(hpmp)
        self.stats['hp'], self.stats['mp'] = tuple(hpmp)

        fout.seek(self.address + 6)
        stats = fout.read(9)
        if not read_only:
            stats = bytes([mutation(v) for v in stats])
            fout.seek(self.address + 6)
            fout.write(stats)
        for name, value in zip(CHARSTATNAMES[2:], stats):
            self.stats[name] = value

        fout.seek(self.address + 21)
        level_run = fout.read(1)[0]
        run = level_run & 0x03
        level = (level_run & 0x0C) >> 2
        run_map = {
            0: [70, 20, 9, 1],
            1: [13, 70, 13, 4],
            2: [4, 13, 70, 13],
            3: [1, 9, 20, 70]
        }

        level_map = {
            0: [70, 20, 5, 5],  # avg. level + 0
            1: [18, 70, 10, 2],  # avg. level + 2
            2: [9, 20, 70, 1],  # avg. level + 5
            3: [20, 9, 1, 70]   # avg. level - 3
        }

        if not read_only:
            run_chance = random.randint(0,99)
            for i, prob in enumerate(run_map[run]):
                run_chance -= prob
                if prob < 0:
                    run = i
                    break

            # Don't randomize level average values if worringtriad is active
            # Also don't randomize Terra's level because it gets added for
            # every loop through the title screen, apparently.
            if 'worringtriad' not in activated_codes and self.id != 0:
                level_chance = random.randint(0,99)
                for i, prob in enumerate(level_map[level]):
                    level_chance -= prob
                    if level_chance < 0:
                        level = i
                        break
            fout.seek(self.address + 21)
            level_run = (level_run & 0xF0) | level << 2 | run
            fout.write(bytes([level_run]))

    def become_invincible(self, fout):
        fout.seek(self.address + 11)
        stats = bytes([0xFF, 0xFF, 0x80, 0x80])
        fout.write(stats)

    def set_id(self, i):
        self.id = i
        if self.id == 13:
            self.beserk = True
        palettes = dict(enumerate([2, 1, 4, 4, 0, 0, 0, 3, 3, 4, 5, 3, 3, 5,
                                   3, 0, 0, 0, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5,
                                   5, 2, 4, 2, 1, 1, 0, 0, 0, 0, 0, 0, 0, 3,
                                   3, 3]))
        if self.id in palettes:
            self.palette = palettes[self.id]


class WindowBlock():
    def __init__(self, windowid):
        self.pointer = 0x2d1c00 + (windowid * 0x20)

    def read_data(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.pointer)
        self.palette = []
        if 'christmas' in activated_codes:
            self.palette = [(0x1c, 0x02, 0x04)] * 2 + [(0x19, 0x00, 0x06)] * 2 + [(0x03, 0x0d, 0x07)] * 2 + [(0x18,0x18,0x18)] + [(0x04, 0x13, 0x0a)]
        elif 'halloween' in activated_codes:
            self.palette = [(0x04, 0x0d, 0x15)] * 2 + [(0x00, 0x00, 0x00)] + [(0x0b, 0x1d, 0x15)] + [(0x00,0x11,0x00)] + [(0x1e, 0x00, 0x00)] + [(0x1d, 0x1c, 0x00)] + [(0x1c, 0x1f, 0x1b)]
        else:
            for i in range(0x8):
                color = read_multi(f, length=2)
                blue = (color & 0x7c00) >> 10
                green = (color & 0x03e0) >> 5
                red = color & 0x001f
                self.negabit = color & 0x8000
                self.palette.append((red, green, blue))
        f.close()

    def write_data(self, fout):
        fout.seek(self.pointer)
        for (red, green, blue) in self.palette:
            color = (blue << 10) | (green << 5) | red
            write_multi(fout, color, length=2)

    def mutate(self):
        if 'halloween' in activated_codes:
            return
        def cluster_colors(colors):
            def distance(cluster, value):
                average = sum([sum(c) for (i, c) in cluster]) / len(cluster)
                return abs(sum(value) - average)

            clusters = []
            clusters.append(set([colors[0]]))
            colors = colors[1:]

            if random.randint(1, 3) != 3:
                i = random.randint(1, len(colors)-3)
                clusters.append(set([colors[i]]))
                colors.remove(colors[i])

            clusters.append(set([colors[-1]]))
            colors = colors[:-1]

            for i, c in colors:
                ideal = min(clusters, key=lambda cl: distance(cl, c))
                ideal.add((i, c))

            return clusters

        ordered_palette = list(zip(list(range(8)), self.palette))
        ordered_palette = sorted(ordered_palette, key=lambda i_c1: sum(i_c1[1]))
        newpalette = [None] * 8
        clusters = cluster_colors(ordered_palette)
        prevdarken = random.uniform(0.3, 0.9)
        for cluster in clusters:
            degree = random.randint(-75, 75)
            darken = random.uniform(prevdarken, min(prevdarken*1.1, 1.0))
            darkener = lambda c: int(round(c * darken))
            if 'christmas' in activated_codes:
                hueswap = lambda w: w
            else:
                hueswap = generate_swapfunc()
            for i, cs in sorted(cluster, key=lambda i_c: sum(i_c[1])):
                newcs = shift_middle(cs, degree, ungray=True)
                newcs = list(map(darkener, newcs))
                newcs = hueswap(newcs)
                newpalette[i] = tuple(newcs)
            prevdarken = darken

        self.palette = newpalette


def commands_from_table(tablefile):
    commands = []
    for i, line in enumerate(open(tablefile)):
        line = line.strip()
        if line[0] == '#':
            continue

        while '  ' in line:
            line = line.replace('  ', ' ')
        c = CommandBlock(*line.split(','))
        c.set_id(i)
        commands.append(c)
    return commands


character_list = []


def get_characters():
    if character_list:
        return character_list

    for i, line in enumerate(open(CHAR_TABLE)):
        line = line.strip()
        if line[0] == '#':
            continue

        while '  ' in line:
            line = line.replace('  ', ' ')
        c = CharacterBlock(*line.split(','))
        c.set_id(i)
        character_list.append(c)
    return get_characters()


def get_character(i):
    characters = get_characters()
    return [c for c in characters if c.id == i][0]


all_espers = None


def get_espers():
    global all_espers
    if all_espers:
        return all_espers

    all_espers = []
    for i, line in enumerate(open(ESPER_TABLE)):
        line = line.strip()
        if line[0] == '#':
            continue

        while '  ' in line:
            line = line.replace('  ', ' ')
        c = EsperBlock(*line.split(','))
        c.read_data(sourcefile)
        c.set_id(i)
        all_espers.append(c)
    return get_espers()


def randomize_colosseum(filename, fout, pointer):
    item_objs = get_ranked_items(filename)
    monster_objs = get_ranked_monsters(filename, bosses=False)
    items = [i.itemid for i in item_objs]
    monsters = [m.id for m in monster_objs]
    results = []
    for i in range(0xFF):
        try:
            index = items.index(i)
        except ValueError:
            continue
        trade = index
        while index == trade:
            trade = index
            while random.randint(1, 3) < 3:
                trade += random.randint(-3, 3)
                trade = max(0, min(trade, len(items)-1))

        opponent = trade
        opponent = max(0, min(opponent, len(monsters)-1))
        while random.randint(1, 3) < 3:
            opponent += random.randint(-1, 1)
            opponent = max(0, min(opponent, len(monsters)-1))
        trade = items[trade]
        opponent = monsters[opponent]
        wager_obj = [j for j in item_objs if j.itemid == i][0]
        opponent_obj = [m for m in monster_objs if m.id == opponent][0]
        win_obj = [j for j in item_objs if j.itemid == trade][0]
        fout.seek(pointer + (i*4))
        fout.write(bytes([opponent]))
        fout.seek(pointer + (i*4) + 2)
        fout.write(bytes([trade]))

        if abs(wager_obj.rank() - win_obj.rank()) >= 5000 and random.randint(1, 2) == 2:
            hidden = True
            fout.write(b'\xFF')
        else:
            hidden = False
            fout.write(b'\x00')
        results.append((wager_obj, opponent_obj, win_obj, hidden))


    results = sorted(results, key=lambda a_b_c_d: a_b_c_d[0].name)

    coliseum_run_sub = Substitution()
    coliseum_run_sub.bytestring = [0xEA] * 2
    coliseum_run_sub.set_location(0x25BEF)
    coliseum_run_sub.write(fout)

    return results


def randomize_slots(filename, fout, pointer):
    spells = get_ranked_spells(filename)
    spells = [s for s in spells if s.spellid >= 0x36]
    attackspells = [s for s in spells if s.target_enemy_default]
    quarter = len(attackspells) // 4
    eighth = quarter // 2
    jokerdoom = ((eighth * 6) + random.randint(0, eighth) +
                 random.randint(0, eighth))
    jokerdoom += random.randint(0, len(attackspells)-(8*eighth)-1)
    jokerdoom = attackspells[jokerdoom]

    def get_slots_spell(i):
        if i in [0, 1]:
            return jokerdoom
        elif i == 3:
            return None
        elif i in [4, 5, 6]:
            half = len(spells) // 2
            index = random.randint(0, half) + random.randint(0, half)
        elif i == 2:
            third = len(spells) // 3
            index = random.randint(third, len(spells)-1)
        elif i == 7:
            twentieth = len(spells)//20
            index = random.randint(0, twentieth)
            while random.randint(1, 3) == 3:
                index += random.randint(0, twentieth)
            index = min(index, len(spells)-1)

        spell = spells[index]
        return spell

    slotNames = ["JokerDoom", "JokerDoom", "Dragons", "Bars", "Airships", "Chocobos", "Gems", "Fail"]
    used = []
    for i in range(1, 8):
        while True:
            spell = get_slots_spell(i)
            if spell is None or spell.spellid not in used:
                break
        if spell:
            from skillrandomizer import spellnames;
            slotString = "%s: %s" % (slotNames[i], spellnames[spell.spellid])
            log(slotString,"slots")
            used.append(spell.spellid)
            fout.seek(pointer+i)
            fout.write(bytes([spell.spellid]))


def auto_recruit_gau():
    args = AutoRecruitGauSub()
    args.set_location(0xcfe1a)
    args.write(fout)

    recruit_gau_sub = Substitution()
    recruit_gau_sub.bytestring = bytes([0x89, 0xFF])
    recruit_gau_sub.set_location(0x24856)
    recruit_gau_sub.write(fout)


def manage_commands(commands):
    characters = get_characters()

    alrs = AutoLearnRageSub(require_gau=False)
    alrs.set_location(0x23b73)
    alrs.write(fout)

    learn_lore_sub = Substitution()
    learn_lore_sub.bytestring = bytes([0xEA, 0xEA, 0xF4, 0x00, 0x00, 0xF4, 0x00,
                                 0x00])
    learn_lore_sub.set_location(0x236E4)
    learn_lore_sub.write(fout)

    learn_dance_sub = Substitution()
    learn_dance_sub.bytestring = bytes([0xEA] * 2)
    learn_dance_sub.set_location(0x25EE8)
    learn_dance_sub.write(fout)

    learn_swdtech_sub = Substitution()
    learn_swdtech_sub.bytestring = bytes([0xEB,       # XBA
                                    0x48,       # PHA
                                    0xEB,       # XBA
                                    0xEA])
    learn_swdtech_sub.set_location(0x261C7)
    learn_swdtech_sub.write(fout)
    learn_swdtech_sub.bytestring = bytes([0x4C, 0xDA, 0xA1, 0x60])
    learn_swdtech_sub.set_location(0xA18A)
    learn_swdtech_sub.write(fout)

    learn_blitz_sub = Substitution()
    learn_blitz_sub.bytestring = bytes([0xF0, 0x09])
    learn_blitz_sub.set_location(0x261CE)
    learn_blitz_sub.write(fout)
    learn_blitz_sub.bytestring = bytes([0xD0, 0x04])
    learn_blitz_sub.set_location(0x261D3)
    learn_blitz_sub.write(fout)
    learn_blitz_sub.bytestring = bytes([0x68,       # PLA
                                  0xEB,       # XBA
                                  0xEA, 0xEA, 0xEA, 0xEA, 0xEA])
    learn_blitz_sub.set_location(0x261D9)
    learn_blitz_sub.write(fout)
    learn_blitz_sub.bytestring = bytes([0xEA] * 4)
    learn_blitz_sub.set_location(0x261E3)
    learn_blitz_sub.write(fout)
    learn_blitz_sub.bytestring = bytes([0xEA])
    learn_blitz_sub.set_location(0xA200)
    learn_blitz_sub.write(fout)

    learn_multiple_sub = Substitution()
    learn_multiple_sub.set_location(0xA1B4)
    reljump = 0xFE - (learn_multiple_sub.location - 0xA186)
    learn_multiple_sub.bytestring = bytes([0xF0, reljump])
    learn_multiple_sub.write(fout)

    learn_multiple_sub.set_location(0xA1D6)
    reljump = 0xFE - (learn_multiple_sub.location - 0xA18A)
    learn_multiple_sub.bytestring = bytes([0xF0, reljump])
    learn_multiple_sub.write(fout)

    learn_multiple_sub.set_location(0x261DD)
    learn_multiple_sub.bytestring = bytes([0xEA] * 3)
    learn_multiple_sub.write(fout)

    rage_blank_sub = Substitution()
    rage_blank_sub.bytestring = bytes([0x01] + ([0x00] * 31))
    rage_blank_sub.set_location(0x47AA0)
    rage_blank_sub.write(fout)

    eems = EnableEsperMagicSub()
    eems.set_location(0x3F091)
    eems.write(fout)

    # Let x-magic user use magic menu.
    enable_xmagic_menu_sub = Substitution()
    enable_xmagic_menu_sub.bytestring = bytes([0xDF, 0x78, 0x4D, 0xC3, # CMP $C34D78,X
    0xF0, 0x07, # BEQ
    0xE0, 0x01, 0x00, # CPX #$0001
    0xD0, 0x02, # BNE
    0xC9, 0x17, # CMP #$17
    0x6b        # RTL
    ])
    enable_xmagic_menu_sub.set_location(0x3F09B)
    enable_xmagic_menu_sub.write(fout)

    enable_xmagic_menu_sub.bytestring = bytes([0x22, 0x9B, 0xF0, 0xC3])
    enable_xmagic_menu_sub.set_location(0x34d56)
    enable_xmagic_menu_sub.write(fout)

    # Prevent Runic, SwdTech, and Capture from being disabled/altered
    protect_battle_commands_sub = Substitution()
    protect_battle_commands_sub.bytestring = bytes([0x03, 0xFF, 0xFF, 0x0C,
                                              0x17, 0x02, 0xFF, 0x00])
    protect_battle_commands_sub.set_location(0x252E9)
    protect_battle_commands_sub.write(fout)

    enable_morph_sub = Substitution()
    enable_morph_sub.bytestring = bytes([0xEA] * 2)
    enable_morph_sub.set_location(0x25410)
    enable_morph_sub.write(fout)

    enable_mpoint_sub = Substitution()
    enable_mpoint_sub.bytestring = bytes([0xEA] * 2)
    enable_mpoint_sub.set_location(0x25E38)
    enable_mpoint_sub.write(fout)

    ungray_statscreen_sub = Substitution()
    ungray_statscreen_sub.bytestring = bytes([0x20, 0x6F, 0x61, 0x30, 0x26, 0xEA,
                                        0xEA, 0xEA])
    ungray_statscreen_sub.set_location(0x35EE1)
    ungray_statscreen_sub.write(fout)

    fanatics_fix_sub = Substitution()
    if "metronome" in activated_codes:
        fanatics_fix_sub.bytestring = bytes([0xA9, 0x1D])
    else:
        fanatics_fix_sub.bytestring = bytes([0xA9, 0x15])
    fanatics_fix_sub.set_location(0x2537E)
    fanatics_fix_sub.write(fout)

    invalid_commands = ["fight", "item", "magic", "xmagic",
                        "def", "row", "summon", "revert"]
    if random.randint(1, 5) != 5:
        invalid_commands.append("magitek")

    if 'w' not in flags:
        invalid_commands.extend(FORBIDDEN_COMMANDS)

    invalid_commands = set([c for c in commands.values() if c.name in invalid_commands])

    def populate_unused():
        unused_commands = set(commands.values())
        unused_commands = unused_commands - invalid_commands
        return sorted(unused_commands, key=lambda c: c.name)

    unused = populate_unused()
    xmagic_taken = False
    random.shuffle(characters)
    for c in characters:
        if c.id == 11:
            # Fixing Gau
            c.set_battle_command(0, commands["fight"])

        if 'metronome' in activated_codes:
            c.set_battle_command(0, command_id=0)
            c.set_battle_command(1, command_id=0x1D)
            c.set_battle_command(2, command_id=2)
            c.set_battle_command(3, command_id=1)
            c.write_battle_commands(fout)
            continue

        if 'collateraldamage' in activated_codes:
            c.set_battle_command(1, command_id=0xFF)
            c.set_battle_command(2, command_id=0xFF)
            c.set_battle_command(3, command_id=1)
            c.write_battle_commands(fout)
            continue

        if c.id <= 11:
            using = []
            while not using:
                if random.randint(0, 1):
                    using.append(commands["item"])
                if random.randint(0, 1):
                    if not xmagic_taken:
                        using.append(commands["xmagic"])
                        xmagic_taken = True
                    else:
                        using.append(commands["magic"])
            while len(using) < 3:
                if not unused:
                    unused = populate_unused()
                com = random.choice(unused)
                unused.remove(com)
                if com not in using:
                    using.append(com)
                    if com.name == "morph":
                        invalid_commands.add(com)
                        morph_char_sub = Substitution()
                        morph_char_sub.bytestring = bytes([0xC9, c.id])
                        morph_char_sub.set_location(0x25E32)
                        morph_char_sub.write(fout)
            for i, command in enumerate(reversed(using)):
                c.set_battle_command(i+1, command=command)
        else:
            c.set_battle_command(1, command_id=0xFF)
            c.set_battle_command(2, command_id=0xFF)
        c.write_battle_commands(fout)

    magitek_skills = [SpellBlock(i, sourcefile) for i in range(0x83, 0x8B)]
    for ms in magitek_skills:
        ms.fix_reflect(fout)

    return commands


def manage_tempchar_commands():
    if "metronome" in activated_codes:
        return
    characters = get_characters()
    chardict = dict([(c.id, c) for c in characters])
    basicpool = set(range(3, 0x1E)) - changed_commands - set([0x4, 0x11, 0x14, 0x15, 0x19])
    mooglepool, banonpool, ghostpool, leopool = list(map(set, [basicpool]*4))
    for key in [0, 1, 0xA]:
        c = chardict[key]
        mooglepool |= set(c.battle_commands)
    for key in [4, 5]:
        c = chardict[key]
        banonpool |= set(c.battle_commands)
    ghostpool = banonpool | set(chardict[3].battle_commands)
    for key in chardict:
        c = chardict[key]
        leopool |= set(c.battle_commands)
    pools = [banonpool, leopool] + ([ghostpool]*2) + ([mooglepool]*10)
    banned = set([0x0, 0x1, 0x2, 0x17, 0xFF])
    # Guest characters with Lore command will have an empty list, so make sure they don't have it.
    if 0xC not in changed_commands:
        banned.add(0xC)
    for i, pool in zip(range(0xE, 0x1C), pools):
        pool = sorted([c for c in pool if c and c not in banned])
        a, b = tuple(random.sample(pool, 2))
        chardict[i].set_battle_command(1, command_id=a)
        chardict[i].set_battle_command(2, command_id=b)
        chardict[i].set_battle_command(3, command_id=0x1)
        chardict[i].write_battle_commands(fout)

    for i in range(0xE, 0x1C):
        c = chardict[i]
        if c.battle_commands[1] == 0xFF and c.battle_commands[2] != 0xFF:
            c.set_battle_command(1, command_id=c.battle_commands[2])
        if c.battle_commands[1] == c.battle_commands[2]:
            c.set_battle_command(2, command_id=0xFF)
        c.write_battle_commands(fout)


def manage_commands_new(commands):
    # note: x-magic targets random party member
    # replacing lore screws up enemy skills
    # replacing jump makes the character never come back down
    # replacing mimic screws up enemy skills too
    characters = get_characters()
    freespaces = []
    freespaces.append(FreeBlock(0x2A65A, 0x2A800))
    freespaces.append(FreeBlock(0x2FAAC, 0x2FC6D))

    multibannedlist = [0x63, 0x58, 0x5B]

    def multibanned(spells):
        if isinstance(spells, int):
            return spells in multibannedlist
        spells = [s for s in spells if s.spellid not in multibannedlist]
        return spells

    valid = set(list(commands))
    valid = sorted(valid - set(["row", "def"]))
    used = []
    all_spells = get_ranked_spells(sourcefile)
    randomskill_names = set([])
    for c in commands.values():
        if c.name in NEVER_REPLACE:
            continue

        if "replaceeverything" not in activated_codes:
            if c.name in RESTRICTED_REPLACE and random.choice([True, False]):
                continue

            if c.name not in ALWAYS_REPLACE:
                if random.randint(1, 100) > 50:
                    continue

        changed_commands.add(c.id)
        x = random.randint(1, 3)
        if x <= 1:
            random_skill = False
            combo_skill = False
        elif x <= 2:
            random_skill = True
            combo_skill = False
        else:
            random_skill = False
            combo_skill = True

        if "allcombos" in activated_codes:
            random_skill = False
            combo_skill = True

        POWER_LEVEL = 130
        scount = 1
        while random.randint(1, 5) == 5:
            scount += 1
        scount = min(scount, 9)
        if "endless9" in activated_codes:
            scount = 9

        def get_random_power():
            basepower = POWER_LEVEL // 2
            power = basepower + random.randint(0, basepower)
            while True:
                power += random.randint(0, basepower)
                if random.choice([True, False]):
                    break
            return power

        while True:
            c.read_properties(sourcefile)
            if not (random_skill or combo_skill):
                power = get_random_power()

                def spell_is_valid(s):
                    if not s.valid:
                        return False
                    if s.spellid in used:
                        return False
                    return s.rank() <= power

                valid_spells = list(filter(spell_is_valid, all_spells))
                if not valid_spells:
                    continue

                sb = random.choice(valid_spells)
                used.append(sb.spellid)
                c.targeting = sb.targeting
                c.targeting = c.targeting & (0xFF ^ 0x10)  # never autotarget
                if not c.targeting & 0x20 and random.randint(1, 15) == 15:
                    c.targeting = 0xC0  # target random individual (both sides)
                if not c.targeting & 0x20 and random.randint(1, 10) == 10:
                    c.targeting |= 0x28  # target random individual
                    c.targeting &= 0xFE
                if (c.targeting & 0x08 and not c.targeting & 0x02
                        and random.randint(1, 5) == 5):
                    c.targeting = 0x04  # target everyone
                if (not c.targeting & 0x64 and
                        sb.spellid not in [0x30, 0x31] and
                        random.randint(1, 5) == 5):
                    c.targeting = 2  # only target self
                if sb.spellid in [0xAB]:  # megazerk
                    c.targeting = random.choice([0x29, 0x6E, 0x6C, 0x27, 0x4])
                if sb.spellid in [0x2B]:  # quick
                    c.targeting = random.choice([0x2, 0x2A, 0xC0, 0x1])

                if c.targeting & 3 == 3:
                    c.targeting ^= 2  # allow targeting either side

                c.properties = 3
                if sb.spellid in [0x23, 0xA3]:
                    c.properties |= 0x4  # enable while imped
                c.unset_retarget(fout)
                c.write_properties(fout)

                if scount == 1 or multibanned(sb.spellid):
                    s = SpellSub(spellid=sb.spellid)
                else:
                    if scount >= 4 or random.choice([True, False]):
                        s = MultipleSpellSub()
                        s.set_spells(sb.spellid)
                        s.set_count(scount)
                    else:
                        s = ChainSpellSub()
                        s.set_spells(sb.spellid)

                newname = sb.name
            elif random_skill:
                power = 10000
                c.properties = 3
                c.set_retarget(fout)
                valid_spells = [v for v in all_spells if
                                v.spellid <= 0xED and v.valid]

                if scount == 1:
                    s = RandomSpellSub()
                else:
                    valid_spells = multibanned(valid_spells)
                    if scount >= 4 or random.choice([True, False]):
                        s = MultipleSpellSub()
                        s.set_count(scount)
                    else:
                        s = ChainSpellSub()

                try:
                    s.set_spells(valid_spells)
                except ValueError:
                    continue

                if s.name in randomskill_names:
                    continue
                randomskill_names.add(s.name)
                c.targeting = 0x2
                if len(s.spells) == 0:
                    c.targeting = 0x4
                elif len(set([spell.targeting for spell in s.spells])) == 1:
                    c.targeting = s.spells[0].targeting
                elif any([spell.target_everyone and
                          not spell.target_one_side_only
                          for spell in s.spells]):
                    c.targeting = 0x4
                else:
                    if not any([spell.target_enemy_default or
                                (spell.target_everyone and
                                 not spell.target_one_side_only)
                               for spell in s.spells]):
                        c.targeting = 0x2e
                    if all([spell.target_enemy_default for spell in s.spells]):
                        c.targeting = 0x6e

                c.write_properties(fout)
                newname = s.name
            elif combo_skill:
                ALWAYS_FIRST = []
                ALWAYS_LAST = [
                    "Palidor", "Quadra Slam", "Quadra Slice", "Spiraler",
                    "Pep Up", "Exploder", "Quick"
                    ]
                WEIGHTED_FIRST = [
                    "Life", "Life 2",
                    ]
                WEIGHTED_LAST = [
                    "ChokeSmoke",
                    ]
                for mylist in [ALWAYS_FIRST, ALWAYS_LAST,
                               WEIGHTED_FIRST, WEIGHTED_LAST]:
                    assert (len([s for s in all_spells if s.name in mylist])
                            == len(mylist))

                def spell_is_valid(s, p):
                    if not s.valid:
                        return False
                    #if multibanned(s.spellid):
                    #    return False
                    return s.rank() <= p

                myspells = []
                while len(myspells) < 2:
                    power = get_random_power()
                    valid_spells = [s for s in all_spells
                                    if spell_is_valid(s, power)
                                    and s not in myspells]
                    if not valid_spells:
                        continue
                    myspells.append(random.choice(valid_spells))
                    targeting_conflict = (len(set([s.targeting & 0x40
                                                   for s in myspells])) > 1)
                    names = set([s.name for s in myspells])
                    if (len(names & set(ALWAYS_FIRST)) == 2
                            or len(names & set(ALWAYS_LAST)) == 2):
                        myspells = []
                    if targeting_conflict and all([s.targeting & 0x10
                                                   for s in myspells]):
                        myspells = []

                c.unset_retarget(fout)
                #if random.choice([True, False]):
                #    nopowers = [s for s in myspells if not s.power]
                #    powers = [s for s in myspells if s.power]
                #    myspells = nopowers + powers
                for s in myspells:
                    if (s.name in WEIGHTED_FIRST
                            and random.choice([True, False])):
                        myspells.remove(s)
                        myspells.insert(0, s)
                    if ((s.name in WEIGHTED_LAST
                                or s.target_auto or s.randomize_target
                                or s.retargetdead or not s.target_group)
                            and random.choice([True, False])):
                        myspells.remove(s)
                        myspells.append(s)

                autotarget = [s for s in myspells if s.target_auto]
                noauto = [s for s in myspells if not s.target_auto]
                autotarget_warning = (0 < len(autotarget) < len(myspells))
                if targeting_conflict:
                    myspells = noauto + autotarget
                for s in myspells:
                    if s.name in ALWAYS_FIRST:
                        myspells.remove(s)
                        myspells.insert(0, s)
                    if s.name in ALWAYS_LAST:
                        myspells.remove(s)
                        myspells.append(s)
                css = ComboSpellSub(myspells)

                c.properties = 3
                c.targeting = 0
                for mask in [0x01, 0x40]:
                    for s in css.spells:
                        if s.targeting & mask:
                            c.targeting |= mask
                            break

                # If the first spell is single-target only, but the combo allows
                # targeting multiple, it'll randomly pick one target and do both
                # spells on that one.
                # So, only allow select multiple targets if the first one does.
                c.targeting |= css.spells[0].targeting & 0x20

                if css.spells[0].targeting & 0x40 == c.targeting & 0x40:
                    c.targeting |= (css.spells[0].targeting & 0x4)

                if (all(s.targeting & 0x08 for s in css.spells)
                        or c.targeting & 0x24 == 0x24):
                    c.targeting |= 0x08

                if (all(s.targeting & 0x02 for s in css.spells)
                        and not targeting_conflict):
                    c.targeting |= 0x02

                if targeting_conflict and c.targeting & 0x20:
                    c.targeting |= 1

                if targeting_conflict and random.randint(1, 10) == 10:
                    c.targeting = 0x04

                if (c.targeting & 1 and not c.targeting & 8
                        and random.randint(1, 30) == 30):
                    c.targeting = 0xC0

                if c.targeting & 3 == 3:
                    c.targeting ^= 2  # allow targeting either side

                c.targeting = c.targeting & (0xFF ^ 0x10)  # never autotarget
                c.write_properties(fout)

                scount = max(1, scount-1)
                if autotarget_warning and targeting_conflict:
                    scount = 1
                css.name = ""
                if scount >= 2:
                    if scount >= 4 or random.choice([True, False]):
                        new_s = MultipleSpellSub()
                        new_s.set_spells(css)
                        new_s.set_count(scount)
                    else:
                        new_s = ChainSpellSub()
                        new_s.set_spells(css)
                    if len(css.spells) == len(multibanned(css.spells)):
                        css = new_s

                if (isinstance(css, MultipleSpellSub) or
                        isinstance(css, ChainSpellSub)):
                    namelengths = [3, 2]
                else:
                    namelengths = [4, 3]
                random.shuffle(namelengths)
                names = [s.name for s in css.spells]
                names = [n.replace('-', '') for n in names]
                names = [n.replace('.', '') for n in names]
                names = [n.replace(' ', '') for n in names]
                for i in range(2):
                    if len(names[i]) < namelengths[i]:
                        namelengths = list(reversed(namelengths))
                newname = names[0][:namelengths[0]]
                newname += names[1][:namelengths[1]]

                s = css
            else:
                assert False
            break

        myfs = get_appropriate_freespace(freespaces, s.size)
        s.set_location(myfs.start)
        if not hasattr(s, "bytestring") or not s.bytestring:
            s.generate_bytestring()
        s.write(fout)
        c.setpointer(s.location, fout)
        freespaces = determine_new_freespaces(freespaces, myfs, s.size)

        if len(newname) > 7:
            newname = newname.replace('-', '')
            newname = newname.replace('.', '')

        if isinstance(s, SpellSub):
            pass
        elif isinstance(s, RandomSpellSub):
            newname = "R-%s" % newname
        elif isinstance(s, MultipleSpellSub):
            if s.count == 2:
                newname = "W-%s" % newname
            else:
                newname = "%sx%s" % (s.count, newname)
        elif isinstance(s, ChainSpellSub):
            newname = "?-%s" % newname

        # Disable menu screens for replaced commands.
        for i, name in enumerate(['swdtech', 'blitz', 'lore', 'rage', 'dance']):
            if c.name == name:
                fout.seek(0x34D7A + i)
                fout.write(b'\xEE')

        c.newname(newname, fout)
        c.unsetmenu(fout)
        c.allow_while_confused(fout)
        if "playsitself" in activated_codes:
            c.allow_while_berserk(fout)
        else:
            c.disallow_while_berserk(fout)

        command_descr = "{0}\n-------\n{1}".format(c.name, str(s))
        log(command_descr, 'commands')

    if "metronome" in activated_codes:
        magitek = [c for c in commands.values() if c.name == "magitek"][0]
        magitek.read_properties(sourcefile)
        magitek.targeting = 0x04
        magitek.set_retarget(fout)
        if "endless9" in activated_codes:
            s = MultipleSpellSub()
            s.set_count(9)
            magitek.newname("9xChaos", fout)
            s.set_spells([])
        else:
            s = RandomSpellSub()
            magitek.newname("R-Chaos", fout)
            s.set_spells([], [], "Chaos")
        magitek.write_properties(fout)
        magitek.unsetmenu(fout)
        magitek.allow_while_confused(fout)
        magitek.allow_while_berserk(fout)

        myfs = get_appropriate_freespace(freespaces, s.size)
        s.set_location(myfs.start)
        if not hasattr(s, "bytestring") or not s.bytestring:
            s.generate_bytestring()
        s.write(fout)
        magitek.setpointer(s.location, fout)
        freespaces = determine_new_freespaces(freespaces, myfs, s.size)

    gogo_enable_all_sub = Substitution()
    gogo_enable_all_sub.bytestring = bytes([0xEA] * 2)
    gogo_enable_all_sub.set_location(0x35E58)
    gogo_enable_all_sub.write(fout)

    cyan_ai_sub = Substitution()
    cyan_ai_sub.bytestring = bytes([0xF0, 0xEE, 0xEE, 0xEE, 0xFF])
    cyan_ai_sub.set_location(0xFBE85)
    cyan_ai_sub.write(fout)

    return commands, freespaces


def manage_suplex(commands, monsters):
    characters = get_characters()
    freespaces = []
    freespaces.append(FreeBlock(0x2A65A, 0x2A800))
    freespaces.append(FreeBlock(0x2FAAC, 0x2FC6D))
    c = [d for d in commands.values() if d.id == 5][0]
    myfs = freespaces.pop()
    s = SpellSub(spellid=0x5F)
    sb = SpellBlock(0x5F, sourcefile)
    s.set_location(myfs.start)
    s.write(fout)
    c.targeting = sb.targeting
    c.setpointer(s.location, fout)
    c.newname(sb.name, fout)
    c.unsetmenu(fout)
    fss = myfs.unfree(s.location, s.size)
    freespaces.extend(fss)
    for c in characters:
        c.set_battle_command(0, command_id=0)
        c.set_battle_command(1, command_id=5)
        c.set_battle_command(2, command_id=0xA)
        c.set_battle_command(3, command_id=1)
        c.write_battle_commands(fout)

    for m in monsters:
        m.misc2 &= 0xFB
        m.write_stats(fout)

    learn_blitz_sub = Substitution()
    learn_blitz_sub.bytestring = [0xEA] * 2
    learn_blitz_sub.set_location(0x261E5)
    learn_blitz_sub.write(fout)
    learn_blitz_sub.bytestring = [0xEA] * 4
    learn_blitz_sub.set_location(0xA18E)
    learn_blitz_sub.write(fout)


def manage_natural_magic():
    characters = get_characters()
    candidates = [c for c in characters if c.id < 12 and (0x02 in c.battle_commands or
                  0x17 in c.battle_commands)]

    num_natural_mages = 1
    if 'supernatural' in activated_codes:
        num_natural_mages = len(candidates)
    else:
        if random.randint(0,9) != 9:
            num_natural_mages = 2
            while num_natural_mages < len(candidates) and random.choice([True, False]):
                num_natural_mages += 1

    try:
        candidates = random.sample(candidates, num_natural_mages)
    except ValueError:
        return

    natmag_learn_sub = Substitution()
    natmag_learn_sub.set_location(0xa182)
    natmag_learn_sub.bytestring = bytes([0x22, 0x73, 0x08, 0xF0] + [0xEA] * 4)
    natmag_learn_sub.write(fout)

    natmag_learn_sub.set_location(0x261b6)
    natmag_learn_sub.bytestring = bytes([0x22, 0x4B, 0x08, 0xF0] + [0xEA] * 10)
    natmag_learn_sub.write(fout)

    natmag_learn_sub.set_location(0x30084B)
    natmag_learn_sub.bytestring = bytes([0xC9, 0x0C, 0xB0, 0x23, 0x48, 0xDA, 0x5A, 0x0B, 0xF4, 0x00, 0x15, 0x2B, 0x85, 0x08, 0xEB, 0x48, 0x85, 0x0B, 0xAE, 0xF4, 0x00, 0x86, 0x09, 0x7B, 0xEB, 0xA9, 0x80, 0x85, 0x0C, 0x22, 0xAB, 0x08, 0xF0, 0x68, 0xEB, 0x2B, 0x7A, 0xFA, 0x68, 0x6B, 0xC9, 0x0C, 0xB0, 0xFB, 0x48, 0xDA, 0x5A, 0x0B, 0xF4, 0x00, 0x15, 0x2B, 0x85, 0x08, 0x8D, 0x02, 0x42, 0xA9, 0x36, 0x8D, 0x03, 0x42, 0xB9, 0x08, 0x16, 0x85, 0x0B, 0xC2, 0x20, 0xAD, 0x16, 0x42, 0x18, 0x69, 0x6E, 0x1A, 0x85, 0x09, 0xA9, 0x00, 0x00, 0xE2, 0x20, 0xA9, 0xFF, 0x85, 0x0C, 0x22, 0xAB, 0x08, 0xF0, 0x2B, 0x7A, 0xFA, 0x68, 0x6B, 0xA0, 0x10, 0x00, 0xA5, 0x08, 0xC2, 0x20, 0x29, 0xFF, 0x00, 0xEB, 0x4A, 0x4A, 0x4A, 0xAA, 0xA9, 0x00, 0x00, 0xE2, 0x20, 0xBF, 0xE1, 0x08, 0xF0, 0xC5, 0x0B, 0xF0, 0x02, 0xB0, 0x11, 0x5A, 0xBF, 0xE0, 0x08, 0xF0, 0xA8, 0xB1, 0x09, 0xC9, 0xFF, 0xF0, 0x04, 0xA5, 0x0C, 0x91, 0x09, 0x7A, 0xE8, 0xE8, 0x88, 0xD0, 0xE0, 0x6B] + [0xFF] * 2 * 16 * 12)
    natmag_learn_sub.write(fout)

    spells = get_ranked_spells(sourcefile, magic_only=True)
    spellids = [s.spellid for s in spells]
    address = 0x2CE3C0

    def mutate_spell(pointer, used):
        fout.seek(pointer)
        spell, level = tuple(fout.read(2))

        while True:
            index = spellids.index(spell)
            levdex = int((level / 99.0) * len(spellids))
            a, b = min(index, levdex), max(index, levdex)
            index = random.randint(a, b)
            index = mutate_index(index, len(spells), [False, True],
                                 (-10, 10), (-5, 5))

            level = mutate_index(level, 99, [False, True],
                                 (-4, 4), (-2, 2))
            level = max(level, 1)

            newspell = spellids[index]
            if newspell in used:
                continue
            break

        used.append(newspell)
        return get_spell(newspell), level

    usedspells = []
    for candidate in candidates:
        candidate.natural_magic = []
        for i in range(16):
            pointer = address + random.choice([0,32]) + (2*i)
            newspell, level = mutate_spell(pointer, usedspells)
            candidate.natural_magic.append((level, newspell))
        candidate.natural_magic = sorted(candidate.natural_magic, key=lambda s: (s[0], s[1].spellid))
        for i, (level, newspell) in enumerate(candidate.natural_magic):
            pointer = 0x3008e0 + candidate.id * 32 + (2*i)
            fout.seek(pointer)
            fout.write(bytes([newspell.spellid]))
            fout.write(bytes([level]))
        usedspells = random.sample(usedspells, 12)

    lores = get_ranked_spells(sourcefile, magic_only=False)
    lores = [s for s in lores if 0x8B <= s.spellid <= 0xA2]
    lore_ids = [l.spellid for l in lores]
    lores_in_order = sorted(lore_ids)
    address = 0x26F564
    fout.seek(address)
    known_lores = read_multi(fout, length=3)
    known_lore_ids = []
    for i in range(24):
        if (1 << i) & known_lores:
            known_lore_ids.append(lores_in_order[i])

    new_known_lores = 0
    random.shuffle(known_lore_ids)
    for lore_id in known_lore_ids:
        if new_known_lores and random.choice([True, False]):
            continue

        index = lore_ids.index(lore_id)
        index += random.randint(-4, 2)
        index = max(0, min(index, len(lores)-1))
        while random.choice([True, False]):
            index += random.randint(-2, 1)
            index = max(0, min(index, len(lores)-1))
        new_lore = lores[index]
        order = lores_in_order.index(new_lore.spellid)
        new_known_lores |= (1 << order)

    fout.seek(address)
    write_multi(fout, new_known_lores, length=3)

    return candidates


def manage_equip_umaro(freespaces):
    # ship unequip - cc3510
    equip_umaro_sub = Substitution()
    equip_umaro_sub.bytestring = [0xC9, 0x0E]
    equip_umaro_sub.set_location(0x31E6E)
    equip_umaro_sub.write(fout)
    equip_umaro_sub.bytestring = [0xEA] * 2
    equip_umaro_sub.set_location(0x39EF6)
    equip_umaro_sub.write(fout)

    f = open(sourcefile, 'r+b')
    f.seek(0xC359D)
    old_unequipper = f.read(218)
    f.close()
    header = old_unequipper[:7]
    footer = old_unequipper[-3:]

    def generate_unequipper(basepointer, not_current_party=False):
        unequipper = bytearray([])
        pointer = basepointer + len(header)
        a, b, c = "LO", "MED", "HI"
        for i in range(14):
            segment = []
            segment += [0xE1]
            segment += [0xC0, 0xA0 | i, 0x01, a, b, c]
            if not_current_party:
                segment += [0xDE]
                segment += [0xC0, 0xA0 | i, 0x81, a, b, c]
            segment += [0x8D, i]
            pointer += len(segment)
            hi, med, lo = pointer >> 16, (pointer >> 8) & 0xFF, pointer & 0xFF
            hi = hi - 0xA
            segment = [hi if j == c else
                       med if j == b else
                       lo if j == a else j for j in segment]
            unequipper += bytes(segment)
        unequipper = header + unequipper + footer
        return unequipper

    unequip_umaro_sub = Substitution()
    unequip_umaro_sub.bytestring = generate_unequipper(0xC351E)
    unequip_umaro_sub.set_location(0xC351E)
    unequip_umaro_sub.write(fout)

    myfs = get_appropriate_freespace(freespaces, 234)
    pointer = myfs.start
    unequip_umaro_sub.bytestring = generate_unequipper(pointer, not_current_party=True)
    freespaces = determine_new_freespaces(freespaces, myfs, unequip_umaro_sub.size)
    unequip_umaro_sub.set_location(pointer)
    unequip_umaro_sub.write(fout)
    unequip_umaro_sub.bytestring = [
        pointer & 0xFF, (pointer >> 8) & 0xFF, (pointer >> 16) - 0xA]
    unequip_umaro_sub.set_location(0xC3514)
    unequip_umaro_sub.write(fout)

    return freespaces


def manage_umaro(commands):
    characters = get_characters()
    candidates = [c for c in characters if c.id <= 13 and
                  c.id != 12 and
                  2 not in c.battle_commands and
                  0xC not in c.battle_commands and
                  0x17 not in c.battle_commands]

    if not candidates:
        candidates = [c for c in characters if c.id <= 13 and
                  c.id != 12]
    umaro_risk = random.choice(candidates)
    if 0xFF in umaro_risk.battle_commands:
        battle_commands = []
        battle_commands.append(0)
        if "collateraldamage" not in activated_codes:
            battle_commands.extend(random.sample([3, 5, 6, 7, 8, 9, 0xA, 0xB,
                                                  0xC, 0xD, 0xE, 0xF, 0x10,
                                                  0x12, 0x13, 0x16, 0x18, 0x1A,
                                                  0x1B, 0x1C, 0x1D], 2))
        battle_commands.append(1)
        umaro_risk.battle_commands = battle_commands

    umaro = [c for c in characters if c.id == 13][0]
    umaro.battle_commands = list(umaro_risk.battle_commands)
    if random.choice([True, False, False]):
        umaro_risk.battle_commands = [0x00, 0xFF, 0xFF, 0xFF]
    else:
        cands = [0x00, 0x05, 0x06, 0x07, 0x09, 0x0A, 0x0B, 0x10,
                 0x12, 0x13, 0x16, 0x18]
        cands = [i for i in cands if i not in changed_commands]
        base_command = random.choice(cands)
        commands = list(commands.values())
        base_command = [c for c in commands if c.id == base_command][0]
        base_command.allow_while_berserk(fout)
        umaro_risk.battle_commands = [base_command.id, 0xFF, 0xFF, 0xFF]

    umaro.beserk = False
    umaro_risk.beserk = True

    if "metronome" in activated_codes:
        umaro_risk.battle_commands = [0x1D, 0xFF, 0xFF, 0xFF]

    umaro_risk.write_battle_commands(fout)
    umaro.write_battle_commands(fout)

    umaro_exchange_sub = Substitution()
    umaro_exchange_sub.bytestring = [0xC9, umaro_risk.id]
    umaro_exchange_sub.set_location(0x21617)
    umaro_exchange_sub.write(fout)
    umaro_exchange_sub.set_location(0x20926)
    umaro_exchange_sub.write(fout)

    spells = get_ranked_spells(sourcefile)
    spells = [x for x in spells if x.target_enemy_default]
    spells = [x for x in spells if x.valid]
    spells = [x for x in spells if x.rank() < 1000]
    spell_ids = [s.spellid for s in spells]
    index = spell_ids.index(0x54)  # storm
    index += random.randint(0, 10)
    while random.choice([True, False]):
        index += random.randint(-10, 10)
    index = max(0, min(index, len(spell_ids)-1))
    spell_id = spell_ids[index]
    storm_sub = Substitution()
    storm_sub.bytestring = bytes([0xA9, spell_id])
    storm_sub.set_location(0x21710)
    storm_sub.write(fout)

    return umaro_risk


def manage_sprint():
    autosprint = Substitution()
    autosprint.set_location(0x4E2D)
    autosprint.bytestring = bytes([0x80, 0x00])
    autosprint.write(fout)


def manage_skips():
    # To identify if this cutscene skip is active in a ROM, look for the bytestring:
    # 41 6E 64 53 68 65 61 74 68 57 61 73 54 68 65 72 65 54 6F 6F
    # at 0xCAA9F
    characters = get_characters();

    def writeToAddress(address, event):
        event_skip_sub = Substitution()
        event_skip_sub.bytestring = bytearray([])
        for byte in event:
            event_skip_sub.bytestring.append(int(byte, 16))
        event_skip_sub.set_location(int(address, 16))
        event_skip_sub.write(fout)

    def handleNormal(split_line): # Replace events that should always be replaced
        writeToAddress(split_line[0], split_line[1:])

    def handleGau(split_line): # Replace events that should be replaced if we are auto-recruiting Gau
        if 'o' in flags or 'w' in flags or 't' in flags:
            writeToAddress(split_line[0], split_line[1:])

    def handlePalette(split_line): # Fix palettes so that they are randomized
        for character in characters:
            if character.id == int(split_line[1], 16):
                palette_correct_sub = Substitution()
                palette_correct_sub.bytestring = bytes([character.palette])
                palette_correct_sub.set_location(int(split_line[0], 16))
                palette_correct_sub.write(fout)

    for line in open(SKIP_EVENTS_TABLE):
        # If "Foo" precedes a line in skipEvents.txt, call "handleFoo"
        split_line = line.strip().split(' ')
        handler = "handle" + split_line[0]
        locals()[handler](split_line[1:])

    flashback_skip_sub = Substitution()
    flashback_skip_sub.bytestring = bytes([0xB2, 0xB8, 0xA5, 0x00, 0xFE])
    flashback_skip_sub.set_location(0xAC582)
    flashback_skip_sub.write(fout)

    boat_skip_sub = Substitution()
    boat_skip_sub.bytestring = bytes(
        [0x97, 0x5C] +  # Fade to black, wait for fade
        [0xD0, 0x87] +  # Set event bit 0x87, Saw the scene with Locke and Celes at night in Albrook
        [0xD0, 0x83] + # Set event bit 0x83, Boarded the ship in Albrook
        [0xD0, 0x86] +  # Set event bit 0x86, Saw the scene with Terra and Leo at night on the ship to Thamasa
        [0x3D, 0x03, 0x3F, 0x03, 0x01, 0x45] +    # Create Shadow, add Shadow to party 1, refresh objects
        [0xD4, 0xE3,  0x77, 0x03, 0xD4, 0xF3] + # Shadow in shop and item menus, level average Shadow, Shadow is available
        [0x88, 0x03, 0x00, 0x40, 0x8B, 0x03, 0x7F, 0x8C, 0x03, 0x7F] + # Cure status ailments of Shadow, set HP and MP to max
        [0xB2, 0xBD, 0xCF, 0x00] + # Subroutine that cures status ailments and set hp and mp to max.
        # clear NPC bits
        [0xDB, 0x06, 0xDB, 0x07, 0xDB, 0x08, 0xDB, 0x11, 0xDB, 0x13, 0xDB, 0x22, 0xDB, 0x42, 0xDB, 0x65] +
        [0xB8, 0x4B] + # Shadow won't run
        [0x6B, 0x00, 0x04, 0xE8, 0x96, 0x40, 0xFF] # Load world map with party near Thamasa, return
        )
    boat_skip_sub.set_location(0xC615A)
    boat_skip_sub.write(fout)

    leo_skip_sub = Substitution()
    leo_skip_sub.bytestring = bytes(
        [0x97, 0x5C] +  # Fade to black, wait for fade
        [0xD0, 0x99, 0xDB, 0x1B] + # Set event bit 0x99, Found the Espers at Gathering Place of the Espers, hide Esper NPCs in cave
        [0xB2, 0x2B, 0x2E, 0x01, 0x3F, 0x01, 0x00, 0x3F, 0x00, 0x00, 0x45, 0x3E, 0x01, 0x3E, 0x00, 0x45, 0x40, 0x0E, 0x0F, 0x3D, 0x0E, 0x3F, 0x0E, 0x01, 0x37, 0x0E, 0x10, 0x43, 0x0E, get_character(0x0F).palette, 0x7F, 0x0E, 0x0F, 0x45, 0x3F, 0x08, 0x00, 0x3F, 0x07, 0x00, 0x45, 0x3E, 0x08, 0x3E, 0x07, 0x45, 0xB2, 0xBD, 0xCF, 0x00, 0x47] + # Setup party with Leo
        [0x6B, 0x55, 0x21, 0x16, 0x16, 0xC0, 0x39, 0x31, 0x05, 0xD5, 0x16, 0x16, 0x28, 0xFF, 0x45, 0x36, 0x1C, 0x36, 0x1B, 0x59, 0x04, 0x92, 0xB2, 0x37, 0x6A, 0x01, 0xB2, 0x09, 0x6A, 0x01] + # Load Thamasa during kefka map
        [0x40, 0x0F, 0x2C, 0x3D, 0x0F, 0x45, 0x7F, 0x0F, 0x2C, 0x37, 0x0F, 0x15, 0x43, 0x0F, get_character(0x15).palette, 0x88, 0x0F, 0x00, 0x00, 0x8B, 0x0F, 0x7F, 0x8C, 0x0F, 0x7F] + # Put Kefka in party
        [0x4D, 0x7C, 0x3F] + # Fight
        [0xB2, 0xA9, 0x5E, 0x00] + # Game over if you lost
        [0xD0, 0x9B] + # Set event bit 0x9B, Fought Kefka at Thamasa
        [0xD0, 0x9C] + # Set event bit 0x9C, Leo is buried in Thamasa
        [0x3D, 0x01, 0x3D, 0x00, 0x45, 0x3F, 0x01, 0x01, 0x3F, 0x00, 0x01, 0x45,0x3F, 0x0E, 0x00, 0x3E, 0x0E, 0x3D, 0x08, 0x3D, 0x07, 0x45, 0x3F, 0x08, 0x01, 0x3F, 0x07, 0x01, 0x45, 0x3C, 0x00, 0x01, 0x07, 0x08, 0x45] + # Set up party as Terra, Locke, Strago, Relm
        # Clear event bits for party members available
        [0xDB, 0xF7, 0xD5, 0xF2, 0xD5, 0xF3, 0xD5, 0xF4, 0xD5, 0xF5, 0xD5, 0xF9, 0xD5, 0xFB, 0xD5, 0xF6] +
        # perform level averaging
        [0x77, 0x02, 0x77, 0x03, 0x77, 0x04, 0x77, 0x05, 0x77, 0x09, 0x77, 0x0B, 0x77, 0x06] +
        # Set event bits for party members available
        [0xD4, 0xF2, 0xD4, 0xF4, 0xD4, 0xF5, 0xD4, 0xF9, 0xD4, 0xFB, 0xD4, 0xF6] +
        [0xB2, 0x35, 0x09, 0x02] +  # Subroutine to do level averaging for Mog if you have him
        [0xD3, 0xCC] +  # Clear temp song override
        [0xD0, 0x9D] +  # set event bit 0x9D Completed the mandatory Thamasa scenario
        [0xD2, 0xBA] +  # Airship is anchored
        [0xDA, 0x5A, 0xDA, 0xD9, 0xDB, 0x20, 0xDA, 0x68] +  # NPC event bits
        [0xD2, 0xB3, 0xD2, 0xB4] +  # Facing left and pressing A?
        [0xD0, 0x7A] +  # Set event bit 0x7A, The Espers attacked the Blackjack
        #[0xD2, 0x76] +  # Set event bit 0x176, Serves to ensure that branching always occurs 2 (always remains clear)
        [0xD2, 0x6F] +  # Set event bit 0x16F, Learned how to operate the airship
        [0x6B, 0x00, 0x04, 0xF9, 0x80, 0x00] +  # load map, place party
        [0xC7, 0xF9, 0x7F, 0xFF]  # place airship, end
        )
    leo_skip_sub.set_location(0xBF2BB)
    leo_skip_sub.write(fout)

    tintinabar_sub = Substitution()
    tintinabar_sub.set_location(0xC67CF)
    tintinabar_sub.bytestring = bytes([0xC1, 0x7F, 0x02, 0x88, 0x82, 0x74, 0x68, 0x02, 0x4B, 0xFF, 0x02, 0xB6, 0xE2, 0x67, 0x02, 0xB3, 0x5E, 0x00, 0xFE, 0x85, 0xC4, 0x09, 0xC0, 0xBE, 0x81, 0xFF, 0x69, 0x01, 0xD4, 0x88])
    tintinabar_sub.write(fout)

    tintinabar_sub.set_location(0xD81F1)
    tintinabar_sub.bytestring = bytes([0x25, 0xB0, 0x7F, 0x56, 0x59, 0x54, 0x54, 0x7F, 0x26, 0x2F, 0xAC, 0x8B, 0xB2, 0x8F, 0x8E, 0xA4, 0x8C, 0x56, 0xBB, 0xD0, 0xBA, 0xC8, 0x98, 0xB9, 0x89, 0xFA, 0x4B, 0x3D, 0x98, 0xB9, 0x33, 0x9F, 0x42, 0x3C, 0x98, 0x8F, 0x8C, 0xB9, 0x3B, 0x48, 0x48, 0x44, 0x65, 0x01, 0x15, 0x7F, 0x6B, 0x32, 0x3E, 0xB5, 0x81, 0x85, 0x46, 0x6C, 0x7F, 0x7F, 0x15, 0x7F, 0x6B, 0x25, 0x48, 0x4B, 0x40, 0xD0, 0x97, 0x4D, 0x6C, 0x00 ]) #'F', 'or', ' ', '2', '5', '0', '0', ' ', 'G', 'P', ' y', 'ou', ' c', 'an', ' s', 'en', 'd ', '2', ' l', 'et', 'te', 'rs', ', ', 'a ', 're', 'co', 'r', 'd', ', ', 'a ', 'T', 'on', 'i', 'c', ', ', 'an', 'd ', 'a ', 'b', 'o', 'o', 'k', '.', '\n', '<choice>', ' ', '(', 'S', 'e', 'nd', ' t', 'he', 't', ')', ' ', ' ', '<choice>', ' ', '(', 'F', 'o', 'r', 'g', 'et', ' i', 't', ')''\0'
    tintinabar_sub.write(fout)

    # We overwrote some of the event items, so write them again
    if 't' in flags:
        for area_name, items in get_event_items().items():
            for e in items:
                e.write_data(fout, cutscene_skip=True)


def activate_airship_mode(freespaces):
    set_airship_sub = Substitution()
    set_airship_sub.bytestring = bytes(
        [0x3A, 0xD2, 0xCC] +  # moving code
        [0xD2, 0xBA] +  # enter airship from below decks
        [0xD2, 0xB9] +  # airship appears on world map
        [0xD0, 0x70] +  # party appears on airship
        [0x6B, 0x00, 0x04, 0x54, 0x22, 0x00] +  # load map, place party
        [0xC7, 0x54, 0x23] +  # place airship
        [0xFF] +  # end map script
        [0xFE]  # end subroutine
        )
    myfs = get_appropriate_freespace(freespaces, set_airship_sub.size)
    pointer = myfs.start
    freespaces = determine_new_freespaces(freespaces, myfs, set_airship_sub.size)

    set_airship_sub.set_location(pointer)
    set_airship_sub.write(fout)

    set_airship_sub.bytestring = bytes([0xD2, 0xB9])  # airship appears in WoR
    set_airship_sub.set_location(0xA532A)
    set_airship_sub.write(fout)

    set_airship_sub.bytestring = bytes(
        [0x6B, 0x01, 0x04, 0x4A, 0x16, 0x01] +  # load WoR, place party
        [0xDD] +  # hide minimap
        [0xC5, 0x00, 0x7E, 0xC2, 0x1E, 0x00] +  # set height and direction
        [0xC6, 0x96, 0x00, 0xE0, 0xFF] +  # propel vehicle, wait 255 units
        [0xC7, 0x4E, 0xf0] +  # place airship
        [0xD2, 0x8E, 0x25, 0x07, 0x07, 0x40])  # load beach with fish
    set_airship_sub.set_location(0xA51E9)
    set_airship_sub.write(fout)

    # point to airship-placing script
    set_airship_sub.bytestring = bytes(
        [0xB2, pointer & 0xFF, (pointer >> 8) & 0xFF,
         (pointer >> 16) - 0xA, 0xFE])
    set_airship_sub.set_location(0xCB046)
    set_airship_sub.write(fout)

    # always access floating continent
    set_airship_sub.bytestring = bytes([0xC0, 0x27, 0x01, 0x79, 0xF5, 0x00])
    set_airship_sub.set_location(0xAF53A)  # need first branch for button press
    set_airship_sub.write(fout)

    # always exit airship
    set_airship_sub.bytestring = bytes([0xFD] * 6)
    set_airship_sub.set_location(0xAF4B1)
    set_airship_sub.write(fout)
    set_airship_sub.bytestring = bytes([0xFD] * 8)
    set_airship_sub.set_location(0xAF4E3)
    set_airship_sub.write(fout)

    # chocobo stables are airship stables now
    set_airship_sub.bytestring = bytes([0xB6, 0x8D, 0xF5, 0x00, 0xB3, 0x5E, 0x00])
    set_airship_sub.set_location(0xA7A39)
    set_airship_sub.write(fout)
    set_airship_sub.set_location(0xA8FB7)
    set_airship_sub.write(fout)
    set_airship_sub.set_location(0xB44D0)
    set_airship_sub.write(fout)
    set_airship_sub.set_location(0xC3335)
    set_airship_sub.write(fout)

    # don't force Locke and Celes at party select
    set_airship_sub.bytestring = bytes([0x99, 0x01, 0x00, 0x00])
    set_airship_sub.set_location(0xAAB67)
    set_airship_sub.write(fout)
    set_airship_sub.set_location(0xAF60F)
    set_airship_sub.write(fout)
    set_airship_sub.set_location(0xCC2F3)
    set_airship_sub.write(fout)

    # Daryl is not such an airship hog
    set_airship_sub.bytestring = bytes([0x6E, 0xF5])
    set_airship_sub.set_location(0x41F41)
    set_airship_sub.write(fout)

    return freespaces


def manage_rng():
    fout.seek(0xFD00)
    if 'norng' in activated_codes:
        numbers = [0 for _ in range(0x100)]
    else:
        numbers = list(range(0x100))
    random.shuffle(numbers)
    fout.write(bytes(numbers))

death_abuse_sub = Substitution()
death_abuse_sub.bytestring = bytes([0x60])
death_abuse_sub.set_location(0xC515)


def manage_balance(newslots=True):
    vanish_doom_sub = Substitution()
    vanish_doom_sub.bytestring = bytes([
        0xAD, 0xA2, 0x11, 0x89, 0x02, 0xF0, 0x07, 0xB9, 0xA1, 0x3A, 0x89, 0x04,
        0xD0, 0x6E, 0xA5, 0xB3, 0x10, 0x1C, 0xB9, 0xE4, 0x3E, 0x89, 0x10, 0xF0,
        0x15, 0xAD, 0xA4, 0x11, 0x0A, 0x30, 0x07, 0xAD, 0xA2, 0x11, 0x4A, 0x4C,
        0xB3, 0x22, 0xB9, 0xFC, 0x3D, 0x09, 0x10, 0x99, 0xFC, 0x3D, 0xAD, 0xA3,
        0x11, 0x89, 0x02, 0xD0, 0x0F, 0xB9, 0xF8, 0x3E, 0x10, 0x0A, 0xC2, 0x20,
        0xB9, 0x18, 0x30, 0x04, 0xA6, 0x4C, 0xE5, 0x22
        ])
    vanish_doom_sub.set_location(0x22215)
    vanish_doom_sub.write(fout)

    evade_mblock_sub = Substitution()
    evade_mblock_sub.bytestring = bytes([
        0xF0, 0x17, 0x20, 0x5A, 0x4B, 0xC9, 0x40, 0xB0, 0x9C, 0xB9, 0xFD, 0x3D,
        0x09, 0x04, 0x99, 0xFD, 0x3D, 0x80, 0x92, 0xB9, 0x55, 0x3B, 0x48,
        0x80, 0x43, 0xB9, 0x54, 0x3B, 0x48, 0xEA
        ])
    evade_mblock_sub.set_location(0x2232C)
    evade_mblock_sub.write(fout)

    manage_rng()
    if newslots:
        randomize_slots(outfile, fout, 0x24E4A)

    death_abuse_sub.write(fout)

    get_monsters(sourcefile)
    sealed_kefka = get_monster(0x174)


def manage_magitek():
    spells = get_ranked_spells()
    exploder = [s for s in spells if s.spellid == 0xA2][0]
    tek_skills = [s for s in spells if s.spellid in TEK_SKILLS]
    targets = sorted(set([s.targeting for s in spells]))
    terra_used, others_used = [], []
    terra_skills, other_skills = [], []
    target_pointer = 0x19104
    terra_pointer = 0x1910C
    others_pointer = 0x19114
    for i in reversed(range(3, 8)):
        while True:
            if i == 5:
                targeting = 0x43
            else:
                targeting = random.choice(targets)
            candidates = [s for s in tek_skills if s.targeting == targeting]
            if not candidates:
                continue

            terra_cand = random.choice(candidates)
            if i > 5:
                others_cand = None
            elif i == 5:
                others_cand = exploder
            else:
                others_cand = random.choice(candidates)
            if terra_cand not in terra_used:
                if i >= 5 or others_cand not in others_used:
                    break

        terra_used.append(terra_cand)
        others_used.append(others_cand)

    terra_used.reverse()
    others_used.reverse()
    fout.seek(target_pointer+3)
    for s in terra_used:
        fout.write(bytes([s.targeting]))
    fout.seek(terra_pointer+3)
    for s in terra_used:
        fout.write(bytes([s.spellid-0x83]))
    fout.seek(others_pointer+3)
    for s in others_used:
        if s is None:
            break
        fout.write(bytes([s.spellid-0x83]))


def manage_final_boss(freespaces):
    kefka1 = get_monster(0x12a)
    kefka2 = get_monster(0x11a)  # dummied kefka
    for m in [kefka1, kefka2]:
        pointer = m.ai + 0xF8700
        freespaces.append(FreeBlock(pointer, pointer + m.aiscriptsize))
    aiscripts = read_ai_table(FINAL_BOSS_AI_TABLE)

    aiscript = aiscripts['KEFKA 1']
    kefka1.aiscript = aiscript

    kefka2.copy_all(kefka1, everything=True)
    aiscript = aiscripts['KEFKA 2']
    kefka2.aiscript = aiscript

    def has_graphics(monster):
        if monster.graphics.graphics == 0:
            return False
        if not monster.name.strip('_'):
            return False
        if monster.id in list(range(0x157, 0x160)) + [0x11a, 0x12a]:
            return False
        return True

    kefka2.graphics.copy_data(kefka1.graphics)
    monsters = get_monsters()
    monsters = [m for m in monsters if has_graphics(m)]
    m = random.choice(monsters)
    kefka1.graphics.copy_data(m.graphics)
    change_enemy_name(fout, kefka1.id, m.name.strip('_'))

    k1formation = get_formation(0x202)
    k2formation = get_formation(KEFKA_EXTRA_FORMATION)
    k2formation.copy_data(k1formation)
    assert k1formation.enemy_ids[0] == (0x12a & 0xFF)
    assert k2formation.enemy_ids[0] == (0x12a & 0xFF)
    k2formation.enemy_ids[0] = kefka2.id & 0xFF
    assert k1formation.enemy_ids[0] == (0x12a & 0xFF)
    assert k2formation.enemy_ids[0] == (0x11a & 0xFF)
    k2formation.lookup_enemies()

    for m in [kefka1, kefka2]:
        myfs = get_appropriate_freespace(freespaces, m.aiscriptsize)
        pointer = myfs.start
        m.set_relative_ai(pointer)
        freespaces = determine_new_freespaces(freespaces, myfs, m.aiscriptsize)

    kefka1.write_stats(fout)
    kefka2.write_stats(fout)
    return freespaces


def manage_monsters():
    monsters = get_monsters(sourcefile)
    itembreaker = "collateraldamage" in activated_codes
    randombosses = "randombosses" in activated_codes
    madworld = "madworld" in activated_codes
    darkworld = "darkworld" in activated_codes
    safe_solo_terra = "ancientcave" not in activated_codes
    change_skillset = True if darkworld in activated_codes else None
    final_bosses = (list(range(0x157, 0x160)) + list(range(0x127, 0x12b)) +
                    [0x112, 0x11a, 0x17d])
    for m in monsters:
        if "zone eater" in m.name.lower():
            continue
        if not m.name.strip('_') and not m.display_name.strip('_'):
            continue
        if m.id in final_bosses:
            if 0x157 <= m.id < 0x160 or m.id == 0x17d:
                # deep randomize three tiers, Atma
                m.randomize_boost_level()
                if darkworld:
                    m.increase_enemy_difficulty()
                m.mutate(change_skillset=True, itembreaker=itembreaker, randombosses=randombosses, madworld=madworld, darkworld=darkworld, safe_solo_terra=False)
            else:
                m.mutate(change_skillset=change_skillset, itembreaker=itembreaker, randombosses=randombosses, madworld=madworld, darkworld=darkworld, safe_solo_terra=False)
            if 0x127 <= m.id < 0x12a or m.id == 0x17d or m.id == 0x11a:
                # boost statues, Atma, final kefka a second time
                m.randomize_boost_level()
                if darkworld:
                    m.increase_enemy_difficulty()
                m.mutate(change_skillset=change_skillset, itembreaker=itembreaker, randombosses=randombosses, madworld=madworld, darkworld=darkworld, safe_solo_terra=False)
            m.misc1 &= (0xFF ^ 0x4)  # always show name
        else:
            if darkworld:
                m.increase_enemy_difficulty()
            m.mutate(change_skillset=change_skillset, itembreaker=itembreaker, randombosses=randombosses, madworld=madworld, darkworld=darkworld, safe_solo_terra=safe_solo_terra)

        m.tweak_fanatics()
        m.relevel_specifics()

    change_enemy_name(fout, 0x166, "L.255Magic")

    shuffle_monsters(monsters, safe_solo_terra=safe_solo_terra)
    for m in monsters:
        m.randomize_special_effect(fout)
        m.write_stats(fout)

    return monsters


def manage_monster_appearance(monsters, preserve_graphics=False):
    mgs = [m.graphics for m in monsters]
    esperptr = 0x127000 + (5*384)
    espers = []
    for j in range(32):
        mg = MonsterGraphicBlock(pointer=esperptr + (5*j), name="")
        mg.read_data(sourcefile)
        espers.append(mg)
        mgs.append(mg)

    for m in monsters:
        g = m.graphics
        pp = g.palette_pointer
        others = [h for h in mgs if h.palette_pointer == pp + 0x10]
        if others:
            g.palette_data = g.palette_data[:0x10]

    nonbosses = [m for m in monsters if not m.is_boss and not m.boss_death]
    bosses = [m for m in monsters if m.is_boss or m.boss_death]
    assert not set(bosses) & set(nonbosses)
    nonbossgraphics = [m.graphics.graphics for m in nonbosses]
    bosses = [m for m in bosses if m.graphics.graphics not in nonbossgraphics]

    for i, m in enumerate(nonbosses):
        if "Chupon" in m.name:
            m.update_pos(6, 6)
            m.update_size(8, 16)
        if "Siegfried" in m.name:
            m.update_pos(8, 8)
            m.update_size(8, 8)
        candidates = nonbosses[i:]
        m.mutate_graphics_swap(candidates)
        name = randomize_enemy_name(fout, m.id)
        m.changed_name = name

    done = {}
    freepointer = 0x127820
    for m in monsters:
        mg = m.graphics
        if m.id == 0x12a and not preserve_graphics:
            idpair = "KEFKA 1"
        if m.id in REPLACE_ENEMIES + [0x172]:
            mg.set_palette_pointer(freepointer)
            freepointer += 0x40
            continue
        else:
            idpair = (m.name, mg.palette_pointer)

        if idpair not in done:
            mg.mutate_palette()
            done[idpair] = freepointer
            freepointer += len(mg.palette_data)
            mg.write_data(fout, palette_pointer=done[idpair])
        else:
            mg.write_data(fout, palette_pointer=done[idpair],
                          no_palette=True)

    for mg in espers:
        mg.mutate_palette()
        mg.write_data(fout, palette_pointer=freepointer)
        freepointer += len(mg.palette_data)

    return mgs


def recolor_character_palette(pointer, palette=None, flesh=False, middle=True, santa=False, skintones = None, char_hues = None, trance = False):
    fout.seek(pointer)
    if palette is None:
        palette = [read_multi(fout, length=2) for _ in range(16)]
        outline, eyes, hair, skintone, outfit1, outfit2, NPC = (
            palette[:2], palette[2:4], palette[4:6], palette[6:8],
            palette[8:10], palette[10:12], palette[12:])
        def components_to_color(xxx_todo_changeme):
            (red, green, blue) = xxx_todo_changeme
            return red | (green << 5) | (blue << 10)

        new_style_palette = None
        if skintones and char_hues:
            new_style_palette = generate_character_palette(skintones, char_hues, trance=trance)
            if random.randint(1,100) == 1:
                transformer = get_palette_transformer(middle=middle)
                new_style_palette = transformer(new_style_palette)
        elif trance:
            new_style_palette = generate_character_palette(trance=True)
            
        new_palette = new_style_palette if new_style_palette else []
        if not flesh:
            pieces = (outline, eyes, hair, skintone, outfit1, outfit2, NPC) if not new_style_palette else [NPC]
            for piece in pieces:
                transformer = get_palette_transformer(middle=middle)
                piece = list(piece)
                piece = transformer(piece)
                new_palette += piece
            if not new_style_palette: new_palette[6:8] = skintone
            if 'christmas' in activated_codes:
                if santa:
                    # color kefka's palette to make him look santa-ish
                    new_palette = palette
                    new_palette[8] = components_to_color((0x18, 0x18, 0x16))
                    new_palette[9] = components_to_color((0x16, 0x15, 0x0F))
                    new_palette[10] = components_to_color((0x1C, 0x08, 0x03))
                    new_palette[11] = components_to_color((0x18, 0x02, 0x05))
                else:
                    # give them red & green outfits
                    red = [components_to_color((0x19, 0x00, 0x05)), components_to_color((0x1c, 0x02, 0x04)) ]
                    green = [components_to_color((0x07, 0x12, 0x0b)), components_to_color((0x03, 0x0d, 0x07))]

                    random.shuffle(red)
                    random.shuffle(green)
                    outfit = [red, green]
                    random.shuffle(outfit)
                    new_palette[8:10] = outfit[0]
                    new_palette[10:12] = outfit[1]

        else:
            transformer = get_palette_transformer(middle=middle)
            new_palette = transformer(palette)
            if new_style_palette:
                new_palette = new_style_palette[0:12] + new_palette[12:]

        palette = new_palette

    fout.seek(pointer)
    for p in palette:
        write_multi(fout, p, length=2)
    return palette


def make_palette_repair(main_palette_changes):
    repair_sub = Substitution()
    bytestring = []
    for c in sorted(main_palette_changes):
        before, after = main_palette_changes[c]
        bytestring.extend([0x43, c, after])
    repair_sub.bytestring = bytestring + [0xFE]
    repair_sub.set_location(0xCB154)  # Narshe secret entrance
    repair_sub.write(fout)


def get_npcs():
    npcs = []
    for l in get_locations():
        npcs.extend(l.npcs)
    return npcs


def get_npc_palettes():
    palettes = {}
    for n in get_npcs():
        g = n.graphics
        if g not in palettes:
            palettes[g] = set([])
        palettes[g].add(n.palette)
    for k, v in list(palettes.items()):
        palettes[k] = sorted(v)
    return palettes

nameiddict = {
    0: "Terra",
    1: "Locke",
    2: "Cyan",
    3: "Shadow",
    4: "Edgar",
    5: "Sabin",
    6: "Celes",
    7: "Strago",
    8: "Relm",
    9: "Setzer",
    0xa: "Mog",
    0xb: "Gau",
    0xc: "Gogo",
    0xd: "Umaro",
    0xe: "Trooper",
    0xf: "Imp",
    0x10: "Leo",
    0x11: "Banon",
    0x12: "Esper Terra",
    0x13: "Merchant",
    0x14: "Ghost",
    0x15: "Kefka"}


def sanitize_names(names):
    delchars = ''.join(c for c in map(chr, range(256)) if not c.isalnum() and c not in "!?/:\"'-.")
    table = str.maketrans(dict.fromkeys(delchars))
    names = [name.translate(table) for name in names]
    return [name[:6] for name in names if name != ""]


def manage_character_names(change_to, male):
    characters = get_characters()
    wild = 'partyparty' in activated_codes
    sabin_mode = 'suplexwrecks' in activated_codes
    tina_mode = 'bravenudeworld' in activated_codes
    soldier_mode = 'quikdraw' in activated_codes
    moogle_mode = 'kupokupo' in activated_codes
    ghost_mode = 'halloween' in activated_codes

    names = []
    if tina_mode:
        names = ["Tina"] * 30 + ["MADUIN"] + ["Tina"] * 3
    elif sabin_mode:
        names = ["Teabin", "Loabin", "Cyabin", "Shabin", "Edabin", "Sabin",
                 "Ceabin", "Stabin", "Reabin", "Seabin", "Moabin", "Gaubin",
                 "Goabin", "Umabin", "Baabin", "Leabin", "??abin", "??abin",
                 "Kuabin", "Kuabin", "Kuabin", "Kuabin", "Kuabin", "Kuabin",
                 "Kuabin", "Kuabin", "Kuabin", "Kaabin", "Moabin", "??abin",
                 "MADUIN", "??abin", "Viabin", "Weabin"]
    elif moogle_mode:
        names = ["Kumop", "Kupo", "Kupek", "Kupop", "Kumama", "Kuku",
                 "Kutan", "Kupan", "Kushu", "Kurin", "Mog", "Kuru",
                 "Kamog", "Kumaro", "Banon", "Leo", "?????", "?????",
                 "Cyan", "Shadow", "Edgar", "Sabin", "Celes", "Strago",
                 "Relm", "Setzer", "Gau", "Gogo"]

        gba_moogle_names = ["Moglin", "Mogret", "Moggie", "Molulu", "Moghan",
                            "Moguel", "Mogsy", "Mogwin", "Mog", "Mugmug", "Cosmog"]

        random_name_ids = []

        # Terra, Locke, and Umaro get a specific name, or a random moogle name from another ff game
        for moogle_id in [0,1,13]:
            if random.choice([True, True, False]):
                random_name_ids.append(moogle_id)
        # Other party members get either the name of their counterpart from snes or gba, or moogle name from another ff game
        for moogle_id in range(2,10) + range(11,13):
            chance = random.randint(1,4)
            if chance == 2:
                names[moogle_id] = gba_moogle_names[moogle_id - 2]
            elif chance != 1:
                random_name_ids.append(moogle_id)

        f = open_mei_fallback(MOOGLE_NAMES_TABLE)
        mooglenames = sorted(set(sanitize_names([line.strip() for line in f.readlines()])))
        f.close()

        random_moogle_names = random.sample(mooglenames, len(random_name_ids))
        for index, id in enumerate(random_name_ids):
            names[id] = random_moogle_names[index]

        # Human Mog gets a human name, maybe
        if random.choice([True, True, False]):
            f = open_mei_fallback(MALE_NAMES_TABLE)
            malenames = sorted(set(sanitize_names([line.strip() for line in f.readlines()])))
            f.close()

            names[10] = random.choice(malenames)
    else:
        f = open_mei_fallback(MALE_NAMES_TABLE)
        malenames = sorted(set(sanitize_names([line.strip() for line in f.readlines()])))
        f.close()
        f = open_mei_fallback(FEMALE_NAMES_TABLE)
        femalenames = sorted(set(sanitize_names([line.strip() for line in f.readlines()])))
        f.close()
        for c in range(14):
            choose_male = False
            if wild or soldier_mode or ghost_mode:
                choose_male = random.choice([True, False])
            elif change_to[c] in male:
                choose_male = True

            if choose_male:
                name = random.choice(malenames)
            else:
                name = random.choice(femalenames)

            if name in malenames:
                malenames.remove(name)
            if name in femalenames:
                femalenames.remove(name)

            names.append(name)

    umaro_name = names[13]
    for umaro_id in [0x10f, 0x110]:
        change_enemy_name(fout, umaro_id, umaro_name)

    if 'capslockoff' not in activated_codes:
        names = [name.upper() for name in names]

    for c in characters:
        if c.id < 14:
            c.newname = names[c.id]
            c.original_appearance = nameiddict[c.id]

    for c, name in enumerate(names):
        name = name_to_bytes(name, 6)
        assert len(name) == 6
        fout.seek(0x478C0 + (6*c))
        fout.write(name)


def get_free_portrait_ids(swap_to, change_to, char_ids, char_portraits):
    # get unused portraits so we can overwrite them if needed
    sprite_swap_mode = 'makeover' in activated_codes
    wild = 'partyparty' in activated_codes
    if not sprite_swap_mode:
        return [], False

    def reserve_portrait_id(used_portrait_ids, new, swap, portrait):
        if swap == None:
            if portrait == 0 and wild and new != 0:
                used_portrait_ids.add(0xE)
            else:
                used_portrait_ids.add(new)
        elif not swap.has_custom_portrait():
            used_portrait_ids.add(swap.fallback_portrait_id)
        else:
            return 1
        return 0

    needed = 0
    used_portrait_ids = set()
    for c in char_ids:
        # skip characters who don't have their own portraits
        if (char_portraits[c] == 0 and c != 0) or c == 0x13:
            continue
        new = change_to[c]
        portrait = char_portraits[new]
        swap = swap_to[c] if c in swap_to else None
        needed += reserve_portrait_id(used_portrait_ids, new, swap, portrait)

    if not wild:
        for i in range(0xE,0x13):
            used_portrait_ids.add(i)

    # Merchant normally uses the same portrait as soldier.
    # If we have a free slot because some others happen to be sharing, use the portrait for the merchant sprite.
    # If not, we have to use the same one as the soldier.
    merchant = False
    if wild and needed < 19 - len(used_portrait_ids):
        c = 0x13
        new = change_to[c]
        portrait = char_portraits[new]
        swap = swap_to[c] if c in swap_to else None
        merchant = reserve_portrait_id(used_portrait_ids, new, swap, portrait)

    free_portrait_ids = list(set(range(19)) - used_portrait_ids)
    return free_portrait_ids, merchant


def get_sprite_swaps(char_ids, male, female, vswaps):
    sprite_swap_mode = 'makeover' in activated_codes
    wild = 'partyparty' in activated_codes
    clone_mode = 'attackoftheclones' in activated_codes
    replace_all = 'novanilla' in activated_codes or 'frenchvanilla' in activated_codes
    external_vanillas = False if 'novanilla' in activated_codes else ('frenchvanilla' in activated_codes or clone_mode)
    if not sprite_swap_mode:
        return []

    class SpriteReplacement:
        def __init__(self, file, name, gender, riding=None, fallback_portrait_id=0xE, portrait_filename=None, uniqueids=None, groups=None):
            self.file = file.strip()
            self.name = name.strip()
            self.gender = gender.strip().lower()
            self.size = 0x16A0 if riding is not None and riding.lower() == "true" else 0x1560
            self.uniqueids = [s.strip() for s in uniqueids.split('|')] if uniqueids else []
            self.groups = [s.strip() for s in groups.split('|')] if groups else []
            if self.gender == "female": self.groups.append("girls")
            if self.gender == "male": self.groups.append("boys")
            self.weight = 1.0
            
            if fallback_portrait_id == '':
                fallback_portrait_id = 0xE
            self.fallback_portrait_id = int(fallback_portrait_id)
            if portrait_filename is not None:
                self.portrait_filename = portrait_filename.strip()
                if self.portrait_filename:
                    self.portrait_palette_filename = portrait_filename.strip()
                    if self.portrait_palette_filename and self.portrait_palette_filename:
                        if self.portrait_palette_filename[-4:] == ".bin":
                            self.portrait_palette_filename = self.portrait_palette_filename[:-4]
                        self.portrait_palette_filename = self.portrait_palette_filename + ".pal"
                else:
                    self.portrait_filename = None

        def has_custom_portrait(self):
            return self.portrait_filename is not None and self.portrait_palette_filename is not None
            
        def is_on(self, checklist):
            val = False
            for g in self.uniqueids:
                if g in checklist:
                    return True
            return False

    f = open_mei_fallback(SPRITE_REPLACEMENT_TABLE)
    known_replacements = [SpriteReplacement(*line.strip().split(',')) for line in f.readlines()]
    f.close()

    #uniqueids for sprites pulled from rom
    vuids = { 0: "terra", 1: "locke", 2: "cyan", 3: "shadow", 4: "edgar", 5: "sabin", 6: "celes", 7: "strago", 8: "relm", 9: "setzer", 10: "moogle", 11: "gau", 12: "gogo6", 13: "umaro", 16: "leo", 17: "banon", 18: "terra", 21: "kefka" }
                
    #determine which character ids are makeover'd
    blacklist = set()
    if replace_all:
        num_to_replace = len(char_ids)
        is_replaced = [True] * num_to_replace
    else:
        replace_min = 8 if not wild else 16
        replace_max = 12 if not wild else 20
        num_to_replace = min(len(known_replacements), random.randint(replace_min,replace_max))
        is_replaced = [True] * num_to_replace + [False]*(len(char_ids)-num_to_replace)
        random.shuffle(is_replaced)
        for i, t in enumerate(is_replaced):
            if i in vuids and not t:
                blacklist.update([s.strip() for s in vuids[i].split('|')])
    
    if external_vanillas:
        #include vanilla characters, but using the same system/chances as all others
        og_replacements = [
            SpriteReplacement("ogterra.bin","Terra","female","true",0,None,"terra"),
            SpriteReplacement("oglocke.bin","Locke","male","true",1,None,"locke"),
            SpriteReplacement("ogcyan.bin","Cyan","male","true",2,None,"cyan"),
            SpriteReplacement("ogshadow.bin","Shadow","male","true",3,None,"shadow"),
            SpriteReplacement("ogedgar.bin","Edgar","male","true",4,None,"edgar"),
            SpriteReplacement("ogsabin.bin","Sabin","male","true",5,None,"sabin"),
            SpriteReplacement("ogceles.bin","Celes","female","true",6,None,"celes"),
            SpriteReplacement("ogstrago.bin","Strago","male","true",7,None,"strago"),
            SpriteReplacement("ogrelm.bin","Relm","female","true",8,None,"relm","kids"),
            SpriteReplacement("ogsetzer.bin","Setzer","male","true",9,None,"setzer"),
            SpriteReplacement("ogmog.bin","Mog","neutral","true",10,None,"moogle"),
            SpriteReplacement("oggau.bin","Gau","male","true",11,None,"gau","kids"),
            SpriteReplacement("oggogo.bin","Gogo","neutral","true",12,None,"gogo6"),
            SpriteReplacement("ogumaro.bin","Umaro","neutral","true",13,None,"umaro")]
        if wild:
            og_replacements.extend( [
                SpriteReplacement("ogtrooper.bin","Trooper","neutral","true",14),
                SpriteReplacement("ogimp.bin","Imp","neutral","true",15),
                SpriteReplacement("ogleo.bin","Leo","male","true",16,None,"leo"),
                SpriteReplacement("ogbanon.bin","Banon","male","true",17,None,"banon"),
                SpriteReplacement("ogesperterra.bin","Esper Terra","female","true",0,"esperterra-p.bin","terra"),
                SpriteReplacement("ogmerchant.bin","Merchant","male","true",1),
                SpriteReplacement("ogghost.bin","Ghost","neutral","true",18),
                SpriteReplacement("ogkefka.bin","Kefka","male","true",17,"kefka-p.bin","kefka")])
        if clone_mode:
            used_vanilla = [nameiddict[change_to[n]] for i, n in enumerate(char_ids) if not is_replaced[i]]
            og_replacements = [r for r in og_replacements if r.name not in used_vanilla]
        known_replacements.extend(og_replacements)
            
    #weight selection based on no*/hate*/like*/love* codes
    whitelist = [c[4:] for c in activated_codes if c.startswith("love")]
    replace_candidates = []
    for r in known_replacements:
        for w in whitelist:
            if w not in r.groups:
                r.weight = 0
                break
        if not r.weight: continue
        for g in r.groups:
            if not r.weight: break
            if "no"+g in activated_codes:
                r.weight = 0
            elif "hate"+g in activated_codes:
                r.weight /= 3
            elif "like"+g in activated_codes:
                r.weight *= 2
        if r.weight:
            replace_candidates.append(r)
    
    #select sprite replacements
    if not wild:
        female_candidates = [c for c in replace_candidates if c.gender == "female"]
        male_candidates = [c for c in replace_candidates if c.gender == "male"]
        neutral_candidates = [c for c in replace_candidates if c.gender != "male" and c.gender != "female"]
    
    swap_to = {}
    for id in random.sample(char_ids, len(char_ids)):
        if not is_replaced[id]:
            continue
        if wild:
            candidates = replace_candidates
        else:
            if id in female:
                candidates = female_candidates
            elif id in male:
                candidates = male_candidates
            else:
                candidates = neutral_candidates
            if random.randint(0,len(neutral_candidates)+2*len(candidates)) <= len(neutral_candidates):
                candidates = neutral_candidates
        if clone_mode:
            reverse_blacklist = [c for c in candidates if c.is_on(blacklist)]
            if reverse_blacklist:
                weights = [c.weight for c in reverse_blacklist]
                swap_to[id] = random.choices(reverse_blacklist, weights)[0]
                blacklist.update(swap_to[id].uniqueids)
                candidates.remove(swap_to[id])
                continue
        final_candidates = [c for c in candidates if not c.is_on(blacklist)]
        if final_candidates:
            weights = [c.weight for c in final_candidates]
            swap_to[id] = random.choices(final_candidates, weights)[0]
            blacklist.update(swap_to[id].uniqueids)
            candidates.remove(swap_to[id])
        else:
            print(f"custom sprite pool for {id} empty, using a vanilla sprite")
            
    return swap_to


def manage_character_appearance(preserve_graphics=False):
    characters = get_characters()
    wild = 'partyparty' in activated_codes
    sabin_mode = 'suplexwrecks' in activated_codes
    tina_mode = 'bravenudeworld' in activated_codes
    soldier_mode = 'quikdraw' in activated_codes
    moogle_mode = 'kupokupo' in activated_codes
    ghost_mode = 'halloween' in activated_codes
    christmas_mode = 'christmas' in activated_codes
    sprite_swap_mode = 'makeover' in activated_codes and not (sabin_mode or tina_mode or soldier_mode or moogle_mode or ghost_mode)
    new_palette_mode = not 'sometimeszombies' in activated_codes

    if new_palette_mode:
        # import recolors for incompatible base sprites
        recolors = [("cyan", 0x152D40, 0x16A0),  ("mog", 0x15E240, 0x16A0),
                    ("umaro", 0x162620, 0x16A0), ("dancer", 0x1731C0, 0x5C0),
                    ("lady", 0x1748C0, 0x5C0)]
        for rc in recolors:
            filename = os.path.join("data","sprites","RC" + rc[0] + ".bin")
            try:
                with open_mei_fallback(filename, "rb") as f:
                    sprite = f.read()
            except:
                continue
            if len(sprite) >= rc[2]: sprite = sprite[:rc[2]]
            fout.seek(rc[1])
            fout.write(sprite)
            
    if (wild or tina_mode or sabin_mode or christmas_mode):
        if christmas_mode:
            char_ids = list(range(0, 0x15)) # don't replace kefka
        else:
            char_ids = list(range(0, 0x16))
    else:
        char_ids = list(range(0, 0x0E))

    male = None
    female = None
    if tina_mode:
        change_to = dict(list(zip(char_ids, [0x12] * 100)))
    elif sabin_mode:
        change_to = dict(list(zip(char_ids, [0x05] * 100)))
    elif soldier_mode:
        change_to = dict(list(zip(char_ids, [0x0e] * 100)))
    elif ghost_mode:
        change_to = dict(list(zip(char_ids, [0x14] * 100)))
    elif moogle_mode:
        # all characters are moogles except Mog, Imp, and Esper Terra
        if wild:
            # make mog human
            mog = random.choice(list(range(0, 0x0A)) + list(range(0x0B, 0x0F)) +[0x10, 0x11, 0x13, 0x15])
            #esper terra and imp neither human nor moogle
            esper_terra, imp  = random.sample([0x0F, 0x12, 0x14], 2)
        else:
            mog = random.choice(list(range(0, 0x0A)) + list(range(0x0B, 0x0E)))
            esper_terra = 0x12
            imp = 0x0F
        change_to = dict(list(zip(char_ids, [0x0A] * 100)))
        change_to[0x0A] = mog
        change_to[0x12] = esper_terra
        change_to[0x0F] = imp
    else:
        female = [0, 0x06, 0x08]
        female += [c for c in [0x03, 0x0A, 0x0C, 0x0D, 0x0E, 0x0F, 0x14] if
                   random.choice([True, False])]
        female = [c for c in char_ids if c in female]
        male = [c for c in char_ids if c not in female]
        if preserve_graphics:
            change_to = dict(list(zip(char_ids, char_ids)))
        elif wild:
            change_to = list(char_ids)
            random.shuffle(change_to)
            change_to = dict(list(zip(char_ids, change_to)))
        else:
            random.shuffle(female)
            random.shuffle(male)
            change_to = dict(list(zip(sorted(male), male)) +
                             list(zip(sorted(female), female)))

    manage_character_names(change_to, male)

    swap_to = get_sprite_swaps(char_ids, male, female, change_to)

    for c in characters:
        if c.id < 14:
            if sprite_swap_mode and c.id in swap_to:
                c.new_appearance = swap_to[c.id].name
            elif not preserve_graphics:
                c.new_appearance = nameiddict[change_to[c.id]]
            else:
                c.new_appearance = c.original_appearance

    sprite_ids = list(range(0x16))

    ssizes = ([0x16A0] * 0x10) + ([0x1560] * 6)
    spointers = dict([(c, sum(ssizes[:c]) + 0x150000) for c in sprite_ids])
    ssizes = dict(list(zip(sprite_ids, ssizes)))

    char_portraits = {}
    char_portrait_palettes = {}
    sprites = {}

    riding_sprites = {}
    try:
        f = open(RIDING_SPRITE_TABLE, "r")
    except IOError:
        pass
    else:
        for line in f.readlines():
            id, filename = line.strip().split(',', 1)
            try:
                g = open_mei_fallback(os.path.join("custom", "sprites", filename), "rb")
            except IOError:
                continue

            riding_sprites[int(id)] = g.read(0x140)
            g.close()
        f.close()

    for c in sprite_ids:
        fout.seek(0x36F1B + (2*c))
        portrait = read_multi(fout, length=2)
        char_portraits[c] = portrait
        fout.seek(0x36F00 + c)
        portrait_palette = fout.read(1)
        char_portrait_palettes[c] = portrait_palette
        fout.seek(spointers[c])
        sprite = fout.read(ssizes[c])

        if c in riding_sprites:
            sprite = sprite[:0x1560] + riding_sprites[c]
        sprites[c] = sprite

    if tina_mode:
        char_portraits[0x12] = char_portraits[0]
        char_portrait_palettes[0x12] = char_portrait_palettes[0]

    portrait_data = []
    portrait_palette_data = []

    fout.seek(0x2D1D00)

    for i in range(19):
        portrait_data.append(fout.read(0x320))

    fout.seek(0x2D5860)
    for i in range(19):
        portrait_palette_data.append(fout.read(0x20))

    free_portrait_ids, merchant = get_free_portrait_ids(swap_to, change_to, char_ids, char_portraits)

    for c in char_ids:
        new = change_to[c]
        portrait = char_portraits[new]
        portrait_palette = char_portrait_palettes[new]

        if c == 0x13 and sprite_swap_mode and not merchant:
            new_soldier = change_to[0xE]
            portrait = char_portraits[new_soldier]
            portrait_palette = char_portrait_palettes[new_soldier]
        elif (char_portraits[c] == 0 and c != 0):
            portrait = char_portraits[0xE]
            portrait_palette = char_portrait_palettes[0xE]
        elif sprite_swap_mode and c in swap_to:
            use_fallback = True
            fallback_portrait_id = swap_to[c].fallback_portrait_id
            if fallback_portrait_id < 0 or fallback_portrait_id > 18:
                fallback_portrait_id = 0xE

            portrait = fallback_portrait_id * 0x320
            portrait_palette = bytes([fallback_portrait_id])
            new_portrait_data = portrait_data[fallback_portrait_id]
            new_portrait_palette_data = portrait_palette_data[fallback_portrait_id]

            if swap_to[c].has_custom_portrait():
                use_fallback = False

                try:
                    g = open_mei_fallback(os.path.join("custom", "sprites", swap_to[c].portrait_filename), "rb")
                    h = open_mei_fallback(os.path.join("custom", "sprites", swap_to[c].portrait_palette_filename), "rb")
                except IOError:
                    use_fallback = True
                    print("failed to load portrait %s for %s, using fallback" %(swap_to[c].portrait_filename, swap_to[c].name))
                else:
                    new_portrait_data = g.read(0x320)
                    new_portrait_palette_data = h.read(0x20)
                    h.close()
                    g.close()

            if not use_fallback or fallback_portrait_id in free_portrait_ids:
                portrait_id = free_portrait_ids[0]
                portrait = portrait_id * 0x320
                portrait_palette = bytes([portrait_id])
                free_portrait_ids.remove(free_portrait_ids[0])
                fout.seek(0x2D1D00 + portrait)
                fout.write(new_portrait_data)
                fout.seek(0x2D5860 + portrait_id * 0x20)
                fout.write(new_portrait_palette_data)

        elif portrait == 0 and wild and change_to[c] != 0:
            portrait = char_portraits[0xE]
            portrait_palette = char_portrait_palettes[0xE]
        fout.seek(0x36F1B + (2*c))
        write_multi(fout, portrait, length=2)
        fout.seek(0x36F00 + c)
        fout.write(portrait_palette)

        if wild:
            fout.seek(spointers[c])
            fout.write(sprites[0xE][:ssizes[c]])
        fout.seek(spointers[c])

        if sprite_swap_mode and c in swap_to:
            try:
                g = open_mei_fallback(os.path.join("custom", "sprites", swap_to[c].file), "rb")
            except IOError:
                newsprite = sprites[change_to[c]]
                for ch in characters:
                    if ch.id == c:
                        ch.new_appearance = nameiddict[change_to[c]]
            else:
                newsprite = g.read(min(ssizes[c], swap_to[c].size))
                # if it doesn't have riding sprites, it probably doesn't have a death sprite either
                if swap_to[c].size < 0x16A0:
                    newsprite = newsprite[:0xAE0] + sprites[0xE][0xAE0:0xBA0] + newsprite[0xBA0:]
                g.close()
        else:
            newsprite = sprites[change_to[c]]
        newsprite = newsprite[:ssizes[c]]
        fout.write(newsprite)

    # celes in chains
    fout.seek(0x159500)
    chains = fout.read(192)
    fout.seek(0x17D660)
    fout.write(chains)
    
    manage_palettes(change_to, char_ids)


def manage_palettes(change_to, char_ids):
    sabin_mode = 'suplexwrecks' in activated_codes
    tina_mode = 'bravenudeworld' in activated_codes
    christmas_mode = 'christmas' in activated_codes
    new_palette_mode = not 'sometimeszombies' in activated_codes
    characters = get_characters()
    npcs = get_npcs()
    charpal_options = {}
    for line in open(CHARACTER_PALETTE_TABLE):
        if line[0] == '#':
            continue
        charid, palettes = tuple(line.strip().split(':'))
        palettes = list(map(hex2int, palettes.split(',')))
        charid = hex2int(charid)
        charpal_options[charid] = palettes

    if new_palette_mode:
        twinpal = random.randint(0,5)
        char_palette_pool = list(range(0,6)) + list(range(0,6))
        char_palette_pool.remove(twinpal)
        char_palette_pool.append(random.choice(list(range(0,twinpal))+list(range(twinpal,6))))
        while True:
            random.shuffle(char_palette_pool)
            if char_palette_pool[0] == twinpal or char_palette_pool[1] == twinpal:
                continue
            break
        char_palette_pool = char_palette_pool[:4] + [twinpal, twinpal] + char_palette_pool[4:]
        
    palette_change_to = {}
    additional_celeses = []
    for npc in npcs:
        if npc.graphics == 0x41:
            additional_celeses.append(npc)
        if npc.graphics not in charpal_options:
            continue
        if npc.graphics in change_to:
            new_graphics = change_to[npc.graphics]
            if (npc.graphics, npc.palette) in palette_change_to:
                new_palette = palette_change_to[(npc.graphics, npc.palette)]
            elif new_palette_mode and npc.graphics < 14:
                new_palette = char_palette_pool[npc.graphics]
                palette_change_to[(npc.graphics, npc.palette)] = new_palette
                npc.palette = new_palette
            else:
                while True:
                    new_palette = random.choice(charpal_options[new_graphics])
                    if sabin_mode or tina_mode:
                        new_palette = random.randint(0, 5)

                    if (new_palette == 5 and new_graphics not in
                            [3, 0xA, 0xC, 0xD, 0xE, 0xF, 0x12, 0x14] and
                            random.randint(1, 10) != 10):
                        continue
                    break
                palette_change_to[(npc.graphics, npc.palette)] = new_palette
                npc.palette = new_palette
            npc.palette = new_palette
    for npc in additional_celeses:
        if (6,0) in palette_change_to:
            npc.palette = palette_change_to[(6,0)]
    
    main_palette_changes = {}
    for character in characters:
        c = character.id
        if c not in change_to:
            continue
        fout.seek(0x2CE2B + c)
        before = ord(fout.read(1))
        new_graphics = change_to[c]
        new_palette = palette_change_to[(c, before)]
        main_palette_changes[c] = (before, new_palette)
        fout.seek(0x2CE2B + c)
        fout.write(bytes([new_palette]))
        pointers = [0, 4, 9, 13]
        pointers = [ptr + 0x18EA60 + (18*c) for ptr in pointers]
        if c < 14:
            for ptr in pointers:
                fout.seek(ptr)
                byte = ord(fout.read(1))
                byte = byte & 0xF1
                byte |= ((new_palette+2) << 1)
                fout.seek(ptr)
                fout.write(bytes([byte]))
        character.palette = new_palette

    if "repairpalette" in activated_codes:
        make_palette_repair(main_palette_changes)

    if new_palette_mode:
        char_hues = shuffle_char_hues([ 0, 15, 30, 45, 60, 75, 90, 120, 150, 165, 180, 210, 240, 270, 300, 315, 330, 360 ])
        skintones = [ ( (31,24,17), (25,13, 7) ),
                      ( (31,23,15), (25,15, 8) ),
                      ( (31,24,17), (25,13, 7) ),
                      ( (31,25,15), (25,19,10) ),
                      ( (31,25,16), (24,15,12) ),
                      ( (27,17,10), (20,12,10) ),
                      ( (25,20,14), (19,12, 4) ),
                      ( (27,22,18), (20,15,12) ),
                      ( (28,22,16), (22,13, 6) ),
                      ( (28,23,15), (22,16, 7) ),
                      ( (27,23,15), (20,14, 9) ) ]
        if christmas_mode or random.randint(1,100) > 50:
            skintones.append( ((29,29,30),(25,25,27)) )
        random.shuffle(skintones)
        
    for i in range(6):
        pointer = 0x268000 + (i*0x20)
        if new_palette_mode:
            palette = recolor_character_palette(pointer, palette=None,
                                    flesh=(i == 5), santa=(christmas_mode and i==3),
                                    skintones=skintones, char_hues=char_hues)
        else:
            palette = recolor_character_palette(pointer, palette=None,
                                            flesh=(i == 5), santa=(christmas_mode and i==3))
        pointer = 0x2D6300 + (i*0x20)
        recolor_character_palette(pointer, palette=palette)

    # esper terra
    pointer = 0x268000 + (8*0x20)
    if new_palette_mode:
        palette = recolor_character_palette(pointer, palette=None, trance=True)
    else:
        palette = recolor_character_palette(pointer, palette=None, flesh=True,
                                        middle=False)
    pointer = 0x2D6300 + (6*0x20)
    palette = recolor_character_palette(pointer, palette=palette)

    # recolor magitek and chocobos
    transformer = get_palette_transformer(middle=True)

    def recolor_palette(pointer, size):
        fout.seek(pointer)
        palette = [read_multi(fout, length=2) for _ in range(size)]
        palette = transformer(palette)
        fout.seek(pointer)
        [write_multi(fout, c, length=2) for c in palette]

    recolor_palette(0x2cfd4, 23)
    recolor_palette(0x268000+(7*0x20), 16)
    recolor_palette(0x12ee20, 16)
    recolor_palette(0x12ef20, 16)

    for line in open(EVENT_PALETTE_TABLE):
        if line[0] == '#':
            continue
        pointer = hex2int(line.strip())
        fout.seek(pointer)
        data = bytearray(fout.read(5))
        char_id, palette = data[1], data[4]
        if char_id not in char_ids:
            continue
        try:
            data[4] = palette_change_to[(char_id, palette)]
        except KeyError:
            continue

        fout.seek(pointer)
        fout.write(data)


def manage_colorize_animations():
    palettes = []
    for i in range(240):
        pointer = 0x126000 + (i*16)
        fout.seek(pointer)
        palette = [read_multi(fout, length=2) for _ in range(8)]
        palettes.append(palette)

    for i, palette in enumerate(palettes):
        transformer = get_palette_transformer(basepalette=palette)
        palette = transformer(palette)
        pointer = 0x126000 + (i*16)
        fout.seek(pointer)
        [write_multi(fout, c, length=2) for c in palette]


def manage_items(items, changed_commands=None):
    from itemrandomizer import (set_item_changed_commands, extend_item_breaks)
    always_break = True if "collateraldamage" in activated_codes else False
    crazy_prices = True if "madworld" in activated_codes else False
    extra_effects= True if "masseffect" in activated_codes else False
    wild_breaks = True if "electricboogaloo" in activated_codes else False

    set_item_changed_commands(changed_commands)
    unhack_tintinabar(fout)
    extend_item_breaks(fout)

    for i in items:
        i.mutate(always_break=always_break, crazy_prices=crazy_prices, extra_effects=extra_effects, wild_breaks=wild_breaks)
        i.unrestrict()
        i.write_stats(fout)

    return items


def manage_equipment(items):
    characters = get_characters()
    reset_equippable(items, characters=characters)
    equippable_dict = {"weapon": lambda i: i.is_weapon,
                       "shield": lambda i: i.is_shield,
                       "helm": lambda i: i.is_helm,
                       "armor": lambda i: i.is_body_armor,
                       "relic": lambda i: i.is_relic}

    tempchars = [14, 15, 16, 17, 32, 33] + list(range(18, 28))
    if 'ancientcave' in activated_codes:
        tempchars += [41, 42, 43]
    for c in characters:
        if c.id >= 14 and c.id not in tempchars:
            continue
        if c.id in tempchars:
            lefthanded = random.randint(1, 10) == 10
            for equiptype in ['weapon', 'shield', 'helm', 'armor',
                              'relic1', 'relic2']:
                fout.seek(c.address + equip_offsets[equiptype])
                equipid = ord(fout.read(1))
                fout.seek(c.address + equip_offsets[equiptype])
                if lefthanded and equiptype == 'weapon':
                    equiptype = 'shield'
                elif lefthanded and equiptype == 'shield':
                    equiptype = 'weapon'
                if equiptype == 'shield' and random.randint(1, 7) == 7:
                    equiptype = 'weapon'
                equiptype = equiptype.strip('1').strip('2')
                func = equippable_dict[equiptype]
                equippable_items = list(filter(func, items))
                equipitem = random.choice(equippable_items)
                equipid = equipitem.itemid
                if (equipitem.has_disabling_status and
                        (0xE <= c.id <= 0xF or c.id > 0x1B)):
                    equipid = 0xFF
                elif equipitem.prevent_encounters and c.id in [0x1C, 0x1D]:
                    equipid = 0xFF
                else:
                    if (equiptype not in ["weapon", "shield"] and
                            random.randint(1, 100) == 100):
                        equipid = random.randint(0, 0xFF)
                fout.write(bytes([equipid]))

            continue

        equippable_items = [i for i in items if i.equippable & (1 << c.id)]
        equippable_items = [i for i in equippable_items if not i.has_disabling_status]
        equippable_items = [i for i in equippable_items if not i.banned]
        if random.randint(1, 4) < 4:
            equippable_items = [i for i in equippable_items if not i.imp_only]
        for equiptype, func in equippable_dict.items():
            if equiptype == 'relic':
                continue
            equippable = list(filter(func, equippable_items))
            weakest = 0xFF
            if equippable:
                weakest = min(equippable, key=lambda i: i.rank()).itemid
            c.write_default_equipment(fout, weakest, equiptype)

    for i in items:
        i.write_stats(fout)

    return items


def manage_reorder_rages(freespaces):
    pointer = 0x301416

    monsters = get_monsters()
    monsters = sorted(monsters, key=lambda m: m.display_name)
    monsters = [m for m in monsters if m.id <= 0xFE]
    assert len(monsters) == 255
    monster_order = [m.id for m in monsters]

    reordered_rages_sub = Substitution()
    reordered_rages_sub.bytestring = monster_order
    reordered_rages_sub.set_location(pointer)
    reordered_rages_sub.write(fout)
    hirage, midrage, lorage = ((pointer >> 16) & 0x3F) + 0xC0, (pointer >> 8) & 0xFF, pointer & 0xFF

    rage_reorder_sub = Substitution()
    rage_reorder_sub.bytestring = [
        0xA9, 0x00,         # LDA #$00
        0xA8,               # TAY
        # main loop
        # get learned rages byte, store in EE
        0xBB, 0xBF, lorage, midrage, hirage,
        0x4A, 0x4A, 0x4A,   # LSR x3
        0xAA,               # TAX
        0xBD, 0x2C, 0x1D,   # LDA $1D2C,X (get rage byte)
        0x85, 0xEE,         # STA $EE
        # get bitmask for learned rage
        0xBB, 0xBF, lorage, midrage, hirage,
        0x29, 0x07,         # AND #$07 get bottom three bits
        0xC9, 0x00,         # CMP #$00
        0xF0, 0x05,         # BEQ 5 bytes forward
        0x46, 0xEE,         # LSR $EE
        0x3A,               # DEC
        0x80, 0xF7,         # BRA 7 bytes back
        # check that rage is learned
        0xA9, 0x01,         # LDA #$01
        0x25, 0xEE,         # AND $EE
        0xEA,               # nothing
        0xC9, 0x01,         # CMP #$01
        0xD0, 0x0C,         # BNE 12 bytes forward (skip if not known)
        #0xEA, 0xEA,
        # add rage to battle menu
        0xEE, 0x9A, 0x3A,   # INC $3A9A (number of rages known)
        0xBB, 0xBF, lorage, midrage, hirage,     # get rage
        0x8F, 0x80, 0x21, 0x00,         # STA $002180 (store rage in menu)
        # check to terminate loop
        0xC8,               # INY (advance to next enemy)
        0xC0, 0xFF,         # CPY #$FF
        0xD0, 0xC8,         # BNE (loop for all enemies 0 to 254)
        # return from subroutine
        0x60,               # RTS
        ]

    myfs = get_appropriate_freespace(freespaces, rage_reorder_sub.size)
    pointer = myfs.start
    freespaces = determine_new_freespaces(freespaces, myfs, rage_reorder_sub.size)
    rage_reorder_sub.set_location(pointer)
    rage_reorder_sub.write(fout)

    rage_reorder_sub = Substitution()
    rage_reorder_sub.bytestring = [
        0x20, pointer & 0xFF, (pointer >> 8) & 0xFF,     # JSR
        0x60,                                            # RTS
        ]
    rage_reorder_sub.set_location(0x25847)
    rage_reorder_sub.write(fout)

    return freespaces


def manage_esper_boosts(freespaces):
    boost_subs = []
    esper_boost_sub = Substitution()
    # experience: $1611,X - $1613,X
    # experience from battle: $0011,X - $0013,X
    # experience needed for levelup: $ED8220,X
    # available registers: FC, FD, X
    # Y contains offset to char block and should not be changed
    esper_boost_sub.bytestring = [
        0xE2, 0x20,        # SEP #$20
        0xB9, 0x08, 0x16,  # LDA $1608,Y (load level)
        0xC9, 0x63,        # Are we level 99?
        0xD0, 0x01,        # Branch if not.
        0x60,              # RTS
        0x0A, 0xAA,        # ASL, TAX
        0xC2, 0x20,        # REP #$20 IMPORTANT
        0xBF, 0x1E, 0x82, 0xED,  # LDA $ED821E,X (load needed exp)
        0x0A, 0x0A,        # ASL, ASL
        0x79, 0x11, 0x16,  # ADC $1611,Y (low bytes exp)
        0x99, 0x11, 0x16,  # STA $1611,Y
        0xE2, 0x20,        # SEP #$20
        0x90, 0x07,        # BCC +7 (skip seven bytes)
        0xB9, 0x13, 0x16,  # LDA $1613,Y
        0x1A,              # INC
        0x99, 0x13, 0x16,  # STA $1613,Y
        0x60,              # RTS
        ]
    boost_subs.append(esper_boost_sub)

    esper_boost_sub = Substitution()
    esper_boost_sub.bytestring = [
        0xE2, 0x20,        # SEP #$20
        0xB9, 0x08, 0x16,  # LDA $1608,Y (load level)
        0xC9, 0x02,        # CMP Are we level 2?
        0xD0, 0x01,        # BNE Branch if not.
        0x60,              # RTS
        0x3A, 0x3A,        # DEC, DEC (decrease two levels)
        0x99, 0x08, 0x16,  # STA $1608,Y
        0xC2, 0x20,        # REP #$20
        0xA9, 0x00, 0x00,  # LDA #$0000
        0x99, 0x12, 0x16,  # STA $1612,Y (clear 1613)
        0xA2, 0x00, 0x00,  # LDX #$0000
        0x99, 0x11, 0x16,  # STA $1611,Y
        # ENTER LOOP
        0xE8, 0xE8,        # INX, INX
        0xB9, 0x11, 0x16,  # LDA $1611,Y
        0x18,              # CLC
        0x7F, 0x1C, 0x82, 0xED,  # ADC $ED821E,X (add needed exp)
        0x90, 0x06,        # BCC +6 (skip six bytes)
        0xDA, 0xBB,        # PHX, TYX
        0xFE, 0x13, 0x16,  # INC $1613
        0xFA,              # PLX
        0x99, 0x11, 0x16,  # STA $1611,Y
        0x8A,              # TXA
        0x4A,              # LSR
        0xE2, 0x20,        # SEP #$20
        0xD9, 0x08, 0x16,  # CMP $1608,Y
        0xC2, 0x20,        # REP #$20
        0xD0, 0xE0,        # BNE ??? bytes backwards
        # EXIT LOOP
        0xE2, 0x20,        # SEP #$20
        0xB9, 0x13, 0x16,  # LDA $1613,Y
        0x0A, 0x0A, 0x0A,  # ASL, ASL, ASL
        0x99, 0x13, 0x16,  # STA $1613,Y
        0xB9, 0x12, 0x16,  # LDA $1612,Y
        0x4A, 0x4A, 0x4A, 0x4A, 0x4A,  # LSR x5
        0x19, 0x13, 0x16,  # ORA $1613,Y
        0x99, 0x13, 0x16,  # STA $1613,Y
        0xB9, 0x12, 0x16,  # LDA $1612,Y
        0x0A, 0x0A, 0x0A,  # ASL, ASL, ASL
        0x99, 0x12, 0x16,  # STA $1612,Y
        0xB9, 0x11, 0x16,  # LDA $1611,Y
        0x4A, 0x4A, 0x4A, 0x4A, 0x4A,  # LSR x5
        0x19, 0x12, 0x16,  # ORA $1612,Y
        0x99, 0x12, 0x16,  # STA $1612,Y
        0xB9, 0x11, 0x16,  # LDA $1611,Y
        0x0A, 0x0A, 0x0A,  # ASL, ASL, ASL
        0x99, 0x11, 0x16,  # STA $1611,Y
        0x20, None, None,  # JSR to below subroutine
        0x20, None, None,  # JSR
        0x60,              # RTS

        # RANDOMLY LOWER ONE STAT
        0xBB,              # TYX
        0x20, 0x5A, 0x4B,  # JSR get random number
        0x29, 0x03,        # AND limit to 0-3
        0xC9, 0x00,        # CMP is it zero?
        0xF0, 0x04,        # BEQ skip 4 bytes
        0xE8, 0x3A,        # INX, DEC
        0x80, 0xF8,        # BRA to beginning of loop
        0xBD, 0x1A, 0x16,  # LDA $161A,X (random stat)
        0x3A,              # DEC decrease stat by 1
        0xC9, 0x00,        # CMP is it zero?
        0xD0, 0x01,        # BNE skip 1 byte
        0x1A,              # INC stat
        0x9D, 0x1A, 0x16,  # STA $161A,X
        0x60,              # RTS
        ]
    assert esper_boost_sub.bytestring.count(0x60) == 3
    boost_subs.append(esper_boost_sub)
    for boost_sub in boost_subs:
        myfs = get_appropriate_freespace(freespaces, boost_sub.size)
        pointer = myfs.start
        freespaces = determine_new_freespaces(freespaces, myfs, boost_sub.size)
        boost_sub.set_location(pointer)

        if None in boost_sub.bytestring:
            indices = [i for (i, x) in enumerate(esper_boost_sub.bytestring)
                       if x == 0x60]
            subpointer = indices[1] + 1
            subpointer = pointer + subpointer
            a, b = subpointer & 0xFF, (subpointer >> 8) & 0xFF
            while None in esper_boost_sub.bytestring:
                index = esper_boost_sub.bytestring.index(None)
                esper_boost_sub.bytestring[index:index+2] = [a, b]
            assert None not in esper_boost_sub.bytestring

        boost_sub.write(fout)

    esper_boost_sub = Substitution()
    esper_boost_sub.set_location(0x2615C)
    pointer1, pointer2 = (boost_subs[0].location, boost_subs[1].location)
    esper_boost_sub.bytestring = [
        pointer2 & 0xFF, (pointer2 >> 8) & 0xFF,
        pointer1 & 0xFF, (pointer1 >> 8) & 0xFF,
        ]
    esper_boost_sub.write(fout)

    esper_boost_sub.set_location(0xFFEED)
    desc = [hex2int(shorttexttable[c]) for c in "LV - 1   "]
    esper_boost_sub.bytestring = desc
    esper_boost_sub.write(fout)
    esper_boost_sub.set_location(0xFFEF6)
    desc = [hex2int(shorttexttable[c]) for c in "LV + 50% "]
    esper_boost_sub.bytestring = desc
    esper_boost_sub.write(fout)

    death_abuse_sub.write(fout)

    return freespaces


def manage_espers(freespaces):
    espers = get_espers()
    random.shuffle(espers)
    for e in espers:
        e.generate_spells(tierless = "madworld" in activated_codes)
        e.generate_bonus()

    bonus_espers = [e for e in espers if e.id in [15, 16]]
    random.shuffle(bonus_espers)
    bonus_espers[0].bonus = 7
    bonus_espers[1].add_spell(0x2B, 1)
    for e in sorted(espers, key=lambda e: e.name):
        e.write_data(fout)

    ragnarok_sub = Substitution()
    ragnarok_sub.set_location(0xC0B37)
    ragnarok_sub.bytestring = bytes([0xB2, 0x58, 0x0B, 0x02, 0xFE])
    ragnarok_sub.write(fout)
    pointer = ragnarok_sub.location + len(ragnarok_sub.bytestring) + 1
    a, b = pointer & 0xFF, (pointer >> 8) & 0xFF
    c = 2
    ragnarok_sub.set_location(0xC557B)
    ragnarok_sub.bytestring = bytes([0xD4, 0xDB,
                               0xDD, 0x99,
                               0x6B, 0x6C, 0x21, 0x08, 0x08, 0x80,
                               0xB2, a, b, c])
    ragnarok_sub.write(fout)
    ragnarok_sub.set_location(pointer)
    # CA5EA9
    ragnarok_sub.bytestring = bytes([0xB2, 0xA9, 0x5E, 0x00,  # event stuff
                               0x5C,
                               0xF4, 0x67,  # SFX
                               0xB2, 0xD5, 0x9A, 0x02,  # GFX
                               0x4B, 0x6A, 0x85,
                               0xB2, 0xD5, 0x9A, 0x02,  # GFX
                               0xF4, 0x8D,  # SFX
                               0x86, 0x46,  # receive esper
                               0xFE,
                               ])
    ragnarok_sub.write(fout)

    freespaces = manage_esper_boosts(freespaces)

    for e in espers:
        log(str(e), section="espers")

    return freespaces


def manage_treasure(monsters, shops=True):
    for mm in get_metamorphs():
        mm.mutate_items()
        mm.write_data(fout)

    for m in monsters:
        m.mutate_items()
        m.mutate_metamorph()
        m.write_stats(fout)

    if shops:
        buyables = manage_shops()

    pointer = 0x1fb600
    results = randomize_colosseum(outfile, fout, pointer)
    wagers = dict([(a.itemid, c) for (a, b, c, d) in results])

    def ensure_striker():
        candidates = []
        for b in buyables:
            if b == 0xFF or b not in wagers:
                continue
            intermediate = wagers[b]
            if intermediate.itemid == 0x29:
                return get_item(b)
            if intermediate in candidates:
                continue
            if intermediate.itemid not in buyables:
                candidates.append(intermediate)

        candidates = sorted(candidates, key=lambda c: c.rank())
        candidates = candidates[len(candidates)//2:]
        wager = random.choice(candidates)
        buycheck = [get_item(b).name for b in buyables
                    if b in wagers and wagers[b] == wager]
        if not buycheck:
            raise Exception("Striker pickup not ensured.")
        fout.seek(pointer + (wager.itemid*4) + 2)
        fout.write(b'\x29')
        return wager

    striker_wager = ensure_striker()
    for wager_obj, opponent_obj, win_obj, hidden in results:
        if wager_obj == striker_wager:
            win_obj = get_item(0x29)
        if hidden:
            winname = "????????????"
        else:
            winname = win_obj.name
        s = "{0:12} -> {1:12}  :  LV {2:02d} {3}".format(
            wager_obj.name, winname, opponent_obj.stats['level'],
            opponent_obj.display_name)
        log(s, section="colosseum")


def manage_chests():
    crazy_prices = True if "madworld" in activated_codes else False
    locations = get_locations(sourcefile)
    locations = sorted(locations, key=lambda l: l.rank())
    for l in locations:
        # if the Zozo clock is randomized, upgrade the chest from chain saw to pearl lance before mutating
        if 'k' in flags:
            if l.locid in [221,225,226]:
                for c in l.chests:
                    if c.contenttype == 0x40 and c.contents == 166:
                        c.contents = 33

        l.mutate_chests(crazy_prices=crazy_prices)
    locations = sorted(locations, key=lambda l: l.locid)

    for m in get_monsters():
        m.write_stats(fout)

def write_all_locations_misc():
    write_all_chests()
    write_all_npcs()
    write_all_events()
    write_all_entrances()


def write_all_chests():
    locations = get_locations()
    locations = sorted(locations, key=lambda l: l.locid)

    nextpointer = 0x2d8634
    for l in locations:
        nextpointer = l.write_chests(fout, nextpointer=nextpointer)


def write_all_npcs():
    locations = get_locations()
    locations = sorted(locations, key=lambda l: l.locid)

    nextpointer = 0x41d52
    for l in locations:
        if hasattr(l, "restrank"):
            nextpointer = l.write_npcs(fout, nextpointer=nextpointer,
                                       ignore_order=True)
        else:
            nextpointer = l.write_npcs(fout, nextpointer=nextpointer)


def write_all_events():
    locations = get_locations()
    locations = sorted(locations, key=lambda l: l.locid)

    nextpointer = 0x40342
    for l in locations:
        nextpointer = l.write_events(fout, nextpointer=nextpointer)


def write_all_entrances():
    entrancesets = [l.entrance_set for l in get_locations()]
    entrancesets = entrancesets[:0x19F]
    nextpointer = 0x1FBB00 + (len(entrancesets) * 2) + 2
    longnextpointer = 0x2DF480 + (len(entrancesets) * 2) + 2
    total = 0
    for e in entrancesets:
        total += len(e.entrances)
        nextpointer, longnextpointer = e.write_data(fout, nextpointer,
                                                    longnextpointer)
    fout.seek(e.pointer + 2)
    write_multi(fout, (nextpointer - 0x1fbb00), length=2)
    fout.seek(e.longpointer + 2)
    write_multi(fout, (longnextpointer - 0x2df480), length=2)


def manage_blitz():
    blitzspecptr = 0x47a40
    # 3: X
    # 4: Y
    # 5: L
    # 6: R
    display_inputs = {0x3: 'X', 0x4: 'Y', 0x5: 'L', 0x6: 'R',
                      0x7: 'down-left', 0x8: 'down',
                      0x9: 'down-right', 0xA: 'right',
                      0xB: 'up-right', 0xC: 'up',
                      0xD: 'up-left', 0xE: 'left'}
    adjacency = {0x7: [0xE, 0x8],  # down-left
                 0x8: [0x7, 0x9],  # down
                 0x9: [0x8, 0xA],  # down-right
                 0xA: [0x9, 0xB],  # right
                 0xB: [0xA, 0xC],  # up-right
                 0xC: [0xB, 0xD],  # up
                 0xD: [0xC, 0xE],  # up-left
                 0xE: [0xD, 0x7]}  # left
    perpendicular = {0x8: [0xA, 0xE],
                     0xA: [0x8, 0xC],
                     0xC: [0xA, 0xE],
                     0xE: [0x8, 0xC]}
    diagonals = [0x7, 0x9, 0xB, 0xD]
    cardinals = [0x8, 0xA, 0xC, 0xE]
    letters = list(range(3, 7))
    log("1. left, right, left", section="blitz inputs")
    for i in range(1, 8):
        # skip pummel
        current = blitzspecptr + (i * 12)
        fout.seek(current + 11)
        length = ord(fout.read(1)) // 2
        halflength = max(length // 2, 2)
        newlength = (halflength + random.randint(0, halflength) +
                     random.randint(1, halflength))
        newlength = min(newlength, 10)

        newcmd = []
        used_cmds = [[0xE, 0xA, 0xE]]
        while True:
            prev = newcmd[-1] if newcmd else None
            pprev = newcmd[-2] if len(newcmd) > 1 else None
            dircontinue = prev and prev in adjacency
            if prev and prev in diagonals:
                dircontinue = True
            elif prev and prev in adjacency and newlength - len(newcmd) > 1:
                dircontinue = random.choice([True, False])
            else:
                dircontinue = False

            if dircontinue:
                nextin = random.choice(adjacency[prev])
                if nextin == pprev and (prev in diagonals or
                                        random.randint(1, 3) != 3):
                    nextin = [j for j in adjacency[prev] if j != nextin][0]
                newcmd.append(nextin)
            else:
                if random.choice([True, False, prev in cardinals]):
                    if prev and prev not in letters:
                        options = [c for c in cardinals if
                                   c not in perpendicular[prev]]
                        if pprev in diagonals:
                            options = [c for c in options if c != prev]
                    else:
                        options = cardinals
                    newcmd.append(random.choice(options))
                else:
                    newcmd.append(random.choice(letters))

            if len(newcmd) == newlength:
                newcmdstr = "".join(map(chr, newcmd))
                if newcmdstr in used_cmds:
                    newcmd = []
                else:
                    used_cmds.append(newcmdstr)
                    break

        newcmd += [0x01]
        while len(newcmd) < 11:
            newcmd += [0x00]
        blitzstr = [display_inputs[j] for j in newcmd if j in display_inputs]
        blitzstr = ", ".join(blitzstr)
        blitzstr = "%s. %s" % (i+1, blitzstr)
        log(blitzstr, section="blitz inputs")
        newcmd += [(newlength+1) * 2]
        fout.seek(current)
        fout.write(bytes(newcmd))


def manage_dragons():
    dragon_pointers = [0xab6df, 0xc18f3, 0xc1920, 0xc2048,
                       0xc205b, 0xc36df, 0xc43cd, 0xc558b]
    dragons = list(range(0x84, 0x8c))
    assert len(dragon_pointers) == len(dragons) == 8
    random.shuffle(dragons)
    for pointer, dragon in zip(dragon_pointers, dragons):
        fout.seek(pointer)
        c = ord(fout.read(1))
        assert c == 0x4D
        fout.seek(pointer+1)
        fout.write(bytes([dragon]))


def manage_formations(formations, fsets):
    for fset in fsets:
        if len(fset.formations) == 4:
            for formation in fset.formations:
                formation.set_music(6)
                formation.set_continuous_music()
                formation.write_data(fout)

    for formation in formations:
        if formation.get_music() != 6:
            #print formation
            if formation.formid in [0xb2, 0xb3, 0xb6]:
                # additional floating continent formations
                formation.set_music(6)
                formation.set_continuous_music()
                formation.write_data(fout)

    ranked_fsets = sorted(fsets, key=lambda fs: fs.rank())
    ranked_fsets = [fset for fset in ranked_fsets if not fset.has_boss]
    valid_fsets = [fset for fset in ranked_fsets if len(fset.formations) == 4]

    outdoors = list(range(0, 0x39)) + [0x57, 0x58, 0x6e, 0x6f, 0x78, 0x7c]

    # don't swap with Narshe Mines formations
    valid_fsets = [fset for fset in valid_fsets if
                   fset.setid not in [0x39, 0x3A] and
                   fset.setid not in [0xB6, 0xB8] and
                   not fset.sixteen_pack and
                   set([fo.formid for fo in fset.formations]) != set([0])]

    outdoor_fsets = [fset for fset in valid_fsets if
                     fset.setid in outdoors]
    indoor_fsets = [fset for fset in valid_fsets if
                    fset.setid not in outdoors]

    def mutate_ordering(fsetset):
        for i in range(len(fsetset)-1):
            if random.choice([True, False, False]):
                fsetset[i], fsetset[i+1] = fsetset[i+1], fsetset[i]
        return fsetset

    for fsetset in [outdoor_fsets, indoor_fsets]:
        fsetset = [f for f in fsetset if f.swappable]
        fsetset = mutate_ordering(fsetset)
        fsetset = sorted(fsetset, key=lambda f: f.rank())
        for a, b in zip(fsetset, fsetset[1:]):
            a.swap_formations(b)

    # just shuffle the rest of the formations within an fset
    valid_fsets = [fset for fset in ranked_fsets if fset not in valid_fsets]
    for fset in valid_fsets:
        fset.shuffle_formations()

    indoor_formations = set([fo for fset in indoor_fsets for fo in
                             fset.formations])
    # include floating continent formations, which are weird
    indoor_formations |= set([fo for fo in formations
                              if 0xB1 <= fo.formid <= 0xBC])
    # fanatics tower too
    indoor_formations |= set([fo for fo in formations if fo.formid in
                              [0xAB, 0xAC, 0xAD,
                               0x16A, 0x16B, 0x16C, 0x16D,
                               0x18A, 0x1D2, 0x1D8, 0x1DE,
                               0x1E0, 0x1E6]])

    for formation in formations:
        formation.mutate(ap=False)
        if formation.formid == 0x1e2:
            formation.set_music(2)  # change music for Atma fight
        if formation.formid == 0x162:
            formation.ap = 255  # Magimaster
        elif formation.formid in [0x1d4, 0x1d5, 0x1d6, 0x1e2]:
            formation.ap = 100  # Triad
        formation.write_data(fout)

    return formations


def manage_formations_hidden(formations, freespaces, esper_graphics=None, form_music_overrides={}):
    for f in formations:
        f.mutate(ap=True)

    unused_enemies = [u for u in get_monsters() if u.id in REPLACE_ENEMIES]

    def unused_validator(formation):
        if formation.formid in NOREPLACE_FORMATIONS:
            return False
        if formation.formid in REPLACE_FORMATIONS:
            return True
        if not set(formation.present_enemies) & set(unused_enemies):
            return False
        return True
    unused_formations = list(filter(unused_validator, formations))

    def single_enemy_validator(formation):
        if formation in unused_formations:
            return False
        if len(formation.present_enemies) != 1:
            return False
        if formation.formid in REPLACE_FORMATIONS + NOREPLACE_FORMATIONS:
            return False
        return True
    single_enemy_formations = list(filter(single_enemy_validator, formations))

    def single_boss_validator(formation):
        if formation.formid == 0x1b5:
            # disallow GhostTrain
            return False
        if not (any([m.boss_death for m in formation.present_enemies])
                or formation.mould in range(2, 8)):
            return False
        return True
    single_boss_formations = list(filter(single_boss_validator,
                                    single_enemy_formations))

    def safe_boss_validator(formation):
        if formation in unused_formations:
            return False
        if formation.formid in REPLACE_FORMATIONS + NOREPLACE_FORMATIONS:
            return False
        if not any([m.boss_death for m in formation.present_enemies]):
            return False
        if formation.battle_event:
            return False
        if any("Phunbaba" in m.name for m in formation.present_enemies):
            return False
        if formation.get_music() == 0:
            return False
        return True

    safe_boss_formations = list(filter(safe_boss_validator, formations))
    sorted_bosses = sorted([m for m in get_monsters() if m.boss_death],
                           key=lambda m: m.stats['level'])

    repurposed_formations = []
    used_graphics = []
    mutated_ues = []
    for ue, uf in zip(unused_enemies, unused_formations):
        while True:
            vbf = random.choice(single_boss_formations)
            vboss = [e for e in vbf.enemies if e][0]

            if not vboss.graphics.graphics:
                continue

            if vboss.graphics.graphics not in used_graphics:
                used_graphics.append(vboss.graphics.graphics)
                break

        ue.graphics.copy_data(vboss.graphics)
        uf.copy_data(vbf)
        uf.lookup_enemies()
        eids = []
        if vbf.formid == 575:
            eids = [ue.id] + ([0xFF] * 5)
        else:
            for eid in uf.enemy_ids:
                if eid & 0xFF == vboss.id & 0xFF:
                    eids.append(ue.id)
                else:
                    eids.append(eid)
        uf.set_big_enemy_ids(eids)
        uf.lookup_enemies()

        for _ in range(100):
            while True:
                bf = random.choice(safe_boss_formations)
                boss_choices = [e for e in bf.present_enemies if e.boss_death]
                boss_choices = [e for e in boss_choices if e in sorted_bosses]
                if boss_choices:
                    break

            boss = random.choice(boss_choices)
            ue.copy_all(boss, everything=True)
            index = sorted_bosses.index(boss)
            index = mutate_index(index, len(sorted_bosses), [False, True],
                                 (-2, 2), (-1, 1))
            boss2 = sorted_bosses[index]
            ue.copy_all(boss2, everything=False)
            ue.stats['level'] = (boss.stats['level']+boss2.stats['level']) // 2

            if ue.id in mutated_ues:
                raise Exception("Double mutation detected.")

            try:
                myfs = get_appropriate_freespace(freespaces, ue.aiscriptsize)
            except:
                continue

            break
        else:
            continue

        pointer = myfs.start
        ue.set_relative_ai(pointer)
        freespaces = determine_new_freespaces(freespaces, myfs, ue.aiscriptsize)

        itembreaker = 'collateraldamage' in activated_codes
        randombosses = 'randombosses' in activated_codes
        madworld = 'madworld' in activated_codes
        darkworld = 'darkworld' in activated_codes
        ue.auxloc = "Missing (Boss)"
        ue.mutate_ai(change_skillset=True, itembreaker=itembreaker, randombosses=randombosses, madworld=madworld, darkworld=darkworld)
        ue.mutate_ai(change_skillset=True, itembreaker=itembreaker, randombosses=randombosses, madworld=madworld, darkworld=darkworld)

        ue.mutate(change_skillset=True, itembreaker=itembreaker, randombosses=randombosses, madworld=madworld, darkworld=darkworld)
        if random.choice([True, False]):
            ue.mutate(change_skillset=True, itembreaker=itembreaker, randombosses=randombosses, madworld=madworld, darkworld=darkworld)
        ue.treasure_boost()
        ue.graphics.mutate_palette()
        name = randomize_enemy_name(fout, ue.id)
        ue.changed_name = name
        ue.misc1 &= (0xFF ^ 0x4)  # always show name
        ue.write_stats(fout)
        fout.flush()
        ue.read_ai(outfile)
        mutated_ues.append(ue.id)
        for m in get_monsters():
            if m.id != ue.id:
                assert m.aiptr != ue.aiptr

        uf.set_music_appropriate()
        form_music_overrides[uf.formid] = uf.get_music()
        appearances = list(range(1, 14))
        if ue.stats['level'] > 50:
            appearances += [15]
        uf.set_appearing(random.choice(appearances))
        uf.get_special_ap()
        uf.mouldbyte = 0x60
        ue.graphics.write_data(fout)
        uf.misc1 &= 0xCF  # allow front and back attacks
        uf.write_data(fout)
        repurposed_formations.append(uf)

    lobo_formation = get_formation(0)
    for uf in unused_formations:
        if uf not in repurposed_formations:
            uf.copy_data(lobo_formation)

    boss_candidates = list(safe_boss_formations)
    boss_candidates = random.sample(boss_candidates,
                                    random.randint(0, len(boss_candidates)//2))
    rare_candidates = list(repurposed_formations + boss_candidates)

    zones = get_zones()
    fsets = []
    for z in zones:
        for i in range(4):
            area_name = z.get_area_name(i)
            if area_name.lower() != "unknown":
                try:
                    fs = z.fsets[i]
                except IndexError:
                    break
                if fs.setid != 0 and fs not in fsets:
                    fsets.append(fs)
    random.shuffle(fsets)

    done_fss = []

    def good_match(fs, f, multiplier=1.5):
        if fs in done_fss:
            return False
        low = max(fo.rank() for fo in fs.formations) * multiplier
        high = low * multiplier
        while random.randint(1, 4) == 4:
            high = high * 1.25
        if low <= f.rank() <= high:
            return fs.remove_redundant_formation(fsets=fsets,
                                                 check_only=True)
        return False

    rare_candidates = sorted(set(rare_candidates), key=lambda r: r.formid)
    for f in rare_candidates:
        fscands = None
        mult = 1.2
        while True:
            fscands = [fs for fs in fsets if good_match(fs, f, mult)]
            if not fscands:
                if mult >= 50:
                    break
                else:
                    mult *= 1.25
                    continue
            fs = None
            while True:
                fs = random.choice(fscands)
                fscands.remove(fs)
                done_fss.append(fs)
                result = fs.remove_redundant_formation(fsets=fsets,
                                                       replacement=f)
                if not result:
                    continue
                fs.write_data(fout)
                if not fscands:
                    break
                if random.randint(1, 5) != 5:
                    break
            break


def assign_unused_enemy_formations():
    from chestrandomizer import add_orphaned_formation, get_orphaned_formations
    get_orphaned_formations()
    siegfried = get_monster(0x37)
    chupon = get_monster(0x40)

    behemoth_formation = get_formation(0xb1)

    for enemy, music in zip([siegfried, chupon], [3, 4]):
        formid = REPLACE_FORMATIONS.pop()
        NOREPLACE_FORMATIONS.append(formid)
        uf = get_formation(formid)
        uf.copy_data(behemoth_formation)
        uf.enemy_ids = [enemy.id] + ([0xFF] * 5)
        uf.lookup_enemies()
        uf.set_music(music)
        uf.set_appearing(random.randint(1, 13))
        add_orphaned_formation(uf)


all_shops = None


def get_shops():
    global all_shops
    if all_shops:
        return all_shops

    shop_names = [line.strip() for line in open(SHOP_TABLE).readlines()]
    all_shops = []
    for i, name in zip(range(0x80), shop_names):
        if "unused" in name.lower():
            continue
        pointer = 0x47AC0 + (9*i)
        s = ShopBlock(pointer, name)
        s.set_id(i)
        s.read_data(sourcefile)
        all_shops.append(s)

    return get_shops()


def manage_shops():
    buyables = set([])
    descriptions = []
    crazy_shops = True if "madworld" in activated_codes else False
    buy_owned_breakable_tools(fout)

    for s in get_shops():
        s.mutate_items(fout, crazy_shops)
        s.mutate_misc()
        s.write_data(fout)
        buyables |= set(s.items)
        descriptions.append(str(s))

    if "ancientcave" not in activated_codes:
        for d in sorted(descriptions):
            log(d, section="shops")

    return buyables


def get_namelocdict():
    if len(namelocdict) > 0:
        return namelocdict

    for line in open(LOCATION_TABLE):
        line = line.strip().split(',')
        name, encounters = line[0], line[1:]
        encounters = list(map(hex2int, encounters))
        namelocdict[name] = encounters
        for encounter in encounters:
            assert encounter not in namelocdict
            namelocdict[encounter] = name

    return namelocdict

def manage_colorize_dungeons(locations=None, freespaces=None):
    locations = locations or get_locations()
    get_namelocdict()
    paldict = {}
    for l in locations:
        if l.setid in namelocdict:
            name = namelocdict[l.setid]
            if l.name and name != l.name:
                raise Exception("Location name mismatch.")
            elif l.name is None:
                l.name = namelocdict[l.setid]
        if l.field_palette not in paldict:
            paldict[l.field_palette] = set([])
        if l.attacks:
            formation = [f for f in get_fsets() if f.setid == l.setid][0]
            if set(formation.formids) != set([0]):
                paldict[l.field_palette].add(l)
        l.write_data(fout)

    from itertools import product
    if freespaces is None:
        freespaces = [FreeBlock(0x271530, 0x271650)]

    done = []
    for line in open(LOCATION_PALETTE_TABLE):
        line = line.strip()
        if line[0] == '#':
            continue
        line = line.split(':')
        if len(line) == 2:
            names, palettes = tuple(line)
            names = names.split(',')
            palettes = palettes.split(',')
            backgrounds = []
        elif len(line) == 3:
            names, palettes, backgrounds = tuple(line)
            names = names.split(',')
            palettes = palettes.split(',')
            backgrounds = backgrounds.split(',')
        elif len(line) == 1:
            names, palettes = [], []
            backgrounds = line[0].split(',')
        else:
            raise Exception("Bad formatting for location palette data.")

        palettes = [int(s, 0x10) for s in palettes]
        backgrounds = [int(s, 0x10) for s in backgrounds]
        candidates = set([])
        for name, palette in product(names, palettes):
            if name.endswith('*'):
                name = name.strip('*')
                break
            candidates |= set([l for l in locations if l.name == name and
                               l.field_palette == palette and l.attacks])

        if not candidates and not backgrounds:
            palettes, battlebgs = [], []

        battlebgs = set([l.battlebg for l in candidates if l.attacks])
        battlebgs |= set(backgrounds)

        transformer = None
        battlebgs = sorted(battlebgs)
        random.shuffle(battlebgs)
        for bg in battlebgs:
            palettenum = battlebg_palettes[bg]
            pointer = 0x270150 + (palettenum * 0x60)
            fout.seek(pointer)
            if pointer in done:
                #raise Exception("Already recolored palette %x" % pointer)
                continue
            raw_palette = [read_multi(fout, length=2) for i in range(0x30)]
            if transformer is None:
                if bg in [0x33, 0x34, 0x35, 0x36]:
                    transformer = get_palette_transformer(always=True)
                else:
                    transformer = get_palette_transformer(
                        basepalette=raw_palette, use_luma=True)
            new_palette = transformer(raw_palette)

            fout.seek(pointer)
            [write_multi(fout, c, length=2) for c in new_palette]
            done.append(pointer)

        for p in palettes:
            if p in done:
                raise Exception("Already recolored palette %x" % p)
            fout.seek(p)
            raw_palette = [read_multi(fout, length=2) for i in range(0x80)]
            new_palette = transformer(raw_palette)
            fout.seek(p)
            [write_multi(fout, c, length=2) for c in new_palette]
            done.append(p)


    if 'p' in flags or 's' in flags or 'partyparty' in activated_codes:
        manage_colorize_wor()
        manage_colorize_esper_world()


def manage_colorize_wor():
    transformer = get_palette_transformer(always=True)
    fout.seek(0x12ed00)
    raw_palette = [read_multi(fout, length=2) for i in range(0x80)]
    new_palette = transformer(raw_palette)
    fout.seek(0x12ed00)
    [write_multi(fout, c, length=2) for c in new_palette]

    fout.seek(0x12ef40)
    raw_palette = [read_multi(fout, length=2) for i in range(0x60)]
    new_palette = transformer(raw_palette)
    fout.seek(0x12ef40)
    [write_multi(fout, c, length=2) for c in new_palette]

    fout.seek(0x12ef00)
    raw_palette = [read_multi(fout, length=2) for i in range(0x12)]
    airship_transformer = get_palette_transformer(basepalette=raw_palette)
    new_palette = airship_transformer(raw_palette)
    fout.seek(0x12ef00)
    [write_multi(fout, c, length=2) for c in new_palette]

    for battlebg in [1, 5, 0x29, 0x2F]:
        palettenum = battlebg_palettes[battlebg]
        pointer = 0x270150 + (palettenum * 0x60)
        fout.seek(pointer)
        raw_palette = [read_multi(fout, length=2) for i in range(0x30)]
        new_palette = transformer(raw_palette)
        fout.seek(pointer)
        [write_multi(fout, c, length=2) for c in new_palette]

    for palette_index in [0x16, 0x2c, 0x2d, 0x29]:
        field_palette = 0x2dc480 + (256 * palette_index)
        fout.seek(field_palette)
        raw_palette = [read_multi(fout, length=2) for i in range(0x80)]
        new_palette = transformer(raw_palette)
        fout.seek(field_palette)
        [write_multi(fout, c, length=2) for c in new_palette]



def manage_colorize_esper_world():
    loc = get_location(217)
    chosen = random.choice([1, 22, 25, 28, 34, 38, 43])
    loc.palette_index = (loc.palette_index & 0xFFFFC0) | chosen
    loc.write_data(fout)


def manage_encounter_rate():
    if 'dearestmolulu' in activated_codes:
        overworld_rates = bytes([1, 0, 1, 0, 1, 0, 0, 0,
                           0xC0, 0, 0x60, 0, 0x80, 1, 0, 0,
                           0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
                           0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
        dungeon_rates = bytes([0, 0, 0, 0, 0, 0, 0, 0,
                         0xC0, 0, 0x60, 0, 0x80, 1, 0, 0,
                         0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
                         0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
        assert len(overworld_rates) == 32
        assert len(dungeon_rates) == 32
        encrate_sub = Substitution()
        encrate_sub.set_location(0xC29F)
        encrate_sub.bytestring = overworld_rates
        encrate_sub.write(fout)
        encrate_sub.set_location(0xC2BF)
        encrate_sub.bytestring = dungeon_rates
        encrate_sub.write(fout)
        return

    get_namelocdict()
    encrates = {}
    change_dungeons = ["floating continent", "veldt cave", "fanatics tower",
                       "ancient castle", "mt zozo", "yeti's cave",
                       "gogo's domain", "phoenix cave", "cyan's dream",
                       "ebot's rock"]

    for name in change_dungeons:
        if name == "fanatics tower":
            encrates[name] = random.randint(2, 3)
        elif random.randint(1, 3) == 3:
            encrates[name] = random.randint(1, 3)
        else:
            encrates[name] = 0

    for name in namelocdict:
        if type(name) is not str:
            continue

        for shortname in change_dungeons:
            if shortname in name:
                encrates[name] = encrates[shortname]

    zones = get_zones()
    for z in zones:
        if z.zoneid >= 0x40:
            z.rates = 0
        if z.zoneid >= 0x80:
            for setid in z.setids:
                if setid in namelocdict:
                    name = namelocdict[setid]
                    z.names[setid] = name
                    if name not in z.names:
                        z.names[name] = set([])
                    z.names[name].add(setid)
            for i, s in enumerate(z.setids):
                if s == 0x7b:
                    continue
                if s in z.names and z.names[s] in encrates:
                    rate = encrates[z.names[s]]
                    z.set_formation_rate(s, rate)
        z.write_data(fout)

    def rates_cleaner(rates):
        rates = [max(int(round(o)), 1) for o in rates]
        rates = [int2bytes(o, length=2) for o in rates]
        rates = [i for sublist in rates for i in sublist]
        return rates

    base4 = [b_t[0]*b_t[1] for b_t in zip([0xC0]*4, [1, 0.5, 2, 1])]
    bangle = 0.5
    moogle = 0.01
    overworld_rates = (
        base4 +
        [b * bangle for b in base4] +
        [b * moogle for b in base4] +
        [b * bangle * moogle for b in base4]
        )
    overworld_rates = rates_cleaner(overworld_rates)
    encrate_sub = Substitution()
    encrate_sub.set_location(0xC29F)
    encrate_sub.bytestring = bytes(overworld_rates)
    encrate_sub.write(fout)

    # dungeon encounters: normal, strongly affected by charms,
    # weakly affected by charms, and unaffected by charms
    base = 0x70
    bangle = 0.5
    moogle = 0.01
    normal = [base, base*bangle, base*moogle, base*bangle*moogle]

    half = base // 2
    quarter = base // 4
    unaffected = [base, half+quarter+(quarter*bangle),
                  half+quarter+(quarter*moogle),
                  half + (quarter*bangle) + (quarter*moogle)]

    sbase = base*2.5
    strong = [sbase, sbase*bangle/2, sbase*moogle/2, sbase*bangle*moogle/4]

    wbase = base*1.5
    half = wbase/2
    weak = [wbase, half+(half*bangle), half+(half*moogle),
            (half*bangle)+(half*moogle)]

    dungeon_rates = list(zip(normal, strong, weak, unaffected))
    dungeon_rates = [i for sublist in dungeon_rates for i in sublist]
    dungeon_rates = rates_cleaner(dungeon_rates)
    encrate_sub = Substitution()
    encrate_sub.set_location(0xC2BF)
    encrate_sub.bytestring = bytes(dungeon_rates)
    encrate_sub.write(fout)


def manage_tower():
    locations = get_locations()
    randomize_tower(filename=sourcefile)
    for l in locations:
        if l.locid in [0x154, 0x155] + list(range(104, 108)):
            # leo's thamasa, etc
            # TODO: figure out consequences of 0x154
            l.entrance_set.entrances = []
            if l.locid == 0x154:
                thamasa_map_sub = Substitution()
                for location in [0xBD330, 0xBD357, 0xBD309, 0xBD37E, 0xBD3A5,
                                 0xBD3CC, 0xBD3ED, 0xBD414]:
                    thamasa_map_sub.set_location(location)
                    thamasa_map_sub.bytestring = bytes([0x57])
                    thamasa_map_sub.write(fout)
        l.write_data(fout)

    npc = [n for n in get_npcs() if n.event_addr == 0x233B8][0]
    npc.event_addr = 0x233A6
    narshe_beginner_sub = Substitution()
    narshe_beginner_sub.bytestring = bytes([0x4B, 0xE5, 0x00])
    narshe_beginner_sub.set_location(0xC33A6)
    narshe_beginner_sub.write(fout)

def manage_strange_events():
    shadow_recruit_sub = Substitution();
    shadow_recruit_sub.set_location(0xB0A9F)
    shadow_recruit_sub.bytestring = bytes([0x42, 0x31]) # hide party member in slot 0

    shadow_recruit_sub.write(fout)
    shadow_recruit_sub.set_location(0xB0A9E)
    shadow_recruit_sub.bytestring = bytes([0x41, 0x31, # show party member in slot 0
    0x41, 0x11, # show object 11
    0x31 # begin queue for party member in slot 0
    ])
    shadow_recruit_sub.write(fout)

    shadow_recruit_sub.set_location(0xB0AD4)
    shadow_recruit_sub.bytestring = bytes([0xB2, 0x29, 0xFB, 0x05, 0x45]) # Call subroutine $CFFB29, refresh objects
    shadow_recruit_sub.write(fout)

    shadow_recruit_sub.set_location(0xFFB29)
    shadow_recruit_sub.bytestring = bytes([0xB2, 0xC1, 0xC5, 0x00, # Call subroutine $CAC5C1 (set CaseWord bit corresponding to number of characters in party)
    0xC0, 0xA3, 0x81, 0x38, 0xFB, 0x05, #If ($1E80($1A3) [$1EB4, bit 3] is set), branch to $CFFB38
    0x3D, 0x03, # Create object $03
    0x3F, 0x03, 0x01, #Assign character $03 (Actor in stot 3) to party 1
    0xFE #return
    ])
    shadow_recruit_sub.write(fout)

    # Always remove the boxes in Mobliz basement
    mobliz_box_sub = Substitution()
    mobliz_box_sub.set_location(0xC50EE)
    mobliz_box_sub.bytestring = bytes([0xC0, 0x27, 0x81, 0xB3, 0x5E, 0x00])
    mobliz_box_sub.write(fout)

    # Always show the door in Fanatics Tower level 1,
    # and don't change commands.
    fanatics_sub = Substitution()
    fanatics_sub.set_location(0xC5173)
    fanatics_sub.bytestring = bytes([0x45, 0x45, 0xC0, 0x27, 0x81, 0xB3, 0x5E, 0x00])
    fanatics_sub.write(fout)

    # skip the flashbacks of Daryl, because it's easier than making them work with unexpected parties
    daryl_cutscene_sub = Substitution()
    daryl_cutscene_sub.set_location(0xA4365)
    daryl_cutscene_sub.bytestring = bytes([0xF0, 0x76, 0x6B, 0x01, 0x04, 0x9E, 0x33, 0x01, 0xC0, 0x20, 0xC2, 0x64, 0x00, 0xFA, 0xD2, 0x11, 0x34, 0x10, 0x08, 0x40, 0xB2, 0x43, 0x48, 0x00, 0xFE])
    daryl_cutscene_sub.write(fout)

def create_dimensional_vortex():
    entrancesets = [l.entrance_set for l in get_locations()]
    entrances = []
    for e in entrancesets:
        e.read_data(sourcefile)
        entrances.extend(e.entrances)

    entrances = sorted(set(entrances), key= lambda x: (x.location.locid, x.entid if (hasattr(x, "entid") and x.entid is not None) else -1))

    # Don't randomize certain entrances
    def should_be_vanilla(k):
        if ( (k.location.locid == 0x1E and k.entid == 1) # leave Arvis's house
        or (k.location.locid == 0x14 and (k.entid == 10 or k.entid == 14)) # return to Arvis's house or go to the mines
        or (k.location.locid == 0x32 and k.entid == 3) # backtrack out of the mines
        or (k.location.locid == 0x2A) # backtrack out of the room with Terrato while you have Vicks and Wedge
        or (0xD7 < k.location.locid < 0xDC) # esper world
        or (k.location.locid == 0x137 or k.dest & 0x1FF == 0x137) # collapsing house
        or (k.location.locid == 0x180 and k.entid == 0) # weird out-of-bounds entrance in the sealed gate cave
        or (k.location.locid == 0x3B and k.dest & 0x1FF == 0x3A) # Figaro interior to throne room
        or (k.location.locid == 0x19A and k.dest & 0x1FF == 0x19A) # Kefka's Tower factory room (bottom level) conveyor/pipe
        ):
            return True
        return False

    entrances = [k for k in entrances if not should_be_vanilla(k)]

    # Make two entrances next to each other (like in the phantom train)
    # that go to the same place still go to the same place.
    # Also make matching entrances from different versions of maps
    # (like Vector pre/post esper attack) go to the same place
    duplicate_entrance_dict = {}
    equivalent_map_dict = { 0x154:0x157, 0x155:0x157, 0xFD:0xF2 }

    for i, c in enumerate(entrances):
        for d in entrances[i+1:]:
            c_locid = c.location.locid & 0x1FF
            d_locid = d.location.locid & 0x1FF
            if ((c_locid == d_locid
            or (d_locid in equivalent_map_dict and equivalent_map_dict[d_locid] == c_locid)
            or (c_locid in equivalent_map_dict and equivalent_map_dict[c_locid] == d_locid))
            and (c.dest & 0x1FF) == (d.dest & 0x1FF)
            and c.destx == d.destx and c.desty == d.desty
            and (abs(c.x - d.x) + abs(c.y - d.y)) <= 3):
                if c_locid in equivalent_map_dict:
                    duplicate_entrance_dict[c]=d
                else:
                    if c in duplicate_entrance_dict:
                        duplicate_entrance_dict[d]=duplicate_entrance_dict[c]
                    else:
                        duplicate_entrance_dict[d]=c

    entrances = [k for k in entrances if k not in equivalent_map_dict]

    entrances2 = list(entrances)
    random.shuffle(entrances2)
    for a, b in zip(entrances, entrances2):
        s = ""
        for z in entrances:
            if z == b or (z.location.locid & 0x1FF) != (b.dest & 0x1FF):
                continue
            value = abs(z.x - b.destx) + abs(z.y - b.desty)
            if value <= 3:
                break
            else:
                s += "%s " % value
        else:
            continue
        if (b.dest & 0x1FF) == (a.location.locid & 0x1FF):
            continue
        a.dest, a.destx, a.desty = b.dest, b.destx, b.desty

    for r in duplicate_entrance_dict:
        s = duplicate_entrance_dict[r]
        r.dest, r.destx, r.desty = s.dest, s.destx, s.desty

    entrancesets = entrancesets[:0x19F]
    nextpointer = 0x1FBB00 + (len(entrancesets) * 2)
    longnextpointer = 0x2DF480 + (len(entrancesets) * 2) + 2
    total = 0
    for e in entrancesets:
        total += len(e.entrances)
        nextpointer, longnextpointer = e.write_data(fout, nextpointer,
                                                    longnextpointer)
    fout.seek(e.pointer + 2)
    write_multi(fout, (nextpointer - 0x1fbb00), length=2)
    fout.seek(e.longpointer + 2)
    write_multi(fout, (longnextpointer - 0x2df480), length=2)

def change_enemy_name(fout, enemy_id, name):
    pointer = 0xFC050 + (enemy_id * 10)
    fout.seek(pointer)
    monster = get_monster(enemy_id)
    monster.changed_name = name
    name = name_to_bytes(name, 10)
    fout.write(name)


def randomize_enemy_name(fout, enemy_id):
    name = generate_name()
    change_enemy_name(fout, enemy_id, name)
    return name


def randomize_final_party_order():
    code = bytes([
        0x20, 0x99, 0xAA,       # JSR $AA99
        0xA9, 0x00,             # LDA #00
        0xA8,                   # TAY
        0xAD, 0x1E, 0x02,       # LDA $021E (frame counter)
        0x6D, 0xA3, 0x1F,       # ADC $1FA3 (encounter seed addition)
        0x8D, 0x6D, 0x1F,       # STA $1F6D
        # 21 bytes
        0xEE, 0x6D, 0x1F,       # INC $1F6D
        0xAD, 0x6D, 0x1F,       # LDA $1F6D
        0x6D, 0xA3, 0x1F,       # ADC $1FA3 (encounter seed addition)
        0xAA,                   # TAX
        0xBF, 0x00, 0xFD, 0xC0, # LDA $C0FD00,X
        0x29, 0x0F,             # AND $0F, Get bottom 4 bits
        0xC9, 0x0B,             # CMP $0B
        0xB0, 0xEC,             # BCS 20 bytes back
        0xAA,                   # TAX

        # 14 bytes
        0xB9, 0x05, 0x02,       # LDA $0205,Y
        0x48,                   # PHA
        0xBD, 0x05, 0x02,       # LDA $0205,X
        0x99, 0x05, 0x02,       # STA $0205,Y
        0x68,                   # PLA
        0x9D, 0x05, 0x02,       # STA $0205,X

        # 6 bytes
        0xC8,                   # INY
        0x98,                   # TYA
        0xC9, 0x0C,             # CMP $0C
        0x90, 0xD7,             # BCC 41 bytes back

        0x60,                   # RTS
    ])
    fout.seek(0x3AA25)
    fout.write(code)


def dummy_item(item):
    dummied = False
    for m in get_monsters():
        dummied = m.dummy_item(item) or dummied

    for mm in get_metamorphs(sourcefile):
        dummied = mm.dummy_item(item) or dummied

    for l in get_locations():
        dummied = l.dummy_item(item) or dummied

    return dummied


def manage_equip_anything():
    equip_anything_sub = Substitution()
    equip_anything_sub.set_location(0x39b8b)
    equip_anything_sub.bytestring = bytes([0x80, 0x04])
    equip_anything_sub.write(fout)
    equip_anything_sub.set_location(0x39b99)
    equip_anything_sub.bytestring = bytes([0xEA, 0xEA])
    equip_anything_sub.write(fout)


def manage_full_umaro():
    full_umaro_sub = Substitution()
    full_umaro_sub.bytestring = bytes([0x80])
    full_umaro_sub.set_location(0x20928)
    full_umaro_sub.write(fout)
    if 'u' in flags:
        full_umaro_sub.set_location(0x21619)
        full_umaro_sub.write(fout)


def manage_opening():
    d = Decompressor(0x2686C, fakeaddress=0x5000, maxaddress=0x28A60)
    d.read_data(sourcefile)

    # removing white logo screen
    d.writeover(0x501A, [0xEA] * 3)
    d.writeover(0x50F7, [0] * 62)
    d.writeover(0x5135, [0] * 0x20)
    d.writeover(0x7445, [0] * 0x20)
    d.writeover(0x5155, [0] * 80)

    # removing notices/symbols
    bg_color = d.get_bytestring(0x7BA5, 2)
    d.writeover(0x7BA7, bg_color)
    d.writeover(0x52F7, [0xEA] * 3)
    d.writeover(0x5306, [0] * 57)

    def mutate_palette_set(addresses, transformer=None):
        if transformer is None:
            transformer = get_palette_transformer(always=True)
        for address in addresses:
            palette = d.get_bytestring(address, 0x20)
            palette = transformer(palette, single_bytes=True)
            d.writeover(address, palette)

    # clouds
    tf = get_palette_transformer(always=True)
    mutate_palette_set([0x7B63, 0x7BE3, 0x7C03, 0x7C43, 0x56D9, 0x6498], tf)

    # lightning
    mutate_palette_set([0x7B43, 0x7C23, 0x5659, 0x5679, 0x5699, 0x56B9], tf)

    # fire
    mutate_palette_set([0x7B83, 0x7BA3, 0x7BC3], tf)

    # end of the world
    mutate_palette_set([0x717D, 0x719D, 0x71BD, 0x71DD])

    # magitek
    palette = d.get_bytestring(0x6470, 0x20)
    tf = get_palette_transformer(use_luma=True, basepalette=palette)
    palette = tf(palette, single_bytes=True)
    d.writeover(0x6470, palette)

    table = ("~ " + "ABCDEFGHIJKLMNOPQRSTUVWXYZ" +
             "." + "abcdefghijklmnopqrstuvwxyz")
    table = dict((c, i) for (i, c) in enumerate(table))

    def replace_credits_text(address, text, split=False):
        original = d.get_bytestring(address, 0x40)
        length = original.index(0)
        original = original[:length]
        if 0xFE in original and not split:
            linebreak = original.index(0xFE)
            length = linebreak
        if len(text) > length:
            raise Exception("Text too long to replace.")
        if not split:
            remaining = length - len(text)
            text = (" " * (remaining//2)) + text
            while len(text) < len(original):
                text += " "
        else:
            midtext = len(text)//2
            midlength = length // 2
            a, b = text[:midtext].strip(), text[midtext:].strip()
            text = ""
            for t in (a, b):
                margin = (midlength - len(t)) // 2
                t = (" " * margin) + t
                while len(t) < midlength:
                    t += " "
                text += t
                text = text[:-1] + chr(0xFE)
            text = text[:-1]
        text = [table[c] if c in table else ord(c) for c in text]
        text.append(0)
        d.writeover(address, bytes(text))

    from string import ascii_letters as alpha
    consonants = "".join([c for c in alpha if c not in "aeiouy"])
    display_flags = sorted([a for a in alpha if a in flags.lower()])
    text = "".join([consonants[int(i)] for i in str(seed)])
    codestatus = "CODES ON" if activated_codes else "CODES OFF"
    display_flags = "".join(display_flags).upper()
    replace_credits_text(0x659C, "ffvi")
    replace_credits_text(0x65A9, "BEYOND CHAOS EX")
    replace_credits_text(0x65C0, "by")
    replace_credits_text(0x65CD, "SubtractionSoup")
    replace_credits_text(0x65F1, "Based on")
    replace_credits_text(0x6605, "Beyond Chaos by Abyssonym", split=True)
    replace_credits_text(0x6625, "flags")
    replace_credits_text(0x663A, display_flags, split=True)
    replace_credits_text(0x6661, codestatus)
    replace_credits_text(0x6682, "seed")
    replace_credits_text(0x668C, text.upper())
    replace_credits_text(0x669E, "ver.")
    replace_credits_text(0x66B1, VERSION_ROMAN)
    replace_credits_text(0x66C5, "")
    replace_credits_text(0x66D8, "")
    replace_credits_text(0x66FB, "")
    replace_credits_text(0x670D, "")
    replace_credits_text(0x6732, "")

    for address in [
                    0x6758, 0x676A, 0x6791, 0x67A7, 0x67C8, 0x67DE, 0x67F4,
                    0x6809, 0x6819, 0x6835, 0x684A, 0x6865, 0x6898, 0x68CE,
                    0x68F9, 0x6916, 0x6929, 0x6945, 0x6959, 0x696C, 0x697E,
                    0x6991, 0x69A9, 0x69B8]:
        replace_credits_text(address, "")

    d.compress_and_write(fout)


def manage_ending():
    ending_sync_sub = Substitution()
    ending_sync_sub.bytestring = bytes([0xC0, 0x07])
    ending_sync_sub.set_location(0x3CF93)
    ending_sync_sub.write(fout)


def manage_auction_house():
    new_format = {
        0x4ea4: [0x5312],          # Entry Point
        0x4ecc: [0x55b0, 0x501d],  # Cherub Down (2x)
        0x501d: [0x5460],          # Chocobo
        0x5197: [0x58fa, 0x58fa],  # Golem (2x)
        0x5312: [0x5197, 0x5197],  # Zoneseek (2x)
        0x5460: [],                # Cure Ring (terminal)
        0x55b0: [0x5b85, 0x5b85],  # Hero Ring (2x)
        0x570c: [0x5cad],          # 1/1200 Airship
        0x58fa: [0x5a39, 0x5a39],  # Golem WoR (2x)
        0x5a39: [0x4ecc, 0x4ecc],  # Zoneseek WoR (2x)
        0x5b85: [0x570c, 0x570c],  # Zephyr Cape (2x)
        0x5cad: [],                # Imp Robot (terminal)
        }
    destinations = [d for (k, v) in new_format.items()
                    for d in v if v is not None]
    for key in new_format:
        if key == 0x4ea4:
            continue
        assert key in destinations
    for key in new_format:
        pointer = 0xb0000 | key
        for dest in new_format[key]:
            fout.seek(pointer)
            value = ord(fout.read(1))
            if value in [0xb2, 0xbd]:
                pointer += 1
            elif value == 0xc0:
                pointer += 3
            elif value == 0xc1:
                pointer += 5
            else:
                raise Exception("Unknown auction house byte %x %x" % (pointer, value))
            fout.seek(pointer)
            oldaddr = read_multi(fout, 2)
            assert oldaddr in new_format
            assert dest in new_format
            fout.seek(pointer)
            write_multi(fout, dest, 2)
            pointer += 3

    if 't' not in flags:
        return

    auction_items = [(0xbc, 0xB4EF1, 0xB5012, 0x0A45, 500), # Cherub Down
                     (0xbd, 0xB547B, 0xB55A4, 0x0A47, 1500), # Cure Ring
                     (0xc9, 0xB55D5, 0xB56FF, 0x0A49, 3000), # Hero Ring
                     (0xc0, 0xB5BAD, 0xB5C9F, 0x0A4B, 3000), # Zephyr Cape
                    ]
    items = get_ranked_items()
    itemids = [i.itemid for i in items]
    for i, auction_item in enumerate(auction_items):
        try:
            index = itemids.index(auction_item[0])
        except ValueError:
            index = 0
        index = mutate_index(index, len(items), [False, True],
                                 (-3, 3), (-2, 2))
        item = items[index]
        auction_sub = Substitution()
        auction_sub.set_location(auction_item[2])
        auction_sub.bytestring = bytes([0x6d, item.itemid, 0x45, 0x45, 0x45])
        auction_sub.write(fout)

        addr = 0x302000 + i * 6
        auction_sub.set_location(addr)
        auction_sub.bytestring = bytes([0x66, auction_item[3] & 0xff, (auction_item[3] & 0xff00) >> 8, item.itemid, # Show text auction_item[3] with item item.itemid
                0x94, # Pause 60 frames
                0xFE]) # return
        auction_sub.write(fout)

        addr -= 0xA0000
        addr_lo = addr & 0xff
        addr_mid = (addr & 0xff00) >> 8
        addr_hi = (addr & 0xff0000) >> 16
        auction_sub.set_location(auction_item[1])
        auction_sub.bytestring = bytes([0xB2, addr_lo, addr_mid, addr_hi])
        auction_sub.write(fout)

        table = {"0": 0x54, "1": 0x55, "2": 0x56, "3": 0x57, "4": 0x58, "5": 0x59, "6": 0x5A, "7": 0x5B, "8": 0x5C, "9": 0x5D }
        fout.seek(0xCE600)
        next_bank_index = read_multi(fout)
        opening_bid = str(auction_item[4])
        fout.seek(0xCE602 + 2 * auction_item[3])
        dialog_ptr = read_multi(fout)
        auction_sub.set_location(0xD0000 if auction_item[3] < next_bank_index else 0xE0000 + dialog_ptr)
        auction_sub.bytestring = bytes([0x01, 0x14, 0x08, 0x73, 0x1A, 0x62, 0x5E, 0x13, # "<LF>        \"<I>\"!<P>"
        0x01, 0x23, 0x48, 0xB8, 0x91, 0xA8, 0x93  # "<LF>Do I hear "
        ] + [table[x] for x in opening_bid] + [  # auction_item[4]
        0x7F, 0x26, 0x2F, 0x5F, 0x5E, 0x00]) #  " GP?!"
        auction_sub.write(fout)


def manage_bingo():
    target_score = 200.0
    print("WELCOME TO BEYOND CHAOS BINGO MODE")
    print("Include what type of squares? (blank for all)")
    print ("    a   Abilities\n"
           "    i   Items\n"
           "    m   Monsters\n"
           "    s   Spells")
    bingoflags = input("> ").strip()
    if not bingoflags:
        bingoflags = "aims"
    bingoflags = [c for c in "aims" if c in bingoflags]

    print("What size grid? (default: 5)")
    size = input("> ").strip()
    if not size:
        size = 5
    else:
        size = int(size)
    target_score = float(target_score) * (size**2)

    print("What difficulty level? Easy, Normal, or Hard? (e/n/h)")
    difficulty = input("> ").strip()
    if not difficulty:
        difficulty = "n"
    else:
        difficulty = difficulty[0].lower()
        if difficulty not in "enh":
            difficulty = "n"

    print("Generate how many cards? (default: 1)")
    numcards = input("> ").strip()
    if not numcards:
        numcards = 1
    else:
        numcards = int(numcards)
    print("Generating Bingo cards, please wait.")

    skills = get_ranked_spells()
    spells = [s for s in skills if s.spellid <= 0x35]
    abilities = [s for s in skills if 0x54 <= s.spellid <= 0xED]
    monsters = get_ranked_monsters()
    items = get_ranked_items()
    monsters = [m for m in monsters if m.display_location and
                "missing" not in m.display_location.lower() and
                "unknown" not in m.display_location.lower() and
                m.display_name.strip('_')]
    monsterskills = set([])
    for m in monsters:
        ids = set(m.get_skillset(ids_only=True))
        monsterskills |= ids
    abilities = [s for s in abilities if s.spellid in monsterskills]
    if difficulty == 'e':
        left, right = lambda x: 0, lambda x: len(x)//2
    elif difficulty == 'h':
        left, right = lambda x: len(x)//2, lambda x: len(x)
    else:
        left, right = lambda x: 0, lambda x: len(x)

    abilities = abilities[left(abilities):right(abilities)]
    items = items[left(items):right(items)]
    monsters = monsters[left(monsters):right(monsters)]
    spells = spells[left(spells):right(spells)]

    difficulty = {'e': "Easy",
                  'n': "Normal",
                  'h': "Hard"}[difficulty]
    flagnames = {'a': "Ability",
                 'i': "Item",
                 'm': "Enemy",
                 's': "Spell"}

    def generate_card(grid):
        midborder = "+" + "+".join(["-"*12]*len(grid)) + "+"
        s = midborder + "\n"
        for row in grid:
            flags = ["{0:^12}".format(c.bingoflag.upper()) for c in row]
            names = ["{0:^12}".format(c.bingoname) for c in row]
            scores = ["{0:^12}".format("%s Points" % c.bingoscore)
                      for c in row]
            flags = "|".join(flags)
            names = "|".join(names)
            scores = "|".join(scores)
            rowstr = "|" + "|\n|".join([flags, names, scores]) + "|"
            s += rowstr + "\n"
            s += midborder + "\n"
        return s.strip()

    for i in range(numcards):
        flaglists = {'a': list(abilities),
                     'i': list(items),
                     'm': list(monsters),
                     's': list(spells)}
        scorelists = dict([(x, dict({})) for x in "aims"])
        random.seed(seed + (i**2))
        grid, flaggrid, displaygrid = [], [], []
        filename = "bingo.%s.%s.txt" % (seed, i)
        s = "Beyond Chaos Bingo Card %s-%s\n" % (i, difficulty)
        s += "Seed: %s\n" % seed
        for y in range(size):
            for g in [grid, flaggrid, displaygrid]:
                g.append([])
            for x in range(size):
                flagoptions = set(bingoflags)
                if y > 0 and flaggrid[y-1][x] in flagoptions:
                    flagoptions.remove(flaggrid[y-1][x])
                if x > 0 and flaggrid[y][x-1] in flagoptions:
                    flagoptions.remove(flaggrid[y][x-1])
                if not flagoptions:
                    flagoptions = set(bingoflags)
                chosenflag = random.choice(sorted(flagoptions))
                flaggrid[y].append(chosenflag)
                chosen = random.choice(flaglists[chosenflag])
                flaglists[chosenflag].remove(chosen)
                scorelists[chosenflag][chosen] = (x, y)
                grid[y].append(chosen)
        for flag in bingoflags:
            scoredict = scorelists[flag]
            chosens = list(scoredict.keys())
            scoresum = sum([c.rank() for c in chosens])
            multiplier = target_score / scoresum
            for c in chosens:
                c.bingoscore = int(round(c.rank() * multiplier, -2))
                c.bingoflag = flagnames[flag]
                c.bingoname = (c.display_name if hasattr(c, "display_name")
                               else c.name)

        assert len(grid) == size
        assert len(grid[0]) == size
        s2 = generate_card(grid)
        s += "\n" + s2
        f = open(filename, "w+")
        f.write(s)
        f.close()


def manage_map_names():
    fout.seek(0xEF101)
    text = ("ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            "abcdefghijklmnopqrstuvwxyz"
            "0123456789")
    text = dict([(c, i + 0x20) for (i, c) in enumerate(text)])
    text[" "] = 0x7F
    pointers = {}
    for i in range(1, 101):
        pointers[i] = fout.tell()
        room_name = "Room %s" % i
        room_name = bytes([text[c] for c in room_name]) + b'\x00'
        fout.write(room_name)
        #fout.write(chr(0))

    for i in range(1, 101):
        fout.seek(0x268400 + (2*i))
        pointer = pointers[i] - 0xEF100
        write_multi(fout, pointer, length=2)


def manage_wor_skip(wor_free_char=0xB):
    characters = get_characters()

    # jump to FC end cutscene for more space
    startsub0 = Substitution()
    startsub0.bytestring = bytes([0xB2, 0x1E, 0xDD, 0x00, 0xFE])
    startsub0.set_location(0xC9A4F)
    startsub0.write(fout)

    # change code at start of game to warp to wor
    wor_sub = Substitution()
    wor_sub.bytestring = bytes([0x6C, 0x01, 0x00, 0x91, 0xD3, 0x02, # make WoR the parent map
                          0x88, 0x00, 0x00, 0x00,  # remove Magitek from Terra
                          0xD5, 0xF0,  # flag Terra as unobtained
                          0xD5, 0xE0,  # flag Terra as unobtained
                          0x3F, 0x00, 0x00,  # remove Terra from party
                          0x3F, 0x0E, 0x00,  # remove Vicks from party
                          0x3F, 0x0F, 0x00,  # remove Wedge from party
                          0x3E, 0x00,  # delete Terra
                          0x3E, 0x0E,  # delete Vicks
                          0x3E, 0x0F,  # delete Wedge

                          # there's no command to set a char's level, so I'ma
                          # do something hacky and continually set Mog/Strago's
                          # properties.  Each of them will consider the other's
                          # level as the "party average".  Strago will be
                          # boosted 2 levels above this average, and Mog will
                          # be boosted 5 levels, which effectively see-saws
                          # their levels upwards until they are around the
                          # level I want Celes to be at.
                          0xD4, 0xF7,  # flag Strago as obtained
                          0xD4, 0xE7,  # flag Strago as obtained
                          0xD4, 0xFA,  # flag Mog as obtained
                          0xD4, 0xEA,  # flag Mog as obtained
                          0x40, 0x0A, 0x0A,  # give Mog properties
                          0x40, 0x07, 0x07,  # give Strago properties
                          0x40, 0x0A, 0x0A,  # give Mog properties
                          0x40, 0x07, 0x07,  # give Strago properties
                          0x40, 0x0A, 0x0A,  # give Mog properties
                          0x40, 0x07, 0x07,  # give Strago properties
                          0x40, 0x0A, 0x0A,  # give Mog properties
                          0x40, 0x07, 0x07,  # give Strago properties
                          0x40, 0x0A, 0x0A,  # give Mog properties
                          0x40, 0x07, 0x07,  # give Strago properties
                          0x40, 0x0A, 0x0A,  # give Mog properties
                          0x40, 0x07, 0x07,  # give Strago properties
                          0x40, 0x06, 0x06,  # give Celes properties
                          0xD5, 0xF7,  # flag Strago as unobtained
                          0xD5, 0xE7,  # flag Strago as unobtained
                          0xD5, 0xFA,  # flag Mog as unobtained
                          0xD5, 0xEA,  # flag Mog as unobtained

                          0xD4, 0xF6,  # flag Celes as obtained
                          0xD4, 0xE6,  # flag Celes as obtained
                          0x3D, 0x06,  # create Celes
                          0x3F, 0x06, 0x01,  # add Celes to party

                          0x40, 0x0C, 0x1B,  # give Gogo the properties of Kamog
                          0x40, 0x0D, 0x1C,  # give Umaro the properties of Mog (three scenario party selection)
                          0x8D, 0x0C,  # unequip Kamog
                          0x8D, 0x0D,  # unequip fake Mog

                          0x40, 0x01, 0x01,  # give Locke properties
                          0x40, 0x02, 0x02,  # give Cyan properties
                          0x40, 0x03, 0x03,  # give Shadow properties
                          0x40, 0x04, 0x04,  # give Edgar properties
                          0x40, 0x05, 0x05,  # give Sabin properties
                          0x40, 0x07, 0x07,  # give Strago properties
                          0x40, 0x08, 0x08,  # give Relm properties
                          0x40, 0x09, 0x09,  # give Setzer properties
                          0x40, 0x0A, 0x0A,  # give Mog properties
                          0x40, 0x0B, 0x0B,  # give Gau properties

                          0x37, 0x01, 0x01,  # give Locke graphics
                          0x37, 0x02, 0x02,  # give Cyan graphics
                          0x37, 0x03, 0x03,  # give Shadow graphics
                          0x37, 0x04, 0x04,  # give Edgar graphics
                          0x37, 0x05, 0x05,  # give Sabin graphics
                          0x37, 0x06, 0x06,  # give Celes graphics
                          0x37, 0x07, 0x07,  # give Strago graphics
                          0x37, 0x08, 0x08,  # give Relm graphics
                          0x37, 0x09, 0x09,  # give Setzer graphics
                          0x37, 0x0A, 0x0A,  # give Mog graphics
                          0x37, 0x0B, 0x0B,  # give Gau graphics

                          0x7F, 0x00, 0x00,  # give Terra name
                          0x7F, 0x01, 0x01,  # give Locke name
                          0x7F, 0x02, 0x02,  # give Cyan name
                          0x7F, 0x03, 0x03,  # give Shadow name
                          0x7F, 0x04, 0x04,  # give Edgar name
                          0x7F, 0x05, 0x05,  # give Sabin name
                          0x7F, 0x06, 0x06,  # give Celes name
                          0x7F, 0x07, 0x07,  # give Strago name
                          0x7F, 0x08, 0x08,  # give Relm name
                          0x7F, 0x09, 0x09,  # give Setzer name
                          0x7F, 0x0A, 0x0A,  # give Mog name
                          0x7F, 0x0B, 0x0B,  # give Gau name

                          0x84, 0x50, 0xC3,  # give party 50K Gil

                          0x86, 0x36,  # give Ramuh
                          0x86, 0x37,  # give Ifrit
                          0x86, 0x38,  # give Shiva
                          0x86, 0x39,  # give Siren
                          0x86, 0x3B,  # give Shoat
                          0x86, 0x3C,  # give Maduin
                          0x86, 0x3D,  # give Bismark
                          0x86, 0x3E,  # give Stray
                          0x86, 0x47,  # give Kirin
                          0x86, 0x49,  # give Carbunkl
                          0x86, 0x4A,  # give Phantom
                          0x86, 0x4D,  # give Unicorn

                          0xB8, 0x42,  # allow Morph
                          0xB8, 0x43,  # display AP
                          0xB8, 0x49,  # Gau handed Meat
                          0xB8, 0x4B,  # Shadow can't leave
                          0xE8, 0x06, 0x08, 0x00,  # set up 8 dragons
                          ])

    # assign a palette to each character
    partymembers = [c for c in characters if 1 <= c.id <= 12]
    for character in partymembers:
        id = character.id
        palette = character.palette
        wor_sub.bytestring += bytes([0x43, id, palette])

    # obtain all locations with WoB treasures
    wobtreasurelocs = []
    for line in open(WOB_TREASURE_TABLE):
        line = line.strip()
        wobtreasurelocs.append(line)

    # obtain a list of all treasures in these areas
    wobtreasures = []
    for l in get_locations():
        if not l.chests:
            continue
        if l.area_name.upper() in wobtreasurelocs:
            wobtreasures.extend(l.treasure_ids)

    # give the items to the player via event code
    for t in wobtreasures:
        wor_sub.bytestring += bytes([0x80, t])

    # give WoB event items
    event_items = get_event_items()
    for l in event_items:
        if l.upper() in wobtreasurelocs + ["FIGARO CASTLE"]:
            for e in event_items[l]:
                if e.contenttype == 0x40 and not e.multiple:
                    wor_sub.bytestring += bytes([0x80, e.contents])

    # give the player a basic set of items.  These items are intended to
    # reflect the items a player would probably have by the time they get this
    # far, so that they aren't missing basic supplies they would have in almost any seed.
    for line in open(WOR_ITEMS_TABLE):
        line = line.strip().split(',')
        for i in range (0, int(line[1])):
            wor_sub.bytestring += bytes([0x80, int(line[0], 16)])

    # jump to overwriting the Ramuh cutscene because we need even more space
    wor_sub.bytestring += bytes([0xB2, 0x49, 0x97, 0x00,
                           0xFE
                          ])
    wor_sub.set_location(0xADD1E)
    wor_sub.write(fout)
    wor_sub2 = Substitution()
    wor_sub2.bytestring = bytearray([])

    # set most of the event bits that would have been set in the WoB
    for line in open(WOB_EVENTS_TABLE):
        line = line.strip().split(',')
        setbit = int(line[1], 16)  # if 1, set the bit from the txt file
        bit = line[0]  # the bit to set/clear from the txt file
        if bit == "2FB":
            bit = "2F" + hex(wor_free_char)[2:]
        firstbyte = 0xD1 + int(bit[0:1], 16) * 2 - setbit
        lastbyte = int(bit[1:], 16)
        wor_sub2.bytestring += bytearray([firstbyte, lastbyte])

    wor_sub2.bytestring += bytearray([0x6B, 0x01, 0x00, 0x91, 0xD3, 0x00, # go to WoR
                            0xFF,  # end map script
                            0xFE,  # return
                            ])

    wor_sub2.set_location(0xA9749)
    wor_sub2.write(fout)

    # set more Lores as starting Lores
    odds = [True, True, False]
    address = 0x26F564
    fout.seek(address)
    extra_known_lores = read_multi(fout, length=3)
    for i in range(24):
        if random.choice(odds):
            extra_known_lores |= (1 << i)
        if random.choice([True, False, False]):
            odds.append(False)
    fout.seek(address)
    write_multi(fout, extra_known_lores, length=3)

def manage_clock():
    hour = random.randint(0,5)
    minute = random.randint(0,4)
    second = random.randint(0,4)

    # Change correct options
    hour_sub = Substitution()
    hour_sub.bytestring = bytearray([0xE4, 0x96, 0x00] * 6)
    hour_sub.bytestring[hour*3] = 0xE2
    hour_sub.set_location(0xA96CF)
    hour_sub.write(fout)

    minute_sub = Substitution()
    minute_sub.bytestring = bytearray([0xFA, 0x96, 0x00] * 5)
    minute_sub.bytestring[minute*3] = 0xF8
    minute_sub.set_location(0xA96E8)
    minute_sub.write(fout)

    second_sub = Substitution()
    second_sub.bytestring = bytearray([0x16, 0x97, 0x00] * 5)
    second_sub.bytestring[second*3] = 0x0E
    second_sub.set_location(0xA96FE)
    second_sub.write(fout)

    clockstr = "%d:%02d:%02d" % ((hour+1)*2, (minute+1) * 10, (second+1) * 10)
    log(clockstr, section="zozo clock")

    # Change text of hints
    wrong_hours = [0, 1, 2, 3, 4, 5]
    wrong_hours.remove(hour)
    random.shuffle(wrong_hours)
    hour_to_hex = [dialogue_to_bytes('2', null_terminate=False),dialogue_to_bytes('4', null_terminate=False), dialogue_to_bytes('6', null_terminate=False), dialogue_to_bytes('8', null_terminate=False), dialogue_to_bytes('10', null_terminate=False), dialogue_to_bytes('12', null_terminate=False)]

    f = open(sourcefile, 'r+b')
    start = 0xDACC7
    end = 0xDAD18
    f.seek(start)
    hour_strings = f.read(end - start)
    f.close()

    hour_strings = hour_strings[0:6] + hour_to_hex[wrong_hours[0]] + hour_strings[7:21] + hour_to_hex[wrong_hours[1]] + hour_strings[22:42] + hour_to_hex[wrong_hours[2]] + hour_strings[43:48] + hour_to_hex[wrong_hours[3]] + hour_strings[50:75] + hour_to_hex[wrong_hours[4]] + hour_strings[77:]

    if hour >= 4: # double digit hour
        hour_strings = hour_strings + b'\0'

    hour_text_sub = Substitution()
    hour_text_sub.bytestring = bytes(hour_strings)
    hour_text_sub.set_location(start)
    hour_text_sub.write(fout)

    ptr_start = 0xCE602
    ptr_index = 0x416

    f = open(outfile, 'r+b')
    offset = 0

    #adjust text pointers
    for i in range(1,5):
        location = ptr_start + (ptr_index+i) * 2
        f.seek(location)
        ptr = read_multi(f, 2)
        if i <= 3:
            if wrong_hours[i-1] >= 4:
                offset += 1
        elif wrong_hours[i-1] < 4:
            offset -= 1
        f.seek(location)
        write_multi(f, ptr + offset, 2)

    f.close()

    # Change text that says "Hand's pointin' at the two."
    if minute != 0:
        minute_text_sub = Substitution()
        if minute == 1:
            minute_text_sub.bytestring = bytes([0xAB, 0x8B, 0x4B]) # ' f', 'ou', 'r'
        elif minute == 2:
            minute_text_sub.bytestring = bytes([0x8E, 0x42, 0x51]) # ' s', 'i', 'x'
        elif minute == 3:
            minute_text_sub.bytestring = bytes([0x7F, 0x5C, 0x65, 0x00]) # ' ', '8', '.', '\0'
        else:
            minute_text_sub.bytestring = bytes([0x81, 0x3E, 0x47]) # ' t', 'e', 'n'

        minute_text_sub.set_location(0xDB035)
        minute_text_sub.write(fout)


    wrong_seconds = [0, 1, 2, 3, 4]
    wrong_seconds.remove(second)
    random.shuffle(wrong_seconds)

    double_clue = wrong_seconds[:2]
    wrong_seconds = wrong_seconds[2:]

    if 0 in double_clue and 1 in double_clue:
        # Change to "The seconds? They're less than 30!".

        second_text_sub0 = Substitution()
        second_text_sub0.bytestring = bytes([0xBB, 0xAF, 0x86, 0x83, 0x8F, 0x7F, 0x57, 0x54, 0x5E, 0x00]) # ' l', 'es', 's ' 'th', 'an', ' ', '3', '0', '!', '\0'
        second_text_sub0.set_location(0xDAEE4)
        second_text_sub0.write(fout)

    elif 0 in double_clue and 2 in double_clue:
        # Change to "The seconds? They're a factor of 30!".

        second_text_sub0 = Substitution()
        second_text_sub0.bytestring = bytes([0x88, 0xAB, 0xEE, 0x96, 0x93, 0xD8, 0x7F, 0x57, 0x54, 0x5E, 0x00]) # ' a', ' f', 'ac', 'to', 'r ', 'of', ' ', '3', '0', '!', '\0',
        second_text_sub0.set_location(0xDAEE4)
        second_text_sub0.write(fout)

    elif 0 in double_clue and 3 in double_clue:
        # Change to "The seconds are 10 modulo 30.".

        second_text_sub0 = Substitution()
        second_text_sub0.bytestring = bytes([0x88, 0x89, 0x7F, 0x55, 0x54, 0x9C, 0x48, 0x3D, 0x4E, 0xEA, 0x7F, 0x57, 0x54, 0x65, 0x00]) # ' a', 're', ' ', '1', '0', ' m', 'o', 'd', 'u', 'lo',  ' ', '3', '0', '.', '\0',
        second_text_sub0.set_location(0xDAEDD)
        second_text_sub0.write(fout)

    elif 0 in double_clue and 4 in double_clue:
        # Change to "The second hand's pointin' a bit upward." (i.e., 10 or 50)
        second_text_sub0 = Substitution()
        second_text_sub0.bytestring = bytes([0x91, 0x8F, 0x3D, 0xB4, 0x7F, 0x49, 0x48, 0x8A, 0xE8, 0xE2, 0x88, 0xA1, 0xA5, 0xF1, 0x49, 0x50, 0x3A, 0x4B, 0x3D, 0x65]) # ' h', 'an', 'd', '\'s', ' ', 'p', 'o', 'in', 'ti', 'n\'', '_a', '_b', 'it', ' u', 'p' 'w', 'a', 'r', 'd', '.'
        second_text_sub0.set_location(0xDAEDC)
        second_text_sub0.write(fout)

    elif 1 in double_clue and 2 in double_clue:
        # Change to "The seconds? They're around 25!".
        second_text_sub0 = Substitution()
        second_text_sub0.bytestring = bytes([0x88, 0xCA, 0x4E, 0xB5, 0x7F, 0x56, 0x59, 0x5E, 0x00]) # ' a', 'ro', 'u', 'nd', ' ', '2', '5', '!', '\0',
        second_text_sub0.set_location(0xDAEE4)
        second_text_sub0.write(fout)

    #elif 1 in double_clue and 3 in double_clue:
        # Leave the clue as "The seconds? They're divisible by 20!".

    elif 1 in double_clue and 4 in double_clue:
        # Change to "The seconds are 20 modulo 30.".

        second_text_sub0 = Substitution()
        second_text_sub0.bytestring = bytes([0x88, 0x89, 0x7F, 0x56, 0x54, 0x9C, 0x48, 0x3D, 0x4E, 0xEA, 0x7F, 0x57, 0x54, 0x65, 0x00]) # ' a', 're', ' ', '2', '0', ' m', 'o', 'd', 'u', 'lo',  ' ', '3', '0', '.', '\0',
        second_text_sub0.set_location(0xDAEDD)
        second_text_sub0.write(fout)

    elif 2 in double_clue and 3 in double_clue:
        # Change to "The seconds? They're around 35!".
        second_text_sub0 = Substitution()
        second_text_sub0.bytestring = bytes([0x88, 0xCA, 0x4e, 0xB5, 0x7F, 0x57, 0x59, 0x5E, 0x00]) # ' a', 'ro', 'u', 'nd', ' ', '3', '5', '!', '\0',
        second_text_sub0.set_location(0xDAEE4)
        second_text_sub0.write(fout)

    elif 2 in double_clue and 4 in double_clue:
        # Change to "The seconds are an odd prime times 10!".
        second_text_sub0 = Substitution()
        second_text_sub0.bytestring = bytes([0x88, 0x89, 0x88, 0x94, 0x48, 0x3D, 0x8C, 0x49, 0xCC, 0xA2, 0x81, 0x42, 0xA2, 0x86, 0x55, 0x54, 0x5E, 0x00]) # ' a', 're', ' a', 'n ', 'o', 'd', 'd ', 'p', 'ri', 'me', ' t', 'i', 'me', 's ', '1', '0', '!'
        second_text_sub0.set_location(0xDAEDD)
        second_text_sub0.write(fout)

    elif 3 in double_clue and 4 in double_clue:
        # Change to "The seconds? They're greater than 30!".
        second_text_sub0 = Substitution()
        second_text_sub0.bytestring = bytes([0xC6, 0x89, 0x95, 0x87, 0x81, 0x9B, 0x94, 0x57, 0x54, 0x5E, 0x00]) # ' g', 're', 'at', 'er', ' t', 'ha', 'n', '3', '0', '!', '\0',
        second_text_sub0.set_location(0xDAEE4)
        second_text_sub0.write(fout)


    # Change text that says 'Clock's second hand's pointin' at 30'
    second_text_sub1 = Substitution()
    second_text_sub1.bytestring = bytes([0x55 + wrong_seconds[0]])
    second_text_sub1.set_location(0xDAEA4)
    second_text_sub1.write(fout)

    if wrong_seconds[1] != 1:
        # Change clue that says "The second hand of my watch is pointing at four."
        # In the original game, this clue is redundant. It should say "at two".
        second_text_sub2 = Substitution()
        if wrong_seconds[1] == 0:
            second_text_sub2.bytestring = bytes([0x81, 0x50, 0x48]) #' t', 'w', 'o'
        elif wrong_seconds[1] == 2:
            second_text_sub2.bytestring = bytes([0x8E, 0x42, 0x51]) #' s', 'i', 'x'
        elif wrong_seconds[1] == 3:
            second_text_sub2.bytestring = bytes([0x7F, 0x5C, 0x65, 0x00]) # ' ', '8', '.', '\0'
        else:
            second_text_sub2.bytestring = bytes([0x81, 0x3E, 0x47]) #' t', 'e', 'n'
        second_text_sub2.set_location(0xDAF63)
        second_text_sub2.write(fout)

def manage_ancient(form_music_overrides={}):
    change_battle_commands = [41, 42, 43]
    if 'o' not in flags:
        alrs = AutoLearnRageSub(require_gau=True)
        alrs.set_location(0x23b73)
        alrs.write(fout)

        enable_morph_sub = Substitution()
        enable_morph_sub.bytestring = bytes([0xEA] * 2)
        enable_morph_sub.set_location(0x25410)
        enable_morph_sub.write(fout)

        enable_mpoint_sub = Substitution()
        enable_mpoint_sub.bytestring = bytes([0xEA] * 2)
        enable_mpoint_sub.set_location(0x25E38)
        enable_mpoint_sub.write(fout)

        change_battle_commands += list(range(18, 28))

    moogle_commands = [0x03, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0a, 0x0b,
                       0x0d, 0x0e, 0x0f, 0x10, 0x12, 0x13, 0x16, 0x18,
                       0x1a, 0x1b, 0x1d]
    for i in change_battle_commands:
        commands = random.sample(moogle_commands, 2)
        c = get_character(i)
        c.battle_commands = [0x00, commands[0], commands[1], 0x01]
        c.write_battle_commands(fout)

    for i in [32, 33]:
        c = get_character(i)
        c.battle_commands = [0x00, 0x1D, 0xFF, 0x01]
        c.write_battle_commands(fout)

    characters = get_characters()
    gau = [c for c in characters if c.id == 11][0]
    if 'w' not in flags and gau.battle_commands[1] in [0x11, None]:
        gau.battle_commands[1] = 0xFF
        gau.write_battle_commands(fout)

    to_dummy = [get_item(0xF6), get_item(0xF7)]
    dummy_names = ["Pebble", "Tissue"]
    for dummy_name, item in zip(dummy_names, to_dummy):
        name = bytes([0xFF]) + name_to_bytes(dummy_name, 12)
        item.dataname = name
        item.price = 4
        item.itemtype = 6
        item.write_stats(fout)
    blank_sub = Substitution()
    blank_sub.set_location(0x2D76C1)
    blank_sub.bytestring = bytearray([0xFF] * (0x2D76F5 - blank_sub.location))
    blank_sub.bytestring[blank_sub.size//2] = 0
    blank_sub.write(fout)

    goddess_save_sub = Substitution()
    goddess_save_sub.bytestring = bytes([0xFD, 0xFD])
    goddess_save_sub.set_location(0xC170A)
    goddess_save_sub.write(fout)
    goddess_save_sub.set_location(0xC1743)
    goddess_save_sub.write(fout)
    goddess_save_sub.set_location(0xC1866)
    goddess_save_sub.write(fout)

    # decrease exp needed for level up
    if 'racecave' in activated_codes:
        maxlevel = 49
        divisor = 12.0
    elif 'speedcave' in activated_codes:
        maxlevel = 49
        divisor = 8.0
    else:
        maxlevel = 49
        divisor = 2.0

    for level in range(maxlevel):
        ratio = (float(level) / maxlevel)**2
        ratio = min(ratio, 1.0)
        xptr = 0x2d8220 + (level*2)
        fout.seek(xptr)
        exp = read_multi(fout, length=2)
        newexp = (exp / divisor)
        remaining = exp - newexp
        newexp = int(round(newexp + (ratio*remaining)))
        newexp = max(newexp, 1)
        fout.seek(xptr)
        write_multi(fout, newexp, length=2)

    startsub = Substitution()
    startsub.bytestring = bytearray([0xD7, 0xF3,  # remove Daryl
                           0xD5, 0xF0,  # remove Terra from party
                           0xD5, 0xE0,  # remove Terra from party
                           0xDC, 0x7E,  # fix ending? $1F4F bit 6
                           0xB8, 0x43,  # show magic points after battle
                           0x3F, 0x0E, 0x00,
                           0x3F, 0x0F, 0x00,
                           ])
    if 'racecave' in activated_codes:
        num_starting = 9 + random.randint(0, 2) + random.randint(0, 1)
    elif 'speedcave' in activated_codes:
        num_starting = 4 + random.randint(0, 3) + random.randint(0, 2)
    else:
        num_starting = 4 + random.randint(0, 1) + random.randint(0, 1)
    starting = random.sample(list(range(14)), num_starting)
    for c in starting:
        startsub.bytestring += bytearray([0xD4, 0xF0 | c])
        startsub.bytestring += bytearray([0xD4, 0xE0 | c])

    for c in characters:
        i = c.id
        cptr = 0x2d7ca0 + 0x15 + (i*22)
        fout.flush()
        fout.seek(cptr)
        level = ord(fout.read(1))
        level &= 0xF3
        if i >= 14 or "speedcave" in activated_codes and i not in starting:
            level |= 0b1000
        fout.seek(cptr)
        fout.write(bytes([level]))
    fout.seek(0xa5e74)
    fout.write(b'\x00')  # remove Terra's magitek

    tempcands = [14, 15, random.choice(list(range(18, 28))), random.choice([32, 33])]
    if 'speedcave' in activated_codes:
        tempcands.append(random.choice([16, 17]))
        tempcands.append(random.choice([41, 42, 43]))
    charcands = list(range(14)) + random.sample(tempcands, 2)
    chargraphics = {14: 0x11, 15: 0x10, 16: 0x14, 17: 0x14, 32: 0xE, 33: 0xE,
                    41: 0x15, 42: 0x15, 43: 0x15}
    for c in range(14):
        chargraphics[c] = c
    for c in range(18, 28):
        chargraphics[c] = 0xA
    for n, i in enumerate(charcands):
        c = [x for x in characters if x.id == i][0]
        if i in chargraphics:
            g = chargraphics[i]
        else:
            g = i
        startsub.bytestring.extend([0x7F, n, i,
                                    0x37, n, g,
                                    0x43, n, c.palette,
                                    0x40, n, i])
        c.slotid = n

    runaway = random.choice([c for c in characters if hasattr(c, "slotid")
                             and c.id == c.slotid]).slotid
    if runaway in starting:
        byte, bit = runaway // 8, runaway % 8
        mem_addr = ((0x1b+byte) << 3) | bit
        startsub.bytestring += bytearray([0xD7, mem_addr])
    shadow_leaving_sub = Substitution()
    shadow_leaving_sub.set_location(0x248A6)
    shadow_leaving_sub.bytestring = bytearray([
        0x1C, 0xDE + (runaway//8), 0x1E,     # TRB $1ede
        0x20, 0xE3, 0x47,
        0xAD, 0xFB + (runaway//8), 0x1E,     # LDA $1efb
        0x09, 1 << (runaway % 8),           # ORA #$08
        0x8D, 0xFB + (runaway//8), 0x1E,     # STA $1efb
        0xAD, 0xDE + (runaway//8), 0x1E,     # LDA $1ede
        0x29, 0xFF ^ (1 << (runaway % 8)),  # AND #$F7
        0x8D, 0xDE + (runaway//8), 0x1E,     # STA $1ede
        ])
    while len(shadow_leaving_sub.bytestring) < 23:
        shadow_leaving_sub.bytestring.append(0xEA)
    shadow_leaving_sub.bytestring += bytearray([0xA9, 0xFE,
                                      0x20, 0x92, 0x07])
    shadow_leaving_sub.write(fout)
    shadow_leaving_sub.set_location(0x24861)
    shadow_leaving_sub.bytestring = bytearray([
        0xAE, runaway, 0x30,
        0x30, 0x26,
        0x20, 0x5A, 0x4B,
        0xC9, random.choice([0x20, 0x10, 0x8, 0x4, 0x2, 0x1]),
        0xB0, 0x1F,
        0xAD, 0x1F, 0x20,
        0xD0, 0x1A,
        0xAD, 0x76, 0x3A,
        0xC9, 0x02,
        0x90, 0x13,
        0xBD, 0xE4, 0x3E,
        0x89, 0xC2,
        0xD0, 0x0C,
        0xA9, 1 << (runaway % 8),
        0x2C, 0xBD + (runaway//8), 0x3E,
        0xD0, 0x05,
        0x2C, 0xDE + (runaway//8), 0x1E,
        ])
    shadow_leaving_sub.write(fout)
    shadow_leaving_sub.set_location(0x10A851)
    shadow_leaving_sub.bytestring = bytearray([
        0x0E, 0x03, runaway, 0x6A, 0xA8, 0x0F,
        0x11,
        0x01, 0xFB,
        0x0E, 0x03, runaway, 0x7E, 0xA8, 0x0F,
        0x01, 0xFC,
        0x0E, 0x03, runaway, 0x92, 0xA8, 0x0F,
        0x10, 0xFF,
        ])
    shadow_leaving_sub.write(fout)
    shadow_leaving_sub.bytestring = bytearray([runaway])
    shadow_leaving_sub.set_location(0x10FC2F)
    shadow_leaving_sub.write(fout)
    shadow_leaving_sub.set_location(0x10FC5D)
    shadow_leaving_sub.write(fout)

    esperevents = [
        "Ramuh", "Ifrit", "Shiva", "Siren", "Terrato", "Shoat", "Maduin",
        "Bismark", "Stray", "Palidor", "Tritoch", "Odin", "Raiden", "Bahamut",
        "Alexandr", "Crusader", "Ragnarok", "Kirin", "ZoneSeek", "Carbunkl",
        "Phantom", "Sraphim", "Golem", "Unicorn", "Fenrir", "Starlet",
        "Phoenix"]
    esperevents = dict([(n, i) for (i, n) in enumerate(esperevents)])
    espers = list(get_espers())
    num_espers = 3
    for i in range(num_espers):
        if "speedcave" in activated_codes:
            esperrank = 999
        else:
            esperrank = 0
            while random.randint(1, 3) == 3:
                esperrank += 1
        candidates = [e for e in espers if e.rank <= esperrank]
        esper = random.choice(candidates)
        espers.remove(esper)
        event_value = esperevents[esper.name] + 0x36
        startsub.bytestring += bytearray([0x86, event_value])
    for i in range(27):  # espers
        byte, bit = i // 8, i % 8
        mem_addr = ((0x17+byte) << 3) | bit
        startsub.bytestring += bytearray([0xD6, mem_addr])
    for i in range(16):  # characters
        if i in starting:
            continue
        byte, bit = i // 8, i % 8
        mem_addr = ((0x1b+byte) << 3) | bit
        startsub.bytestring += bytearray([0xD6, mem_addr])
    startsub.bytestring += bytearray([0xB2, 0x09, 0x21, 0x02,  # start on airship
                            ])
    startsub.bytestring.append(0xFE)
    startsub.set_location(0xADD1E)
    startsub.write(fout)

    startsub0 = Substitution()
    startsub0.bytestring = bytearray([0xB2, 0x1E, 0xDD, 0x00, 0xFE])
    startsub0.set_location(0xC9A4F)
    startsub0.write(fout)

    set_airship_sub = Substitution()
    set_airship_sub.bytestring = bytearray([0xB2, 0xD6, 0x02, 0x00,
                                  0xFE])
    set_airship_sub.set_location(0xAF53A)  # need first branch for button press
    set_airship_sub.write(fout)

    tower_msg_sub = Substitution()
    tower_msg_sub.bytestring = bytearray([0xD6, 0xE6, 0xD6, 0xE7])  # reset temp chars
    while len(tower_msg_sub.bytestring) < 12:
        tower_msg_sub.bytestring.append(0xFD)
    tower_msg_sub.set_location(0xA03A7)
    tower_msg_sub.write(fout)

    from locationrandomizer import NPCBlock, EventBlock
    falcon = get_location(0xb)
    save_point = NPCBlock(pointer=None, locid=falcon.locid)
    attributes = {
        "graphics": 0x6f, "palette": 6, "x": 20, "y": 8,
        "event_addr": 0x5eb3, "facing": 0x47,
        "memaddr": 0, "membit": 0, "unknown": 0,
        "graphics_index": 0x10}
    for key, value in attributes.items():
        setattr(save_point, key, value)
    save_point.set_id(len(falcon.npcs))
    falcon.npcs.append(save_point)
    save_event = EventBlock(pointer=None, locid=falcon.locid)
    attributes = {"event_addr": 0x29aeb, "x": 20, "y": 8}
    for key, value in attributes.items():
        setattr(save_event, key, value)
    falcon.events.append(save_event)
    partyswitch = NPCBlock(pointer=None, locid=falcon.locid)
    attributes = {
        "graphics": 0x17, "palette": 0, "x": 16, "y": 6,
        "event_addr": 0x047d, "facing": 2,
        "memaddr": 0, "membit": 0, "unknown": 0,
        "graphics_index": 0, "npcid": 2}
    for key, value in attributes.items():
        setattr(partyswitch, key, value)
    falcon.npcs.append(partyswitch)

    pilot = random.choice([s for s in starting if s < 12])
    pilot_sub = Substitution()
    pilot_sub.bytestring = bytearray([0x3D, pilot, 0x45,
                            0x3F, pilot, 0x01])
    for i in range(14):
        if i == pilot:
            continue
        pilot_sub.bytestring += bytearray([0x3F, i, 0x00])
    pilot_sub.set_location(0xC2110)
    pilot_sub.write(fout)

    if "racecave" in activated_codes:
        randomize_tower(filename=sourcefile, ancient=True, nummaps=50)
    elif "speedcave" in activated_codes:
        randomize_tower(filename=sourcefile, ancient=True, nummaps=85)
    else:
        randomize_tower(filename=sourcefile, ancient=True, nummaps=300)
    manage_map_names()

    unused_enemies = [u for u in get_monsters() if u.id in REPLACE_ENEMIES]

    def safe_boss_validator(formation):
        if formation.is_fanatics:
            return False
        if set(formation.present_enemies) & set(unused_enemies):
            return False
        if formation.formid in NOREPLACE_FORMATIONS:
            return False
        if not (any([m.boss_death for m in formation.present_enemies]) or
                formation.get_music() in [1, 2, 5]):
            return False
        if formation.get_music() == 0:
            return False
        if formation.formid in [0x1b0, 0x1b3, 0x1d9, 0x1db, 0x1d7]:
            return False
        if formation.formid in [0x1a4, 0x1d4, 0x1d5, 0x1d6, 0x1e4,
                                0x1e2, 0x1ff, 0x1bd, 0x1be]:
            return False
        if ("racecave" in activated_codes
                and formation.formid in [0x162, 0x1c8, 0x1d3]):
            return False
        return True

    def challenge_battle_validator(formation):
        if len(formation.present_enemies) == 0:
            return False
        if set(formation.present_enemies) & set(unused_enemies):
            return False
        if formation.formid in NOREPLACE_FORMATIONS:
            return False
        if formation.battle_event:
            return False
        if formation.formid in [0x1a4, 0x1ff, 0x1bd, 0x1d7, 0x200, 0x201,
                                0x23f]:
            return False
        if formation.get_music() == 0:
            if any([f for f in formations if f.formid != formation.formid
                    and set(f.enemy_ids) == set(formation.enemy_ids)
                    and f.get_music() != 0]):
                return False
        best_drop = formation.get_best_drop()
        if best_drop and (best_drop.price <= 2 or best_drop.price >= 30000 or "madworld" in activated_codes):
            return True
        return False

    formations = sorted(get_formations(), key=lambda f: f.rank())
    enemy_formations = [
        f for f in formations if f.is_fanatics or
        (f.present_enemies and not f.has_event and not f.has_boss)]
    enemy_formations = [f for f in enemy_formations if f.formid not in
                        REPLACE_FORMATIONS + NOREPLACE_FORMATIONS]
    boss_formations = [f for f in formations if safe_boss_validator(f)]
    used_formations = []

    challenges = sorted([f for f in formations
                         if challenge_battle_validator(f)],
                        key=lambda f: f.get_best_drop().rank())[-48:]
    challenges = sorted(random.sample(challenges, 24), key=lambda f: f.rank())
    challenges = [f.formid for f in challenges]
    challenges = {1: challenges[:6],
                  2: challenges[6:12],
                  3: challenges[12:18],
                  4: challenges[18:24]}
    ch_bgs = list(range(0x31)) + [0x36, 0x37]
    waters = [0xD, 0x1F, 0x23]
    snows = [0x12]
    ch_bgs = random.sample(ch_bgs, 10) + [random.choice(waters), snows[0]]
    random.shuffle(ch_bgs)

    for l in get_locations():
        if not hasattr(l, "ancient_rank"):
            l.entrance_set.entrances = []
            l.entrance_set.longentrances = []
            l.chests = []
            l.attacks = 0
            l.write_data(fout)

    pointer = 0xB4E35
    if 'racecave' in activated_codes:
        candidates = [c for c in starting if c != runaway]
        leaders = random.sample(candidates, 3)
        subptr = pointer - 0xa0000
        leader_sub = Substitution()

        # makes switching impossible and makes row change instant
        # could freeze the game d+pad and A on same frame tho
        leader_sub.set_location(0x324b7)
        leader_sub.bytestring = bytes([0xEA, 0xEA, 0xEA])
        leader_sub.write(fout)
        leader_sub.set_location(0x32473)
        leader_sub.bytestring = bytes([0xEA, 0xEA])
        leader_sub.write(fout)

        leader_sub.set_location(0xa02da)
        leader_sub.bytestring = bytes([
            0xB2, subptr & 0xFF, (subptr >> 8) & 0xFF, subptr >> 16])
        leader_sub.write(fout)
        leader_sub.set_location(pointer)
        leader_sub.bytestring = bytearray([])
        locked = 0
        for i, c in enumerate(leaders):
            leader_sub.bytestring += bytearray([0x3F, c, i+1])
            locked |= (1 << c)
        for c in range(16):
            if c in leaders:
                continue
            leader_sub.bytestring += bytearray([0x3F, c, 0x00])
            leader_sub.bytestring += bytearray([0x3E, c])
        leader_sub.bytestring += bytearray([0x47,
                                  0xE1,
                                  0xB2, 0x0B, 0xC9, 0x00,
                                  0x45])
        for i, c in enumerate(leaders):
            leader_sub.bytestring += bytearray([0x3F, c, 0])
            leader_sub.bytestring += bytearray([0x3F, c, i+1])
        leader_sub.bytestring += bytearray([0x99, 0x03, locked & 0xFF, locked >> 8])
        for i in [14, 15]:
            byte, bit = i // 8, i % 8
            mem_addr = ((0x1b+byte) << 3) | bit
            leader_sub.bytestring += bytearray([0xD6, mem_addr])
        leader_sub.bytestring += bytearray([0x96, 0xFE])
        leader_sub.write(fout)
        pswitch_ptr = pointer - 0xa0000
        pointer += len(leader_sub.bytestring)

    espersubs = {}
    for esper, event_value in esperevents.items():
        byte, bit = event_value // 8, event_value % 8
        mem_addr = ((0x17+byte) << 3) | bit
        espersub = Substitution()
        espersub.set_location(pointer)
        espersub.bytestring = [0xF4, 0x8D,
                               0x86, event_value + 0x36,
                               0xD7, mem_addr,
                               0x3E, None, 0xFE]
        espersubs[esper] = espersub
        pointer += espersub.size

    inn_template = [0x4B, None, None,
                    0x4B, 0x11, 0x81,
                    0xB6, None, None, None,
                    None, None, None,
                    0xFE]
    inn_template2 = [0x85, None, None,
                     0xC0, 0xBE, 0x81, 0xFF, 0x69, 0x01,
                     0x31, 0x84, 0xC3, 0x8F, 0x84, 0xFF,
                     0xF4, 0x2C, 0x73, 0x30, 0x0E, 0x01, 0x02, 0x06, 0x16,
                     0x31, 0x86, 0xC3, 0x9C, 0x80, 0x8D, 0xCE, 0xFF,
                     0xB2, 0x67, 0xCF, 0x00,
                     0xF0, 0xB8, 0xFA,
                     0x31, 0x85, 0xD5, 0x36, 0x05, 0xCE, 0xFF,
                     0xB2, 0x96, 0xCF, 0x00,
                     0xFE]

    prices = {1: (500, 0xA6E),
              2: (2000, 0xA71),
              3: (8000, 0xA5F),
              4: (30000, 0xA64)}

    if "racecave" in activated_codes:
        partyswitch_template = [
            0x4B, None, None,
            0x4B, 0x86, 0x83,
            0xB6, None, None, None,
            None, None, None,
            0xFE]

        partyswitch_template2 = [
            0x85, None, None,
            0xC0, 0xBE, 0x81, 0xFF, 0x69, 0x01,
            0xB2,
            pswitch_ptr & 0xFF, (pswitch_ptr >> 8) & 0xFF, pswitch_ptr >> 16,
            0xFE]

    save_template = [0x4B, None, None,
                     0x4B, 0x24, 0x85,
                     0xB6, None, None, None,
                     None, None, None,
                     0xFE]
    save_template2 = [0x85, None, None,
                      0xC0, 0xBE, 0x81, 0xFF, 0x69, 0x01,
                      0xB2, 0xEB, 0x9A, 0x02,
                      0xFE]

    enemy_template = [0x4B, 0x0B, 0x07,
                      0xB6, None, None, None,
                      None, None, None,
                      0xA0, None, None, 0xB3, 0x5E, 0x70,
                      0x4D, None, None,
                      0xA1, 0x00,
                      0x96, 0x5C,
                      0xFE]

    def make_challenge_event(loc, ptr):
        bg = ch_bgs.pop()
        formids = random.sample(challenges[loc.restrank], 2)
        formations = [get_formation(formid) for formid in formids]
        for formid in formids:
            challenges[loc.restrank].remove(formid)
        setcands = [f for f in get_fsets() if f.setid >= 0x100 and f.unused]
        fset = setcands.pop()
        fset.formids = formids
        fset.write_data(fout)
        timer = max([e.stats['hp'] for f in formations
                     for e in f.present_enemies])
        reverse = False
        if timer >= 32768:
            reverse = True
            timer = 65535 - timer
        timer = max(timer, 3600)
        half = None
        while half is None or random.randint(1, 5) == 5:
            half = timer // 2
            timer = half + random.randint(0, half) + random.randint(0, half)
        if reverse:
            timer = 65535 - timer
        timer = int(round(timer / 1800.0))
        timer = max(2, min(timer, 36))
        timer = timer * 1800
        timer = [timer & 0xFF, timer >> 8]
        addr1 = ptr + 10 - 0xa0000
        addr2 = ptr + (len(enemy_template) - 1) - 0xa0000
        addr1 = [addr1 & 0xFF, (addr1 >> 8) & 0xFF, addr1 >> 16]
        addr2 = [addr2 & 0xFF, (addr2 >> 8) & 0xFF, addr2 >> 16]
        bytestring = list(enemy_template)
        bytestring[4:7] = addr1
        bytestring[7:10] = addr2
        bytestring[11:13] = timer
        bytestring[17] = fset.setid & 0xFF
        bytestring[18] = bg
        assert None not in bytestring
        sub = Substitution()
        sub.set_location(ptr)
        sub.bytestring = bytes(bytestring)
        sub.write(fout)
        return ptr + len(enemy_template)

    shops = get_shops()
    shopranks = {}
    itemshops = [s for s in shops
                 if s.shoptype_pretty in ["items", "misc"]]
    othershops = [s for s in shops if s not in itemshops]
    othershops = othershops[random.randint(0, len(othershops)//2):]
    itemshops = sorted(random.sample(itemshops, 5), key=lambda p: p.rank())
    othershops = sorted(random.sample(othershops, 7),
                        key=lambda p: p.rank())
    for i in range(1, 5):
        if i > 1:
            shopranks[i] = othershops[:2] + itemshops[:1]
            othershops = othershops[2:]
            itemshops = itemshops[1:]
        else:
            shopranks[i] = othershops[:1] + itemshops[:2]
            othershops = othershops[1:]
            itemshops = itemshops[2:]
        assert len(shopranks[i]) == 3
        random.shuffle(shopranks[i])
    shopranks[random.randint(1, 4)][random.randint(0, 2)] = None

    levelmusic = {}
    dungeonmusics = [23, 24, 33, 35, 55, 71, 40, 41, 75, 77, 78]
    random.shuffle(dungeonmusics)
    for i in range(5):
        levelmusic[i] = dungeonmusics.pop()

    locations = [l for l in get_locations() if hasattr(l, "ancient_rank")]
    locations = sorted(locations, key=lambda l: l.ancient_rank)
    restlocs = [l for l in locations if hasattr(l, "restrank")]
    ban_musics = [0, 36, 56, 57, 58, 73, 74, 75] + list(levelmusic.values())
    restmusics = [m for m in range(1, 85) if m not in ban_musics]
    random.shuffle(restmusics)

    optional_chars = [c for c in characters if hasattr(c, "slotid")]
    optional_chars = [c for c in optional_chars if c.slotid == runaway or
                      (c.id not in starting and c.id in charcands)]
    if "speedcave" in activated_codes:
        while len(optional_chars) < 24:
            if random.choice([True, True, False]):
                supplement = [c for c in optional_chars if c.id >= 14 or
                              c.slotid == runaway]
            else:
                supplement = list(optional_chars)
            supplement = sorted(set(supplement), key=lambda c: c.id)
            optional_chars.append(random.choice(supplement))
    random.shuffle(optional_chars)

    ptr = pointer - 0xA0000
    c0, b0, a0 = ptr & 0xFF, (ptr >> 8) & 0xFF, ptr >> 16
    ptr = (pointer + 10) - 0xA0000
    c1, b1, a1 = ptr & 0xFF, (ptr >> 8) & 0xFF, ptr >> 16
    ptr = (pointer + 20) - 0xA0000
    c2, b2, a2 = ptr & 0xFF, (ptr >> 8) & 0xFF, ptr >> 16
    num_in_party_sub = Substitution()
    num_in_party_sub.set_location(0xAC654)
    num_in_party_sub.bytestring = [0xB2, c0, b0, a0]
    num_in_party_sub.write(fout)
    num_in_party_sub.set_location(pointer)
    num_in_party_sub.bytestring = bytes([0xC0, 0xAE, 0x01, c1, b1, a1,
                                   0xB2, 0x80, 0xC6, 0x00,
                                   0xC0, 0xAF, 0x01, c2, b2, a2,
                                   0xB2, 0x80, 0xC6, 0x00,
                                   0xD3, 0xA3,
                                   0xD3, 0xA2,
                                   0xFE])
    num_in_party_sub.write(fout)
    pointer += len(num_in_party_sub.bytestring)
    ally_addrs = {}
    for chosen in set(optional_chars):
        byte, bit = chosen.slotid // 8, chosen.slotid % 8
        mem_addr = ((0x1b+byte) << 3) | bit
        allysub = Substitution()
        for party_id in range(1, 4):
            for npc_id in range(4, 6):
                allysub.set_location(pointer)
                allysub.bytestring = [0xB2, 0xC1, 0xC5, 0x00,  # set caseword
                                      0xC0, 0xA3, 0x81, None, None, None]
                allysub.bytestring += [0xD4, 0xF0 | chosen.slotid,
                                       0xD4, 0xE0 | chosen.slotid,
                                       0xD7, mem_addr]
                if chosen.id >= 14 or "speedcave" in activated_codes:
                    allysub.bytestring += [0x77, chosen.slotid,
                                           0x8b, chosen.slotid, 0x7F,
                                           0x8c, chosen.slotid, 0x7F,
                                           0x88, chosen.slotid, 0x00, 0x00]
                allysub.bytestring += [0x3E, 0x10 | npc_id,
                                       0x3D, chosen.slotid,
                                       0x3F, chosen.slotid, party_id,
                                       0x47,
                                       0x45,
                                       0xF4, 0xD0,
                                       0xFE]
                pointer = pointer + len(allysub.bytestring)
                uptr = (pointer - 1) - 0xa0000
                a, b, c = (uptr >> 16, (uptr >> 8) & 0xFF, uptr & 0xFF)
                allysub.bytestring[7:10] = [c, b, a]
                allysub.write(fout)
                event_addr = (allysub.location - 0xa0000) & 0x3FFFF
                ally_addrs[chosen.id, party_id, npc_id] = event_addr

    npc_palettes = get_npc_palettes()
    for g in npc_palettes:
        npc_palettes[g] = [v for v in npc_palettes[g] if 0 <= v <= 5]
    for g in range(14, 63):
        if g not in npc_palettes or not npc_palettes[g]:
            npc_palettes[g] = list(range(6))

    def make_paysub(template, template2, loc, ptr):
        sub = Substitution()
        sub.set_location(ptr)
        price, message = prices[loc.restrank]
        message |= 0x8000
        sub.bytestring = list(template)
        ptr += len(template)
        price = [price & 0xFF, price >> 8]
        message = [message & 0xFF, message >> 8]
        p = (ptr - 0xA0000) & 0x3FFFF
        p2 = p - 1
        ptrbytes = [p & 0xFF, (p >> 8) & 0xFF, p >> 16]
        ptrbytes2 = [p2 & 0xFF, (p2 >> 8) & 0xFF, p2 >> 16]
        mapid = [loc.locid & 0xFF, loc.locid >> 8]
        mapid[1] |= 0x23
        sub.bytestring[1:3] = message
        sub.bytestring[7:10] = ptrbytes
        sub.bytestring[10:13] = ptrbytes2
        assert None not in sub.bytestring
        assert len(sub.bytestring) == 14
        sub.bytestring += template2
        ptr += len(template2)
        sub.bytestring[15:17] = price
        assert None not in sub.bytestring
        sub.bytestring = bytes(sub.bytestring)
        sub.write(fout)
        return sub

    random.shuffle(restlocs)
    for l in restlocs:
        assert l.ancient_rank == 0
        l.music = restmusics.pop()
        l.make_warpable()

        innsub = make_paysub(inn_template, inn_template2, l, pointer)
        pointer += innsub.size
        savesub = make_paysub(save_template, save_template2, l, pointer)
        pointer += savesub.size
        if "racecave" in activated_codes:
            pswitch_sub = make_paysub(partyswitch_template,
                                      partyswitch_template2, l, pointer)
            pointer += pswitch_sub.size

        event_addr = (innsub.location - 0xa0000) & 0x3FFFF
        innkeeper = NPCBlock(pointer=None, locid=l.locid)
        graphics = random.randint(14, 62)
        palette = random.choice(npc_palettes[graphics])
        attributes = {
            "graphics": graphics, "palette": palette, "x": 52, "y": 16,
            "event_addr": event_addr, "facing": 2,
            "memaddr": 0, "membit": 0, "unknown": 0,
            "graphics_index": 0}
        for key, value in attributes.items():
            setattr(innkeeper, key, value)
        l.npcs.append(innkeeper)

        unequipper = NPCBlock(pointer=None, locid=l.locid)
        attributes = {
            "graphics": 0x1e, "palette": 3, "x": 49, "y": 16,
            "event_addr": 0x23510, "facing": 2,
            "memaddr": 0, "membit": 0, "unknown": 0,
            "graphics_index": 0}
        for key, value in attributes.items():
            setattr(unequipper, key, value)
        l.npcs.append(unequipper)

        event_addr = (savesub.location - 0xa0000) & 0x3FFFF
        pay_to_save = NPCBlock(pointer=None, locid=l.locid)
        attributes = {
            "graphics": 0x6f, "palette": 6, "x": 47, "y": 4,
            "event_addr": event_addr, "facing": 0x43,
            "memaddr": 0, "membit": 0, "unknown": 0,
            "graphics_index": 0}
        for key, value in attributes.items():
            setattr(pay_to_save, key, value)
        l.npcs.append(pay_to_save)

        if l.restrank == 4:
            final_loc = get_location(412)
            if len(final_loc.npcs) < 2:
                final_save = NPCBlock(pointer=None, locid=l.locid)
                attributes = {
                    "graphics": 0x6f, "palette": 6, "x": 82, "y": 43,
                    "event_addr": event_addr, "facing": 0x43,
                    "memaddr": 0, "membit": 0, "unknown": 0,
                    "graphics_index": 0, "npcid": 1}
                for key, value in attributes.items():
                    setattr(final_save, key, value)
                final_loc.npcs.append(final_save)

        shop = shopranks[l.restrank].pop()
        if shop is not None:
            shopsub = Substitution()
            shopsub.set_location(pointer)
            shopsub.bytestring = bytes([0x9B, shop.shopid, 0xFE])
            shopsub.write(fout)
            pointer += len(shopsub.bytestring)
            event_addr = (shopsub.location - 0xa0000) & 0x3FFFF
        else:
            event_addr = 0x178cb
            colsub = Substitution()
            colsub.set_location(0xb78ea)
            colsub.bytestring = bytes([0x59, 0x04, 0x5C, 0xFE])
            colsub.write(fout)
        shopkeeper = NPCBlock(pointer=None, locid=l.locid)
        graphics = random.randint(14, 62)
        palette = random.choice(npc_palettes[graphics])
        attributes = {
            "graphics": graphics, "palette": palette, "x": 39, "y": 11,
            "event_addr": event_addr, "facing": 1,
            "memaddr": 0, "membit": 0, "unknown": 0,
            "graphics_index": 0}
        for key, value in attributes.items():
            setattr(shopkeeper, key, value)
        l.npcs.append(shopkeeper)

        if optional_chars:
            chosen = optional_chars.pop()
            assert chosen.palette is not None
            if chosen.id >= 14 and False:
                byte, bit = 0, 0
            else:
                byte, bit = (chosen.slotid // 8) + 0x1b, chosen.slotid % 8
            event_addr = ally_addrs[chosen.id, l.party_id, len(l.npcs)]
            ally = NPCBlock(pointer=None, locid=l.locid)
            attributes = {
                "graphics": chargraphics[chosen.id],
                "palette": chosen.palette,
                "x": 54, "y": 18, "event_addr": event_addr,
                "facing": 2, "memaddr": byte, "membit": bit,
                "unknown": 0, "graphics_index": 0}
            for key, value in attributes.items():
                setattr(ally, key, value)
            l.npcs.append(ally)
            if (len(optional_chars) == 12 or (len(optional_chars) > 0 and
                                              "speedcave" in activated_codes)):
                temp = optional_chars.pop()
                if chosen.id != temp.id:
                    chosen = temp
                    if chosen.id >= 14 and False:
                        byte, bit = 0, 0
                    else:
                        byte, bit = (chosen.slotid // 8) + 0x1b, chosen.slotid % 8
                    event_addr = ally_addrs[chosen.id, l.party_id, len(l.npcs)]
                    attributes = {
                        "graphics": chargraphics[chosen.id],
                        "palette": chosen.palette,
                        "x": 53, "y": 18, "event_addr": event_addr,
                        "facing": 2, "memaddr": byte, "membit": bit,
                        "unknown": 0, "graphics_index": 0}
                    ally = NPCBlock(pointer=None, locid=l.locid)
                    for key, value in attributes.items():
                        setattr(ally, key, value)
                    l.npcs.append(ally)

        if l.restrank == 1:
            num_espers = 3
        elif l.restrank in [2, 3]:
            num_espers = 2
        elif l.restrank == 4:
            num_espers = 1
        for i in range(num_espers):
            if len(espers) == 0:
                break
            if "speedcave" in activated_codes:
                candidates = espers
            else:
                esperrank = l.restrank
                if random.randint(1, 7) == 7:
                    esperrank += 1
                candidates = []
                while not candidates:
                    candidates = [e for e in espers if e.rank == esperrank]
                    if not candidates or random.randint(1, 3) == 3:
                        candidates = [e for e in espers if e.rank <= esperrank]
                    if not candidates:
                        esperrank += 1
            esper = random.choice(candidates)
            espers.remove(esper)
            espersub = espersubs[esper.name]
            index = espersub.bytestring.index(None)
            espersub.bytestring[index] = 0x10 | len(l.npcs)
            espersub.write(fout)
            event_addr = (espersub.location - 0xa0000) & 0x3FFFF
            event_value = esperevents[esper.name]
            byte, bit = event_value // 8, event_value % 8
            magicite = NPCBlock(pointer=None, locid=l.locid)
            attributes = {
                "graphics": 0x5B, "palette": 2, "x": 44+i, "y": 16,
                "event_addr": event_addr, "facing": 4 | 0x50,
                "memaddr": byte + 0x17, "membit": bit, "unknown": 0,
                "graphics_index": 0}
            for key, value in attributes.items():
                setattr(magicite, key, value)
            l.npcs.append(magicite)

        event_addr = pointer - 0xa0000
        pointer = make_challenge_event(l, pointer)
        enemy = NPCBlock(pointer=None, locid=l.locid)
        attributes = {
            "graphics": 0x3e, "palette": 2, "x": 42, "y": 6,
            "event_addr": event_addr, "facing": 2,
            "memaddr": 0, "membit": 0, "unknown": 0,
            "graphics_index": 0}
        for key, value in attributes.items():
            setattr(enemy, key, value)
        l.npcs.append(enemy)

        if "racecave" in activated_codes:
            event_addr = (pswitch_sub.location - 0xa0000) & 0x3FFFF
            partyswitch = NPCBlock(pointer=None, locid=l.locid)
            attributes = {
                "graphics": 0x17, "palette": 0, "x": 55, "y": 16,
                "event_addr": event_addr, "facing": 2,
                "memaddr": 0, "membit": 0, "unknown": 0,
                "graphics_index": 0}
            for key, value in attributes.items():
                setattr(partyswitch, key, value)
            l.npcs.append(partyswitch)

    assert len(optional_chars) == 0

    if pointer >= 0xb6965:
        raise Exception("Cave events out of bounds. %x" % pointer)

    # lower encounter rate
    dungeon_rates = [0x38, 0, 0x20, 0, 0xb0, 0, 0x00, 1,
                     0x1c, 0, 0x10, 0, 0x58, 0, 0x80, 0] + ([0]*16)
    assert len(dungeon_rates) == 32
    encrate_sub = Substitution()
    encrate_sub.set_location(0xC2BF)
    encrate_sub.bytestring = bytes(dungeon_rates)
    encrate_sub.write(fout)

    maxrank = max(locations, key=lambda l: l.ancient_rank).ancient_rank
    for l in locations:
        if l not in restlocs and (l.npcs or l.events):
            for n in l.npcs:
                if n == final_save:
                    continue
                if n.graphics == 0x6F:
                    n.memaddr, n.membit, n.event_addr = 0x73, 1, 0x5EB3
                    success = False
                    for e in l.events:
                        if e.x % 128 == n.x % 128 and e.y % 128 == n.y % 128:
                            if success:
                                raise Exception("Duplicate events found.")
                            e.event_addr = 0x5EB3
                            success = True
                    if not success:
                        raise Exception("No corresponding event found.")
        for e in l.entrances:
            e.dest |= 0x800
        rank = l.ancient_rank
        l.name_id = min(rank, 0xFF)

        if not hasattr(l, "restrank"):
            if hasattr(l, "secret_treasure") and l.secret_treasure:
                pass
            elif l.locid == 334 or not hasattr(l, "routerank"):
                l.music = 58
            elif l.routerank in levelmusic:
                l.music = levelmusic[l.routerank]
            else:
                raise Exception

        l.setid = rank
        if rank == 0:
            l.attacks = 0
        elif rank > 0xFF:
            l.setid = random.randint(0xF0, 0xFF)
        else:
            def enrank(r):
                mr = min(maxrank, 0xFF)
                r = max(0, min(r, mr))
                if "racecave" in activated_codes:
                    half = r//2
                    quarter = half//2
                    r = (half + random.randint(0, quarter) +
                         random.randint(0, quarter))
                if r <= 0:
                    return 0
                elif r >= mr:
                    return 1.0
                ratio = float(r) / mr
                return ratio

            low = enrank(rank-3)
            high = enrank(rank+2)
            high = int(round(high * len(enemy_formations)))
            low = int(round(low * len(enemy_formations)))
            while high - low < 4:
                high = min(high + 1, len(enemy_formations))
                low = max(low - 1, 0)
            candidates = enemy_formations[low:high]
            chosen_enemies = random.sample(candidates, 4)

            chosen_enemies = sorted(chosen_enemies, key=lambda f: f.rank())

            if "racecave" in activated_codes:
                bossify = False
            elif rank >= maxrank * 0.9:
                bossify = True
            else:
                if "speedcave" in activated_codes:
                    thresh = 0.5
                else:
                    thresh = 0.1
                bossify = rank >= random.randint(int(maxrank * thresh),
                                                 int(maxrank * 0.9))
                bossify = bossify and random.randint(1, 3) == 3
            if bossify:
                formrank = chosen_enemies[0].rank()
                candidates = [c for c in boss_formations if c.rank() >= formrank]
                if candidates:
                    if rank < maxrank * 0.75:
                        candidates = candidates[:random.randint(2, 4)]
                    chosen_boss = random.choice(candidates)
                    chosen_enemies[3] = chosen_boss

            if "speedcave" in activated_codes:
                thresh, bossthresh = 2, 1
            else:
                # allow up to three of the same formation
                thresh, bossthresh = 3, 2
            for c in chosen_enemies:
                used_formations.append(c)
                if used_formations.count(c) >= bossthresh:
                    if c in boss_formations:
                        boss_formations.remove(c)
                    if used_formations.count(c) >= thresh:
                        if c in enemy_formations:
                            enemy_formations.remove(c)

            fset = get_fset(rank)
            fset.formids = [f.formid for f in chosen_enemies]
            for formation in fset.formations:
                if formation.get_music() == 0:
                    formation.set_music(6)
                    formation.set_continuous_music()
                    formation.write_data(fout)
            fset.write_data(fout)

        if not (hasattr(l, "secret_treasure") and l.secret_treasure):
            if 'speedcave' in activated_codes or rank == 0:
                low = random.randint(0, 400)
                high = random.randint(low, low*5)
                high = random.randint(low, high)
            else:
                low = rank * 2
                high = low * 1.5
                while random.choice([True, False, False]):
                    high = high * 1.5
            if rank < maxrank * 0.4:
                monster = False
            else:
                monster = None
            if 0 < rank < maxrank * 0.75:
                enemy_limit = sorted([f.rank() for f in fset.formations])[-2]
                enemy_limit *= 1.5
            else:
                enemy_limit = None
            l.unlock_chests(int(low), int(high), monster=monster,
                            guarantee_miab_treasure=True,
                            enemy_limit=enemy_limit)

        l.write_data(fout)

    final_cut = Substitution()
    final_cut.set_location(0xA057D)
    final_cut.bytestring = bytearray([0x3F, 0x0E, 0x00,
                            0x3F, 0x0F, 0x00,
                            ])
    if "racecave" not in activated_codes:
        final_cut.bytestring += bytearray([0x9D,
                                 0x4D, 0x65, 0x33,
                                 0xB2, 0xA9, 0x5E, 0x00])
    elif "racecave" in activated_codes:
        for i in range(16):
            final_cut.bytestring += bytearray([0x3F, i, 0x00])
        locked = 0
        protected = random.sample(starting, 4)
        assignments = {0: [], 1: [], 2: [], 3: []}
        for i, c in enumerate(protected):
            if 1 <= i <= 3 and random.choice([True, False]):
                assignments[i].append(c)

        chars = list(range(16))
        random.shuffle(chars)
        for c in chars:
            if c in protected:
                continue
            if c >= 14 and random.choice([True, False]):
                continue
            if random.choice([True, True, False]):
                i = random.randint(0, 3)
                if len(assignments[i]) >= 3:
                    continue
                elif len(assignments[i]) == 2 and random.choice([True, False]):
                    continue
                assignments[i].append(c)

        for key in assignments:
            for c in assignments[key]:
                locked |= (1 << c)
                if key > 0:
                    final_cut.bytestring += bytearray([0x3F, c, key])
        final_cut.bytestring += bytearray([0x99, 0x03, locked & 0xFF, locked >> 8])
        from chestrandomizer import get_2pack
        event_bosses = {
            1: [0xC18A4, 0xC184B],
            2: [0xC16DD, 0xC171D, 0xC1756],
            3: [None, None, None]}
        fout.seek(0xA0F6F)
        fout.write(bytes([0x36]))
        candidates = sorted(boss_formations, key=lambda b: b.rank())
        candidates = [c for c in candidates if c.inescapable]
        candidates = candidates[random.randint(0, len(candidates)-16):]
        chosens = random.sample(candidates, 8)
        chosens = sorted(chosens, key=lambda b: b.rank())
        for rank in sorted(event_bosses):
            num = len(event_bosses[rank])
            rankchosens, chosens = chosens[:num], chosens[num:]
            assert len(rankchosens) == num
            random.shuffle(rankchosens)
            if rank == 3:
                bgs = random.sample([0x07, 0x0D, 0x17, 0x18, 0x19, 0x1C,
                                     0x1F, 0x21, 0x22, 0x23, 0x29, 0x2C,
                                     0x30, 0x36, 0x37], 3)
            for i, (address, chosen) in enumerate(
                    zip(event_bosses[rank], rankchosens)):
                if rank == 3:
                    chosen.set_music(5)
                elif rank == 2:
                    chosen.set_music(2)
                else:
                    chosen.set_music(4)
                form_music_overrides[chosen.formid] = chosen.get_music()
                chosen.set_appearing([1, 2, 3, 4, 5, 6,
                                      7, 8, 9, 10, 11, 13])
                fset = get_2pack(chosen)
                if address is not None:
                    fout.seek(address)
                    fout.write(bytes([fset.setid & 0xFF]))
                else:
                    bg = bgs.pop()
                    final_cut.bytestring += bytearray([0x46, i+1,
                                             0x4D, fset.setid & 0xFF, bg,
                                             0xB2, 0xA9, 0x5E, 0x00])

        assert len(chosens) == 0

    final_cut.bytestring += bytearray([0xB2, 0x64, 0x13, 0x00])
    final_cut.write(fout)

def manage_santa():
    Santasub = Substitution()
    Santasub.bytestring = bytes([0x32, 0x3A, 0x47, 0x4D, 0x3A])
    for location in [0xD1526, 0xD158D, 0xD16AB, 0xD1AA9, 0xD3F5F, 0xD51C1, 0xD52D7, 0xD5413, 0xD5B03, 0xD8F6A, 0xD9265, 0xD92B5, 0xD92DB, 0xD9334, 0xD9B33, 0xDDC27, 0xDDD10, 0xDDD5E, 0xDE654, 0xDE789, 0xDF79C, 0xDF7CF, 0xDF82A, 0xE0B56, 0xE0C1F, 0xE0C88, 0xE0FD6, 0xE10D2, 0xE114D, 0xE1197, 0xE1A75, 0xEAB8E, 0xE234B, 0xE2480, 0xE24EB, 0xE256B, 0xE2E3C, 0xE2EA9, 0xE4896, 0xE4915, 0xE4971, 0xE4BBC, 0xE5282, 0xE5656, 0xE56D6, 0xE56EF, 0xE6059, 0xE607A, 0xE6151, 0xE6296, 0xE62E7, 0xE651A, 0xE65AE, 0xE6601, 0xE68F2, 0xE6A54, 0xE6A7E, 0xE6B38, 0xE6B7E, 0xE7579, 0xE7B49, 0xE8160, 0xE8239, 0xE82A3, 0xE8755, 0xE8C67, 0xE91AF, 0xE9707, 0xE9980, 0xE9DFB, 0xEA8AB, 0xEDBA7, 0xEE0E6, 0xEE5FE, 0xEE755] :
        Santasub.set_location(location)
        Santasub.write(fout)

    SANTAsub = Substitution()
    SANTAsub.bytestring = bytes([0x32, 0x20, 0x2D, 0x33, 0x20])
    for location in [0xD06B6, 0xD153A, 0xD1594, 0xD15BB, 0xD1600, 0xD163D, 0xD16D9, 0xD1756, 0xD17D3, 0xD17FF, 0xD1ABE, 0xD1AF2, 0xD1B51, 0xD1B83, 0xD1C4A, 0xD1C5F, 0xD53D8, 0xD542F, 0xD585B, 0xD58C3, 0xD592A, 0xD5957, 0xD5978, 0xD59A6, 0xD5A05, 0xD5A29, 0xD5A4B, 0xD5A6B, 0xD5A86, 0xD5ACA, 0xD5B17, 0xD8F2E, 0xD8F83, 0xD8FB5, 0xD8FC2, 0xD9203, 0xD9239, 0xD93B3, 0xDE115, 0xDE170, 0xDE1A6, 0xDE45F, 0xDE48A, 0xDE4BC, 0xDE535, 0xDE582, 0xDE58E, 0xDE7C9, 0xDE7FC, 0xE09C9, 0xE0A3E, 0xE10FF, 0xE1128, 0xE113D, 0xE47E8, 0xE48AB, 0xE491F, 0xE4998, 0xE49BE, 0xE49E2, 0xE4A2C, 0xE4AA0, 0xE4AC2, 0xE4AE8, 0xE4B2B, 0xE4B50, 0xE549E, 0xE54C4, 0xE5542, 0xE5550, 0xE5560, 0xE55C2, 0xE55FC, 0xE5623, 0xE569B, 0xE571A, 0xE572B, 0xE57A9, 0xEE23D, 0xEE261, 0xEE28D, 0xEE2D7, 0xEE3ED, 0xEE591, 0xEE5D3, 0xEE621, 0xEE656, 0xEE6B2, 0xEE710, 0xEE75C, 0xEF3D7]:
        SANTAsub.set_location(location)
        SANTAsub.write(fout)

    BattleSantasub = Substitution()
    BattleSantasub.bytestring = bytes([0x92, 0x9A, 0xA7, 0xAD, 0x9A])
    for location in [0xFCB54, 0xFCBF4, 0xFCD34, 0x10D9D5, 0x10DF9E, 0x10E0C1, 0x10E10E, 0x10E602, 0x10E8EE, 0x10F41A, 0x10F5DD, 0x10F7A7, 0x10F8FA]:
        BattleSantasub.set_location(location)
        BattleSantasub.write(fout)

    BattleSANTAsub = Substitution()
    BattleSANTAsub.bytestring = bytes([0x92, 0x80, 0x8D, 0x93, 0x80])
    for location in [0x479B6, 0x479BC, 0x479C2, 0x479C8, 0x479CE, 0x479D4, 0x479DA, 0x10D7A0, 0x10D9C0, 0x10D9E6, 0x10DEF8, 0x10DF0C, 0x10DF29, 0x10DF67, 0x10DF82, 0x10DFB9, 0x10E034, 0x10E072, 0x10E0C9, 0x10E5BD, 0x10E61C, 0x10E748, 0x10E82E, 0x10E903, 0x10E978, 0x10F375, 0x10F3C1, 0x10F423, 0x10F5F4, 0x10F7E1, 0x10F887, 0x10F920, 0x10F942, 0x10F959, 0x10F98B, 0x10F9AC, 0x10F9D7, 0x10F9E6, 0x10FB6B]:
        BattleSANTAsub.set_location(location)
        BattleSANTAsub.write(fout)

def manage_spookiness():
    n_o_e_s_c_a_p_e_sub = Substitution()
    n_o_e_s_c_a_p_e_sub.bytestring = bytes([0x4B, 0xAE, 0x42])
    for location in [0xCA1C8, 0xCA296, 0xA89BF, 0xB1963,0xB198B]:
        n_o_e_s_c_a_p_e_sub.set_location(location)
        n_o_e_s_c_a_p_e_sub.write(fout)

    n_o_e_s_c_a_p_e_bottom_sub = Substitution()
    n_o_e_s_c_a_p_e_bottom_sub.bytestring = bytes([0x4B, 0xAE, 0xC2])
    for location in [0xA6325]:
        n_o_e_s_c_a_p_e_bottom_sub.set_location(location)
        n_o_e_s_c_a_p_e_bottom_sub.write(fout)

    nowhere_to_run_sub = Substitution()
    nowhere_to_run_sub.bytestring = bytes([0x4B, 0xB3, 0x42])
    for location in [0xCA215, 0xCA270, 0xB19B5, 0xB19F0, 0xC8293]:
        nowhere_to_run_sub.set_location(location)
        nowhere_to_run_sub.write(fout)

    nowhere_to_run_bottom_sub = Substitution()
    nowhere_to_run_bottom_sub.bytestring = bytes([0x4B, 0xB3, 0xC2])
    for location in [0xCA2F0, 0xCA7EE]:
        nowhere_to_run_bottom_sub.set_location(location)
        nowhere_to_run_bottom_sub.write(fout)

def manage_dances():
    if 'madworld' in activated_codes:
         spells = get_ranked_spells(sourcefile)
         dances = random.sample(spells, 32)
         dances = [s.spellid for s in dances]
    else:
        f = open(sourcefile, 'r+b')
        f.seek(0x0FFE80)
        dances = bytes(f.read(32))
        f.close()

        # Shuffle the geos, plus Fire Dance, Pearl Wind, Lullaby, Acid Rain, and Absolute 0 because why not
        geo = [dances[i*4] for i in range(8)] + [dances[i*4+1] for i in range(8)] + [0x60, 0x93, 0xA8, 0xA9, 0xBB]
        random.shuffle(geo)

        # Shuffle 1/16 beasts, plus chocobop, takedown, and wild fang, since they seem on theme
        beasts = [dances[i*4+3] for i in range(8)] + [0x7F, 0xFC, 0xFD]
        random.shuffle(beasts)

        # Replace 2/16 moves that are duplicated from other dances
        spells = get_ranked_spells(sourcefile)
        spells = [s for s in spells
                  if s.valid and s.spellid >= 0x36
                  and s.spellid not in geo and s.spellid not in beasts]
        half = len(spells) // 2

        other = []
        for i in range(8):
            while True:
                index = random.randint(0, half) + random.randint(0, half)
                if index not in other:
                    break
            other.append(spells[index].spellid)

        dances = geo[:16] + other[:8] + beasts[:8]
        random.shuffle(dances)

    Dancesub = Substitution()
    Dancesub.bytestring = bytes(dances)
    Dancesub.set_location(0x0FFE80)
    Dancesub.write(fout)

    # Randomize names
    bases = []
    prefixes = [[] for i in range(0,8)]
    i = -1
    for line in open_mei_fallback(DANCE_NAMES_TABLE):
        line = line.strip()
        if line[0] == '*':
            i += 1
            continue
        if i < 0:
            bases.append(line)
        elif i < 8:
            prefixes[i].append(line)

    used_bases = random.sample(bases, 8)
    used_prefixes = [''] * 8
    for i, terrain_prefixes in enumerate(prefixes):
        max_len = 11 - len(used_bases[i])
        candidates = [p for p in terrain_prefixes if len(p) <= max_len]
        if not candidates:
            candidates = terrain_prefixes
            used_bases[i] = None
        prefix = random.choice(candidates)
        used_prefixes[i] = prefix
        if not used_bases[i]:
            max_len = 11 - len(prefix)
            candidates = [b for b in bases if len(b) <= max_len]
            used_bases[i] = random.choice(candidates)

    dance_names = [" ".join(p) for p in zip(used_prefixes, used_bases)]
    for i, name in enumerate(dance_names):
        name = name_to_bytes(name, 12)
        fout.seek(0x26FF9D + i * 12)
        fout.write(name)

    for i, dance in enumerate(dance_names):
        from skillrandomizer import spellnames;
        dance_names = [spellnames[dances[i*4 + j]] for j in range(4)]
        dancestr = "%s:\n  " % dance
        frequencies = [7, 6, 2, 1]
        for frequency, dance_name in zip(frequencies, dance_names):
            dancestr += "{0}/16 {1:<12} ".format(frequency, dance_name)
        dancestr = dancestr.rstrip()
        log(dancestr, "dances")
        
    # Randomize dance backgrounds
    backgrounds = [
        [0x00, 0x05, 0x06, 0x07, 0x36], #Wind Song
        [0x01, 0x03], #Forest Suite
        [0x02, 0x0E, 0x2F], #Desert Aria
        [0x04, 0x08, 0x10, 0x13, 0x14, 0x17, 0x18, 0x19, 0x1A, 0x1B, 0x1C,
            0x1D, 0x1E, 0x20, 0x24, 0x2B, 0x2D, 0x2E, 0x37], #Love Sonata
        [0x0B, 0x15, 0x16], #Earth Blues
        [0x0D, 0x1F, 0x23], #Water Rondo
        [0x09, 0x0A, 0x0C, 0x11, 0x22, 0x26, 0x28, 0x2A], #Dusk Requiem
        [0x12] ] #Snowman Jazz
    fout.seek(0x11F9AB)
    for i, terrain in enumerate(backgrounds):
        fout.write(bytes([random.choice(terrain)]))
    
    # Change some semi-unused dance associations to make more sense
    # 1C (Colosseum) from Wind Song to Love Sonata
    # 1E (Thamasa) from Wind Song to Love Sonata
    fout.seek(0x2D8E77)
    fout.write(bytes([3]))
    fout.seek(0x2D8E79)
    fout.write(bytes([3]))

    
class WoRRecruitInfo(object):
    def __init__(self, event_pointers, recruited_bit_pointers, location_npcs,
                 dialogue_pointers, caseword_pointers=None, prerequisite=None, special=None):
        self.event_pointers = event_pointers
        self.recruited_bit_pointers = recruited_bit_pointers
        self.location_npcs = location_npcs
        self.dialogue_pointers=dialogue_pointers
        self.caseword_pointers=caseword_pointers
        self.prerequisite = prerequisite
        self.special = special

    def write_data(self, fout):
        assert(self.char_id is not None)
        for event_pointer in self.event_pointers:
            fout.seek(event_pointer)
            fout.write(bytes([self.char_id]))
        for recruited_bit_pointer in self.recruited_bit_pointers:
            fout.seek(recruited_bit_pointer)
            fout.write(bytes([0xf0 + self.char_id]))
        for location_id, npc_id in self.location_npcs:
            location = get_location(location_id)
            npc = location.npcs[npc_id]
            npc.graphics = self.char_id
            npc.palette = get_character(self.char_id).palette
        for location in self.dialogue_pointers:
            fout.seek(location)
            fout.write(bytes([self.char_id + 2]))
        if self.caseword_pointers:
            for location in self.caseword_pointers:
                fout.seek(location)
                byte = ord(fout.read(1))
                fout.seek(location)
                fout.write(bytes([byte & 0x0F | (self.char_id << 4)]))
        if self.special:
            self.special(self.char_id)

def gau_recruit(char_id):
    gau_recruit_sub = Substitution()
    gau_recruit_sub.set_location(0xA5324)
    gau_recruit_sub.bytestring = bytes([0xD5, 0xFB])
    gau_recruit_sub.write(fout)

    gau_recruit_sub.set_location(0xA5310 + 2 * char_id - (2 if char_id > 6 else 0))
    gau_recruit_sub.bytestring = bytes([0xD4, 0xF0 + char_id])
    gau_recruit_sub.write(fout)

def manage_wor_recruitment():
    candidates = [0x00, 0x01, 0x02, 0x05, 0x07, 0x08]
    locke_event_pointers = [0xc2c48, 0xc2c51, 0xc2c91, 0xc2c9d, 0xc2c9e, 0xc2caf, 0xc2cb8, 0xc2cc5, 0xc2cca, 0xc2cd8, 0xc2ce3, 0xc2ce9, 0xc2cee, 0xc2cf4, 0xc2cfa, 0xc2d0b, 0xc2d33, 0xc2e32, 0xc2e4a, 0xc2e80, 0xc2e86, 0xc2e8b, 0xc2e91, 0xc2ea5, 0xc2eb1, 0xc2ec4, 0xc2f0b, 0xc2fe1, 0xc3102, 0xc3106, 0xc3117, 0xc311d, 0xc3124, 0xc3134, 0xc313d, 0xc3163, 0xc3183, 0xc3185, 0xc3189, 0xc318b, 0xc318e, 0xc3191, 0xc3197, 0xc31c7, 0xc31cb, 0xc31e2, 0xc31e8, 0xc31ed, 0xc31f2, 0xc31f8, 0xc3210, 0xc3215, 0xc321d, 0xc3229, 0xc322f, 0xc3235, 0xc323b]
    locke_event_pointers_2 = [0xc3244, 0xc324a, 0xc324f, 0xc3258, 0xc326a]
    if 't' in flags:
        locke_event_pointers_2 = [p + 12 for p in locke_event_pointers_2]
    recruit_info = [
        # Phoenix Cave / Locke
        WoRRecruitInfo(
            event_pointers=locke_event_pointers + locke_event_pointers_2,
            recruited_bit_pointers=[0xc3195],
            location_npcs=[(0x139, 0)],
            dialogue_pointers=[0xe8a06, 0xe8a44, 0xe8ae6, 0xe8b2d, 0xea365, 0xea368, 0xea3ad, 0xea430, 0xea448, 0xea528, 0xea561, 0xea5f1, 0xea617, 0xea668, 0xea674, 0xea6d4, 0xea6e7, 0xea7ac, 0xea7af, 0xea7ba, 0xea7bd, 0xea86c, 0xea886]),
        # Mt. Zozo / Cyan
        WoRRecruitInfo(
            event_pointers=[0xc429c, 0xc429e, 0xc42a2, 0xc42a4, 0xc42a7, 0xc42aa],
            recruited_bit_pointers=[0xc42ae],
            location_npcs=[(0xb4, 8), (0xb5, 2)],
            dialogue_pointers=[0xe9a1e, 0xe9b85, 0xe9bdf, 0xe9c31, 0xe9c34, 0xe9c46, 0xe9c49, 0xe9ca0, 0xe9cc9, 0xe9cde, 0xe9cf4, 0xe9cff, 0xe9d67, 0xe9f53, 0xe9fc5, 0xe9fde]),
        # Collapsing House / Sabin
        WoRRecruitInfo(
            event_pointers=[0xa6c0e, 0xc5aa8, 0xc5aaa, 0xc5aae, 0xc5ab0, 0xc5ab3, 0xc5ab6],
            recruited_bit_pointers=[0xc5aba],
            location_npcs=[(0x131, 1)],
            dialogue_pointers=[0xe6326, 0xe6329, 0xe6341, 0xe6349, 0xe634d, 0xe636e, 0xe63ce, 0xe63f7, 0xe6400, 0xe640c, 0xe6418, 0xe6507, 0xe80b8, 0xe81ad],
            caseword_pointers=[0xa6af1, 0xa6b0c, 0xa6bbd]),
        # Fanatics' Tower / Strago
        WoRRecruitInfo(
            event_pointers=[0xc5418, 0xc541a, 0xc541e, 0xc5420, 0xc5423, 0xc5426],
            recruited_bit_pointers=[0xc542a],
            location_npcs=[(0x16a, 3)],
            prerequisite=[0x08],
            dialogue_pointers=[0xe680d, 0xe6841, 0xe687e, 0xe68be]),
        # Owzer's House / Relm
        WoRRecruitInfo(
            event_pointers=[0xb4e09, 0xb4e0b, 0xb4e0f, 0xb4e11, 0xb4e14, 0xb4e17],
            recruited_bit_pointers=[0xb4e1b],
            location_npcs=[(0x161, 3), (0x15d, 21), (0xd0, 3)],
            dialogue_pointers=[0xea190, 0xeb351, 0xeb572, 0xeb6c1, 0xeb6d2, 0xeb6fc, 0xeb752, 0xeb81b, 0xebd2b, 0xebd7a, 0xebdff, 0xebe31, 0xebe72, 0xebe9c]),
        # Mobliz / Terra
        WoRRecruitInfo(
            event_pointers=[0xc49d1, 0xc49d3, 0xc49da, 0xc49de, 0xc49e2, 0xc4a01, 0xc4a03, 0xc4a0c, 0xc4a0d, 0xc4a2b, 0xc4a37, 0xc4a3a, 0xc4a43, 0xc4a79, 0xc4a7b, 0xc4ccf, 0xc4cd1, 0xc4cd5, 0xc4cd7, 0xc4cdb, 0xc4cde, 0xc4ce1, 0xc4ce5, 0xc4cf4, 0xc4cf6, 0xc5040, 0xc5042, 0xc5048, 0xc504a, 0xc504d, 0xc5050], 
            recruited_bit_pointers=[0xc4cd9, 0xc4cfa, 0xc5046],
            location_npcs=[(0x09A, 1), (0x09A, 2), (0x096, 0), (0x09E, 13)],
            dialogue_pointers=[0xe6ae1, 0xe6af9, 0xe6b1f, 0xe6b48, 0xe6b4d, 0xe6b6b, 0xe6bc5, 0xe6c05, 0xe6c36, 0xe6c5d, 0xe6cb7, 0xe6d26, 0xe6d58, 0xe6d71, 0xe6d9c, 0xe6de0, 0xe6de5, 0xe6ea3, 0xe6f63, 0xe6f70, 0xe702e, 0xe70f7, 0xe70ff, 0xe7103, 0xe7110, 0xe7189, 0xe720f, 0xe7230, 0xe72c0, 0xe72ff, 0xe7347, 0xe73ba, 0xe746d]),
    ]

    if 'o' in flags or 'w' in flags or 't' in flags:
        candidates.append(0x0B)
        recruit_info.append(WoRRecruitInfo([], [], [], [0xe9dd2], special=gau_recruit))
        
    restricted_info = [info for info in recruit_info if info.prerequisite]
    unrestricted_info = [info for info in recruit_info if not info.prerequisite]
    recruit_info = restricted_info + unrestricted_info
    wor_free_char = 0xB  # gau
    for info in recruit_info:
        valid_candidates = candidates
        if info.prerequisite:
            valid_candidates = [c for c in candidates if c not in info.prerequisite]
        candidate = random.choice(valid_candidates)
        candidates.remove(candidate)
        info.char_id = candidate
        if info.special == gau_recruit:
            wor_free_char = candidate
        info.write_data(fout)
        
    return wor_free_char


def nerf_paladin_shield():
    paladin_shield = get_item(0x67)
    paladin_shield.mutate_learning()
    paladin_shield.write_stats(fout)

    
def sprint_shoes_hint():
    sprint_shoes = get_item(0xE6)
    spell_id = sprint_shoes.features['learnspell']
    spellname = get_spell(spell_id).name
    hint = "Equip relics to gain a variety of abilities!<page>These teach me {}!".format(spellname)
    sprint_sub = Substitution()
    sprint_sub.set_location(0xD2099)
    sprint_sub.bytestring = dialogue_to_bytes(hint)
    sprint_sub.write(fout)

    # disable fade to black relics tutorial
    sprint_sub.set_location(0xA790E)
    sprint_sub.bytestring = b'\xFE'
    sprint_sub.write(fout)

def sabin_hint(commands):
    sabin = get_character(0x05)
    command_id = sabin.battle_commands[1]
    if not command_id or command_id == 0xFF:
        command_id = sabin.battle_commands[0]

    command = [c for c in commands.values() if c.id == command_id][0]
    hint = "My husband, Duncan, is a world-famous martial artist!<page>He is a master of the art of {}.".format(command.name)
    sabin_hint_sub = Substitution()
    sabin_hint_sub.set_location(0xD20D0)
    sabin_hint_sub.bytestring = dialogue_to_bytes(hint)
    
    sabin_hint_sub.write(fout)


# Moves check for dead banon after Life 3 so he doesn't revive and then game over.
def manage_banon_life3():
    banon_sub = Substitution()
    banon_sub.set_location(0x206bf)
    banon_sub.bytestring = [
        0x89, 0xC2,        # BIT #$C2       (Check for Dead, Zombie, or Petrify status)
        #06C1
        0xF0, 0x09,        # BEQ $06CC      (branch if none set)
        #06C3
        0xBD, 0x19, 0x30,  # LDA $3019,X
        #06C6
        0x0C, 0x3A, 0x3A,  # TSB $3A3A      (add to bitfield of dead-ish or escaped monsters)
        #06C9
        0x20, 0xC8, 0x07,  # JSR $07C8      (Clear Zinger, Love Token, and Charm bonds, and
                                            # clear applicable Quick variables)
        #06CC
        0xBD, 0xE4, 0x3E,  # LDA $3EE4,X
        #06CF
        0x10, 0x2F,        # BPL $0700      (Branch if alive)
        #06D1
        0x20, 0x10, 0x07,  # JSR $0710   (If Wound status set on mid-Jump entity, replace
                                       # it with Air Anchor effect so they can land first)
        #06D4
        0xBD, 0xE4, 0x3E, # LDA $3EE4,X
        #06D7
        0x89, 0x02,       # BIT #$02
        #06D9
        0xF0, 0x03,       # BEQ $06DE      (branch if no Zombie Status)
        #06DB
        0x20, 0x28, 0x07, # JSR $0728      (clear Wound status, and some other bit)
        #06DE
        0xBD, 0xE4, 0x3E, # LDA $3EE4,X
        #06E1
        0x10, 0x1D,       # BPL $0700      (Branch if alive)
        #06E3
        0xBD, 0xF9, 0x3E, # LDA $3EF9,X
        #06E6
        0x89, 0x04,       # BIT #$04
        #06E8
        0xF0, 0x05,       # BEQ $06EF      (branch if no Life 3 status)
        #06EA
        0x20, 0x99, 0x07, # JSR $0799      (prepare Life 3 revival)
        #06ED
        0x80, 0x11,       # BRA $0700
        #06EF
        0xE0, 0x08,       # CPX #$08
        #06F1
        0xB0, 0x0C,       # BCS $06E4      (branch if monster)
        #06F3
        0xBD, 0xD8, 0x3E, # LDA $3ED8,X    (Which character)
        #06F6
        0xC9, 0x0E,       # CMP #$0E
        #06F8
        0xD0, 0x06,       # BNE $0700      (Branch if not Banon)
        #06FA
        0xA9, 0x06,       # LDA #$06
        #06FC
        0x8D, 0x6E, 0x3A, # STA $3A6E      (Banon fell... "End of combat" method #6)
        #06FF
        0xEA,
    ]
    banon_sub.write(fout)

def expand_rom():
    fout.seek(0,2)
    if fout.tell() < 0x400000:
        expand_sub = Substitution()
        expand_sub.set_location(fout.tell())
        expand_sub.bytestring = bytes([0x00] * (0x400000 - fout.tell()))
        expand_sub.write(fout)


def randomize():
    global outfile, sourcefile, flags, seed, fout, ALWAYS_REPLACE, NEVER_REPLACE

    args = list(argv)
    if TEST_ON:
        while len(args) < 3:
            args.append(None)
        args[1] = TEST_FILE
        args[2] = TEST_SEED
    sleep(0.5)
    print('You are using Beyond Chaos EX randomizer version "%s".' % VERSION)
    if BETA:
        print("WARNING: This version is a beta! Things may not work correctly.")

    if len(args) > 2:
        sourcefile = args[1].strip()
    else:
        sourcefile = input("Please input the file name of your copy of "
                               "the FF3 US 1.0 rom:\n> ").strip()
        print()

    try:
        f = open(sourcefile, 'rb')
        data = f.read()
        f.close()
    except IOError:
        response = input(
            "File not found. Would you like to search the current directory \n"
            "for a valid FF3 1.0 rom? (y/n) ")
        if response and response[0].lower() == 'y':
            for filename in sorted(os.listdir('.')):
                stats = os.stat(filename)
                size = stats.st_size
                if size not in [3145728, 3145728 + 0x200]:
                    continue

                try:
                    f = open(filename, 'r+b')
                except IOError:
                    continue

                data = f.read()
                f.close()
                if size == 3145728 + 0x200:
                    data = data[0x200:]
                h = md5(data).hexdigest()
                if h == MD5HASH:
                    sourcefile = filename
                    break
            else:
                raise Exception("File not found.")
        else:
            raise Exception("File not found.")
        print("Success! Using valid rom file: %s\n" % sourcefile)
    del(f)

    flaghelptext = '''o   Shuffle characters' in-battle commands.
w   Generate new commands for characters, replacing old commands.
z   Always have "Sprint Shoes" effect.
b   Make the game more balanced by removing exploits such as Joker Doom,
        Vanish/Doom, and the Evade/Mblock bug.
m   Randomize enemy stats.
c   Randomize palettes and names of various things.
i   Randomize the stats of equippable items.
q   Randomize what equipment each character can wear and character stats.
e   Randomize esper spells and levelup bonuses.
t   Randomize treasure, including chests, colosseum, shops, and enemy drops.
u   Umaro risk. (Random character will be berserk)
l   Randomize blitz inputs.
n   Randomize window background colors.
f   Randomize enemy formations.
s   Swap character graphics around.
p   Randomize the palettes of spells and weapon animations.
d   Randomize final dungeon.
g   Randomize dances
k   Randomize the clock in Zozo
r   Randomize character locations in the world of ruin.
0-9 Shorthand for the text saved under that digit, if any
-   Use all flags EXCEPT the ones listed'''

    speeddial_opts = {}
    saveflags = False
    if len(args) > 2:
        fullseed = args[2].strip()
    else:
        fullseed = input("Please input a seed value (blank for a random "
                             "seed):\n> ").strip()
        print()
        if '.' not in fullseed:
            try:
                with open('savedflags.txt', 'r') as sff:
                    savedflags = [l.strip() for l in sff.readlines() if ":" in l]
                    for line in savedflags:
                        line = line.split(':')
                        line[0] = ''.join(c for c in line[0] if c in '0123456789')
                        speeddial_opts[line[0]] = ''.join(line[1:]).strip()
            except IOError:
                pass

            print(flaghelptext + "\n")
            print("Save frequently used flag sets by adding 0: through 9: before the flags.")
            for k, v in sorted(speeddial_opts.items()):
                print("    %s: %s" % (k, v))
            print()
            flags = input("Please input your desired flags (blank for "
                              "all of them):\n> ").strip()
            if ":" in flags:
                flags = flags.split(':')
                dial = ''.join(c for c in flags[0] if c in '0123456789')
                if len(dial) == 1:
                    speeddial_opts[dial] = flags[1]
                    print('\nSaving flags "%s" in slot %s' % (flags[1], dial))
                    saveflags = True
                flags = flags[1]
            fullseed = ".%s.%s" % (flags, fullseed)
            print()

    try:
        version, flags, seed = tuple(fullseed.split('.'))
    except ValueError:
        raise ValueError('Seed should be in the format <version>.<flags>.<seed>')
    seed = seed.strip()
    if not seed:
        seed = int(time())
    else:
        seed = int(seed)
    seed = seed % (10**10)
    reseed()

    if saveflags:
        try:
            with open('savedflags.txt', 'w') as sff:
                for k, v in speeddial_opts.items():
                    if v: sff.write("%s: %s" % (k, v) + '\n')
        except:
            print("Couldn't save flag string\n")

    if '.' in sourcefile:
        tempname = sourcefile.rsplit('.', 1)
    else:
        tempname = [sourcefile, 'smc']
    outfile = '.'.join([tempname[0], str(seed), tempname[1]])
    outlog = '.'.join([tempname[0], str(seed), 'txt'])

    if len(data) % 0x400 == 0x200:
        print("NOTICE: Headered ROM detected. Output file will have no header.")
        data = data[0x200:]
        sourcefile = '.'.join([tempname[0], "unheadered", tempname[1]])
        f = open(sourcefile, 'w+b')
        f.write(data)
        f.close()

    h = md5(data).hexdigest()
    if h != MD5HASH:
        print ("WARNING! The md5 hash of this file does not match the known "
               "hash of the english FF6 1.0 rom!")
        x = input("Continue? y/n ")
        if not (x and x.lower()[0] == 'y'):
            return

    copyfile(sourcefile, outfile)

    flags = flags.lower()
    flags = flags.replace('endless9', 'endless~nine~')
    for d in "0123456789":
        if d in speeddial_opts:
            replacement = speeddial_opts[d]
        else:
            replacement = ''
        flags = flags.replace(d, replacement)
    flags = flags.replace('endless~nine~', 'endless9')

    if version and version != VERSION:
        print ("WARNING! Version mismatch! "
               "This seed will not produce the expected result!")
    s = "Using seed: %s.%s.%s" % (VERSION, flags, seed)
    print(s)
    log(s, section=None)
    log("This is a game guide generated for the Beyond Chaos EX FF6 randomizer.",
        section=None)
    log("For more information, visit https://github.com/subtractionsoup/beyondchaos",
        section=None)

    commands = commands_from_table(COMMAND_TABLE)
    commands = dict([(c.name, c) for c in commands])

    characters = get_characters()

    secret_codes['airship'] = "AIRSHIP MODE"
    secret_codes['partyparty'] = "CRAZY PARTY MODE"
    secret_codes['bravenudeworld'] = "TINA PARTY MODE"
    secret_codes['suplexwrecks'] = "SUPLEX MODE"
    secret_codes['strangejourney'] = "BIZARRE ADVENTURE"
    secret_codes['dearestmolulu'] = "ENCOUNTERLESS MODE"
    secret_codes['canttouchthis'] = "INVINCIBILITY"
    secret_codes['easymodo'] = "EASY MODE"
    secret_codes['norng'] = "NO RNG MODE"
    secret_codes['endless9'] = "ENDLESS NINE MODE"
    secret_codes['equipanything'] = "EQUIP ANYTHING MODE"
    secret_codes['collateraldamage'] = "ITEM BREAK MODE"
    secret_codes['repairpalette'] = "PALETTE REPAIR"
    secret_codes['llg'] = "LOW LEVEL GAME MODE"
    secret_codes['naturalmagic'] = "NATURAL MAGIC MODE"
    secret_codes['naturalstats'] = "NATURAL STATS MODE"
    secret_codes['playsitself'] = "AUTOBATTLE MODE"
    secret_codes['bingoboingo'] = "BINGO BONUS"
    secret_codes['worringtriad'] = "START IN WOR"
    secret_codes['ancientcave'] = "CHAOS TOWER MODE"
    secret_codes['speedcave'] = "FAST CHAOS TOWER MODE"
    secret_codes['racecave'] = "EXTRA FAST CHAOS TOWER MODE"
    secret_codes['metronome'] = "R-CHAOS MODE"
    secret_codes['quikdraw'] = "QUIKDRAW MODE"
    secret_codes['makeover'] = "SPRITE REPLACEMENT MODE"
    secret_codes['kupokupo'] = "MOOGLE MODE"
    secret_codes['capslockoff'] = "Mixed Case Names Mode"
    secret_codes['replaceeverything'] = "REPLACE ALL SKILLS MODE"
    secret_codes['allcombos'] = "ALL COMBOS MODE"
    secret_codes['randomboost'] = "RANDOM BOOST MODE"
    secret_codes['dancingmaduin'] = "RESTRICTED ESPERS MODE"
    secret_codes['masseffect'] = "WILD EQUIPMENT EFFECT MODE"
    secret_codes['darkworld'] = "SLASHER'S DELIGHT MODE"
    secret_codes['supernatural'] = "SUPER NATURAL MAGIC MODE"
    secret_codes['madworld'] = "TIERS FOR FEARS MODE"
    secret_codes['randombosses'] = "RANDOM BOSSES MODE"
    secret_codes['electricboogaloo'] = "WILD ITEM BREAK MODE"
    secret_codes['notawaiter'] = "CUTSCENE SKIPS"
    secret_codes['rushforpower'] = "OLD VARGAS FIGHT MODE"
    secret_codes['johnnydmad'] = "MUSIC REPLACEMENT MODE"
    secret_codes['johnnyachaotic'] = "MUSIC MANGLING MODE"
    #secret_codes['sometimeszombies'] = "OLD CHARACTER PALETTE MODE"
    secret_codes['novanilla'] = "COMPLETE MAKEOVER MODE"
    secret_codes['frenchvanilla'] = "EQUAL RIGHTS MAKEOVER MODE"
    secret_codes['attackoftheclones'] = "CLONE COSPLAY MAKEOVER MODE"
    
    makeover_groups = ["boys", "girls", "kids", "pets", "potato"]
    for mg in makeover_groups:
        secret_codes['no'+mg] = f"NO {mg.upper()} ALLOWED MODE"
        secret_codes['hate'+mg] = f"RARE {mg.upper()} MODE"
        secret_codes['like'+mg] = f"COMMON {mg.upper()} MODE"
        secret_codes['love'+mg] = f"{mg.upper()} WORLD MODE"
        
    s = ""
    for code, text in secret_codes.items():
        if code in flags:
            flags = flags.replace(code, '')
            s += "SECRET CODE: %s ACTIVATED\n" % text
            activated_codes.add(code)
    if 'racecave' in activated_codes:
        activated_codes.add('speedcave')
    if 'speedcave' in activated_codes:
        activated_codes.add('ancientcave')

    tm = gmtime(seed)
    if tm.tm_mon == 12 and (tm.tm_mday == 24 or tm.tm_mday == 25):
        activated_codes.add('christmas')
        s += "CHRISTMAS MODE ACTIVATED\n"
    elif tm.tm_mon == 10 and tm.tm_mday == 31:
        activated_codes.add('halloween')
        s += "ALL HALLOWS EVE MODE ACTIVATED\n"

    print(s.strip())

    if 'randomboost' in activated_codes:
        x = input("Please enter a randomness "
                      "multiplier value (blank for tierless): ")
        try:
            multiplier = float(x)
            if multiplier <= 0:
                multiplier = None
        except:
            multiplier = None
        set_randomness_multiplier(multiplier)
    elif 'madworld' in activated_codes:
        set_randomness_multiplier(None)

    fout = open(outfile, "r+b")
    expand_rom()

    print (
        "\nNow beginning randomization.\n"
        "The randomization is very thorough, so it may take some time.\n"
        'Please be patient and wait for "randomization successful" to appear.')

    allFlags = 'abcdefghijklmnopqrstuvwxyz'

    if '-' in flags:
        print("NOTE: Using all flags EXCEPT the specified flags.")
        newFlags = allFlags
        for f in flags.strip():
            newFlags = newFlags.replace(f,"")
        flags = newFlags

    if not flags.strip():
        flags = allFlags

    if 'o' in flags or 'w' in flags or 't' in flags:
        auto_recruit_gau()

    if 'o' in flags and 'suplexwrecks' not in activated_codes:
        manage_commands(commands)
        improve_gogo_status_menu(fout)
    reseed()

    spells = get_ranked_spells(sourcefile)
    if 'madworld' in activated_codes:
        random.shuffle(spells)
        for i, s in enumerate(spells):
            s._rank = i+1
            s.valid = True
    if 'w' in flags and 'suplexwrecks' not in activated_codes:
        if 'quikdraw' in activated_codes:
            ALWAYS_REPLACE += ["rage"]
        _, freespaces = manage_commands_new(commands)
        improve_gogo_status_menu(fout)
    reseed()

    if 'z' in flags:
        manage_sprint()

    if 'b' in flags:
        manage_balance(newslots='w' in flags)
        if 'm' in flags or 'f' in flags or 'd' in flags:
            randomize_final_party_order()
    reseed()

    preserve_graphics = ('s' not in flags and
                         'partyparty' not in activated_codes)

    monsters = get_monsters(sourcefile)
    formations = get_formations(sourcefile)
    fsets = get_fsets(sourcefile)
    locations = get_locations(sourcefile)
    items = get_ranked_items(sourcefile)
    zones = get_zones(sourcefile)
    get_metamorphs(sourcefile)

    aispaces = []
    aispaces.append(FreeBlock(0xFCF50, 0xFCF50 + 384))
    aispaces.append(FreeBlock(0xFFF47, 0xFFF47 + 87))
    aispaces.append(FreeBlock(0xFFFBE, 0xFFFBE + 66))

    if 'd' in flags or 'ancientcave' in activated_codes:
        # do this before treasure
        if 'm' in flags and 't' in flags and 'q' in flags:
            dirk = get_item(0)
            dirk.become_another()
            dirk.write_stats(fout)
            dummy_item(dirk)
            assert not dummy_item(dirk)
    if 'm' in flags and 't' in flags and 'q' in flags:
        if random.randint(1, 10) != 10:
            rename_card = get_item(231)
            rename_card.become_another(tier="low")
            rename_card.write_stats(fout)

            weapon_anim_fix = Substitution()
            weapon_anim_fix.set_location(0x19DB8)
            weapon_anim_fix.bytestring = bytes([0x22, 0x80, 0x30, 0xF0])
            weapon_anim_fix.write(fout)

            weapon_anim_fix.set_location(0x303080)
            weapon_anim_fix.bytestring = bytes([0xE0, 0xE8, 0x02, 0xB0, 0x05, 0xBF, 0x00, 0xE4, 0xEC, 0x6B, 0xDA, 0xC2, 0x20, 0x8A, 0xE9, 0xF0, 0x02, 0xAA, 0x29, 0xFF, 0x00, 0xE2, 0x20, 0xBF, 0x00, 0x31, 0xF0, 0xFA, 0x6B])
            weapon_anim_fix.write(fout)
    reseed()

    items = get_ranked_items()
    if 'i' in flags:
        manage_items(items, changed_commands=changed_commands)
        improve_item_display(fout)
    reseed()

    if 'm' in flags:
        aispaces = manage_final_boss(aispaces)
        monsters = manage_monsters()
        improve_rage_menu(fout)
    reseed()

    if 'm' in flags or 'o' in flags or 'w' in flags:
        for m in monsters:
            m.screw_tutorial_bosses(old_vargas_fight='rushforpower' in activated_codes)
            m.write_stats(fout)

    if 'c' in flags and 'm' in flags:
        mgs = manage_monster_appearance(monsters,
                                        preserve_graphics=preserve_graphics)
    reseed()

    if 'c' in flags or 's' in flags or (
            set(['partyparty', 'bravenudeworld', 'suplexwrecks',
                 'christmas', 'halloween',
                 'kupokupo', 'quikdraw']) & activated_codes):
        manage_character_appearance(preserve_graphics=preserve_graphics)
        show_original_names(fout)
    reseed()

    if 'q' in flags:
        # do this after items
        manage_equipment(items)
    reseed()

    esperrage_spaces = [FreeBlock(0x26469, 0x26469 + 919)]
    if 'e' in flags:
        if 'dancingmaduin' in activated_codes:
            allocate_espers('ancientcave' in activated_codes, get_espers(), get_characters(), fout)
            nerf_paladin_shield()
        manage_espers(esperrage_spaces)
    reseed()

    if flags:
        esperrage_spaces = manage_reorder_rages(esperrage_spaces)

        titlesub = Substitution()
        titlesub.bytestring = [0xFD] * 4
        titlesub.set_location(0xA5E8E)
        titlesub.write(fout)

        manage_opening()
        manage_ending()
        manage_auction_house()

        savetutorial_sub = Substitution()
        savetutorial_sub.set_location(0xC9AF1)
        savetutorial_sub.bytestring = [0xD2, 0x33, 0xEA, 0xEA, 0xEA, 0xEA]
        savetutorial_sub.write(fout)

        savecheck_sub = Substitution()
        savecheck_sub.bytestring = [0xEA, 0xEA]
        savecheck_sub.set_location(0x319f2)
        savecheck_sub.write(fout)
    reseed()
        
    if 'o' in flags and 'suplexwrecks' not in activated_codes:
        # do this after swapping beserk
        manage_natural_magic()
    reseed()

    if 'u' in flags:
        umaro_risk = manage_umaro(commands)
        reset_rage_blizzard(items, umaro_risk, fout)
    reseed()

    if 'o' in flags and 'suplexwrecks' not in activated_codes:
        # do this after swapping beserk
        manage_tempchar_commands()
    reseed()

    if 'q' in flags:
        # do this after swapping beserk
        from itemrandomizer import set_item_changed_commands
        set_item_changed_commands(changed_commands)
        loglist = reset_special_relics(items, characters, fout)
        for name, before, after in loglist:
            beforename = [c for c in commands.values() if c.id == before][0].name
            aftername = [c for c in commands.values() if c.id == after][0].name
            logstr = "{0:13} {1:7} -> {2:7}".format(
                name + ":", beforename.lower(), aftername.lower())
            log(logstr, section="command-change relics")
        reset_cursed_shield(fout)

        for c in characters:
            c.mutate_stats(fout)
    else:
        for c in characters:
            c.mutate_stats(fout, read_only=True)
    reseed()

    if 'f' in flags:
        formations = get_formations()
        fsets = get_fsets()
        manage_formations(formations, fsets)
        for fset in fsets:
            fset.write_data(fout)

    if 'f' in flags or 'ancientcave' in activated_codes:
        manage_dragons()
    reseed()

    if 'd' in flags and 'ancientcave' not in activated_codes:
        # do this before treasure
        manage_tower()
    reseed()

    if 'f' in flags or 't' in flags:
        assign_unused_enemy_formations()

    form_music = {}
    if 'f' in flags:
        manage_formations_hidden(formations, freespaces=aispaces, form_music_overrides=form_music)
        for m in get_monsters():
            m.write_stats(fout)
    reseed()

    for f in get_formations():
        f.write_data(fout)

    if 't' in flags:
        # do this after hidden formations
        manage_treasure(monsters, shops=True)
        if 'ancientcave' not in activated_codes:
            manage_chests()
            mutate_event_items(fout, cutscene_skip='notawaiter' in activated_codes)
            for fs in fsets:
                # write new formation sets for MiaBs
                fs.write_data(fout)

    if 'c' in flags:
        # do this before ancient cave
        # could probably do it after if I wasn't lazy
        manage_colorize_dungeons()

    if 'ancientcave' in activated_codes:
        manage_ancient(form_music_overrides=form_music)
    reseed()

    if 'o' in flags or 'w' in flags or 'm' in flags:
        manage_magitek()
    reseed()

    if 'l' in flags:
        if 0x0A not in changed_commands:
            manage_blitz()
    reseed()

    if 'halloween' in activated_codes:
        demon_chocobo_sub = Substitution()
        fout.seek(0x2d0000 + 896 * 7)
        demon_chocobo_sub.bytestring = fout.read(896)
        for i in range(7):
            demon_chocobo_sub.set_location(0x2d0000 + 896 * i)
            demon_chocobo_sub.write(fout)

    if 'n' in flags or 'christmas' in activated_codes or 'halloween' in activated_codes:
        for i in range(8):
            w = WindowBlock(i)
            w.read_data(sourcefile)
            w.mutate()
            w.write_data(fout)
    reseed()

    if 'dearestmolulu' in activated_codes or (
            'f' in flags and 'b' in flags and
            'ancientcave' not in activated_codes):
        manage_encounter_rate()
    reseed()
    reseed()

    if 'p' in flags:
        manage_colorize_animations()
    reseed()

    if 'suplexwrecks' in activated_codes:
        manage_suplex(commands, monsters)
    reseed()

    if 'strangejourney' in activated_codes and 'ancientcave' not in activated_codes:
        create_dimensional_vortex()
        manage_strange_events()
    reseed()

    if 'notawaiter' in activated_codes and 'ancientcave' not in activated_codes:
        print("Cutscenes are currently skipped up to Kefka @ Narshe")
        manage_skips()
    reseed()

    wor_free_char = 0xB  # gau
    if 'r' in flags and 'ancientcave' not in activated_codes:
        wor_free_char = manage_wor_recruitment()

    if 'worringtriad' in activated_codes and 'ancientcave' not in activated_codes:
        manage_wor_skip(wor_free_char)
    reseed()

    if 'k' in flags and 'ancientcave' not in activated_codes:
        manage_clock()
    reseed()

    if 'g' in flags:
        if 0x13 not in changed_commands:
            manage_dances()
            improve_dance_menu(fout)
    reseed()

    if 'johnnydmad' in activated_codes or 'johnnyachaotic' in activated_codes:
        f_mchaos = True if 'johnnyachaotic' in activated_codes else False
        music_log = randomize_music(fout, f_mchaos = f_mchaos, codes=activated_codes, form_music_overrides=form_music)
        log(music_log, section="music")

    # ----- NO MORE RANDOMNESS PAST THIS LINE -----
    write_all_locations_misc()
    for fs in fsets:
        fs.write_data(fout)

    # This needs to be after write_all_locations_misc()
    # so the changes to Daryl don't get stomped.
    event_freespaces = [FreeBlock(0xCFE2A, 0xCFE2a + 470)]
    if 'airship' in activated_codes:
        event_freespaces = activate_airship_mode(event_freespaces)

    if 'u' in flags or 'q' in flags:
        manage_equip_umaro(event_freespaces)

    if 'easymodo' in activated_codes or 'llg' in activated_codes or 'dearestmolulu' in activated_codes:
        for m in monsters:
            if 'easymodo' in activated_codes:
                m.stats['hp'] = 1
            if 'llg' in activated_codes:
                m.stats['xp'] = 0
            elif 'dearestmolulu' in activated_codes:
                m.stats['xp'] = min(0xFFFF, 3 * m.stats['xp'])
            m.write_stats(fout)

    if 'naturalmagic' in activated_codes or 'naturalstats' in activated_codes:
        espers = get_espers()
        if 'naturalstats' in activated_codes:
            for e in espers:
                e.bonus = 0xFF
        if 'naturalmagic' in activated_codes:
            for e in espers:
                e.spells, e.learnrates = [], []
            for i in items:
                i.features['learnrate'] = 0
                i.features['learnspell'] = 0
                i.write_stats(fout)
        for e in espers:
            e.write_data(fout)

    if 'canttouchthis' in activated_codes:
        for c in characters:
            if c.id >= 14:
                continue
            c.become_invincible(fout)

    if 'equipanything' in activated_codes:
        manage_equip_anything()

    if 'playsitself' in activated_codes:
        manage_full_umaro()
        for c in commands.values():
            if c.id not in [0x01, 0x08, 0x0E, 0x0F, 0x15, 0x19]:
                c.allow_while_berserk(fout)
        whelkhead = get_monster(0x134)
        whelkhead.stats['hp'] = 1
        whelkhead.write_stats(fout)
        whelkshell = get_monster(0x100)
        whelkshell.stats['hp'] = 1
        whelkshell.write_stats(fout)

    for item in get_ranked_items(allow_banned=True):
        if item.banned:
            assert not dummy_item(item)

    if 'christmas' in activated_codes:
        manage_santa()
    elif 'halloween' in activated_codes:
        manage_spookiness()

    manage_banon_life3()

    if 'w' in flags or 'o' in flags:
        sabin_hint(commands)
        
    if 'z' in flags:
        sprint_shoes_hint()

    rewrite_title(text="FF6 BCEX %s" % seed)
    fout.close()
    rewrite_checksum()

    print("\nWriting log...")
    for c in sorted(characters, key=lambda c: c.id):
        c.associate_command_objects(list(commands.values()))
        if c.id > 13:
            continue
        log(str(c), section="characters")

    for m in sorted(get_monsters(), key=lambda m: m.display_name):
        if m.display_name:
            log(m.get_description(changed_commands=changed_commands),
                section="monsters")

    if "ancientcave" not in activated_codes:
        log_chests()
    log_break_learn_items()

    f = open(outlog, 'w+')
    f.write(get_logstring())
    f.close()

    print("Randomization successful. Output filename: %s\n" % outfile)

    if 'bingoboingo' in activated_codes:
        manage_bingo()


if __name__ == "__main__":
    args = list(argv)
    if len(argv) > 3 and argv[3].strip().lower() == "test" or TEST_ON:
        randomize()
        exit()
    try:
        randomize()
        input("Press enter to close this program. ")
    except Exception as e:
        print("ERROR: %s" % e)
        import traceback
        traceback.print_exc()
        if fout:
            fout.close()
        if outfile is not None:
            print("Please try again with a different seed.")
            input("Press enter to delete %s and quit. " % outfile)
            os.remove(outfile)
        else:
            input("Press enter to quit. ")
