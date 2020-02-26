#!/usr/bin/env python3

import configparser
from time import time, sleep, gmtime
import re
import sys
from sys import argv
from shutil import copyfile
import os
from hashlib import md5

from ancient import manage_ancient
from appearance import manage_character_appearance
from character import get_characters, get_character, equip_offsets
from chestrandomizer import mutate_event_items, get_event_items
from decompress import Decompressor
from dialoguemanager import manage_dialogue_patches, get_dialogue, set_dialogue, read_dialogue, read_location_names, write_location_names
from esperrandomizer import (get_espers, allocate_espers, randomize_magicite)
from formationrandomizer import (REPLACE_FORMATIONS, KEFKA_EXTRA_FORMATION, NOREPLACE_FORMATIONS,
                                 get_formations, get_fsets, get_formation)
from itemrandomizer import (reset_equippable, get_ranked_items, get_item,
                            reset_special_relics, reset_rage_blizzard,
                            reset_cursed_shield, unhardcode_tintinabar)
from locationrandomizer import (get_locations, get_location, get_zones, get_npcs, randomize_forest)
from menufeatures import (improve_item_display, improve_gogo_status_menu, improve_rage_menu,
                          show_original_names, improve_dance_menu, y_equip_relics, fix_gogo_portrait)
from monsterrandomizer import (REPLACE_ENEMIES, MonsterGraphicBlock, get_monsters,
                               get_metamorphs, get_ranked_monsters,
                               shuffle_monsters, get_monster, read_ai_table,
                               change_enemy_name, randomize_enemy_name,
                               get_collapsing_house_help_skill)
from musicrandomizer import randomize_music, manage_opera, insert_instruments
from options import ALL_MODES, ALL_FLAGS, options_
from patches import allergic_dog, banon_life3, vanish_doom, evade_mblock, death_abuse, no_kutan_skip, show_coliseum_rewards
from shoprandomizer import (get_shops, buy_owned_breakable_tools)
from sillyclowns import randomize_passwords, randomize_poem
from skillrandomizer import (SpellBlock, CommandBlock, SpellSub, ComboSpellSub,
                             RandomSpellSub, MultipleSpellSub, ChainSpellSub,
                             get_ranked_spells, get_spell)
from towerrandomizer import randomize_tower
from utils import (COMMAND_TABLE, LOCATION_TABLE, LOCATION_PALETTE_TABLE,
                   FINAL_BOSS_AI_TABLE, SKIP_EVENTS_TABLE, DANCE_NAMES_TABLE,
                   DIVERGENT_TABLE,
                   get_long_battle_text_pointer,
                   Substitution, shorttexttable, name_to_bytes,
                   hex2int, int2bytes, read_multi, write_multi,
                   generate_swapfunc, shift_middle, get_palette_transformer,
                   battlebg_palettes, set_randomness_multiplier,
                   mutate_index, utilrandom as random, open_mei_fallback,
                   AutoLearnRageSub)
from wor import manage_wor_recruitment, manage_wor_skip


VERSION = "4"
BETA = True
VERSION_ROMAN = "IV"
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

MD5HASH = "e986575b98300f721ce27c180264d890"


TEK_SKILLS = (
    # [0x18, 0x6E, 0x70, 0x7D, 0x7E] +
    list(range(0x86, 0x8B)) +
    [0xA7, 0xB1] +
    list(range(0xB4, 0xBA)) +
    [0xBF, 0xCD, 0xD1, 0xD4, 0xD7, 0xDD, 0xE3])


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
        ordering = sorted([o for o in randlog if o is not None])
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


class AutoRecruitGauSub(Substitution):
    @property
    def bytestring(self):
        return bytes([0x50, 0xBC, 0x59, 0x10, 0x3F, 0x0B, 0x01, 0xD4, 0xFB, 0xFE])

    def write(self, fout):
        sub_addr = self.location - 0xa0000
        call_recruit_sub = Substitution()
        call_recruit_sub.bytestring = bytes([0xB2]) + int2bytes(sub_addr, length=3)
        call_recruit_sub.set_location(0xBC19C)
        call_recruit_sub.write(fout)
        gau_stays_wor_sub = Substitution()
        gau_stays_wor_sub.bytestring = bytes([0xD4, 0xFB])
        gau_stays_wor_sub.set_location(0xA5324)
        gau_stays_wor_sub.write(fout)

        REPLACE_ENEMIES.append(0x172)
        super(AutoRecruitGauSub, self).write(fout)


class EnableEsperMagicSub(Substitution):
    @property
    def bytestring(self):
        return bytes([0xA9, 0x20, 0xA6, 0x00, 0x95, 0x79, 0xE8, 0xA9, 0x24, 0x60])

    def write(self, fout):
        jsr_sub = Substitution()
        jsr_sub.bytestring = bytes([0x20]) + int2bytes(self.location, length=2) + bytes([0xEA])
        jsr_sub.set_location(0x34D3D)
        jsr_sub.write(fout)
        super(EnableEsperMagicSub, self).write(fout)


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
        if end > self.end:
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


class WindowBlock():
    def __init__(self, windowid):
        self.pointer = 0x2d1c00 + (windowid * 0x20)
        self.palette = [(0, 0, 0)] * 8
        self.negabit = 0

    def read_data(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.pointer)
        self.palette = []
        if options_.is_code_active('christmas'):
            self.palette = [(0x1c, 0x02, 0x04)] * 2 + [(0x19, 0x00, 0x06)] * 2 + [(0x03, 0x0d, 0x07)] * 2 + [(0x18, 0x18, 0x18)] + [(0x04, 0x13, 0x0a)]
        elif options_.is_code_active('halloween'):
            self.palette = [(0x04, 0x0d, 0x15)] * 2 + [(0x00, 0x00, 0x00)] + [(0x0b, 0x1d, 0x15)] + [(0x00, 0x11, 0x00)] + [(0x1e, 0x00, 0x00)] + [(0x1d, 0x1c, 0x00)] + [(0x1c, 0x1f, 0x1b)]
        else:
            for _ in range(0x8):
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
        if options_.is_code_active('halloween'):
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
            if options_.is_code_active('christmas'):
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

    if options_.is_code_active('fightclub'):
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
        if i in [4, 5, 6]:
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
            from skillrandomizer import spellnames
            slotString = "%s: %s" % (slotNames[i], spellnames[spell.spellid])
            log(slotString, "slots")
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


def auto_learn_rage():
    alrs = AutoLearnRageSub(require_gau=False)
    alrs.set_location(0x23b73)
    alrs.write(fout)


def manage_commands(commands):
    characters = get_characters()

    learn_lore_sub = Substitution()
    learn_lore_sub.bytestring = bytes([0xEA, 0xEA, 0xF4, 0x00, 0x00, 0xF4, 0x00, 0x00])
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
    enable_xmagic_menu_sub.bytestring = bytes([
        0xDF, 0x78, 0x4D, 0xC3, # CMP $C34D78,X
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
    protect_battle_commands_sub.bytestring = bytes([
        0x03, 0xFF, 0xFF, 0x0C, 0x17, 0x02, 0xFF, 0x00])
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
    ungray_statscreen_sub.bytestring = bytes([0x20, 0x6F, 0x61, 0x30, 0x26, 0xEA, 0xEA, 0xEA])
    ungray_statscreen_sub.set_location(0x35EE1)
    ungray_statscreen_sub.write(fout)

    fanatics_fix_sub = Substitution()
    if options_.is_code_active('metronome'):
        fanatics_fix_sub.bytestring = bytes([0xA9, 0x1D])
    else:
        fanatics_fix_sub.bytestring = bytes([0xA9, 0x15])
    fanatics_fix_sub.set_location(0x2537E)
    fanatics_fix_sub.write(fout)

    invalid_commands = ["fight", "item", "magic", "xmagic",
                        "def", "row", "summon", "revert"]
    if random.randint(1, 5) != 5:
        invalid_commands.append("magitek")

    if not options_.replace_commands:
        invalid_commands.extend(FORBIDDEN_COMMANDS)

    invalid_commands = {c for c in commands.values() if c.name in invalid_commands}

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

        if options_.is_code_active('metronome'):
            c.set_battle_command(0, command_id=0)
            c.set_battle_command(1, command_id=0x1D)
            c.set_battle_command(2, command_id=2)
            c.set_battle_command(3, command_id=1)
            c.write_battle_commands(fout)
            continue

        if options_.is_code_active('collateraldamage'):
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
    if options_.is_code_active('metronome'):
        return
    characters = get_characters()
    chardict = {c.id:c for c in characters}
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

        if not options_.is_code_active("replaceeverything"):
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

        if options_.is_code_active('allcombos'):
            random_skill = False
            combo_skill = True

        POWER_LEVEL = 130
        scount = 1
        while random.randint(1, 5) == 5:
            scount += 1
        scount = min(scount, 9)
        if options_.is_code_active("endless9"):
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
                if not s.spells:
                    c.targeting = 0x4
                elif len({spell.targeting for spell in s.spells}) == 1:
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
                    targeting_conflict = (len({s.targeting & 0x40
                                               for s in myspells}) > 1)
                    names = {s.name for s in myspells}
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

                if isinstance(css, (MultipleSpellSub, ChainSpellSub)):
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
        if options_.is_code_active('playsitself'):
            c.allow_while_berserk(fout)
        else:
            c.disallow_while_berserk(fout)

        command_descr = "{0}\n-------\n{1}".format(c.name, str(s))
        log(command_descr, 'commands')

    if options_.is_code_active('metronome'):
        magitek = [c for c in commands.values() if c.name == "magitek"][0]
        magitek.read_properties(sourcefile)
        magitek.targeting = 0x04
        magitek.set_retarget(fout)
        if options_.is_code_active("endless9"):
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
    candidates = [c for c in characters if c.id < 12 and
                  (0x02 in c.battle_commands or 0x17 in c.battle_commands)]

    num_natural_mages = 1
    if options_.is_code_active('supernatural'):
        num_natural_mages = len(candidates)
    else:
        if random.randint(0, 9) != 9:
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
            pointer = address + random.choice([0, 32]) + (2*i)
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
        if not options_.is_code_active("collateraldamage"):
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

    if options_.is_code_active('metronome'):
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
    characters = get_characters()

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
        # at least for now, divergent paths doesn't skip the cutscene with Gau
        if options_.is_code_active("thescenarionottaken"):
            return
        if options_.shuffle_commands or options_.replace_commands or options_.random_treasure:
            writeToAddress(split_line[0], split_line[1:])

    def handlePalette(split_line): # Fix palettes so that they are randomized
        for character in characters:
            if character.id == int(split_line[1], 16):
                palette_correct_sub = Substitution()
                palette_correct_sub.bytestring = bytes([character.palette])
                palette_correct_sub.set_location(int(split_line[0], 16))
                palette_correct_sub.write(fout)

    def handleConvergentPalette(split_line):
        if options_.is_code_active('thescenarionottaken'):
            return
        handlePalette(split_line)

    def handleDivergentPalette(split_line):
        if not options_.is_code_active('thescenarionottaken'):
            return
        handlePalette(split_line)

    def handleAirship(split_line): # Replace events that should be modified if we start with the airship
        if not options_.is_code_active('airship'):
            writeToAddress(split_line[0], split_line[1:])
        else:
            writeToAddress(
                split_line[0],
                split_line[1:-1] +  # remove FE from the end
                ['D2', 'BA'] +  # enter airship from below decks
                ['D2', 'B9'] +  # airship appears on world map
                ['D0', '70'] +  # party appears on airship
                ['6B', '00', '04', '54', '22', '00'] +  # load map, place party
                ['C7', '54', '23'] +  # place airship
                ['FF'] +  # end map script
                ['FE']  # end subroutine
            )

    def handleConvergent(split_line): # Replace events that should be modified if the scenarios are changed
        if options_.is_code_active('thescenarionottaken'):
            return
        handleNormal(split_line)

    def handleDivergent(split_line): # Replace events that should be modified if the scenarios are changed
        if not options_.is_code_active('thescenarionottaken'):
            return
        handleNormal(split_line)

    for line in open(SKIP_EVENTS_TABLE):
        # If "Foo" precedes a line in skipEvents.txt, call "handleFoo"
        line = line.split('#')[0].strip()  # Ignore everything after '#'
        if not line:
            continue
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
        [0xD4, 0xE3, 0x77, 0x03, 0xD4, 0xF3] + # Shadow in shop and item menus, level average Shadow, Shadow is available
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
        [0x3D, 0x01, 0x3D, 0x00, 0x45, 0x3F, 0x01, 0x01, 0x3F, 0x00, 0x01, 0x45, 0x3F, 0x0E, 0x00, 0x3E, 0x0E, 0x3D, 0x08, 0x3D, 0x07, 0x45, 0x3F, 0x08, 0x01, 0x3F, 0x07, 0x01, 0x45, 0x3C, 0x00, 0x01, 0x07, 0x08, 0x45] + # Set up party as Terra, Locke, Strago, Relm
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
        [0xDA, 0x5A, 0xDA, 0x59, 0xDB, 0x20, 0xDA, 0x68] +  # NPC event bits
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

    set_dialogue(0x2ff, "For 2500 GP you can send 2 letters, a record, a Tonic, and a book.<line><choice> (Send them)  <choice> (Forget it)")

    # skip the flashbacks of Daryl
    daryl_cutscene_sub = Substitution()
    daryl_cutscene_sub.set_location(0xA4365)
    daryl_cutscene_sub.bytestring = bytes([
        0xF0, 0x4C, # play song "Searching for Friends"
        0x6B, 0x01, 0x04, 0x9E, 0x33, 0x01, # load map World of Ruin, continue playing song, party at (158,51) facing up, in airship
        0xC0, 0x20, # allow ship to propel without changing facing
        0xC2, 0x64, 0x00, # set bearing 100
        0xFA, # show airship emerging from the ocean
        0xD2, 0x11, 0x34, 0x10, 0x08, 0x40, # load map Falcon upper deck
        0xD7, 0xF3,  # hide Daryl on the Falcon
        0xB2, 0x43, 0x48, 0x00,  # jump to part where it sets a bunch of bits then flys to Maranda
        0xFE])
    daryl_cutscene_sub.write(fout)

    # We overwrote some of the event items, so write them again
    if options_.random_treasure:
        for items in get_event_items().values():
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
    # ... except in the World of Ruin
    set_airship_sub.write(fout)
    set_airship_sub.bytestring = bytes([0xC0, 0xA4, 0x80, 0x6E, 0xF5, 0x00])
    set_airship_sub.set_location(0xAF579)  # need first branch for button press
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
    if options_.is_code_active('norng'):
        numbers = [0 for _ in range(0x100)]
    else:
        numbers = list(range(0x100))
    random.shuffle(numbers)
    fout.write(bytes(numbers))




def manage_balance(newslots=True):
    vanish_doom(fout)
    evade_mblock(fout)

    manage_rng()
    if newslots:
        randomize_slots(outfile, fout, 0x24E4A)

    death_abuse(fout)

    get_monsters(sourcefile)
    sealed_kefka = get_monster(0x174)

    if not options_.is_code_active('sketch'):
        sketch_fix_sub = Substitution()
        sketch_fix_sub.set_location(0x2F5C6)
        sketch_fix_sub.bytestring = bytes([
            0x80, 0xCA, 0xEA, 0xEA, 0xEA, 0xEA, 0xEA, 0xEA, 0xEA, 0x4C, 0x09, 0xF8,
            0xA0, 0x00, 0x28, 0xA9, 0x01, 0x1C, 0x8D, 0x89, 0xA0, 0x03, 0x00,
            0xB1, 0x76, 0x0A, 0xAA, 0xC2, 0x20, 0xBD, 0x01, 0x20, 0x90, 0x02,
            0x7B, 0x3A, 0xAA, 0x7B, 0xE2, 0x20, 0x22, 0xD1, 0x24, 0xC1, 0x80, 0xD7,
            ])


def manage_magitek():
    spells = get_ranked_spells()
    exploder = [s for s in spells if s.spellid == 0xA2][0]
    tek_skills = [s for s in spells if s.spellid in TEK_SKILLS]
    targets = sorted({s.targeting for s in spells})
    terra_used, others_used = [], []
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
    safe_solo_terra = not options_.is_code_active("ancientcave")
    darkworld = options_.is_code_active("darkworld")
    change_skillset = True if darkworld else None
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
                m.mutate(options_=options_, change_skillset=True, safe_solo_terra=False)
            else:
                m.mutate(options_=options_, change_skillset=change_skillset, safe_solo_terra=False)
            if 0x127 <= m.id < 0x12a or m.id == 0x17d or m.id == 0x11a:
                # boost statues, Atma, final kefka a second time
                m.randomize_boost_level()
                if darkworld:
                    m.increase_enemy_difficulty()
                m.mutate(options_=options_, change_skillset=change_skillset, safe_solo_terra=False)
            m.misc1 &= (0xFF ^ 0x4)  # always show name
        else:
            if darkworld:
                m.increase_enemy_difficulty()
            m.mutate(options_=options_, change_skillset=change_skillset, safe_solo_terra=safe_solo_terra)

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
        for c in palette:
            write_multi(fout, c, length=2)


def manage_items(items, changed_commands=None):
    from itemrandomizer import (set_item_changed_commands, extend_item_breaks)
    always_break = options_.is_code_active('collateraldamage')
    crazy_prices = options_.is_code_active('madworld')
    extra_effects = options_.is_code_active('masseffect')
    wild_breaks = options_.is_code_active('electricboogaloo')

    set_item_changed_commands(changed_commands)
    unhardcode_tintinabar(fout)
    extend_item_breaks(fout)

    auto_equip_relics = []

    for i in items:
        i.mutate(always_break=always_break, crazy_prices=crazy_prices, extra_effects=extra_effects, wild_breaks=wild_breaks)
        i.unrestrict()
        i.write_stats(fout)
        if i.features['special2'] & 0x38 and i.is_relic:
            auto_equip_relics.append(i.itemid)

    assert(auto_equip_relics)

    auto_equip_sub = Substitution()
    auto_equip_sub.set_location(0x39EF9)
    auto_equip_sub.bytestring = bytes([0xA0, 0xF1,])
    auto_equip_sub.write(fout)

    auto_equip_sub.set_location(0x3F1A0)
    auto_equip_sub.bytestring = bytes([
        0x20, 0xF2, 0x93,
        0xB9, 0x23, 0x00,
        0xC5, 0xB0,
        0xD0, 0x09,
        0xB9, 0x24, 0x00,
        0xC5, 0xB1,
        0xD0, 0x02,
        0x80, 0x4C,
        0x64, 0x99,
        0xA5, 0xB0,
        0x20, 0x21, 0x83,
        0xAE, 0x34, 0x21,
        0xBF, 0x0C, 0x50, 0xD8,
        0x29, 0x38,
        0x04, 0xFE,
        0xA5, 0xB1,
        0x20, 0x21, 0x83,
        0xAE, 0x34, 0x21,
        0xBF, 0x0C, 0x50, 0xD8,
        0x29, 0x38,
        0x04, 0xFE,
        0xB9, 0x23, 0x00,
        0x20, 0x21, 0x83,
        0xAE, 0x34, 0x21,
        0xBF, 0x0C, 0x50, 0xD8,
        0x29, 0x38,
        0x04, 0xFF,
        0xB9, 0x24, 0x00,
        0x20, 0x21, 0x83,
        0xAE, 0x34, 0x21,
        0xBF, 0x0C, 0x50, 0xD8,
        0x29, 0x38,
        0x04, 0xFF,
        0xA5, 0xFE,
        0xC5, 0xFF,
        0xF0, 0x02,
        0xE6, 0x99,
        0x60])
    auto_equip_sub.write(fout)

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
    if options_.is_code_active('ancientcave'):
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

    death_abuse(fout)

    return freespaces


def manage_espers(freespaces, replacements=None):
    espers = get_espers(sourcefile)
    random.shuffle(espers)
    for e in espers:
        e.generate_spells(tierless=options_.is_code_active('madworld'))
        e.generate_bonus()

    if replacements:
        bonus_espers = [replacements[i] for i in [15, 16]]
    else:
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
    ragnarok_sub.bytestring = bytes([
        0xD4, 0xDB,
        0xDD, 0x99,
        0x6B, 0x6C, 0x21, 0x08, 0x08, 0x80,
        0xB2, a, b, c])
    ragnarok_sub.write(fout)
    ragnarok_sub.set_location(pointer)
    # CA5EA9
    ragnarok_sub.bytestring = bytes([
        0xB2, 0xA9, 0x5E, 0x00,  # event stuff
        0x5C,
        0xF4, 0x67,  # SFX
        0xB2, 0xD5, 0x9A, 0x02,  # GFX
        0x4B, 0x6A, 0x85,
        0xB2, 0xD5, 0x9A, 0x02,  # GFX
        0xF4, 0x8D,  # SFX
        0x86, 0x46,  # receive esper
        0xFE,])
    ragnarok_sub.write(fout)

    freespaces = manage_esper_boosts(freespaces)

    for e in espers:
        log(str(e), section="espers")

    return freespaces


def manage_treasure(monsters, shops=True, no_charm_drops=False):
    for mm in get_metamorphs():
        mm.mutate_items()
        mm.write_data(fout)

    for m in monsters:
        m.mutate_items()
        if no_charm_drops:
            charms = [222, 223]
            while any(x in m.drops for x in charms):
                m.mutate_items()
        m.mutate_metamorph()
        m.write_stats(fout)

    if shops:
        buyables = manage_shops()

    pointer = 0x1fb600
    results = randomize_colosseum(outfile, fout, pointer)
    wagers = {a.itemid:c for (a, b, c, d) in results}

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
    crazy_prices = options_.is_code_active('madworld')
    no_monsters = options_.mode.name == 'katn'
    uncapped_monsters = options_.is_code_active('bsiab')
    locations = get_locations(sourcefile)
    locations = sorted(locations, key=lambda l: l.rank())
    for l in locations:
        # if the Zozo clock is randomized, upgrade the chest from chain saw to pearl lance before mutating
        if options_.random_clock:
            if l.locid in [221, 225, 226]:
                for c in l.chests:
                    if c.content_type == 0x40 and c.contents == 166:
                        c.contents = 33

        l.mutate_chests(crazy_prices=crazy_prices, no_monsters=no_monsters, uncapped_monsters=uncapped_monsters)
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
    used_cmds = [[0xE, 0xA, 0xE]]
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
                        candidates = [c for c in cardinals
                                      if c not in perpendicular[prev]]
                        if pprev in diagonals:
                            candidates = [c for c in candidates if c != prev]
                    else:
                        candidates = cardinals
                    newcmd.append(random.choice(candidates))
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
                   {fo.formid for fo in fset.formations} != {0}]

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

    indoor_formations = {fo for fset in indoor_fsets for fo in fset.formations}
    # include floating continent formations, which are weird
    indoor_formations |= {fo for fo in formations
                          if 0xB1 <= fo.formid <= 0xBC}
    # fanatics tower too
    indoor_formations |= {fo for fo in formations if fo.formid in
                          [0xAB, 0xAC, 0xAD,
                           0x16A, 0x16B, 0x16C, 0x16D,
                           0x18A, 0x1D2, 0x1D8, 0x1DE,
                           0x1E0, 0x1E6]}

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


def manage_formations_hidden(formations, freespaces, form_music_overrides=None):
    if not form_music_overrides:
        form_music_overrides = {}
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

        ue.auxloc = "Missing (Boss)"
        ue.mutate_ai(change_skillset=True, options_=options_)
        ue.mutate_ai(change_skillset=True, options_=options_)

        ue.mutate(change_skillset=True, options_=options_)
        if random.choice([True, False]):
            ue.mutate(change_skillset=True, options_=options_)
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





def manage_shops():
    buyables = set([])
    descriptions = []
    crazy_shops = options_.is_code_active("madworld")

    for s in get_shops(sourcefile):
        s.mutate_items(fout, crazy_shops)
        s.mutate_misc()
        s.write_data(fout)
        buyables |= set(s.items)
        descriptions.append(str(s))

    if not options_.is_code_active("ancientcave"):
        for d in sorted(descriptions):
            log(d, section="shops")

    return buyables


def get_namelocdict():
    if namelocdict:
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
            if l.name is None:
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
        candidates = set()
        for name, palette in product(names, palettes):
            if name.endswith('*'):
                name = name.strip('*')
                break
            candidates |= {l for l in locations if l.name == name and
                           l.field_palette == palette and l.attacks}

        if not candidates and not backgrounds:
            palettes, battlebgs = [], []

        battlebgs = {l.battlebg for l in candidates if l.attacks}
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
            for c in new_palette:
                write_multi(fout, c, length=2)
            done.append(pointer)

        for p in palettes:
            if p in done:
                raise Exception("Already recolored palette %x" % p)
            fout.seek(p)
            raw_palette = [read_multi(fout, length=2) for i in range(0x80)]
            new_palette = transformer(raw_palette)
            fout.seek(p)
            for c in new_palette:
                write_multi(fout, c, length=2)
            done.append(p)


    if options_.random_animation_palettes or options_.swap_sprites or options_.is_code_active('partyparty'):
        manage_colorize_wor()
        manage_colorize_esper_world()


def manage_colorize_wor():
    transformer = get_palette_transformer(always=True)
    fout.seek(0x12ed00)
    raw_palette = [read_multi(fout, length=2) for i in range(0x80)]
    new_palette = transformer(raw_palette)
    fout.seek(0x12ed00)
    for c in new_palette:
        write_multi(fout, c, length=2)

    fout.seek(0x12ef40)
    raw_palette = [read_multi(fout, length=2) for i in range(0x60)]
    new_palette = transformer(raw_palette)
    fout.seek(0x12ef40)
    for c in new_palette:
        write_multi(fout, c, length=2)

    fout.seek(0x12ef00)
    raw_palette = [read_multi(fout, length=2) for i in range(0x12)]
    airship_transformer = get_palette_transformer(basepalette=raw_palette)
    new_palette = airship_transformer(raw_palette)
    fout.seek(0x12ef00)
    for c in new_palette:
        write_multi(fout, c, length=2)

    for battlebg in [1, 5, 0x29, 0x2F]:
        palettenum = battlebg_palettes[battlebg]
        pointer = 0x270150 + (palettenum * 0x60)
        fout.seek(pointer)
        raw_palette = [read_multi(fout, length=2) for i in range(0x30)]
        new_palette = transformer(raw_palette)
        fout.seek(pointer)
        for c in new_palette:
            write_multi(fout, c, length=2)

    for palette_index in [0x16, 0x2c, 0x2d, 0x29]:
        field_palette = 0x2dc480 + (256 * palette_index)
        fout.seek(field_palette)
        raw_palette = [read_multi(fout, length=2) for i in range(0x80)]
        new_palette = transformer(raw_palette)
        fout.seek(field_palette)
        for c in new_palette:
            write_multi(fout, c, length=2)



def manage_colorize_esper_world():
    loc = get_location(217)
    chosen = random.choice([1, 22, 25, 28, 34, 38, 43])
    loc.palette_index = (loc.palette_index & 0xFFFFC0) | chosen
    loc.write_data(fout)


def manage_encounter_rate():
    if options_.is_code_active('dearestmolulu'):
        overworld_rates = bytes([
            1, 0, 1, 0, 1, 0, 0, 0,
            0xC0, 0, 0x60, 0, 0x80, 1, 0, 0,
            0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
            0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
        dungeon_rates = bytes([
            0, 0, 0, 0, 0, 0, 0, 0,
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
        if not isinstance(name, str):
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
            for s in z.setids:
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
    shadow_recruit_sub = Substitution()
    shadow_recruit_sub.set_location(0xB0A9F)
    shadow_recruit_sub.bytestring = bytes([0x42, 0x31]) # hide party member in slot 0

    shadow_recruit_sub.write(fout)
    shadow_recruit_sub.set_location(0xB0A9E)
    shadow_recruit_sub.bytestring = bytes([
        0x41, 0x31, # show party member in slot 0
        0x41, 0x11, # show object 11
        0x31 # begin queue for party member in slot 0
    ])
    shadow_recruit_sub.write(fout)

    shadow_recruit_sub.set_location(0xB0AD4)
    shadow_recruit_sub.bytestring = bytes([0xB2, 0x29, 0xFB, 0x05, 0x45]) # Call subroutine $CFFB29, refresh objects
    shadow_recruit_sub.write(fout)

    shadow_recruit_sub.set_location(0xFFB29)
    shadow_recruit_sub.bytestring = bytes([
        0xB2, 0xC1, 0xC5, 0x00, # Call subroutine $CAC5C1 (set CaseWord bit corresponding to number of characters in party)
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


def create_dimensional_vortex():
    entrancesets = [l.entrance_set for l in get_locations()]
    entrances = []
    for e in entrancesets:
        e.read_data(sourcefile)
        entrances.extend(e.entrances)

    entrances = sorted(set(entrances), key=lambda x: (x.location.locid, x.entid if (hasattr(x, "entid") and x.entid is not None) else -1))

    # Don't randomize certain entrances
    def should_be_vanilla(k):
        if ((k.location.locid == 0x1E and k.entid == 1) # leave Arvis's house
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
    equivalent_map_dict = {0x154:0x157, 0x155:0x157, 0xFD:0xF2}

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
                    duplicate_entrance_dict[c] = d
                else:
                    if c in duplicate_entrance_dict:
                        duplicate_entrance_dict[d] = duplicate_entrance_dict[c]
                    else:
                        duplicate_entrance_dict[d] = c

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
    if options_.random_zerker:
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

    table = ("! " + "ABCDEFGHIJKLMNOPQRSTUVWXYZ" +
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
    flag_names = [f.name for f in options_.active_flags]
    display_flags = sorted([a for a in alpha if a in flag_names])
    text = "".join([consonants[int(i)] for i in str(seed)])
    codestatus = "CODES ON" if options_.active_codes else "CODES OFF"
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

    if not options_.random_treasure:
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
        auction_sub.bytestring = bytes([
            0x66, auction_item[3] & 0xff, (auction_item[3] & 0xff00) >> 8, item.itemid, # Show text auction_item[3] with item item.itemid
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

        table = {"0": 0x54, "1": 0x55, "2": 0x56, "3": 0x57, "4": 0x58, "5": 0x59, "6": 0x5A, "7": 0x5B, "8": 0x5C, "9": 0x5D}
        fout.seek(0xCE600)
        next_bank_index = read_multi(fout)
        opening_bid = str(auction_item[4])
        fout.seek(0xCE602 + 2 * auction_item[3])
        dialog_ptr = read_multi(fout)
        auction_sub.set_location(0xD0000 if auction_item[3] < next_bank_index else 0xE0000 + dialog_ptr)
        auction_sub.bytestring = bytes([
            0x01, 0x14, 0x08, 0x73, 0x1A, 0x62, 0x5E, 0x13, # "<LF>        \"<I>\"!<P>"
            0x01, 0x23, 0x48, 0xB8, 0x91, 0xA8, 0x93  # "<LF>Do I hear "
        ] + [table[x] for x in opening_bid] + [  # auction_item[4]
            0x7F, 0x26, 0x2F, 0x5F, 0x5E, 0x00]) #  " GP?!"
        auction_sub.write(fout)


def manage_bingo():
    target_score = 200.0
    print("WELCOME TO BEYOND CHAOS BINGO MODE")
    print("Include what type of squares? (blank for all)")
    print("    a   Abilities\n"
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
        left, right = lambda x: len(x)//2, len
    else:
        left, right = lambda x: 0, len

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
        scorelists = {x:dict({}) for x in "aims"}
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


def manage_clock():
    hour = random.randint(0, 5)
    minute = random.randint(0, 4)
    second = random.randint(0, 4)

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

    hour = (hour + 1) * 2
    minute = (minute + 1) * 10
    second = (second + 1) * 10
    clockstr = f"{hour}:{minute:02}:%{second:02}"
    log(clockstr, section="zozo clock")

    # Change text of hints
    wrong_hours = [2, 4, 6, 8, 10, 12]
    wrong_hours.remove(hour)
    random.shuffle(wrong_hours)

    for i in range(0, 5):
        text = get_dialogue(0x416 + i)
        text = re.sub(r'\d+(?=:00)', str(wrong_hours[i]), text)
        set_dialogue(0x416 + i, text)

    # Change text that says "Hand's pointin' at the two."
    clock_number_text = {10: "two", 20: "four", 30: "six", 40: "eight", 50: "ten"}

    if minute != 10:
        text = get_dialogue(0x42A)
        text = re.sub(r'two', clock_number_text[minute], text)

        set_dialogue(0x42A, text)

    wrong_seconds = [10, 20, 30, 40, 50]
    wrong_seconds.remove(second)
    random.shuffle(wrong_seconds)

    double_clue = sorted(wrong_seconds[:2])
    wrong_seconds = wrong_seconds[2:]

    if double_clue == [10, 20]:
        text = "The seconds? They’re less than 30!"
    elif double_clue == [10, 30]:
        text = "The seconds? They’re a factor of 30!"
    elif double_clue == [10, 40]:
        text = "The seconds? They’re a square times 10."
    elif double_clue == [10, 50]:
        text = "The second hand’s in the clock’s top half."
    elif double_clue == [20, 30]:
        text = "The seconds? They’re around 25!"
    elif double_clue == [20, 40]:
        pass
        # Leave the clue as "The seconds? They’re divisible by 20!".
    elif double_clue == [20, 50]:
        text = "The seconds have four proper factors."
    elif double_clue == [30, 40]:
        text = "The seconds? They’re around 35!"
    elif double_clue == [30, 50]:
        text = "The seconds are an odd prime times 10!"
    elif double_clue == [40, 50]:
        text = "The seconds? They’re greater than 30!"

    if double_clue != [20, 40]:
        set_dialogue(0x423, text)


    text = f"Clock’s second hand’s pointin’ at {wrong_seconds[0]}."
    set_dialogue(0x421, text)

    # In the original game, this clue says "four" and is redundant. It should say "two".
    text = get_dialogue(0x425)
    text = re.sub(r'four', clock_number_text[wrong_seconds[1]], text)
    set_dialogue(0x425, text)


def manage_santa():
    for index in [0x72, 0x75, 0x7c, 0x8e, 0x17e, 0x1e1, 0x1e7, 0x1eb, 0x20f, 0x35c, 0x36d, 0x36e, 0x36f, 0x372, 0x3a9, 0x53a, 0x53f, 0x53f, 0x57c, 0x580, 0x5e9, 0x5ec, 0x5ee, 0x67e, 0x684, 0x686, 0x6aa, 0x6b3, 0x6b7, 0x6ba, 0x6ef, 0xa40, 0x717, 0x721, 0x723, 0x726, 0x775, 0x777, 0x813, 0x814, 0x818, 0x823, 0x851, 0x869, 0x86b, 0x86c, 0x89a, 0x89b, 0x89d, 0x8a3, 0x8a5, 0x8b1, 0x8b6, 0x8b8, 0x8c6, 0x8ca, 0x8cb, 0x8d2, 0x8d4, 0x913, 0x934, 0x959, 0x95d, 0x960, 0x979, 0x990, 0x9ae, 0x9e7, 0x9ef, 0xa07, 0xa35, 0xb76, 0xba0, 0xbc2, 0xbc9]:
        text = get_dialogue(index)
        text = re.sub(r'Kefka', "Santa", text)
        set_dialogue(index, text)

    SANTAsub = Substitution()
    SANTAsub.bytestring = bytes([0x32, 0x20, 0x2D, 0x33, 0x20])
    for index in [0x24, 0x72, 0x76, 0x77, 0x78, 0x7a, 0x7c, 0x7d, 0x7f, 0x80, 0x90, 0x90, 0x94, 0x97, 0x9e, 0x9f, 0x1eb, 0x1eb, 0x203, 0x204, 0x205, 0x206, 0x207, 0x207, 0x207, 0x209, 0x20a, 0x20b, 0x20c, 0x20e, 0x210, 0x35b, 0x35c, 0x35c, 0x35d, 0x36b, 0x36c, 0x377, 0x55c, 0x55d, 0x55e, 0x56d, 0x56f, 0x570, 0x573, 0x575, 0x576, 0x585, 0x587, 0x66d, 0x674, 0x6b4, 0x6b5, 0x6b6, 0x80f, 0x813, 0x815, 0x819, 0x81a, 0x81b, 0x81c, 0x81d, 0x81e, 0x81f, 0x820, 0x821, 0x85d, 0x85e, 0x861, 0x862, 0x863, 0x866, 0x867, 0x868, 0x869, 0x86d, 0x86e, 0x871, 0xbab, 0xbac, 0xbad, 0xbaf, 0xbb2, 0xbc0, 0xbc1, 0xbc3, 0xbc4, 0xbc6, 0xbc8, 0xbca, 0xc0b]:
        text = get_dialogue(index)
        text = re.sub(r'KEFKA', "SANTA", text)
        set_dialogue(index, text)

    BattleSantasub = Substitution()
    BattleSantasub.bytestring = bytes([0x92, 0x9A, 0xA7, 0xAD, 0x9A])
    for location in [0xFCB54, 0xFCBF4, 0xFCD34]:
        BattleSantasub.set_location(location)
        BattleSantasub.write(fout)
    for index, offset in [(0x30, 0x4), (0x5F, 0x4), (0x64, 0x1A), (0x66, 0x5), (0x86, 0x14), (0x93, 0xE), (0xCE, 0x59), (0xD9, 0x9), (0xE3, 0xC), (0xE8, 0xD)]:
        BattleSantasub.set_location(get_long_battle_text_pointer(fout, index) + offset)
        BattleSantasub.write(fout)

    BattleSANTAsub = Substitution()
    BattleSANTAsub.bytestring = bytes([0x92, 0x80, 0x8D, 0x93, 0x80])
    for location in [0x479B6, 0x479BC, 0x479C2, 0x479C8, 0x479CE, 0x479D4, 0x479DA]:
        BattleSANTAsub.set_location(location)
        BattleSANTAsub.write(fout)
    for index, offset in [(0x1F, 0x0), (0x2F, 0x0), (0x31, 0x0), (0x57, 0x0), (0x58, 0x0), (0x5A, 0x0), (0x5C, 0x0), (0x5D, 0x0), (0x60, 0x0), (0x62, 0x0), (0x63, 0x0), (0x65, 0x0), (0x85, 0x0), (0x87, 0x0), (0x8d, 0x0), (0x91, 0x0), (0x94, 0x0), (0x95, 0x0), (0xCD, 0x0), (0xCE, 0x0), (0xCF, 0x0), (0xDA, 0x0), (0xE5, 0x0), (0xE7, 0x0), (0xE9, 0x0), (0xEA, 0x0), (0xEB, 0x0), (0xEC, 0x0), (0xED, 0x0), (0xEE, 0x0), (0xEF, 0x0), (0xF5, 0x0)]:
        BattleSANTAsub.set_location(get_long_battle_text_pointer(fout, index) + offset)
        BattleSANTAsub.write(fout)


def manage_spookiness():
    n_o_e_s_c_a_p_e_sub = Substitution()
    n_o_e_s_c_a_p_e_sub.bytestring = bytes([0x4B, 0xAE, 0x42])
    locations = [0xCA1C8, 0xCA296, 0xB198B]
    if not options_.is_code_active('notawaiter'):
        locations.extend([0xA89BF, 0xB1963])
    for location in locations:
        n_o_e_s_c_a_p_e_sub.set_location(location)
        n_o_e_s_c_a_p_e_sub.write(fout)

    n_o_e_s_c_a_p_e_bottom_sub = Substitution()
    n_o_e_s_c_a_p_e_bottom_sub.bytestring = bytes([0x4B, 0xAE, 0xC2])
    for location in [0xA6325]:
        n_o_e_s_c_a_p_e_bottom_sub.set_location(location)
        n_o_e_s_c_a_p_e_bottom_sub.write(fout)

    nowhere_to_run_sub = Substitution()
    nowhere_to_run_sub.bytestring = bytes([0x4B, 0xB3, 0x42])
    locations = [0xCA215, 0xCA270, 0xC8293]
    if not options_.is_code_active('notawaiter'):
        locations.extend([0xB19B5, 0xB19F0])
    for location in locations:
        nowhere_to_run_sub.set_location(location)
        nowhere_to_run_sub.write(fout)

    nowhere_to_run_bottom_sub = Substitution()
    nowhere_to_run_bottom_sub.bytestring = bytes([0x4B, 0xB3, 0xC2])
    locations = [0xCA7EE]
    if not options_.is_code_active('notawaiter'):
        locations.append(0xCA2F0)
    for location in locations:
        nowhere_to_run_bottom_sub.set_location(location)
        nowhere_to_run_bottom_sub.write(fout)

def manage_dances():
    if options_.is_code_active('madworld'):
        spells = get_ranked_spells(sourcefile)
        dances = random.sample(spells, 32)
        dances = [s.spellid for s in dances]
    else:
        f = open(sourcefile, 'rb')
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
                spellid = spells[index].spellid
                if spellid not in other:
                    break
            other.append(spellid)

        dances = geo[:16] + other[:8] + beasts[:8]
        random.shuffle(dances)

    Dancesub = Substitution()
    Dancesub.bytestring = bytes(dances)
    Dancesub.set_location(0x0FFE80)
    Dancesub.write(fout)

    # Randomize names
    bases = []
    prefixes = [[] for i in range(0, 8)]
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
        from skillrandomizer import spellnames
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
        [0x12]] #Snowman Jazz
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


def nerf_paladin_shield():
    paladin_shield = get_item(0x67)
    paladin_shield.mutate_learning()
    paladin_shield.write_stats(fout)


def sprint_shoes_hint():
    sprint_shoes = get_item(0xE6)
    spell_id = sprint_shoes.features['learnspell']
    spellname = get_spell(spell_id).name
    hint = f"Equip relics to gain a variety of abilities!<page>These teach me {spellname}!"

    set_dialogue(0xb8, hint)

    # disable fade to black relics tutorial
    sprint_sub = Substitution()
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

    set_dialogue(0xb9, hint)


def house_hint():
    skill = get_collapsing_house_help_skill()

    hint = f"There are monsters inside! They keep {skill}ing everyone who goes in to help. You using suitable Relics?".format(skill)
    set_dialogue(0x8A4, hint)


def start_with_random_espers():
    fout.seek(0xC9ab6)
    fout.write(bytes([0xB2, 0x00, 0x50, 0xF0 - 0xCA]))

    espers = sorted(get_espers(sourcefile), key=lambda e: e.rank)

    num_espers = 4 + random.randint(0, 2) + random.randint(0, 1)
    fout.seek(0x305000)
    bytestring = bytes([0x78, 0x0e, 0x78, 0x0f])
    for _ in range(num_espers):
        rank = espers[0].rank
        while rank < 5 and random.randint(1, 3) == 3:
            rank += 1
        candidates = [e for e in espers if e.rank == rank]
        while not candidates:
            candidates = [e for e in espers if e.rank <= rank]
            rank += 1

        e = random.choice(candidates)
        espers.remove(e)
        bytestring += bytes([0x86, 0x36 + e.id])
    bytestring += bytes([0xFE])
    fout.write(bytestring)


def the_end_comes_beyond_katn():
    fout.seek(0x25f821)
    fout.write(bytes([0xEA]*5))

    fout.seek(0x25f852)
    fout.write(bytes([0xEA]*5))

    fout.seek(0xcbfa3)
    fout.write(bytes([0xf6, 0xf1, 0x00, 0x00, 0xbb, 0xfe]))


def the_end_comes_beyond_crusader():
    fout.seek(0x25f821)
    fout.write(bytes([0xEA]*5))

    fout.seek(0x25f852)
    fout.write(bytes([0xEA]*5))

    fout.seek(0xc203f)
    fout.write(bytes([0x97, 0xf6, 0xf1, 0x00, 0x00, 0x5c, 0xbb, 0xfe]))


def expand_rom():
    fout.seek(0, 2)
    if fout.tell() < 0x400000:
        expand_sub = Substitution()
        expand_sub.set_location(fout.tell())
        expand_sub.bytestring = bytes([0x00] * (0x400000 - fout.tell()))
        expand_sub.write(fout)


def diverge(fout):
    for line in open(DIVERGENT_TABLE):
        line = line.strip().split('#')[0]  # Ignore everything after '#'
        if not line:
            continue
        split_line = line.strip().split(' ')
        address = int(split_line[0], 16)
        data = bytes([int(b, 16) for b in split_line[1:]])
        #print(hex(address), hex(len(data)))
        fout.seek(address)
        fout.write(data)


def randomize(args):
    global outfile, sourcefile, flags, seed, fout, ALWAYS_REPLACE, NEVER_REPLACE

    if TEST_ON:
        while len(args) < 3:
            args.append(None)
        args[1] = TEST_FILE
        args[2] = TEST_SEED
    sleep(0.5)
    print('You are using Beyond Chaos EX randomizer version "%s".' % VERSION)
    if BETA:
        print("WARNING: This version is a beta! Things may not work correctly.")

    previous_rom_path = ''
    if len(args) > 2:
        sourcefile = args[1].strip()
    else:
        try:
            config = configparser.ConfigParser()
            config.read('bcex.cfg')
            if 'ROM' in config:
                previous_rom_path = config['ROM']['Path']
        except IOError:
            pass

        previous = f" (blank for previous: {previous_rom_path})" if previous_rom_path else ""
        sourcefile = input(f"Please input the file name of your copy of "
                           f"the FF3 US 1.0 rom{previous}:\n> ").strip()
        print()

    if previous_rom_path and not sourcefile:
        sourcefile = previous_rom_path
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
    del f

    saveflags = False
    if sourcefile != previous_rom_path:
        saveflags = True

    flaghelptext = '''0-9 Shorthand for the text saved under that digit, if any
!   Recommended new player flags
-   Use all flags EXCEPT the ones listed'''

    speeddial_opts = {}

    if len(args) > 2:
        fullseed = args[2].strip()
    else:
        fullseed = input("Please input a seed value (blank for a random "
                         "seed):\n> ").strip()
        print()

        if '.' not in fullseed:
            config = configparser.ConfigParser()
            config.read('bcex.cfg')
            if 'speeddial' in config:
                speeddial_opts = config['speeddial']
            else:
                try:
                    savedflags = []
                    with open('savedflags.txt', 'r') as sff:
                        savedflags = [l.strip() for l in sff.readlines() if ":" in l]
                    for line in savedflags:
                        line = line.split(':')
                        line[0] = ''.join(c for c in line[0] if c in '0123456789')
                        speeddial_opts[line[0]] = ''.join(line[1:]).strip()
                except IOError:
                    pass

            speeddial_opts['!'] = '-dfklu partyparty makeover johnnydmad'

            mode_num = None
            while mode_num not in range(len(ALL_MODES)):
                print("Available modes:\n")
                for i, mode in enumerate(ALL_MODES):
                    print("{}. {} - {}".format(i+1, mode.name, mode.description))
                mode_str = input("\nEnter desired mode number or name:\n").strip()
                try:
                    mode_num = int(mode_str) - 1
                except ValueError:
                    for i, m in enumerate(ALL_MODES):
                        if m.name == mode_str:
                            mode_num = i
                            break
            mode = ALL_MODES[mode_num]
            allowed_flags = [f for f in ALL_FLAGS if f.name not in mode.prohibited_flags]
            print()
            for flag in sorted(allowed_flags):
                print(flag.name, flag.description)
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
            fullseed = ".%i.%s.%s" % (mode_num+1, flags, fullseed)
            print()

    try:
        version, mode_str, flags, seed = tuple(fullseed.split('.'))
    except ValueError:
        raise ValueError('Seed should be in the format <version>.<mode>.<flags>.<seed>')
    mode_str = mode_str.strip()
    mode_num = None
    try:
        mode_num = int(mode_str) - 1
    except ValueError:
        for i, m in enumerate(ALL_MODES):
            if m.name == mode_str:
                mode_num = i
                break

    if mode_num not in range(len(ALL_MODES)):
        raise Exception("Invalid mode specified")
    options_.mode = ALL_MODES[mode_num]
    allowed_flags = [f for f in ALL_FLAGS if f.name not in options_.mode.prohibited_flags]

    seed = seed.strip()
    if not seed:
        seed = int(time())
    else:
        seed = int(seed)
    seed = seed % (10**10)
    reseed()

    if saveflags:
        try:
            config = configparser.ConfigParser()
            config.read('bcex.cfg')
            if 'ROM' not in config:
                config['ROM'] = {}
            if 'speeddial' not in config:
                config['speeddial'] = {}
            config['ROM']['Path'] = sourcefile
            config['speeddial'].update({k:v for k, v in speeddial_opts.items() if k != '!'})
            with open('bcex.cfg', 'w') as cfg_file:
                config.write(cfg_file)
        except:
            print("Couldn't save flag string\n")
        else:
            try:
                os.remove('savedflags.txt')
            except OSError:
                pass

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
        print("WARNING! The md5 hash of this file does not match the known "
              "hash of the english FF6 1.0 rom!")
        x = input("Continue? y/n ")
        if not (x and x.lower()[0] == 'y'):
            return

    copyfile(sourcefile, outfile)

    flags = flags.lower()
    flags = flags.replace('endless9', 'endless~nine~')
    for d in "!0123456789":
        if d in speeddial_opts:
            replacement = speeddial_opts[d]
        else:
            replacement = ''
        flags = flags.replace(d, replacement)
        flags = flags.replace('endless9', 'endless~nine~')
    flags = flags.replace('endless~nine~', 'endless9')

    if version and version != VERSION:
        print("WARNING! Version mismatch! "
              "This seed will not produce the expected result!")
    s = "Using seed: %s.%s.%s.%s" % (VERSION, options_.mode.name, flags, seed)
    print(s)
    log(s, section=None)
    log("This is a game guide generated for the Beyond Chaos EX FF6 randomizer.",
        section=None)
    log("For more information, visit https://github.com/subtractionsoup/beyondchaos",
        section=None)

    commands = commands_from_table(COMMAND_TABLE)
    commands = {c.name:c for c in commands}

    characters = get_characters()

    activation_string = options_.activate_from_string(flags)

    tm = gmtime(seed)
    if tm.tm_mon == 12 and (tm.tm_mday == 24 or tm.tm_mday == 25):
        options_.activate_code('christmas')
        activation_string += "CHRISTMAS MODE ACTIVATED\n"
    elif tm.tm_mon == 10 and tm.tm_mday == 31:
        options_.activate_code('halloween')
        activation_string += "ALL HALLOWS' EVE MODE ACTIVATED\n"

    print(activation_string)

    if options_.is_code_active('randomboost'):
        x = input("Please enter a randomness "
                  "multiplier value (blank for tierless): ")
        try:
            multiplier = float(x)
            if multiplier <= 0:
                multiplier = None
        except (ValueError, OverflowError):
            multiplier = None
        set_randomness_multiplier(multiplier)
    elif options_.is_code_active('madworld'):
        set_randomness_multiplier(None)

    fout = open(outfile, "r+b")
    expand_rom()

    print(
        "\nNow beginning randomization.\n"
        "The randomization is very thorough, so it may take some time.\n"
        'Please be patient and wait for "randomization successful" to appear.')

    if options_.is_code_active("thescenarionottaken"):
        diverge(fout)

    read_dialogue(fout)
    read_location_names(fout)

    if options_.shuffle_commands or options_.replace_commands or options_.random_treasure:
        auto_recruit_gau()
        if options_.shuffle_commands or options_.replace_commands:
            auto_learn_rage()

    if options_.shuffle_commands and not options_.is_code_active('suplexwrecks'):
        manage_commands(commands)
        improve_gogo_status_menu(fout)
    reseed()

    spells = get_ranked_spells(sourcefile)
    if options_.is_code_active('madworld'):
        random.shuffle(spells)
        for i, s in enumerate(spells):
            s._rank = i+1
            s.valid = True
    if options_.replace_commands and not options_.is_code_active('suplexwrecks'):
        if options_.is_code_active('quikdraw'):
            ALWAYS_REPLACE += ["rage"]
        if options_.is_code_active('sketch'):
            NEVER_REPLACE += ["sketch"]
        _, freespaces = manage_commands_new(commands)
        improve_gogo_status_menu(fout)
    reseed()

    if options_.sprint:
        manage_sprint()

    if options_.fix_exploits:
        manage_balance(newslots=options_.replace_commands)
        if options_.random_enemy_stats or options_.random_formations or options_.random_final_dungeon:
            randomize_final_party_order()
    reseed()

    preserve_graphics = (not options_.swap_sprites and
                         not options_.is_code_active('partyparty'))

    monsters = get_monsters(sourcefile)
    formations = get_formations(sourcefile)
    fsets = get_fsets(sourcefile)
    locations = get_locations(outfile)
    items = get_ranked_items(sourcefile)
    zones = get_zones(sourcefile)
    get_metamorphs(sourcefile)

    aispaces = []
    aispaces.append(FreeBlock(0xFCF50, 0xFCF50 + 384))
    aispaces.append(FreeBlock(0xFFF47, 0xFFF47 + 87))
    aispaces.append(FreeBlock(0xFFFBE, 0xFFFBE + 66))

    if options_.random_final_dungeon or options_.is_code_active('ancientcave'):
        # do this before treasure
        if options_.random_enemy_stats and options_.random_treasure and options_.random_character_stats:
            dirk = get_item(0)
            dirk.become_another()
            dirk.write_stats(fout)
            dummy_item(dirk)
            assert not dummy_item(dirk)
    if options_.random_enemy_stats and options_.random_treasure and options_.random_character_stats:
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
    if options_.random_items:
        manage_items(items, changed_commands=changed_commands)
        buy_owned_breakable_tools(fout)
        improve_item_display(fout)
    reseed()

    if options_.random_enemy_stats:
        aispaces = manage_final_boss(aispaces)
        monsters = manage_monsters()
        improve_rage_menu(fout)
    reseed()

    if options_.random_enemy_stats or options_.shuffle_commands or options_.replace_commands:
        for m in monsters:
            m.screw_tutorial_bosses(old_vargas_fight=options_.is_code_active('rushforpower'))
            m.write_stats(fout)

    if options_.random_palettes_and_names and options_.random_enemy_stats:
        mgs = manage_monster_appearance(monsters,
                                        preserve_graphics=preserve_graphics)
    reseed()

    if options_.random_palettes_and_names or options_.swap_sprites or options_.is_any_code_active(
            ['partyparty', 'bravenudeworld', 'suplexwrecks',
             'christmas', 'halloween', 'kupokupo', 'quikdraw', 'makeover']):
        manage_character_appearance(fout, preserve_graphics=preserve_graphics)
        show_original_names(fout)
    reseed()

    if options_.random_character_stats:
        # do this after items
        manage_equipment(items)
    reseed()

    if options_.randomize_magicite:
        esper_replacements = randomize_magicite(fout, sourcefile)
    reseed()

    esperrage_spaces = [FreeBlock(0x26469, 0x26469 + 919)]
    if options_.random_espers:
        if options_.is_code_active('dancingmaduin'):
            allocate_espers(options_.is_code_active('ancientcave'), get_espers(sourcefile), get_characters(), fout, esper_replacements)
            nerf_paladin_shield()
        manage_espers(esperrage_spaces, esper_replacements)
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

    if options_.shuffle_commands and not options_.is_code_active('suplexwrecks'):
        # do this after swapping beserk
        manage_natural_magic()
    reseed()

    if options_.random_zerker:
        umaro_risk = manage_umaro(commands)
        reset_rage_blizzard(items, umaro_risk, fout)
    reseed()

    if options_.shuffle_commands and not options_.is_code_active('suplexwrecks'):
        # do this after swapping beserk
        manage_tempchar_commands()
    reseed()

    start_in_wor = options_.is_code_active('worringtriad')
    if options_.random_character_stats:
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
            c.mutate_stats(fout, start_in_wor)
    else:
        for c in characters:
            c.mutate_stats(fout, start_in_wor, read_only=True)
    reseed()

    if options_.random_formations:
        formations = get_formations()
        fsets = get_fsets()
        manage_formations(formations, fsets)
        for fset in fsets:
            fset.write_data(fout)

    if options_.random_formations or options_.is_code_active('ancientcave'):
        manage_dragons()
    reseed()

    if options_.random_final_dungeon and not options_.is_code_active('ancientcave') and not options_.is_code_active('strangejourney'):
        randomize_forest()
    reseed()

    if options_.random_final_dungeon and not options_.is_code_active('ancientcave'):
        # do this before treasure
        manage_tower()
    reseed()

    if options_.random_formations or options_.random_treasure:
        assign_unused_enemy_formations()

    form_music = {}
    if options_.random_formations:
        manage_formations_hidden(formations, freespaces=aispaces, form_music_overrides=form_music)
        for m in get_monsters():
            m.write_stats(fout)
    reseed()

    for f in get_formations():
        f.write_data(fout)

    if options_.random_treasure:
        wedge_money = 1000 + random.randint(0, 1500)
        vicks_money = 500 + random.randint(0, 750)
        starting_money = wedge_money + vicks_money
        starting_money_sub = Substitution()
        starting_money_sub.set_location(0xC9A93)
        starting_money_sub.bytestring = bytes([0x84, starting_money & 0xFF, (starting_money >> 8) & 0xFF])
        starting_money_sub.write(fout)

        # do this after hidden formations
        katn = options_.mode.name == 'katn'
        manage_treasure(monsters, shops=True, no_charm_drops=katn)
        if not options_.is_code_active('ancientcave'):
            manage_chests()
            mutate_event_items(fout, cutscene_skip=options_.is_code_active('notawaiter'), crazy_prices=options_.is_code_active('madworld'), no_monsters=katn, uncapped_monsters=options_.is_code_active('bsiab'))
            for fs in fsets:
                # write new formation sets for MiaBs
                fs.write_data(fout)

    if options_.random_palettes_and_names:
        # do this before ancient cave
        # could probably do it after if I wasn't lazy
        manage_colorize_dungeons()

    if options_.is_code_active('ancientcave'):
        manage_ancient(options_, fout, sourcefile, form_music_overrides=form_music)
    reseed()

    if options_.shuffle_commands or options_.replace_commands or options_.random_enemy_stats:
        manage_magitek()
    reseed()

    if options_.random_blitz:
        if 0x0A not in changed_commands:
            manage_blitz()
    reseed()

    if options_.is_code_active('halloween'):
        demon_chocobo_sub = Substitution()
        fout.seek(0x2d0000 + 896 * 7)
        demon_chocobo_sub.bytestring = fout.read(896)
        for i in range(7):
            demon_chocobo_sub.set_location(0x2d0000 + 896 * i)
            demon_chocobo_sub.write(fout)

    if options_.random_window or options_.is_code_active('christmas') or options_.is_code_active('halloween'):
        for i in range(8):
            w = WindowBlock(i)
            w.read_data(sourcefile)
            w.mutate()
            w.write_data(fout)
    reseed()

    if options_.is_code_active('dearestmolulu') or (
            options_.random_formations and options_.fix_exploits and
            not options_.is_code_active('ancientcave')):
        manage_encounter_rate()
    reseed()
    reseed()

    if options_.random_animation_palettes:
        manage_colorize_animations()
    reseed()

    if options_.is_code_active('suplexwrecks'):
        manage_suplex(commands, monsters)
    reseed()

    if options_.is_code_active('strangejourney') and not options_.is_code_active('ancientcave'):
        create_dimensional_vortex()
        manage_strange_events()
    reseed()

    if options_.is_code_active('notawaiter') and not options_.is_code_active('ancientcave'):
        print("Cutscenes are currently skipped up to Kefka @ Narshe")
        manage_skips()
    reseed()

    wor_free_char = 0xB  # gau
    alternate_gogo = options_.is_code_active('mimetime')
    if (options_.shuffle_wor or alternate_gogo) and not options_.is_code_active('ancientcave'):
        include_gau = options_.shuffle_commands or options_.replace_commands or options_.random_treasure
        wor_free_char = manage_wor_recruitment(fout,
                                               shuffle_wor=options_.shuffle_wor,
                                               random_treasure=options_.random_treasure,
                                               include_gau=include_gau,
                                               alternate_gogo=alternate_gogo)
    reseed()

    if options_.is_code_active('worringtriad') and not options_.is_code_active('ancientcave'):
        manage_wor_skip(fout, wor_free_char, options_.is_code_active('airship'), options_.mode.name == 'dragonhunt', options_.is_code_active('mimetime'))
    reseed()

    if options_.random_clock and not options_.is_code_active('ancientcave'):
        manage_clock()
    reseed()

    if options_.random_dances:
        if 0x13 not in changed_commands:
            manage_dances()
            improve_dance_menu(fout)
    reseed()

    has_music = options_.is_any_code_active(['johnnydmad', 'johnnyachaotic'])
    if has_music or options_.is_code_active('alasdraco'):
        insert_instruments(fout, 0x310000)
        opera = None

    if options_.is_code_active('alasdraco'):
        opera = manage_opera(fout, has_music)
    reseed()

    if has_music:
        music_log = randomize_music(fout, options_=options_, opera=opera, form_music_overrides=form_music)
        log(music_log, section="music")
    reseed()

    if options_.mode.name == "katn":
        start_with_random_espers()
    reseed()

    if options_.random_enemy_stats or options_.random_formations:
        house_hint()
    reseed()
    reseed()

    randomize_poem(fout)
    randomize_passwords()
    reseed()

    # ----- NO MORE RANDOMNESS PAST THIS LINE -----
    if options_.is_code_active('thescenarionottaken'):
        no_kutan_skip(fout)

    write_all_locations_misc()
    for fs in fsets:
        fs.write_data(fout)

    # This needs to be after write_all_locations_misc()
    # so the changes to Daryl don't get stomped.
    event_freespaces = [FreeBlock(0xCFE2A, 0xCFE2a + 470)]
    if options_.is_code_active('airship'):
        event_freespaces = activate_airship_mode(event_freespaces)

    if options_.random_zerker or options_.random_character_stats:
        manage_equip_umaro(event_freespaces)

    if options_.is_code_active('easymodo') or options_.is_code_active('llg') or options_.is_code_active('dearestmolulu'):
        for m in monsters:
            if options_.is_code_active('easymodo'):
                m.stats['hp'] = 1
            if options_.is_code_active('llg'):
                m.stats['xp'] = 0
            elif options_.is_code_active('dearestmolulu'):
                m.stats['xp'] = min(0xFFFF, 3 * m.stats['xp'])
            m.write_stats(fout)

    if options_.is_code_active('naturalmagic') or options_.is_code_active('naturalstats'):
        espers = get_espers(sourcefile)
        if options_.is_code_active('naturalstats'):
            for e in espers:
                e.bonus = 0xFF
        if options_.is_code_active('naturalmagic'):
            for e in espers:
                e.spells, e.learnrates = [], []
            for i in items:
                i.features['learnrate'] = 0
                i.features['learnspell'] = 0
                i.write_stats(fout)
        for e in espers:
            e.write_data(fout)

    if options_.is_code_active('canttouchthis'):
        for c in characters:
            if c.id >= 14:
                continue
            c.become_invincible(fout)

    if options_.is_code_active('equipanything'):
        manage_equip_anything()

    if options_.is_code_active('playsitself'):
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

    if options_.is_code_active('christmas') and not options_.is_code_active('ancientcave'):
        manage_santa()
    elif options_.is_code_active('halloween') and not options_.is_code_active('ancientcave'):
        manage_spookiness()

    banon_life3(fout)
    allergic_dog(fout)
    y_equip_relics(fout)
    fix_gogo_portrait(fout)

    if not options_.is_code_active('fightclub'):
        show_coliseum_rewards(fout)

    if options_.replace_commands or options_.shuffle_commands:
        sabin_hint(commands)

    if options_.sprint:
        sprint_shoes_hint()

    if options_.mode.name == "katn":
        the_end_comes_beyond_katn()
    elif options_.mode.name == "dragonhunt":
        the_end_comes_beyond_crusader()

    manage_dialogue_patches(fout)
    write_location_names(fout)

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

    if not options_.is_code_active("ancientcave"):
        log_chests()
    log_break_learn_items()

    f = open(outlog, 'w+')
    f.write(get_logstring())
    f.close()

    print("Randomization successful. Output filename: %s\n" % outfile)

    if options_.is_code_active('bingoboingo'):
        manage_bingo()

    return outfile


if __name__ == "__main__":
    args = list(argv)
    if len(argv) > 3 and argv[3].strip().lower() == "test" or TEST_ON:
        randomize(args=args)
        sys.exit()
    try:
        randomize(args=args)
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
