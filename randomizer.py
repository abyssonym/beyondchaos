from time import time, sleep
from sys import argv
from shutil import copyfile
import os
from hashlib import md5
from utils import (ESPER_TABLE,
                   CHAR_TABLE, COMMAND_TABLE, LOCATION_TABLE,
                   LOCATION_PALETTE_TABLE, CHARACTER_PALETTE_TABLE,
                   EVENT_PALETTE_TABLE, MALE_NAMES_TABLE, FEMALE_NAMES_TABLE,
                   FINAL_BOSS_AI_TABLE, SHOP_TABLE,
                   Substitution, shorttexttable, name_to_bytes,
                   hex2int, int2bytes, read_multi, write_multi,
                   generate_swapfunc, shift_middle, get_palette_transformer,
                   battlebg_palettes,
                   mutate_index, utilrandom as random)
from skillrandomizer import (SpellBlock, CommandBlock, SpellSub,
                             RandomSpellSub, MultipleSpellSub,
                             get_ranked_spells, get_spell)
from monsterrandomizer import (MonsterGraphicBlock, get_monsters,
                               get_metamorphs, get_ranked_monsters,
                               shuffle_monsters, get_monster, read_ai_table)
from itemrandomizer import (reset_equippable, get_ranked_items, get_item,
                            reset_special_relics, reset_rage_blizzard,
                            reset_cursed_shield)
from esperrandomizer import EsperBlock
from shoprandomizer import ShopBlock
from namerandomizer import generate_name
from formationrandomizer import (get_formations, get_fsets,
                                 get_formation, get_fset)
from locationrandomizer import (EntranceSet,
                                get_locations, get_location, get_zones)
from towerrandomizer import randomize_tower
from decompress import Decompressor


VERSION = "60"
BETA = False
VERSION_ROMAN = "LX"
if BETA:
    VERSION_ROMAN += " BETA"
TEST_ON = False
TEST_SEED = "44.abcefghijklmnopqrstuvwxyz-partyparty.42069"
TEST_FILE = "program.rom"
seed, flags = None, None
seedcounter = 1
sourcefile, outfile = None, None


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
              range(0x86, 0x8B) +
              [0xA7, 0xB1] +
              range(0xB4, 0xBA) +
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
        ordering = sorted(randlog.keys())
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
    for l in get_locations():
        if not l.chests:
            continue
        if l.area_name not in areachests:
            areachests[l.area_name] = ""
        areachests[l.area_name] += l.chest_contents + "\n"
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
        spell = get_spell(i.features['breakeffect'] & 0x3F)
        indestructible = not i.features['breakeffect'] & 0x80
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
    print state
    return state


def reseed():
    global seedcounter
    random.seed(seed + seedcounter)
    seedcounter += (seedcounter * 2) + 1


def rewrite_title(text):
    f = open(outfile, 'r+b')
    while len(text) < 20:
        text += ' '
    text = text[:20]
    f.seek(0xFFC0)
    f.write(text)
    f.seek(0xFFDB)
    f.write(chr(int(VERSION)))
    f.close()


def rewrite_checksum(filename=None):
    if filename is None:
        filename = outfile
    MEGABIT = 0x20000
    f = open(filename, 'r+b')
    subsums = [sum(map(ord, f.read(MEGABIT))) for _ in xrange(24)]
    subsums += subsums[-8:]
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
        return bs

    def write(self, filename):
        learn_leap_sub = Substitution()
        learn_leap_sub.bytestring = [0xEA] * 7
        learn_leap_sub.set_location(0x2543E)
        learn_leap_sub.write(filename)

        vict_sub = Substitution()
        vict_sub.bytestring = [0x20] + int2bytes(self.location, length=2)
        vict_sub.set_location(0x25EE5)
        vict_sub.write(filename)

        super(AutoLearnRageSub, self).write(filename)


class AutoRecruitGauSub(Substitution):
    @property
    def bytestring(self):
        return [0x50, 0xBC, 0x59, 0x10, 0x3F, 0x0B, 0x01, 0xD4, 0xFB, 0xFE]

    def write(self, filename):
        sub_addr = self.location - 0xa0000
        call_recruit_sub = Substitution()
        call_recruit_sub.bytestring = [0xB2] + int2bytes(sub_addr, length=3)
        call_recruit_sub.set_location(0xBC19C)
        call_recruit_sub.write(filename)
        gau_stays_wor_sub = Substitution()
        gau_stays_wor_sub.bytestring = [0xD4, 0xFB]
        gau_stays_wor_sub.set_location(0xA5324)
        gau_stays_wor_sub.write(filename)
        gau_cant_appear_sub = Substitution()
        gau_cant_appear_sub.bytestring = [0x80, 0x0C]
        gau_cant_appear_sub.set_location(0x22FB5)
        gau_cant_appear_sub.write(filename)
        REPLACE_ENEMIES.append(0x172)
        super(AutoRecruitGauSub, self).write(filename)


class EnableEsperMagicSub(Substitution):
    @property
    def bytestring(self):
        return [0xA9, 0x20, 0xA6, 0x00, 0x95, 0x79, 0xE8, 0xA9, 0x24, 0x60]

    def write(self, filename):
        jsr_sub = Substitution()
        jsr_sub.bytestring = [0x20] + int2bytes(self.location, length=2) + [0xEA]
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
            #for level, spell in self.natural_magic:
            #    s += "  LV %s - %s\n" % (level, spell.name)
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

    def write_battle_commands(self, filename):
        f = open(filename, 'r+b')
        for i, command in enumerate(self.battle_commands):
            if command is None:
                if i == 0:
                    command = 0
                else:
                    continue
            f.seek(self.address + 2 + i)
            f.write(chr(command))
        f.close()

    def write_default_equipment(self, filename, equipid, equiptype):
        f = open(filename, 'r+b')
        f.seek(self.address + equip_offsets[equiptype])
        f.write(chr(equipid))
        f.close()

    def mutate_stats(self, filename, read_only=False):
        f = open(filename, 'r+b')

        def mutation(base):
            while True:
                value = max(base / 2, 1)
                if self.beserk:
                    value += 1

                value += random.randint(0, value) + random.randint(0, value)
                while random.randint(1, 10) == 10:
                    value = max(value / 2, 1)
                    value += random.randint(0, value) + random.randint(0, value)
                value = max(1, min(value, 0xFE))

                if not self.beserk:
                    break
                elif value >= base:
                    break

            return value

        self.stats = {}
        f.seek(self.address)
        hpmp = map(ord, f.read(2))
        if not read_only:
            hpmp = map(lambda v: mutation(v), hpmp)
            f.seek(self.address)
            f.write("".join(map(chr, hpmp)))
        self.stats['hp'], self.stats['mp'] = tuple(hpmp)

        f.seek(self.address + 6)
        stats = map(ord, f.read(9))
        if not read_only:
            stats = map(lambda v: mutation(v), stats)
            f.seek(self.address + 6)
            f.write("".join(map(chr, stats)))
        for name, value in zip(CHARSTATNAMES[2:], stats):
            self.stats[name] = value

        f.close()

    def become_invincible(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.address + 11)
        stats = [0xFF, 0xFF, 0x80, 0x80]
        f.write("".join(map(chr, stats)))
        f.close()

    def set_id(self, i):
        self.id = i
        if self.id == 13:
            self.beserk = True
        palettes = dict(enumerate([2, 1, 4, 4, 0, 0, 0, 3, 3, 4, 5, 3, 3, 5,
                                   3, 0, 0, 0, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5,
                                   5, 2, 4, 2, 1, 1]))
        if self.id in palettes:
            self.palette = palettes[self.id]


class WindowBlock():
    def __init__(self, windowid):
        self.pointer = 0x2d1c00 + (windowid * 0x20)

    def read_data(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.pointer)
        self.palette = []
        for i in xrange(0x8):
            color = read_multi(f, length=2)
            blue = (color & 0x7c00) >> 10
            green = (color & 0x03e0) >> 5
            red = color & 0x001f
            self.negabit = color & 0x8000
            self.palette.append((red, green, blue))
        f.close()

    def write_data(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.pointer)
        for (red, green, blue) in self.palette:
            color = (blue << 10) | (green << 5) | red
            write_multi(f, color, length=2)
        f.close()

    def mutate(self):
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

        ordered_palette = zip(range(8), self.palette)
        ordered_palette = sorted(ordered_palette, key=lambda (i, c): sum(c))
        newpalette = [None] * 8
        clusters = cluster_colors(ordered_palette)
        prevdarken = random.uniform(0.3, 0.9)
        for cluster in clusters:
            degree = random.randint(-75, 75)
            darken = random.uniform(prevdarken, min(prevdarken*1.1, 1.0))
            darkener = lambda c: int(round(c * darken))
            hueswap = generate_swapfunc()
            for i, cs in sorted(cluster, key=lambda (i, c): sum(c)):
                newcs = shift_middle(cs, degree, ungray=True)
                newcs = map(darkener, newcs)
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


def randomize_colosseum(filename, pointer):
    item_objs = get_ranked_items(filename)
    monster_objs = get_ranked_monsters(filename, bosses=False)
    items = [i.itemid for i in item_objs]
    monsters = [m.id for m in monster_objs]
    results = []
    f = open(filename, 'r+b')
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
        f.seek(pointer + (i*4))
        f.write(chr(opponent))
        f.seek(pointer + (i*4) + 2)
        f.write(chr(trade))

        if abs(wager_obj.rank() - win_obj.rank()) >= 5000 and random.randint(1, 2) == 2:
            hidden = True
            f.write(chr(0xFF))
        else:
            hidden = False
            f.write(chr(0x00))
        results.append((wager_obj, opponent_obj, win_obj, hidden))

    f.close()
    results = sorted(results, key=lambda (a, b, c, d): a.name)

    coliseum_run_sub = Substitution()
    coliseum_run_sub.bytestring = [0xEA] * 2
    coliseum_run_sub.set_location(0x25BEF)
    coliseum_run_sub.write(outfile)

    return results


def randomize_slots(filename, pointer):
    spells = get_ranked_spells(filename)
    spells = [s for s in spells if s.spellid >= 0x36]
    attackspells = [s for s in spells if s.target_enemy_default]
    quarter = len(attackspells) / 4
    eighth = quarter / 2
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
            half = len(spells) / 2
            index = random.randint(0, half) + random.randint(0, half)
        elif i == 2:
            third = len(spells) / 3
            index = random.randint(third, len(spells)-1)
        elif i == 7:
            twentieth = len(spells)/20
            index = random.randint(0, twentieth)
            while random.randint(1, 3) == 3:
                index += random.randint(0, twentieth)
            index = min(index, len(spells)-1)

        spell = spells[index]
        return spell

    used = []
    f = open(filename, 'r+b')
    for i in xrange(1, 8):
        while True:
            spell = get_slots_spell(i)
            if spell is None or spell.spellid not in used:
                break
        if spell:
            used.append(spell.spellid)
            f.seek(pointer+i)
            f.write(chr(spell.spellid))
    f.close()


def manage_commands(commands):
    characters = get_characters()

    alrs = AutoLearnRageSub(require_gau=False)
    alrs.set_location(0x23b73)
    alrs.write(outfile)

    args = AutoRecruitGauSub()
    args.set_location(0xcfe1a)
    args.write(outfile)

    recruit_gau_sub = Substitution()
    recruit_gau_sub.bytestring = [0x89, 0xFF]
    recruit_gau_sub.set_location(0x24856)
    recruit_gau_sub.write(outfile)

    learn_lore_sub = Substitution()
    learn_lore_sub.bytestring = [0xEA, 0xEA, 0xF4, 0x00, 0x00, 0xF4, 0x00,
                                 0x00]
    learn_lore_sub.set_location(0x236E4)
    learn_lore_sub.write(outfile)

    learn_dance_sub = Substitution()
    learn_dance_sub.bytestring = [0xEA] * 2
    learn_dance_sub.set_location(0x25EE8)
    learn_dance_sub.write(outfile)

    learn_swdtech_sub = Substitution()
    learn_swdtech_sub.bytestring = [0xEB,       # XBA
                                    0x48,       # PHA
                                    0xEB,       # XBA
                                    0xEA]
    learn_swdtech_sub.set_location(0x261C7)
    learn_swdtech_sub.write(outfile)
    learn_swdtech_sub.bytestring = [0x4C, 0xDA, 0xA1, 0x60]
    learn_swdtech_sub.set_location(0xA18A)
    learn_swdtech_sub.write(outfile)

    learn_blitz_sub = Substitution()
    learn_blitz_sub.bytestring = [0xF0, 0x09]
    learn_blitz_sub.set_location(0x261CE)
    learn_blitz_sub.write(outfile)
    learn_blitz_sub.bytestring = [0xD0, 0x04]
    learn_blitz_sub.set_location(0x261D3)
    learn_blitz_sub.write(outfile)
    learn_blitz_sub.bytestring = [0x68,       # PLA
                                  0xEB,       # XBA
                                  0xEA, 0xEA, 0xEA, 0xEA, 0xEA]
    learn_blitz_sub.set_location(0x261D9)
    learn_blitz_sub.write(outfile)
    learn_blitz_sub.bytestring = [0xEA] * 4
    learn_blitz_sub.set_location(0x261E3)
    learn_blitz_sub.write(outfile)
    learn_blitz_sub.bytestring = [0xEA]
    learn_blitz_sub.set_location(0xA200)
    learn_blitz_sub.write(outfile)

    learn_multiple_sub = Substitution()
    learn_multiple_sub.set_location(0xA1B4)
    reljump = 0xFE - (learn_multiple_sub.location - 0xA186)
    learn_multiple_sub.bytestring = [0xF0, reljump]
    learn_multiple_sub.write(outfile)

    learn_multiple_sub.set_location(0xA1D6)
    reljump = 0xFE - (learn_multiple_sub.location - 0xA18A)
    learn_multiple_sub.bytestring = [0xF0, reljump]
    learn_multiple_sub.write(outfile)

    learn_multiple_sub.set_location(0x261DD)
    learn_multiple_sub.bytestring = [0xEA] * 3
    learn_multiple_sub.write(outfile)

    rage_blank_sub = Substitution()
    rage_blank_sub.bytestring = [0x01] + ([0x00] * 31)
    rage_blank_sub.set_location(0x47AA0)
    rage_blank_sub.write(outfile)

    eems = EnableEsperMagicSub()
    eems.set_location(0x3F091)
    eems.write(outfile)

    # Prevent Runic, SwdTech, and Capture from being disabled/altered
    protect_battle_commands_sub = Substitution()
    protect_battle_commands_sub.bytestring = [0x03, 0xFF, 0xFF, 0x0C,
                                              0x17, 0x02, 0xFF, 0x00]
    protect_battle_commands_sub.set_location(0x252E9)
    protect_battle_commands_sub.write(outfile)

    enable_morph_sub = Substitution()
    enable_morph_sub.bytestring = [0xEA] * 2
    enable_morph_sub.set_location(0x25410)
    enable_morph_sub.write(outfile)

    enable_mpoint_sub = Substitution()
    enable_mpoint_sub.bytestring = [0xEA] * 2
    enable_mpoint_sub.set_location(0x25E38)
    enable_mpoint_sub.write(outfile)

    ungray_statscreen_sub = Substitution()
    ungray_statscreen_sub.bytestring = [0x20, 0x6F, 0x61, 0x30, 0x26, 0xEA,
                                        0xEA, 0xEA]
    ungray_statscreen_sub.set_location(0x35EE1)
    ungray_statscreen_sub.write(outfile)

    fanatics_fix_sub = Substitution()
    fanatics_fix_sub.bytestring = [0xA9, 0x15]
    fanatics_fix_sub.set_location(0x2537E)
    fanatics_fix_sub.write(outfile)

    invalid_commands = ["fight", "item", "magic", "xmagic",
                        "def", "row", "summon", "revert"]
    if random.randint(1, 5) != 5:
        invalid_commands.append("magitek")

    if 'w' not in flags:
        invalid_commands.extend(FORBIDDEN_COMMANDS)

    invalid_commands = set([c for c in commands.values() if c.name in invalid_commands])

    def populate_unused():
        unused_commands = set(commands.values())
        unused_commands = sorted(unused_commands - invalid_commands)
        return sorted(unused_commands, key=lambda c: c.name)

    unused = populate_unused()
    xmagic_taken = False
    random.shuffle(characters)
    for c in characters:
        if c.id == 11:
            # Fixing Gau
            c.set_battle_command(0, commands["fight"])

        if 'collateraldamage' in activated_codes:
            c.set_battle_command(1, command_id=0xFF)
            c.set_battle_command(2, command_id=0xFF)
            c.set_battle_command(3, command_id=1)
            c.write_battle_commands(outfile)
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
                        morph_char_sub.bytestring = [0xC9, c.id]
                        morph_char_sub.set_location(0x25E32)
                        morph_char_sub.write(outfile)
            for i, command in enumerate(reversed(using)):
                c.set_battle_command(i+1, command=command)
        else:
            c.set_battle_command(1, command_id=0xFF)
            c.set_battle_command(2, command_id=0xFF)
        c.write_battle_commands(outfile)

    magitek_skills = [SpellBlock(i, sourcefile) for i in xrange(0x83, 0x8B)]
    for ms in magitek_skills:
        ms.fix_reflect(outfile)

    return commands


def manage_tempchar_commands():
    characters = get_characters()
    chardict = dict([(c.id, c) for c in characters])
    basicpool = set(range(3, 0x1E)) - changed_commands - set([0x4, 0x11, 0x14, 0x15, 0x19])
    mooglepool, banonpool, ghostpool, leopool = map(set, [basicpool]*4)
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
    for i, pool in zip(range(0xE, 0x1C), pools):
        pool = sorted([c for c in pool if c and c not in banned])
        a, b = tuple(random.sample(pool, 2))
        chardict[i].set_battle_command(1, command_id=a)
        chardict[i].set_battle_command(2, command_id=b)
        chardict[i].set_battle_command(3, command_id=0x1)
        chardict[i].write_battle_commands(outfile)

    for i in range(0xE, 0x1C):
        c = chardict[i]
        if c.battle_commands[1] == 0xFF and c.battle_commands[2] != 0xFF:
            c.set_battle_command(1, command_id=c.battle_commands[2])
        if c.battle_commands[1] == c.battle_commands[2]:
            c.set_battle_command(2, command_id=0xFF)
        c.write_battle_commands(outfile)


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
    all_spells = [SpellBlock(i, sourcefile) for i in xrange(0xFF)]
    randomskill_names = set([])
    for c in commands.values():
        if c.name in NEVER_REPLACE:
            continue
        elif c.name in RESTRICTED_REPLACE and random.choice([True, False]):
            continue

        if c.name not in ALWAYS_REPLACE:
            if random.randint(1, 100) > 50:
                continue

        changed_commands.add(c.id)
        random_skill = random.choice([True, False])
        POWER_LEVEL = 130
        scount = 1
        while random.randint(1, 7) == 7:
            scount += 1
        scount = min(scount, 9)

        while True:
            if random_skill:
                power = 10000
            else:
                basepower = POWER_LEVEL / 2
                power = basepower + random.randint(0, basepower)
                while True:
                    power += random.randint(0, basepower)
                    if random.choice([True, False]):
                        break

            c.read_properties(sourcefile)
            if not random_skill:
                def spell_is_valid(s):
                    if not s.valid:
                        return False
                    if s.spellid in used:
                        return False
                    return s.rank() <= power

                valid_spells = filter(spell_is_valid, all_spells)
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

                c.properties = 3
                if sb.spellid in [0x23, 0xA3]:
                    c.properties |= 0x4  # enable while imped
                c.unset_retarget(outfile)
                c.write_properties(outfile)

                if "endless9" in activated_codes:
                    scount = 10

                if scount < 3 or multibanned(sb.spellid):
                    s = SpellSub(spellid=sb.spellid)
                    scount = 1
                else:
                    scount -= 1
                    s = MultipleSpellSub()
                    s.set_spells(sb.spellid)
                    s.set_count(scount)

                newname = sb.name
            elif random_skill:
                c.properties = 3
                c.set_retarget(outfile)
                valid_spells = [v for v in all_spells if
                                v.spellid <= 0xED and v.valid]

                if "endless9" in activated_codes:
                    scount = 9

                if scount == 1:
                    s = RandomSpellSub()
                else:
                    valid_spells = multibanned(valid_spells)
                    s = MultipleSpellSub()
                    s.set_count(scount)

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

                c.write_properties(outfile)
                newname = s.name
            break

        myfs = get_appropriate_freespace(freespaces, s.size)
        s.set_location(myfs.start)
        if not hasattr(s, "bytestring") or not s.bytestring:
            s.generate_bytestring()
        s.write(outfile)
        c.setpointer(s.location, outfile)
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
        c.newname(newname, outfile)
        c.unsetmenu(outfile)
        c.allow_while_confused(outfile)
        if "playsitself" in activated_codes:
            c.allow_while_berserk(outfile)
        else:
            c.disallow_while_berserk(outfile)

    gogo_enable_all_sub = Substitution()
    gogo_enable_all_sub.bytestring = [0xEA] * 2
    gogo_enable_all_sub.set_location(0x35E58)
    gogo_enable_all_sub.write(outfile)

    cyan_ai_sub = Substitution()
    cyan_ai_sub.bytestring = [0xF0, 0xEE, 0xEE, 0xEE, 0xFF]
    cyan_ai_sub.set_location(0xFBE85)
    cyan_ai_sub.write(outfile)

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
    s.write(outfile)
    c.targeting = sb.targeting
    c.setpointer(s.location, outfile)
    c.newname(sb.name, outfile)
    c.unsetmenu(outfile)
    fss = myfs.unfree(s.location, s.size)
    freespaces.extend(fss)
    for c in characters:
        c.set_battle_command(0, command_id=0)
        c.set_battle_command(1, command_id=5)
        c.set_battle_command(2, command_id=0xA)
        c.set_battle_command(3, command_id=1)
        c.write_battle_commands(outfile)

    for m in monsters:
        m.misc2 &= 0xFB
        m.write_stats(outfile)

    learn_blitz_sub = Substitution()
    learn_blitz_sub.bytestring = [0xEA] * 2
    learn_blitz_sub.set_location(0x261E5)
    learn_blitz_sub.write(outfile)
    learn_blitz_sub.bytestring = [0xEA] * 4
    learn_blitz_sub.set_location(0xA18E)
    learn_blitz_sub.write(outfile)


def manage_natural_magic():
    characters = get_characters()
    candidates = [c for c in characters if 0x02 in c.battle_commands or
                  0x17 in c.battle_commands]
    try:
        candidates = random.sample(candidates, 2)
    except ValueError:
        return
    natmag_learn_sub = Substitution()
    natmag_learn_sub.bytestring = [0xC9, candidates[0].id]
    natmag_learn_sub.set_location(0x261B9)
    natmag_learn_sub.write(outfile)
    natmag_learn_sub.set_location(0xA182)
    natmag_learn_sub.write(outfile)
    address = 0x1A6E + (54 * candidates[0].id)
    natmag_learn_sub.bytestring = [0x99, address & 0xFF, address >> 8]
    natmag_learn_sub.set_location(0xA1AB)
    natmag_learn_sub.write(outfile)

    natmag_learn_sub.bytestring = [0xC9, candidates[1].id]
    natmag_learn_sub.set_location(0x261C0)
    natmag_learn_sub.write(outfile)
    natmag_learn_sub.set_location(0xA186)
    natmag_learn_sub.write(outfile)
    address = 0x1A6E + (54 * candidates[1].id)
    natmag_learn_sub.bytestring = [0x99, address & 0xFF, address >> 8]
    natmag_learn_sub.set_location(0xA1CD)
    natmag_learn_sub.write(outfile)

    spells = get_ranked_spells(sourcefile, magic_only=True)
    spellids = [s.spellid for s in spells]
    f = open(outfile, 'r+b')
    address = 0x2CE3C0

    def mutate_spell(pointer, used):
        f.seek(pointer)
        spell, level = tuple(map(ord, f.read(2)))

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

    candidates[0].natural_magic = []
    candidates[1].natural_magic = []
    usedspells = []
    for i in xrange(16):
        pointer = address + (2*i)
        newspell, level = mutate_spell(pointer, usedspells)
        candidates[0].natural_magic.append((level, newspell))
    candidates[0].natural_magic = sorted(candidates[0].natural_magic)
    for i, (level, newspell) in enumerate(candidates[0].natural_magic):
        pointer = address + (2*i)
        f.seek(pointer)
        f.write(chr(level))
        f.write(chr(newspell.spellid))

    usedspells = random.sample(usedspells, 12)
    for i in xrange(16):
        pointer = address + 32 + (2*i)
        newspell, level = mutate_spell(pointer, usedspells)
        candidates[1].natural_magic.append((level, newspell))
    candidates[1].natural_magic = sorted(candidates[1].natural_magic)
    for i, (level, newspell) in enumerate(candidates[1].natural_magic):
        pointer = address + +32 + (2*i)
        f.seek(pointer)
        f.write(chr(level))
        f.write(chr(newspell.spellid))

    lores = get_ranked_spells(sourcefile, magic_only=False)
    lores = filter(lambda s: 0x8B <= s.spellid <= 0xA2, lores)
    lore_ids = [l.spellid for l in lores]
    lores_in_order = sorted(lore_ids)
    address = 0x26F564
    f.seek(address)
    known_lores = read_multi(f, length=3)
    known_lore_ids = []
    for i in xrange(24):
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

    f.seek(address)
    write_multi(f, new_known_lores, length=3)
    f.close()

    return candidates


def manage_equip_umaro(freespaces):
    # ship unequip - cc3510
    equip_umaro_sub = Substitution()
    equip_umaro_sub.bytestring = [0xC9, 0x0E]
    equip_umaro_sub.set_location(0x31E6E)
    equip_umaro_sub.write(outfile)
    equip_umaro_sub.bytestring = [0xEA] * 2
    equip_umaro_sub.set_location(0x39EF6)
    equip_umaro_sub.write(outfile)

    f = open(sourcefile, 'r+b')
    f.seek(0xC359D)
    old_unequipper = map(ord, f.read(218))
    f.close()
    header = old_unequipper[:7]
    footer = old_unequipper[-3:]

    def generate_unequipper(basepointer, not_current_party=False):
        unequipper = []
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
            unequipper += segment
        unequipper = header + unequipper + footer
        return unequipper

    unequip_umaro_sub = Substitution()
    unequip_umaro_sub.bytestring = generate_unequipper(0xC351E)
    unequip_umaro_sub.set_location(0xC351E)
    unequip_umaro_sub.write(outfile)

    myfs = get_appropriate_freespace(freespaces, 234)
    pointer = myfs.start
    unequip_umaro_sub.bytestring = generate_unequipper(pointer, not_current_party=True)
    freespaces = determine_new_freespaces(freespaces, myfs, unequip_umaro_sub.size)
    unequip_umaro_sub.set_location(pointer)
    unequip_umaro_sub.write(outfile)
    unequip_umaro_sub.bytestring = [
        pointer & 0xFF, (pointer >> 8) & 0xFF, (pointer >> 16) - 0xA]
    unequip_umaro_sub.set_location(0xC3514)
    unequip_umaro_sub.write(outfile)

    return freespaces


def manage_umaro(commands):
    characters = get_characters()
    candidates = [c for c in characters if c.id <= 13 and
                  c.id != 12 and
                  2 not in c.battle_commands and
                  0xC not in c.battle_commands and
                  0x17 not in c.battle_commands]

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
        cands = [0x00, 0x03, 0x05, 0x06, 0x07, 0x09, 0x0A, 0x0B, 0x0D, 0x10,
                 0x12, 0x13, 0x16, 0x18]
        cands = [i for i in cands if i not in changed_commands]
        base_command = random.choice(cands)
        commands = commands.values()
        base_command = [c for c in commands if c.id == base_command][0]
        base_command.allow_while_berserk(outfile)
        umaro_risk.battle_commands = [base_command.id, 0xFF, 0xFF, 0xFF]

    umaro.beserk = False
    umaro_risk.beserk = True

    umaro_risk.write_battle_commands(outfile)
    umaro.write_battle_commands(outfile)

    umaro_exchange_sub = Substitution()
    umaro_exchange_sub.bytestring = [0xC9, umaro_risk.id]
    umaro_exchange_sub.set_location(0x21617)
    umaro_exchange_sub.write(outfile)
    umaro_exchange_sub.set_location(0x20926)
    umaro_exchange_sub.write(outfile)

    spells = get_ranked_spells(sourcefile)
    spells = filter(lambda x: x.target_enemy_default, spells)
    spells = filter(lambda x: x.valid, spells)
    spells = filter(lambda x: x.rank() < 1000, spells)
    spell_ids = [s.spellid for s in spells]
    index = spell_ids.index(0x54)  # storm
    index += random.randint(0, 10)
    while random.choice([True, False]):
        index += random.randint(-10, 10)
    index = max(0, min(index, len(spell_ids)-1))
    spell_id = spell_ids[index]
    storm_sub = Substitution()
    storm_sub.bytestring = [0xA9, spell_id]
    storm_sub.set_location(0x21710)
    storm_sub.write(outfile)

    return umaro_risk


def manage_sprint():
    autosprint = Substitution()
    autosprint.set_location(0x4E2D)
    autosprint.bytestring = [0x80, 0x00]
    autosprint.write(outfile)


def manage_skips():
    flashback_skip_sub = Substitution()
    flashback_skip_sub.bytestring = [0xB2, 0xB8, 0xA5, 0x00, 0xFE]
    flashback_skip_sub.set_location(0xAC582)
    flashback_skip_sub.write(outfile)

    boat_skip_sub = Substitution()
    boat_skip_sub.bytestring = (
        [0x97, 0x5C] +
        [0xD0, 0x87] +
        [0x3D, 0x03, 0x3F, 0x03, 0x01] +
        [0x6B, 0x00, 0x04, 0xE8, 0x96, 0x40, 0xFF]
        )
    boat_skip_sub.set_location(0xC615A)
    boat_skip_sub.write(outfile)

    leo_skip_sub = Substitution()
    leo_skip_sub.bytestring = (
        [0x97, 0x5C] +  # ???
        # ???
        [0xDB, 0xF7, 0xD5, 0xF2, 0xD5, 0xF3, 0xD5, 0xF4, 0xD5, 0xF5, 0xD5, 0xF9, 0xD5, 0xFB, 0xD5, 0xF6] +
        [0x77, 0x02, 0x77, 0x03, 0x77, 0x04, 0x77, 0x05, 0x77, 0x09, 0x77, 0x0B, 0x77, 0x06] +  # ???
        # add people to party
        [0xD4, 0xF2, 0xD4, 0xF4, 0xD4, 0xF5, 0xD4, 0xF9, 0xD4, 0xFB, 0xD4, 0xF6] +
        [0xB2, 0x35, 0x09, 0x02] +  # ???
        # entering airship triggers cutscene
        [0xD3, 0xCC] +  # ???
        [0xD0, 0x9D] +  # activate floating continent cutscene
        [0xD2, 0xBA] +  # ???
        [0xDA, 0x5A, 0xDA, 0xD9, 0xDB, 0x20, 0xDA, 0x68] +  # ???
        [0xD2, 0xB3, 0xD2, 0xB4] +  # ???
        [0xD0, 0x7A] +  # ???
        [0xD2, 0x76] +  # airship flyable
        [0xD2, 0x6F] +  # ???
        [0x6B, 0x00, 0x04, 0xF9, 0x80, 0x00] +  # load map, place party
        [0xC7, 0xF9, 0x7F, 0xFF]  # place airship
        )
    leo_skip_sub.set_location(0xBF2B5)
    leo_skip_sub.write(outfile)

    shadow_leaving_sub = Substitution()
    shadow_leaving_sub.bytestring = [0xEA] * 2
    shadow_leaving_sub.set_location(0x2488A)
    shadow_leaving_sub.write(outfile)

    narshe_skip_sub = Substitution()
    narshe_skip_sub.bytestring = []
    narshe_skip_sub.bytestring += [0x3E, 0x0D, 0x3D, 0x00, 0x3D, 0x04,
                                   0x3D, 0x0E, 0x3D, 0x05, 0x3D, 0x02,
                                   0x3D, 0x0B, 0x3D, 0x01, 0x3D, 0x06]
    narshe_skip_sub.bytestring += [0xD2, 0xCC, 0xD4, 0xBC]
    narshe_skip_sub.bytestring += [0x3F, 0x00, 0x01, 0x3F, 0x0D, 0x00]
    address = 0x2BC44 - len(narshe_skip_sub.bytestring)
    narshe_skip_sub.set_location(address + 0xA0000)
    narshe_skip_sub.write(outfile)
    narshe_skip_sub.bytestring = [0xB2, address & 0xFF, (address >> 8) & 0xFF, address >> 16]
    narshe_skip_sub.set_location(0xAADC4)
    narshe_skip_sub.write(outfile)


def activate_airship_mode(freespaces):
    set_airship_sub = Substitution()
    set_airship_sub.bytestring = (
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
    set_airship_sub.write(outfile)

    set_airship_sub.bytestring = [0xD2, 0xB9]  # airship appears in WoR
    set_airship_sub.set_location(0xA532A)
    set_airship_sub.write(outfile)

    set_airship_sub.bytestring = (
        [0x6B, 0x01, 0x04, 0x4A, 0x16, 0x01] +  # load WoR, place party
        [0xDD] +  # hide minimap
        [0xC5, 0x00, 0x7E, 0xC2, 0x1E, 0x00] +  # set height and direction
        [0xC6, 0x96, 0x00, 0xE0, 0xFF] +  # propel vehicle, wait 255 units
        [0xC7, 0x4E, 0xf0] +  # place airship
        [0xD2, 0x8E, 0x25, 0x07, 0x07, 0x40])  # load beach with fish
    set_airship_sub.set_location(0xA51E9)
    set_airship_sub.write(outfile)

    # point to airship-placing script
    set_airship_sub.bytestring = (
        [0xB2, pointer & 0xFF, (pointer >> 8) & 0xFF,
         (pointer >> 16) - 0xA, 0xFE])
    set_airship_sub.set_location(0xCB046)
    set_airship_sub.write(outfile)

    # always access floating continent
    set_airship_sub.bytestring = [0xC0, 0x27, 0x01, 0x79, 0xF5, 0x00]
    set_airship_sub.set_location(0xAF53A)  # need first branch for button press
    set_airship_sub.write(outfile)

    # always exit airship
    set_airship_sub.bytestring = [0xFD] * 6
    set_airship_sub.set_location(0xAF4B1)
    set_airship_sub.write(outfile)
    set_airship_sub.bytestring = [0xFD] * 8
    set_airship_sub.set_location(0xAF4E3)
    set_airship_sub.write(outfile)

    # chocobo stables are airship stables now
    set_airship_sub.bytestring = [0xB6, 0x8D, 0xF5, 0x00, 0xB3, 0x5E, 0x00]
    set_airship_sub.set_location(0xA7A39)
    set_airship_sub.write(outfile)
    set_airship_sub.set_location(0xA8FB7)
    set_airship_sub.write(outfile)
    set_airship_sub.set_location(0xB44D0)
    set_airship_sub.write(outfile)
    set_airship_sub.set_location(0xC3335)
    set_airship_sub.write(outfile)

    # don't force Locke and Celes at party select
    set_airship_sub.bytestring = [0x99, 0x01, 0x00, 0x00]
    set_airship_sub.set_location(0xAAB67)
    set_airship_sub.write(outfile)
    set_airship_sub.set_location(0xAF60F)
    set_airship_sub.write(outfile)
    set_airship_sub.set_location(0xCC2F3)
    set_airship_sub.write(outfile)

    # Daryl is not such an airship hog
    set_airship_sub.bytestring = [0x32, 0xF5]
    set_airship_sub.set_location(0x41F41)
    set_airship_sub.write(outfile)

    return freespaces


def manage_rng():
    f = open(outfile, 'r+b')
    f.seek(0xFD00)
    if 'norng' in activated_codes:
        numbers = [0 for _ in range(0x100)]
    else:
        numbers = range(0x100)
    random.shuffle(numbers)
    f.write("".join(map(chr, numbers)))
    f.close()

death_abuse_sub = Substitution()
death_abuse_sub.bytestring = [0x60]
death_abuse_sub.set_location(0xC515)


def manage_balance(newslots=True):
    vanish_doom_sub = Substitution()
    vanish_doom_sub.bytestring = [
        0xAD, 0xA2, 0x11, 0x89, 0x02, 0xF0, 0x07, 0xB9, 0xA1, 0x3A, 0x89, 0x04,
        0xD0, 0x6E, 0xA5, 0xB3, 0x10, 0x1C, 0xB9, 0xE4, 0x3E, 0x89, 0x10, 0xF0,
        0x15, 0xAD, 0xA4, 0x11, 0x0A, 0x30, 0x07, 0xAD, 0xA2, 0x11, 0x4A, 0x4C,
        0xB3, 0x22, 0xB9, 0xFC, 0x3D, 0x09, 0x10, 0x99, 0xFC, 0x3D, 0xAD, 0xA3,
        0x11, 0x89, 0x02, 0xD0, 0x0F, 0xB9, 0xF8, 0x3E, 0x10, 0x0A, 0xC2, 0x20,
        0xB9, 0x18, 0x30, 0x04, 0xA6, 0x4C, 0xE5, 0x22
        ]
    vanish_doom_sub.set_location(0x22215)
    vanish_doom_sub.write(outfile)

    evade_mblock_sub = Substitution()
    evade_mblock_sub.bytestring = [
        0xF0, 0x17, 0x20, 0x5A, 0x4B, 0xC9, 0x40, 0xB0, 0x9C, 0xB9, 0xFD, 0x3D,
        0x09, 0x04, 0x99, 0xFD, 0x3D, 0x80, 0x92, 0xB9, 0x55, 0x3B, 0x48,
        0x80, 0x43, 0xB9, 0x54, 0x3B, 0x48, 0xEA
        ]
    evade_mblock_sub.set_location(0x2232C)
    evade_mblock_sub.write(outfile)

    manage_rng()
    if newslots:
        randomize_slots(outfile, 0x24E4A)

    death_abuse_sub.write(outfile)

    get_monsters(sourcefile)
    sealed_kefka = get_monster(0x174)


def manage_magitek(spells):
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
    f = open(outfile, 'r+b')
    f.seek(target_pointer+3)
    for s in terra_used:
        f.write(chr(s.targeting))
    f.seek(terra_pointer+3)
    for s in terra_used:
        f.write(chr(s.spellid-0x83))
    f.seek(others_pointer+3)
    for s in others_used:
        if s is None:
            break
        f.write(chr(s.spellid-0x83))
    f.close()


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
        if monster.id in range(0x157, 0x160) + [0x11a, 0x12a]:
            return False
        return True

    kefka2.graphics.copy_data(kefka1.graphics)
    monsters = get_monsters()
    monsters = [m for m in monsters if has_graphics(m)]
    m = random.choice(monsters)
    kefka1.graphics.copy_data(m.graphics)
    change_enemy_name(outfile, kefka1.id, m.name.strip('_'))

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

    kefka1.write_stats(outfile)
    kefka2.write_stats(outfile)
    return freespaces


def manage_monsters():
    monsters = get_monsters(sourcefile)
    itembreaker = "collateraldamage" in activated_codes
    final_bosses = (range(0x157, 0x160) + range(0x127, 0x12b) +
                    [0x112, 0x11a, 0x17d])
    for m in monsters:
        if not m.name.strip('_') and not m.display_name.strip('_'):
            continue
        if m.id in final_bosses:
            if 0x157 <= m.id < 0x160 or m.id == 0x17d:
                # deep randomize three tiers, Atma
                m.randomize_boost_level()
                m.mutate(change_skillset=True, itembreaker=itembreaker)
            else:
                m.mutate(itembreaker=itembreaker)
            if 0x127 <= m.id < 0x12a or m.id == 0x17d or m.id == 0x11a:
                # boost statues, Atma, final kefka a second time
                m.randomize_boost_level()
                m.mutate(itembreaker=itembreaker)
            m.misc1 &= (0xFF ^ 0x4)  # always show name
        else:
            m.mutate(itembreaker=itembreaker)
        m.tweak_fanatics()
        m.relevel_specifics()

    change_enemy_name(outfile, 0x166, "L.255Magic")

    shuffle_monsters(monsters)
    for m in monsters:
        m.randomize_special_effect(outfile)
        m.write_stats(outfile)

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
        name = randomize_enemy_name(outfile, m.id)
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
            mg.write_data(outfile, palette_pointer=done[idpair])
        else:
            mg.write_data(outfile, palette_pointer=done[idpair],
                          no_palette=True)

    for mg in espers:
        mg.mutate_palette()
        mg.write_data(outfile, palette_pointer=freepointer)
        freepointer += len(mg.palette_data)

    return mgs


def recolor_character_palette(pointer, palette=None, flesh=False, middle=True):
    f = open(outfile, 'r+b')
    f.seek(pointer)
    if palette is None:
        palette = [read_multi(f, length=2) for _ in xrange(16)]
        outline, eyes, hair, skintone, outfit1, outfit2, NPC = (
            palette[:2], palette[2:4], palette[4:6], palette[6:8],
            palette[8:10], palette[10:12], palette[12:])
        new_palette = []
        if not flesh:
            for piece in (outline, eyes, hair, skintone, outfit1, outfit2, NPC):
                transformer = get_palette_transformer(middle=middle)
                piece = list(piece)
                piece = transformer(piece)
                new_palette += piece
            new_palette[6:8] = skintone
        else:
            transformer = get_palette_transformer(middle=middle)
            new_palette = transformer(palette)

        palette = new_palette

    f.seek(pointer)
    for p in palette:
        write_multi(f, p, length=2)
    f.close()
    return palette


def make_palette_repair(main_palette_changes):
    repair_sub = Substitution()
    bytestring = []
    for c in sorted(main_palette_changes):
        before, after = main_palette_changes[c]
        bytestring.extend([0x43, c, after])
    repair_sub.bytestring = bytestring + [0xFE]
    repair_sub.set_location(0xCB154)  # Narshe secret entrance
    repair_sub.write(outfile)


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
    for k, v in palettes.items():
        palettes[k] = sorted(v)
    return palettes


def manage_character_appearance(preserve_graphics=False):
    characters = get_characters()
    wild = 'partyparty' in activated_codes
    sabin_mode = 'suplexwrecks' in activated_codes
    tina_mode = 'bravenudeworld' in activated_codes
    charpal_options = {}
    for line in open(CHARACTER_PALETTE_TABLE):
        if line[0] == '#':
            continue
        charid, palettes = tuple(line.strip().split(':'))
        palettes = map(hex2int, palettes.split(','))
        charid = hex2int(charid)
        charpal_options[charid] = palettes

    npcs = get_npcs()

    if wild or tina_mode or sabin_mode:
        char_ids = range(0, 0x16)
    else:
        char_ids = range(0, 0x0E)

    if tina_mode:
        change_to = dict(zip(char_ids, [0x12] * 100))
    elif sabin_mode:
        change_to = dict(zip(char_ids, [0x05] * 100))
    else:
        female = [0, 0x06, 0x08]
        female += [c for c in [0x03, 0x0A, 0x0C, 0x0D, 0x0E, 0x0F, 0x14] if
                   random.choice([True, False])]
        female = [c for c in char_ids if c in female]
        male = [c for c in char_ids if c not in female]
        if preserve_graphics:
            change_to = dict(zip(char_ids, char_ids))
        elif wild:
            change_to = list(char_ids)
            random.shuffle(change_to)
            change_to = dict(zip(char_ids, change_to))
        else:
            random.shuffle(female)
            random.shuffle(male)
            change_to = dict(zip(sorted(male), male) +
                             zip(sorted(female), female))

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

    names = []
    if not tina_mode and not sabin_mode:
        f = open(MALE_NAMES_TABLE)
        malenames = sorted(set([line.strip() for line in f.readlines()]))
        f.close()
        f = open(FEMALE_NAMES_TABLE)
        femalenames = sorted(set([line.strip() for line in f.readlines()]))
        f.close()
        for c in range(14):
            choose_male = False
            if wild:
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

            name = name.upper()
            names.append(name)
    elif tina_mode:
        names = ["TINA"] * 14
    elif sabin_mode:
        names = ["TEABIN", "LOABIN", "CYABIN", "SHABIN", "EDABIN", "SABIN",
                 "CEABIN", "STABIN", "REABIN", "SEABIN", "MOABIN", "GAUBIN",
                 "GOABIN", "UMABIN"]

    for c in characters:
        if c.id < 14:
            c.newname = names[c.id]
            c.original_appearance = nameiddict[c.id]
            if not preserve_graphics:
                c.new_appearance = nameiddict[change_to[c.id]]
            else:
                c.new_appearance = c.original_appearance

    f = open(outfile, 'r+b')
    for c, name in enumerate(names):
        name = name_to_bytes(name, 6)
        assert len(name) == 6
        f.seek(0x478C0 + (6*c))
        f.write("".join(map(chr, name)))
    f.close()

    ssizes = ([0x16A0] * 0x10) + ([0x1560] * 6)
    spointers = dict([(c, sum(ssizes[:c]) + 0x150000) for c in char_ids])
    ssizes = dict(zip(char_ids, ssizes))

    char_portraits = {}
    char_portrait_palettes = {}
    sprites = {}
    f = open(outfile, 'r+b')
    for c in char_ids:
        f.seek(0x36F1B + (2*c))
        portrait = read_multi(f, length=2)
        char_portraits[c] = portrait
        f.seek(0x36F00 + c)
        portrait_palette = f.read(1)
        char_portrait_palettes[c] = portrait_palette
        f.seek(spointers[c])
        sprite = f.read(ssizes[c])
        sprites[c] = sprite

    if tina_mode:
        char_portraits[0x12] = char_portraits[0]
        char_portrait_palettes[0x12] = char_portrait_palettes[0]

    for c in char_ids:
        new = change_to[c]
        portrait = char_portraits[new]
        portrait_palette = char_portrait_palettes[new]
        if wild and portrait == 0 and change_to[c] != 0:
            portrait = char_portraits[0xE]
            portrait_palette = char_portrait_palettes[0xE]
        f.seek(0x36F1B + (2*c))
        write_multi(f, portrait, length=2)
        f.seek(0x36F00 + c)
        f.write(portrait_palette)
        if wild:
            f.seek(spointers[c])
            f.write(sprites[0xE][:ssizes[c]])
        f.seek(spointers[c])
        newsprite = sprites[change_to[c]]
        newsprite = newsprite[:ssizes[c]]
        f.write(newsprite)
    f.close()

    palette_change_to = {}
    for npc in npcs:
        if npc.graphics not in charpal_options:
            continue
        if npc.graphics in change_to:
            new_graphics = change_to[npc.graphics]
            if (npc.graphics, npc.palette) in palette_change_to:
                new_palette = palette_change_to[(npc.graphics, npc.palette)]
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

    main_palette_changes = {}
    f = open(outfile, 'r+b')
    for character in characters:
        c = character.id
        if c not in change_to:
            continue
        f.seek(0x2CE2B + c)
        before = ord(f.read(1))
        new_graphics = change_to[c]
        new_palette = palette_change_to[(c, before)]
        main_palette_changes[c] = (before, new_palette)
        f.seek(0x2CE2B + c)
        f.write(chr(new_palette))
        pointers = [0, 4, 9, 13]
        pointers = [ptr + 0x18EA60 + (18*c) for ptr in pointers]
        if c < 14:
            for ptr in pointers:
                f.seek(ptr)
                byte = ord(f.read(1))
                byte = byte & 0xF1
                byte |= ((new_palette+2) << 1)
                f.seek(ptr)
                f.write(chr(byte))
        character.palette = new_palette
    f.close()

    if "repairpalette" in activated_codes:
        make_palette_repair(main_palette_changes)

    for i in xrange(6):
        pointer = 0x268000 + (i*0x20)
        palette = recolor_character_palette(pointer, palette=None,
                                            flesh=(i == 5))
        pointer = 0x2D6300 + (i*0x20)
        recolor_character_palette(pointer, palette=palette)

    # esper terra
    pointer = 0x268000 + (8*0x20)
    palette = recolor_character_palette(pointer, palette=None, flesh=True,
                                        middle=False)
    pointer = 0x2D6300 + (6*0x20)
    palette = recolor_character_palette(pointer, palette=palette)

    # recolor magitek and chocobos
    transformer = get_palette_transformer(middle=True)

    def recolor_palette(pointer, size):
        f = open(outfile, 'r+b')
        f.seek(pointer)
        palette = [read_multi(f, length=2) for _ in xrange(size)]
        palette = transformer(palette)
        f.seek(pointer)
        [write_multi(f, c, length=2) for c in palette]
        f.close()

    recolor_palette(0x2cfd4, 23)
    recolor_palette(0x268000+(7*0x20), 16)
    recolor_palette(0x12ee20, 16)
    recolor_palette(0x12ef20, 16)

    f = open(outfile, 'r+b')
    for line in open(EVENT_PALETTE_TABLE):
        if line[0] == '#':
            continue
        pointer = hex2int(line.strip())
        f.seek(pointer)
        data = map(ord, f.read(5))
        char_id, palette = data[1], data[4]
        if char_id not in char_ids:
            continue
        try:
            data[4] = palette_change_to[(char_id, palette)]
        except KeyError:
            continue

        f.seek(pointer)
        f.write("".join(map(chr, data)))
    f.close()


def manage_colorize_animations():
    f = open(sourcefile, 'r+b')
    palettes = []
    for i in xrange(240):
        pointer = 0x126000 + (i*16)
        f.seek(pointer)
        palette = [read_multi(f, length=2) for _ in xrange(8)]
        palettes.append(palette)
    f.close()

    f = open(outfile, 'r+b')
    for i, palette in enumerate(palettes):
        transformer = get_palette_transformer(basepalette=palette)
        palette = transformer(palette)
        pointer = 0x126000 + (i*16)
        f.seek(pointer)
        [write_multi(f, c, length=2) for c in palette]
    f.close()


def manage_items(items, changed_commands=None):
    from itemrandomizer import set_item_changed_commands
    always_break = True if "collateraldamage" in activated_codes else False
    set_item_changed_commands(changed_commands)

    for i in items:
        i.mutate(always_break=always_break)
        i.unrestrict()
        i.write_stats(outfile)

    return items


def manage_equipment(items):
    characters = get_characters()
    reset_equippable(items, characters=characters)
    equippable_dict = {"weapon": lambda i: i.is_weapon,
                       "shield": lambda i: i.is_shield,
                       "helm": lambda i: i.is_helm,
                       "armor": lambda i: i.is_body_armor,
                       "relic": lambda i: i.is_relic}

    for c in characters:
        if c.id >= 0xE:
            f = open(outfile, 'r+b')
            lefthanded = random.randint(1, 10) == 10
            for equiptype in ['weapon', 'shield', 'helm', 'armor',
                              'relic1', 'relic2']:
                f.seek(c.address + equip_offsets[equiptype])
                equipid = ord(f.read(1))
                f.seek(c.address + equip_offsets[equiptype])
                if lefthanded and equiptype == 'weapon':
                    equiptype = 'shield'
                elif lefthanded and equiptype == 'shield':
                    equiptype = 'weapon'
                if equiptype == 'shield' and random.randint(1, 7) == 7:
                    equiptype = 'weapon'
                equiptype = equiptype.strip('1').strip('2')
                func = equippable_dict[equiptype]
                equippable_items = filter(func, items)
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
                f.write(chr(equipid))

            f.close()
            continue

        equippable_items = filter(lambda i: i.equippable & (1 << c.id), items)
        equippable_items = filter(lambda i: not i.has_disabling_status, equippable_items)
        equippable_items = filter(lambda i: not i.banned, equippable_items)
        if random.randint(1, 4) < 4:
            equippable_items = filter(lambda i: not i.imp_only, equippable_items)
        for equiptype, func in equippable_dict.items():
            if equiptype == 'relic':
                continue
            equippable = filter(func, equippable_items)
            weakest = 0xFF
            if equippable:
                weakest = min(equippable, key=lambda i: i.rank()).itemid
            c.write_default_equipment(outfile, weakest, equiptype)

    for i in items:
        i.write_stats(outfile)

    return items


def manage_reorder_rages(freespaces, by_level=False):
    myfs = get_appropriate_freespace(freespaces, 0x100)
    pointer = myfs.start
    freespaces = determine_new_freespaces(freespaces, myfs, 0x100)

    monsters = get_monsters()
    monsters = sorted(monsters, key=lambda m: m.display_name)
    monsters = [m for m in monsters if m.id <= 0xFE]
    assert len(monsters) == 255
    if by_level:
        monsters = reversed(sorted(monsters, key=lambda m: m.stats['level']))
    monster_order = [m.id for m in monsters]

    reordered_rages_sub = Substitution()
    reordered_rages_sub.bytestring = monster_order
    reordered_rages_sub.set_location(pointer)
    reordered_rages_sub.write(outfile)
    hirage, lorage = (pointer >> 8) & 0xFF, pointer & 0xFF

    rage_reorder_sub = Substitution()
    rage_reorder_sub.bytestring = [
        0xA9, 0x00,         # LDA #$00
        0xA8,               # TAY
        # main loop
        # get learned rages byte, store in EE
        0xBB, 0xBF, lorage, hirage, 0xC2,
        0x4A, 0x4A, 0x4A,   # LSR x3
        0xAA,               # TAX
        0xBD, 0x2C, 0x1D,   # LDA $1D2C,X (get rage byte)
        0x85, 0xEE,         # STA $EE
        # get bitmask for learned rage
        0xBB, 0xBF, lorage, hirage, 0xC2,
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
        0xBB, 0xBF, lorage, hirage, 0xC2,     # get rage
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
    rage_reorder_sub.write(outfile)

    rage_reorder_sub = Substitution()
    rage_reorder_sub.bytestring = [
        0x20, pointer & 0xFF, (pointer >> 8) & 0xFF,     # JSR
        0x60,                                            # RTS
        ]
    rage_reorder_sub.set_location(0x25847)
    rage_reorder_sub.write(outfile)

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

        boost_sub.write(outfile)

    esper_boost_sub = Substitution()
    esper_boost_sub.set_location(0x2615C)
    pointer1, pointer2 = (boost_subs[0].location, boost_subs[1].location)
    esper_boost_sub.bytestring = [
        pointer2 & 0xFF, (pointer2 >> 8) & 0xFF,
        pointer1 & 0xFF, (pointer1 >> 8) & 0xFF,
        ]
    esper_boost_sub.write(outfile)

    esper_boost_sub.set_location(0xFFEED)
    desc = map(lambda c: hex2int(shorttexttable[c]), "LV - 1   ")
    esper_boost_sub.bytestring = desc
    esper_boost_sub.write(outfile)
    esper_boost_sub.set_location(0xFFEF6)
    desc = map(lambda c: hex2int(shorttexttable[c]), "LV + 50% ")
    esper_boost_sub.bytestring = desc
    esper_boost_sub.write(outfile)

    death_abuse_sub.write(outfile)

    return freespaces


def manage_espers(freespaces):
    espers = get_espers()
    random.shuffle(espers)
    for e in espers:
        e.generate_spells()
        e.generate_bonus()

    bonus_espers = [e for e in espers if e.id in [15, 16]]
    random.shuffle(bonus_espers)
    bonus_espers[0].bonus = 7
    bonus_espers[1].add_spell(0x2B, 1)
    for e in sorted(espers, key=lambda e: e.name):
        e.write_data(outfile)

    ragnarok_sub = Substitution()
    ragnarok_sub.set_location(0xC0B37)
    ragnarok_sub.bytestring = [0xB2, 0x58, 0x0B, 0x02, 0xFE]
    ragnarok_sub.write(outfile)
    pointer = ragnarok_sub.location + len(ragnarok_sub.bytestring) + 1
    a, b = pointer & 0xFF, (pointer >> 8) & 0xFF
    c = 2
    ragnarok_sub.set_location(0xC557B)
    ragnarok_sub.bytestring = [0xD4, 0xDB,
                               0xDD, 0x99,
                               0x6B, 0x6C, 0x21, 0x08, 0x08, 0x80,
                               0xB2, a, b, c]
    ragnarok_sub.write(outfile)
    ragnarok_sub.set_location(pointer)
    # CA5EA9
    ragnarok_sub.bytestring = [0xB2, 0xA9, 0x5E, 0x00,  # event stuff
                               0x5C,
                               0xF4, 0x67,  # SFX
                               0xB2, 0xD5, 0x9A, 0x02,  # GFX
                               0x4B, 0x6A, 0x85,
                               0xB2, 0xD5, 0x9A, 0x02,  # GFX
                               0xF4, 0x8D,  # SFX
                               0x86, 0x46,  # receive esper
                               0xFE,
                               ]
    ragnarok_sub.write(outfile)

    freespaces = manage_esper_boosts(freespaces)

    for e in espers:
        log(str(e), section="espers")

    return freespaces


def manage_treasure(monsters, shops=True):
    for mm in get_metamorphs():
        mm.mutate_items()
        mm.write_data(outfile)

    for m in monsters:
        m.mutate_items()
        m.mutate_metamorph()
        m.write_stats(outfile)

    if shops:
        buyables = manage_shops()

    pointer = 0x1fb600
    results = randomize_colosseum(outfile, pointer)
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
        candidates = candidates[len(candidates)/2:]
        wager = random.choice(candidates)
        buycheck = [get_item(b).name for b in buyables
                    if b in wagers and wagers[b] == wager]
        if not buycheck:
            raise Exception("Striker pickup not ensured.")
        f = open(outfile, 'r+b')
        f.seek(pointer + (wager.itemid*4) + 2)
        f.write(chr(0x29))
        f.close()
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
    locations = get_locations(sourcefile)
    locations = sorted(locations, key=lambda l: l.rank())
    for l in locations:
        l.mutate_chests()
    locations = sorted(locations, key=lambda l: l.locid)

    for m in get_monsters():
        m.write_stats(outfile)


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
        nextpointer = l.write_chests(outfile, nextpointer=nextpointer)


def write_all_npcs():
    locations = get_locations()
    locations = sorted(locations, key=lambda l: l.locid)

    nextpointer = 0x41d52
    for l in locations:
        if hasattr(l, "restrank"):
            nextpointer = l.write_npcs(outfile, nextpointer=nextpointer,
                                       ignore_order=True)
        else:
            nextpointer = l.write_npcs(outfile, nextpointer=nextpointer)


def write_all_events():
    locations = get_locations()
    locations = sorted(locations, key=lambda l: l.locid)

    nextpointer = 0x40342
    for l in locations:
        nextpointer = l.write_events(outfile, nextpointer=nextpointer)


def write_all_entrances():
    entrancesets = [l.entrance_set for l in get_locations()]
    entrancesets = entrancesets[:0x19F]
    nextpointer = 0x1FBB00 + (len(entrancesets) * 2) + 2
    longnextpointer = 0x2DF480 + (len(entrancesets) * 2) + 2
    total = 0
    for e in entrancesets:
        total += len(e.entrances)
        nextpointer, longnextpointer = e.write_data(outfile, nextpointer,
                                                    longnextpointer)
    f = open(outfile, 'r+b')
    f.seek(e.pointer + 2)
    write_multi(f, (nextpointer - 0x1fbb00), length=2)
    f.seek(e.longpointer + 2)
    write_multi(f, (longnextpointer - 0x2df480), length=2)
    f.close()


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
    letters = range(3, 7)
    f = open(outfile, 'r+b')
    log("1. left, right, left", section="blitz inputs")
    for i in xrange(1, 8):
        # skip pummel
        current = blitzspecptr + (i * 12)
        f.seek(current + 11)
        length = ord(f.read(1)) / 2
        halflength = max(length / 2, 2)
        newlength = (halflength + random.randint(0, halflength) +
                     random.randint(1, halflength))
        newlength = min(newlength, 10)

        newcmd = []
        used_cmds = []
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
        f.seek(current)
        f.write("".join(map(chr, newcmd)))
    f.close()


def manage_dragons():
    dragon_pointers = [0xab6df, 0xc18f3, 0xc1920, 0xc2048,
                       0xc205b, 0xc36df, 0xc43cd, 0xc558b]
    dragons = range(0x84, 0x8c)
    assert len(dragon_pointers) == len(dragons) == 8
    random.shuffle(dragons)
    f = open(outfile, 'r+b')
    for pointer, dragon in zip(dragon_pointers, dragons):
        f.seek(pointer)
        c = ord(f.read(1))
        assert c == 0x4D
        f.seek(pointer+1)
        f.write(chr(dragon))
    f.close()


def manage_formations(formations, fsets):
    for fset in fsets:
        if len(fset.formations) == 4:
            for formation in fset.formations:
                formation.set_music(6)
                formation.set_continuous_music()
                formation.write_data(outfile)

    for formation in formations:
        if formation.get_music() != 6:
            #print formation
            if formation.formid in [0xb2, 0xb3, 0xb6]:
                # additional floating continent formations
                formation.set_music(6)
                formation.set_continuous_music()
                formation.write_data(outfile)

    ranked_fsets = sorted(fsets, key=lambda fs: fs.rank())
    ranked_fsets = [fset for fset in ranked_fsets if not fset.has_boss]
    valid_fsets = [fset for fset in ranked_fsets if len(fset.formations) == 4]

    outdoors = range(0, 0x39) + [0x57, 0x58, 0x6e, 0x6f, 0x78, 0x7c]

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
        for i in xrange(len(fsetset)-1):
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
        formation.write_data(outfile)

    return formations


def manage_formations_hidden(formations, freespaces, esper_graphics=None):
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
    unused_formations = filter(unused_validator, formations)

    def single_enemy_validator(formation):
        if formation in unused_formations:
            return False
        if len(formation.present_enemies) != 1:
            return False
        if formation.formid in REPLACE_FORMATIONS + NOREPLACE_FORMATIONS:
            return False
        return True
    single_enemy_formations = filter(single_enemy_validator, formations)

    def single_boss_validator(formation):
        if formation.formid == 0x1b5:
            # disallow GhostTrain
            return False
        if not (any([m.boss_death for m in formation.present_enemies])
                or formation.mould in xrange(2, 8)):
            return False
        return True
    single_boss_formations = filter(single_boss_validator,
                                    single_enemy_formations)

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

    safe_boss_formations = filter(safe_boss_validator, formations)
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

        for _ in xrange(100):
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
            ue.stats['level'] = (boss.stats['level']+boss2.stats['level']) / 2

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
        ue.mutate_ai(change_skillset=True)
        ue.mutate_ai(change_skillset=True)

        ue.mutate(change_skillset=True)
        if random.choice([True, False]):
            ue.mutate(change_skillset=True)
        ue.treasure_boost()
        ue.graphics.mutate_palette()
        name = randomize_enemy_name(outfile, ue.id)
        ue.changed_name = name
        ue.misc1 &= (0xFF ^ 0x4)  # always show name
        ue.write_stats(outfile)
        ue.read_ai(outfile)
        mutated_ues.append(ue.id)
        for m in get_monsters():
            if m.id != ue.id:
                assert m.aiptr != ue.aiptr

        uf.set_music_appropriate()
        appearances = range(1, 14)
        if ue.stats['level'] > 50:
            appearances += [15]
        uf.set_appearing(random.choice(appearances))
        uf.get_special_ap()
        uf.mouldbyte = 0x60
        ue.graphics.write_data(outfile)
        uf.misc1 &= 0xCF  # allow front and back attacks
        uf.write_data(outfile)
        repurposed_formations.append(uf)

    lobo_formation = get_formation(0)
    for uf in unused_formations:
        if uf not in repurposed_formations:
            uf.copy_data(lobo_formation)

    boss_candidates = list(safe_boss_formations)
    boss_candidates = random.sample(boss_candidates,
                                    random.randint(0, len(boss_candidates)/2))
    rare_candidates = list(repurposed_formations + boss_candidates)

    zones = get_zones()
    fsets = []
    for z in zones:
        for i in xrange(4):
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
                fs.write_data(outfile)
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
    for i, name in zip(xrange(0x80), shop_names):
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
    for s in get_shops():
        s.mutate_items(outfile)
        s.mutate_misc()
        s.write_data(outfile)
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
        encounters = map(hex2int, encounters)
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
        l.write_data(outfile)

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

        f = open(outfile, 'r+b')
        battlebgs = set([l.battlebg for l in candidates if l.attacks])
        battlebgs |= set(backgrounds)

        transformer = None
        battlebgs = sorted(battlebgs)
        random.shuffle(battlebgs)
        for bg in battlebgs:
            palettenum = battlebg_palettes[bg]
            pointer = 0x270150 + (palettenum * 0x60)
            f.seek(pointer)
            if pointer in done:
                #raise Exception("Already recolored palette %x" % pointer)
                continue
            raw_palette = [read_multi(f, length=2) for i in xrange(0x30)]
            if transformer is None:
                if bg in [0x33, 0x34, 0x35, 0x36]:
                    transformer = get_palette_transformer(always=True)
                else:
                    transformer = get_palette_transformer(
                        basepalette=raw_palette, use_luma=True)
            new_palette = transformer(raw_palette)

            f.seek(pointer)
            [write_multi(f, c, length=2) for c in new_palette]
            done.append(pointer)

        for p in palettes:
            if p in done:
                raise Exception("Already recolored palette %x" % p)
            f.seek(p)
            raw_palette = [read_multi(f, length=2) for i in xrange(0x80)]
            new_palette = transformer(raw_palette)
            f.seek(p)
            [write_multi(f, c, length=2) for c in new_palette]
            done.append(p)

        f.close()

    if 'p' in flags or 's' in flags or 'partyparty' in activated_codes:
        manage_colorize_wor()
        manage_colorize_esper_world()


def manage_colorize_wor():
    transformer = get_palette_transformer(always=True)
    f = open(outfile, 'r+b')
    f.seek(0x12ed00)
    raw_palette = [read_multi(f, length=2) for i in xrange(0x80)]
    new_palette = transformer(raw_palette)
    f.seek(0x12ed00)
    [write_multi(f, c, length=2) for c in new_palette]

    f.seek(0x12ef40)
    raw_palette = [read_multi(f, length=2) for i in xrange(0x60)]
    new_palette = transformer(raw_palette)
    f.seek(0x12ef40)
    [write_multi(f, c, length=2) for c in new_palette]

    f.seek(0x12ef00)
    raw_palette = [read_multi(f, length=2) for i in xrange(0x12)]
    airship_transformer = get_palette_transformer(basepalette=raw_palette)
    new_palette = airship_transformer(raw_palette)
    f.seek(0x12ef00)
    [write_multi(f, c, length=2) for c in new_palette]

    for battlebg in [1, 5, 0x29, 0x2F]:
        palettenum = battlebg_palettes[battlebg]
        pointer = 0x270150 + (palettenum * 0x60)
        f.seek(pointer)
        raw_palette = [read_multi(f, length=2) for i in xrange(0x30)]
        new_palette = transformer(raw_palette)
        f.seek(pointer)
        [write_multi(f, c, length=2) for c in new_palette]

    for palette_index in [0x16, 0x2c, 0x2d, 0x29]:
        field_palette = 0x2dc480 + (256 * palette_index)
        f.seek(field_palette)
        raw_palette = [read_multi(f, length=2) for i in xrange(0x80)]
        new_palette = transformer(raw_palette)
        f.seek(field_palette)
        [write_multi(f, c, length=2) for c in new_palette]

    f.close()


def manage_colorize_esper_world():
    loc = get_location(217)
    chosen = random.choice([1, 22, 25, 28, 34, 38, 43])
    loc.palette_index = (loc.palette_index & 0xFFFFC0) | chosen
    loc.write_data(outfile)


def manage_encounter_rate():
    if 'dearestmolulu' in activated_codes:
        overworld_rates = [1, 0, 1, 0, 1, 0, 0, 0,
                           0xC0, 0, 0x60, 0, 0x80, 1, 0, 0,
                           0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
                           0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]
        dungeon_rates = [0, 0, 0, 0, 0, 0, 0, 0,
                         0xC0, 0, 0x60, 0, 0x80, 1, 0, 0,
                         0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
                         0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]
        assert len(overworld_rates) == 32
        assert len(dungeon_rates) == 32
        encrate_sub = Substitution()
        encrate_sub.set_location(0xC29F)
        encrate_sub.bytestring = overworld_rates
        encrate_sub.write(outfile)
        encrate_sub.set_location(0xC2BF)
        encrate_sub.bytestring = dungeon_rates
        encrate_sub.write(outfile)
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
        z.write_data(outfile)

    def rates_cleaner(rates):
        rates = [max(int(round(o)), 1) for o in rates]
        rates = [int2bytes(o, length=2) for o in rates]
        rates = [i for sublist in rates for i in sublist]
        return rates

    base4 = map(lambda (b, t): b*t, zip([0xC0]*4, [1, 0.5, 2, 1]))
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
    encrate_sub.bytestring = overworld_rates
    encrate_sub.write(outfile)

    # dungeon encounters: normal, strongly affected by charms,
    # weakly affected by charms, and unaffected by charms
    base = 0x70
    bangle = 0.5
    moogle = 0.01
    normal = [base, base*bangle, base*moogle, base*bangle*moogle]
    unaffected = [base, base, base, base]

    sbase = base*2.5
    strong = [sbase, sbase*bangle/2, sbase*moogle/2, sbase*bangle*moogle/4]

    wbase = base*1.5
    half = wbase/2
    weak = [wbase, half+(half*bangle), half+(half*moogle),
            half+(half*bangle*moogle)]

    dungeon_rates = zip(normal, strong, weak, unaffected)
    dungeon_rates = [i for sublist in dungeon_rates for i in sublist]
    dungeon_rates = rates_cleaner(dungeon_rates)
    encrate_sub = Substitution()
    encrate_sub.set_location(0xC2BF)
    encrate_sub.bytestring = dungeon_rates
    encrate_sub.write(outfile)


def manage_tower():
    locations = get_locations()
    randomize_tower(filename=sourcefile)
    for l in locations:
        if l.locid in [0x154, 0x155] + range(104, 108):
            # leo's thamasa, etc
            # TODO: figure out consequences of 0x154
            l.entrance_set.entrances = []
            if l.locid == 0x154:
                thamasa_map_sub = Substitution()
                for location in [0xBD330, 0xBD357, 0xBD309, 0xBD37E, 0xBD3A5,
                                 0xBD3CC, 0xBD3ED, 0xBD414]:
                    thamasa_map_sub.set_location(location)
                    thamasa_map_sub.bytestring = [0x57]
                    thamasa_map_sub.write(outfile)
        l.write_data(outfile)

    npc = [n for n in get_npcs() if n.event_addr == 0x233B8][0]
    npc.event_addr = 0x233A6
    narshe_beginner_sub = Substitution()
    narshe_beginner_sub.bytestring = [0xE5, 0x00]
    narshe_beginner_sub.set_location(0xC33A7)
    narshe_beginner_sub.write(outfile)


def create_dimensional_vortex():
    entrancesets = []
    entrances = []
    for i in xrange(512):
        e = EntranceSet(i)
        e.read_data(sourcefile)
        entrancesets.append(e)
        entrances.extend(e.entrances)

    entrances = sorted(set(entrances))

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

    entrancesets = entrancesets[:0x19F]
    nextpointer = 0x1FBB00 + (len(entrancesets) * 2)
    for e in entrancesets:
        nextpointer = e.write_data(outfile, nextpointer)


def change_enemy_name(filename, enemy_id, name):
    pointer = 0xFC050 + (enemy_id * 10)
    f = open(filename, 'r+b')
    f.seek(pointer)
    monster = get_monster(enemy_id)
    monster.changed_name = name
    name = name_to_bytes(name, 10)
    f.write("".join(map(chr, name)))
    f.close()


def randomize_enemy_name(filename, enemy_id):
    name = generate_name()
    change_enemy_name(filename, enemy_id, name)
    return name


def randomize_final_party_order():
    f = open(outfile, 'r+b')
    code = [
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
    ]
    f.seek(0x3AA25)
    f.write("".join(map(chr, code)))
    f.close()


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
    equip_anything_sub.bytestring = [0x80, 0x04]
    equip_anything_sub.write(outfile)
    equip_anything_sub.set_location(0x39b99)
    equip_anything_sub.bytestring = [0xEA, 0xEA]
    equip_anything_sub.write(outfile)


def manage_full_umaro():
    full_umaro_sub = Substitution()
    full_umaro_sub.bytestring = [0x80]
    full_umaro_sub.set_location(0x20928)
    full_umaro_sub.write(outfile)
    if 'u' in flags:
        full_umaro_sub.set_location(0x21619)
        full_umaro_sub.write(outfile)


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
            text = (" " * (remaining/2)) + text
            while len(text) < len(original):
                text += " "
        else:
            midtext = len(text)/2
            midlength = length / 2
            a, b = text[:midtext], text[midtext:]
            text = ""
            for t in (a, b):
                margin = (midlength - len(t)) / 2
                t = (" " * margin) + t
                while len(t) < midlength:
                    t += " "
                text += t
                text = text[:-1] + chr(0xFE)
            text = text[:-1]
        text = [table[c] if c in table else c for c in text]
        text.append(0)
        d.writeover(address, text)

    from string import letters as alpha
    consonants = "".join([c for c in alpha if c not in "aeiouy"])
    replace_credits_text(0x659C, "ffvi")
    replace_credits_text(0x65A9, "BEYOND CHAOS")
    replace_credits_text(0x65C0, "creator")
    replace_credits_text(0x65CD, "Abyssonym")
    replace_credits_text(0x65F1, "seed")
    text = "".join([consonants[int(i)] for i in str(seed)])
    replace_credits_text(0x6605, text.upper())
    replace_credits_text(0x6625, "flags")
    display_flags = sorted([a for a in alpha if a in flags.lower()])
    display_flags = "".join(display_flags).upper()
    replace_credits_text(0x663A, display_flags, split=True)
    codestatus = "CODES ON" if activated_codes else "CODES OFF"
    replace_credits_text(0x6661, codestatus)
    replace_credits_text(0x6682, "ver.")
    replace_credits_text(0x668C, VERSION_ROMAN)

    for address in [0x669E, 0x66B1, 0x66C5, 0x66D8, 0x66FB, 0x670D, 0x6732,
                    0x6758, 0x676A, 0x6791, 0x67A7, 0x67C8, 0x67DE, 0x67F4,
                    0x6809, 0x6819, 0x6835, 0x684A, 0x6865, 0x6898, 0x68CE,
                    0x68F9, 0x6916, 0x6929, 0x6945, 0x6959, 0x696C, 0x697E,
                    0x6991, 0x69A9, 0x69B8]:
        replace_credits_text(address, "")

    d.compress_and_write(outfile)


def manage_ending():
    ending_sync_sub = Substitution()
    ending_sync_sub.bytestring = [0xC0, 0x07]
    ending_sync_sub.set_location(0x3CF93)
    ending_sync_sub.write(outfile)


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
    f = open(outfile, "r+b")
    for key in new_format:
        pointer = 0xb0000 | key
        for dest in new_format[key]:
            f.seek(pointer)
            value = ord(f.read(1))
            if value in [0xb2, 0xbd]:
                pointer += 1
            elif value == 0xc0:
                pointer += 3
            elif value == 0xc1:
                pointer += 5
            else:
                raise Exception("Unknown auction house byte %x %x" % (pointer, value))
            f.seek(pointer)
            oldaddr = read_multi(f, 2)
            assert oldaddr in new_format
            assert dest in new_format
            f.seek(pointer)
            write_multi(f, dest, 2)
            pointer += 3
    f.close()


def manage_bingo():
    target_score = 200.0
    print "WELCOME TO BEYOND CHAOS BINGO MODE"
    print "Include what type of squares? (blank for all)"
    print ("    a   Abilities\n"
           "    i   Items\n"
           "    m   Monsters\n"
           "    s   Spells")
    bingoflags = raw_input("> ").strip()
    if not bingoflags:
        bingoflags = "aims"
    bingoflags = [c for c in "aims" if c in bingoflags]

    print "What size grid? (default: 5)"
    size = raw_input("> ").strip()
    if not size:
        size = 5
    else:
        size = int(size)
    target_score = float(target_score) * (size**2)

    print "What difficulty level? Easy, Normal, or Hard? (e/n/h)"
    difficulty = raw_input("> ").strip()
    if not difficulty:
        difficulty = "n"
    else:
        difficulty = difficulty[0].lower()
        if difficulty not in "enh":
            difficulty = "n"

    print "Generate how many cards? (default: 1)"
    numcards = raw_input("> ").strip()
    if not numcards:
        numcards = 1
    else:
        numcards = int(numcards)
    print "Generating Bingo cards, please wait."

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
        left, right = lambda x: 0, lambda x: len(x)/2
    elif difficulty == 'h':
        left, right = lambda x: len(x)/2, lambda x: len(x)
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

    for i in xrange(numcards):
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
        for y in xrange(size):
            for g in [grid, flaggrid, displaygrid]:
                g.append([])
            for x in xrange(size):
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
            chosens = scoredict.keys()
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
    f = open(outfile, 'r+b')
    f.seek(0xEF101)
    text = ("ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            "abcdefghijklmnopqrstuvwxyz"
            "0123456789")
    text = dict([(c, i + 0x20) for (i, c) in enumerate(text)])
    text[" "] = 0x7F
    pointers = {}
    for i in xrange(1, 101):
        pointers[i] = f.tell()
        room_name = "Room %s" % i
        room_name = "".join([chr(text[c]) for c in room_name])
        f.write(room_name)
        f.write(chr(0))

    for i in xrange(1, 101):
        f.seek(0x268400 + (2*i))
        pointer = pointers[i] - 0xEF100
        write_multi(f, pointer, length=2)

    f.close()


def manage_ancient():
    if 'o' not in flags:
        alrs = AutoLearnRageSub(require_gau=True)
        alrs.set_location(0x23b73)
        alrs.write(outfile)

        enable_morph_sub = Substitution()
        enable_morph_sub.bytestring = [0xEA] * 2
        enable_morph_sub.set_location(0x25410)
        enable_morph_sub.write(outfile)

        enable_mpoint_sub = Substitution()
        enable_mpoint_sub.bytestring = [0xEA] * 2
        enable_mpoint_sub.set_location(0x25E38)
        enable_mpoint_sub.write(outfile)

    shadow_leaving_sub = Substitution()
    shadow_leaving_sub.bytestring = [0xEA] * 2
    shadow_leaving_sub.set_location(0x2488A)
    shadow_leaving_sub.write(outfile)

    characters = get_characters()
    gau = [c for c in characters if c.id == 11][0]
    if gau.battle_commands[1] in [0x11, None]:
        gau.battle_commands[0] = 0x10
        gau.battle_commands[1] = 0xFF
        gau.write_battle_commands(outfile)

    fi = open(outfile, 'r+b')
    for i in xrange(34):
        pointer = 0x2d7ca0 + 0x15 + (i*22)
        fi.seek(pointer)
        level = ord(fi.read(1))
        level &= 0xF3
        if i >= 14:
            level |= 0b1000
        fi.seek(pointer)
        fi.write(chr(level))

    fi.seek(0xa5e74)
    fi.write(chr(0))  # remove Terra's magitek

    to_dummy = [get_item(0xF6), get_item(0xF7)]
    name = [0xFF] + name_to_bytes("Pebble", 12)
    for item in to_dummy:
        item.dataname = name
        item.price = 4
        item.itemtype = 6
        item.write_stats(outfile)
    blank_sub = Substitution()
    blank_sub.set_location(0x2D76C1)
    blank_sub.bytestring = [0xFF] * (0x2D76F5 - blank_sub.location)
    blank_sub.bytestring[blank_sub.size/2] = 0
    blank_sub.write(outfile)

    goddess_save_sub = Substitution()
    goddess_save_sub.bytestring = [0xFD, 0xFD]
    goddess_save_sub.set_location(0xC170A)
    goddess_save_sub.write(outfile)
    goddess_save_sub.set_location(0xC1743)
    goddess_save_sub.write(outfile)
    goddess_save_sub.set_location(0xC1866)
    goddess_save_sub.write(outfile)

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
    for level in xrange(maxlevel):
        ratio = (float(level) / maxlevel)**2
        ratio = min(ratio, 1.0)
        pointer = 0x2d8220 + (level*2)
        fi.seek(pointer)
        exp = read_multi(fi, length=2)
        newexp = (exp / divisor)
        remaining = exp - newexp
        newexp = int(round(newexp + (ratio*remaining)))
        newexp = max(newexp, 1)
        fi.seek(pointer)
        write_multi(fi, newexp, length=2)

    fi.close()

    startsub = Substitution()
    startsub.bytestring = [0xD7, 0xF3,  # remove Daryl
                           0xD5, 0xF0,  # remove Terra from party
                           0xD5, 0xE0,  # remove Terra from party
                           0xDC, 0x7E,  # fix ending? $1F4F bit 6
                           0xB8, 0x43,  # show magic points after battle
                           0x3F, 0x0E, 0x00,
                           0x3F, 0x0F, 0x00,
                           ]
    if 'racecave' in activated_codes:
        num_starting = 9 + random.randint(0, 2) + random.randint(0, 1)
    elif 'speedcave' in activated_codes:
        num_starting = 4 + random.randint(0, 3) + random.randint(0, 2)
    else:
        num_starting = 4 + random.randint(0, 1) + random.randint(0, 1)
    starting = random.sample(range(14), num_starting)
    for c in starting:
        startsub.bytestring += [0xD4, 0xF0 | c]
        startsub.bytestring += [0xD4, 0xE0 | c]

    charcands = range(14) + random.sample([14, 15, random.choice([16, 17]),
                                           random.choice(range(18, 28)),
                                           random.choice([32, 33])], 2)
    chargraphics = {14: 0x11, 15: 0x10, 16: 0x14, 17: 0x14, 32: 0xE, 33: 0xE}
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

    esperevents = [
        "Ramuh", "Ifrit", "Shiva", "Siren", "Terrato", "Shoat", "Maduin",
        "Bismark", "Stray", "Palidor", "Tritoch", "Odin", "Raiden", "Bahamut",
        "Alexandr", "Crusader", "Ragnarok", "Kirin", "ZoneSeek", "Carbunkl",
        "Phantom", "Sraphim", "Golem", "Unicorn", "Fenrir", "Starlet",
        "Phoenix"]
    esperevents = dict([(n, i) for (i, n) in enumerate(esperevents)])
    espers = list(get_espers())
    num_espers = 3
    for i in xrange(num_espers):
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
        startsub.bytestring += [0x86, event_value]
    for i in xrange(27):  # espers
        byte, bit = i / 8, i % 8
        mem_addr = ((0x17+byte) << 3) | bit
        startsub.bytestring += [0xD6, mem_addr]
    for i in xrange(16):  # characters
        byte, bit = i / 8, i % 8
        mem_addr = ((0x1b+byte) << 3) | bit
        startsub.bytestring += [0xD6, mem_addr]
    startsub.bytestring += [0xB2, 0x09, 0x21, 0x02,  # start on airship
                            ]
    startsub.bytestring.append(0xFE)
    startsub.set_location(0xADD1E)
    startsub.write(outfile)

    startsub0 = Substitution()
    startsub0.bytestring = [0xB2, 0x1E, 0xDD, 0x00, 0xFE]
    startsub0.set_location(0xC9A4F)
    startsub0.write(outfile)

    set_airship_sub = Substitution()
    set_airship_sub.bytestring = [0xB2, 0xD6, 0x02, 0x00,
                                  0xFE]
    set_airship_sub.set_location(0xAF53A)  # need first branch for button press
    set_airship_sub.write(outfile)

    tower_msg_sub = Substitution()
    tower_msg_sub.bytestring = [0xD6, 0xE6, 0xD6, 0xE7]  # reset temp chars
    while len(tower_msg_sub.bytestring) < 12:
        tower_msg_sub.bytestring.append(0xFD)
    tower_msg_sub.set_location(0xA03A7)
    tower_msg_sub.write(outfile)

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

    pilot = random.choice([s for s in starting if s < 12])
    pilot_sub = Substitution()
    pilot_sub.bytestring = [0x3D, pilot, 0x45,
                            0x3F, pilot, 0x01]
    for i in xrange(14):
        if i == pilot:
            continue
        pilot_sub.bytestring += [0x3F, i, 0x00]
    pilot_sub.set_location(0xC2110)
    pilot_sub.write(outfile)

    if "racecave" in activated_codes:
        randomize_tower(filename=sourcefile, ancient=True, nummaps=40)
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
        if not any([m.boss_death for m in formation.present_enemies]):
            return False
        if formation.battle_event:
            return False
        if formation.get_music() == 0:
            return False
        if formation.formid in [0x1a4, 0x1d4, 0x1d5, 0x1d6, 0x1e4,
                                0x1e2, 0x1ff, 0x1bd, 0x1be]:
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
        if best_drop and (best_drop.price <= 2 or best_drop.price >= 30000):
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
    ch_bgs = range(0x31) + [0x36, 0x37]
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
            l.write_data(outfile)

    espersubs = {}
    pointer = 0xB4E56
    for esper, event_value in esperevents.items():
        byte, bit = event_value / 8, event_value % 8
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
        fset.write_data(outfile)
        timer = max([e.stats['hp'] for f in formations
                     for e in f.present_enemies])
        reverse = False
        if timer >= 32768:
            reverse = True
            timer = 65535 - timer
        timer = max(timer, 3600)
        half = None
        while half is None or random.randint(1, 5) == 5:
            half = timer / 2
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
        sub.bytestring = bytestring
        sub.write(outfile)
        return ptr + len(enemy_template)

    shops = get_shops()
    shopranks = {}
    itemshops = [s for s in shops
                 if s.shoptype_pretty in ["items", "misc"]]
    othershops = [s for s in shops if s not in itemshops]
    othershops = othershops[random.randint(0, len(othershops)/2):]
    itemshops = sorted(random.sample(itemshops, 5), key=lambda p: p.rank())
    othershops = sorted(random.sample(othershops, 7),
                        key=lambda p: p.rank())
    for i in xrange(1, 5):
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
    for i in xrange(5):
        levelmusic[i] = dungeonmusics.pop()

    locations = [l for l in get_locations() if hasattr(l, "ancient_rank")]
    locations = sorted(locations, key=lambda l: l.ancient_rank)
    restlocs = [l for l in locations if hasattr(l, "restrank")]
    ban_musics = [0, 36, 56, 57, 58, 73, 74, 75] + levelmusic.values()
    restmusics = [m for m in range(1, 85) if m not in ban_musics]
    random.shuffle(restmusics)

    optional_chars = [c for c in characters if c.id not in starting
                      and c.id in charcands]
    if "speedcave" in activated_codes:
        while len(optional_chars) < 24:
            if random.choice([True, True, False]):
                supplement = [c for c in optional_chars if c.id >= 14]
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
    num_in_party_sub.write(outfile)
    num_in_party_sub.set_location(pointer)
    num_in_party_sub.bytestring = [0xC0, 0xAE, 0x01, c1, b1, a1,
                                   0xB2, 0x80, 0xC6, 0x00,
                                   0xC0, 0xAF, 0x01, c2, b2, a2,
                                   0xB2, 0x80, 0xC6, 0x00,
                                   0xD3, 0xA3,
                                   0xD3, 0xA2,
                                   0xFE]
    num_in_party_sub.write(outfile)
    pointer += len(num_in_party_sub.bytestring)
    ally_addrs = {}
    for chosen in sorted(set(optional_chars)):
        byte, bit = chosen.slotid / 8, chosen.slotid % 8
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
                                       0x45,
                                       0xF4, 0xD0,
                                       0xFE]
                pointer = pointer + len(allysub.bytestring)
                uptr = (pointer - 1) - 0xa0000
                a, b, c = (uptr >> 16, (uptr >> 8) & 0xFF, uptr & 0xFF)
                allysub.bytestring[7:10] = [c, b, a]
                allysub.write(outfile)
                event_addr = (allysub.location - 0xa0000) & 0x3FFFF
                ally_addrs[chosen.id, party_id, npc_id] = event_addr

    npc_palettes = get_npc_palettes()
    for g in npc_palettes:
        npc_palettes[g] = [v for v in npc_palettes[g] if 0 <= v <= 5]
    for g in range(14, 63):
        if g not in npc_palettes or not npc_palettes[g]:
            npc_palettes[g] = range(6)

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
        sub.write(outfile)
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
            "graphics": 0x17, "palette": 0, "x": 55, "y": 16,
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
            shopsub.bytestring = [0x9B, shop.shopid, 0xFE]
            shopsub.write(outfile)
            pointer += len(shopsub.bytestring)
            event_addr = (shopsub.location - 0xa0000) & 0x3FFFF
        else:
            event_addr = 0x178cb
            colsub = Substitution()
            colsub.set_location(0xb78ea)
            colsub.bytestring = [0x59, 0x04, 0x5C, 0xFE]
            colsub.write(outfile)
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
                byte, bit = (chosen.slotid / 8) + 0x1b, chosen.slotid % 8
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
            if len(optional_chars) > 0 and "speedcave" in activated_codes:
                temp = optional_chars.pop()
                if chosen.id != temp.id:
                    chosen = temp
                    if chosen.id >= 14 and False:
                        byte, bit = 0, 0
                    else:
                        byte, bit = (chosen.slotid / 8) + 0x1b, chosen.slotid % 8
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
        for i in xrange(num_espers):
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
            espersub.write(outfile)
            event_addr = (espersub.location - 0xa0000) & 0x3FFFF
            event_value = esperevents[esper.name]
            byte, bit = event_value / 8, event_value % 8
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

    assert len(optional_chars) == 0

    if pointer >= 0xb5ec9:
        raise Exception("Cave events out of bounds.")

    # lower encounter rate
    dungeon_rates = [0x38, 0, 0x20, 0, 0xb0, 0, 0x00, 1,
                     0x1c, 0, 0x10, 0, 0x58, 0, 0x80, 0] + ([0]*16)
    assert len(dungeon_rates) == 32
    encrate_sub = Substitution()
    encrate_sub.set_location(0xC2BF)
    encrate_sub.bytestring = dungeon_rates
    encrate_sub.write(outfile)

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
                    half = r/2
                    quarter = half/2
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
                    formation.write_data(outfile)
            fset.write_data(outfile)

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

        l.write_data(outfile)

    if "racecave" in activated_codes:
        event_bosses = {
            1: [0xC18A4, 0xC184B],
            2: [0xC16DD, 0xC171D, 0xC1755],
            3: [0xA0F6E]}
        pass


def randomize():
    global outfile, sourcefile, flags, seed

    args = list(argv)
    if TEST_ON:
        while len(args) < 3:
            args.append(None)
        args[1] = TEST_FILE
        args[2] = TEST_SEED
    sleep(0.5)
    print 'You are using Beyond Chaos randomizer version "%s".' % VERSION
    if BETA:
        print "WARNING: This version is a beta! Things may not work correctly."

    if len(args) > 2:
        sourcefile = args[1].strip()
    else:
        sourcefile = raw_input("Please input the file name of your copy of "
                               "the FF3 US 1.0 rom:\n> ").strip()
        print

    try:
        f = open(sourcefile, 'rb')
        data = f.read()
        f.close()
    except IOError:
        response = raw_input(
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
        print "Success! Using valid rom file: %s\n" % sourcefile
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
a   Organize rages alphabetically (default)
h   Organize rages by highest level first'''

    if len(args) > 2:
        fullseed = args[2].strip()
    else:
        fullseed = raw_input("Please input a seed value (blank for a random "
                             "seed):\n> ").strip()
        print
        if '.' not in fullseed:
            print flaghelptext + "\n"
            flags = raw_input("Please input your desired flags (blank for "
                              "all of them):\n> ").strip()
            fullseed = ".%s.%s" % (flags, fullseed)
            print

    version, flags, seed = tuple(fullseed.split('.'))
    seed = seed.strip()
    if not seed:
        seed = int(time())
    else:
        seed = int(seed)
    seed = seed % (10**10)
    reseed()

    if '.' in sourcefile:
        tempname = sourcefile.rsplit('.', 1)
    else:
        tempname = [sourcefile, 'smc']
    outfile = '.'.join([tempname[0], str(seed), tempname[1]])
    outlog = '.'.join([tempname[0], str(seed), 'txt'])

    if len(data) % 0x400 == 0x200:
        print "NOTICE: Headered ROM detected. Output file will have no header."
        data = data[0x200:]
        sourcefile = '.'.join([tempname[0], "unheadered", tempname[1]])
        f = open(sourcefile, 'w+b')
        f.write(data)
        f.close()

    h = md5(data).hexdigest()
    if h != MD5HASH:
        print ("WARNING! The md5 hash of this file does not match the known "
               "hash of the english FF6 1.0 rom!")
        x = raw_input("Continue? y/n ")
        if not (x and x.lower()[0] == 'y'):
            return

    copyfile(sourcefile, outfile)

    if version and version != VERSION:
        print ("WARNING! Version mismatch! "
               "This seed will not produce the expected result!")
    s = "Using seed: %s.%s.%s" % (VERSION, flags, seed)
    print s
    log(s, section=None)
    log("This is a game guide generated for the Beyond Chaos FF6 randomizer.",
        section=None)
    log("For more information, visit https://github.com/abyssonym/beyondchaos",
        section=None)

    commands = commands_from_table(COMMAND_TABLE)
    commands = dict([(c.name, c) for c in commands])

    characters = get_characters()

    flags = flags.lower()

    secret_codes['airship'] = "AIRSHIP MODE"
    secret_codes['cutscenes'] = "CUTSCENE SKIPS"
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
    secret_codes['ancientcave'] = "CHAOS TOWER MODE"
    secret_codes['speedcave'] = "FAST CHAOS TOWER MODE"
    secret_codes['racecave'] = "EXTRA FAST CHAOS TOWER MODE"
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

    print s.strip()

    if 'cutscenes' in activated_codes:
        print "NOTICE: You have selected CUTSCENE SKIPS."
        print "This feature has proven to be unstable with strange effects."
        x = raw_input("Would you like to use cutscene skips? (y/n) ")
        if x and x.lower()[0] == 'y':
            manage_skips()
        else:
            print "Cutscenes will NOT be skipped."
        print

    print (
        "\nNow beginning randomization.\n"
        "The randomization is very thorough, so it may take some time.\n"
        'Please be patient and wait for "randomization successful" to appear.')

    event_freespaces = [FreeBlock(0xCFE2A, 0xCFE2a + 470)]
    if 'airship' in activated_codes:
        event_freespaces = activate_airship_mode(event_freespaces)

    if not flags.strip():
        flags = 'abcdefghijklmnopqrstuvwxyz'

    if 'w' in flags and 'o' not in flags:
        flags += 'o'

    if 'o' in flags and 'suplexwrecks' not in activated_codes:
        manage_commands(commands)
    reseed()

    spells = get_ranked_spells(sourcefile)
    if 'w' in flags and 'suplexwrecks' not in activated_codes:
        _, freespaces = manage_commands_new(commands)
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
            dirk.write_stats(outfile)
            dummy_item(dirk)
            assert not dummy_item(dirk)
    reseed()

    items = get_ranked_items()
    if 'i' in flags:
        manage_items(items, changed_commands=changed_commands)
    reseed()

    if 'm' in flags:
        aispaces = manage_final_boss(aispaces)
        monsters = manage_monsters()
    reseed()

    if 'm' in flags or 'o' in flags or 'w' in flags:
        for m in monsters:
            m.screw_tutorial_bosses()
            m.write_stats(outfile)

    if 'c' in flags and 'm' in flags:
        mgs = manage_monster_appearance(monsters,
                                        preserve_graphics=preserve_graphics)
    reseed()

    if 'c' in flags or 's' in flags or (
            set(['partyparty', 'bravenudeworld', 'suplexwrecks']) & activated_codes):
        manage_character_appearance(preserve_graphics=preserve_graphics)
    reseed()

    if 'q' in flags:
        # do this after items
        manage_equipment(items)
    reseed()

    esperrage_spaces = [FreeBlock(0x26469, 0x26469 + 919)]
    if 'e' in flags:
        manage_espers(esperrage_spaces)
    reseed()

    if flags:
        by_level = 'h' in flags and 'a' not in flags
        esperrage_spaces = manage_reorder_rages(esperrage_spaces,
                                                by_level=by_level)

        titlesub = Substitution()
        titlesub.bytestring = [0xFD] * 4
        titlesub.set_location(0xA5E8E)
        titlesub.write(outfile)

        manage_opening()
        manage_ending()
        manage_auction_house()

        savetutorial_sub = Substitution()
        savetutorial_sub.set_location(0xC9AF1)
        savetutorial_sub.bytestring = [0xD2, 0x33, 0xEA, 0xEA, 0xEA, 0xEA]
        savetutorial_sub.write(outfile)

        savecheck_sub = Substitution()
        savecheck_sub.bytestring = [0xEA, 0xEA]
        savecheck_sub.set_location(0x319f2)
        savecheck_sub.write(outfile)

    if 'o' in flags and 'suplexwrecks' not in activated_codes:
        # do this after swapping beserk
        manage_natural_magic()
    reseed()

    if 'u' in flags:
        umaro_risk = manage_umaro(commands)
        reset_rage_blizzard(items, umaro_risk, outfile)
    reseed()

    if 'o' in flags and 'suplexwrecks' not in activated_codes:
        # do this after swapping beserk
        manage_tempchar_commands()
    reseed()

    if 'q' in flags:
        # do this after swapping beserk
        from itemrandomizer import set_item_changed_commands
        set_item_changed_commands(changed_commands)
        loglist = reset_special_relics(items, characters, outfile)
        for name, before, after in loglist:
            beforename = [c for c in commands.values() if c.id == before][0].name
            aftername = [c for c in commands.values() if c.id == after][0].name
            logstr = "{0:13} {1:7} -> {2:7}".format(
                name + ":", beforename.lower(), aftername.lower())
            log(logstr, section="command changes")
        reset_cursed_shield(outfile)

        for c in characters:
            c.mutate_stats(outfile)
    else:
        for c in characters:
            c.mutate_stats(outfile, read_only=True)
    reseed()

    if 'f' in flags:
        formations = get_formations()
        fsets = get_fsets()
        manage_formations(formations, fsets)
        for fset in fsets:
            fset.write_data(outfile)

    if 'f' in flags or 'ancientcave' in activated_codes:
        manage_dragons()
    reseed()

    if 'd' in flags and 'ancientcave' not in activated_codes:
        # do this before treasure
        manage_tower()
    reseed()

    if 'f' in flags or 't' in flags:
        assign_unused_enemy_formations()

    if 'f' in flags:
        manage_formations_hidden(formations, freespaces=aispaces)
        for m in get_monsters():
            m.write_stats(outfile)
    reseed()

    for f in get_formations():
        f.write_data(outfile)

    if 't' in flags:
        # do this after hidden formations
        manage_treasure(monsters, shops=True)
        if 'ancientcave' not in activated_codes:
            manage_chests()
            for fs in fsets:
                # write new formation sets for MiaBs
                fs.write_data(outfile)

    if 'c' in flags:
        # do this before ancient cave
        # could probably do it after if I wasn't lazy
        manage_colorize_dungeons()

    if 'ancientcave' in activated_codes:
        manage_ancient()
    reseed()

    if 'o' in flags or 'w' in flags or 'm' in flags:
        manage_magitek(spells)
    reseed()

    if 'l' in flags:
        if 0x0A not in changed_commands:
            manage_blitz()
    reseed()

    if 'n' in flags:
        for i in range(8):
            w = WindowBlock(i)
            w.read_data(sourcefile)
            w.mutate()
            w.write_data(outfile)
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

    if 'strangejourney' in activated_codes:
        create_dimensional_vortex()
    reseed()

    # ----- NO MORE RANDOMNESS PAST THIS LINE -----
    write_all_locations_misc()
    for fs in fsets:
        fs.write_data(outfile)

    if 'u' in flags or 'q' in flags:
        manage_equip_umaro(event_freespaces)

    if 'easymodo' in activated_codes or 'llg' in activated_codes:
        for m in monsters:
            if 'easymodo' in activated_codes:
                m.stats['hp'] = 1
            if 'llg' in activated_codes:
                m.stats['xp'] = 0
            m.write_stats(outfile)

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
                i.write_stats(outfile)
        for e in espers:
            e.write_data(outfile)

    if 'canttouchthis' in activated_codes:
        for c in characters:
            c.become_invincible(outfile)

    if 'equipanything' in activated_codes:
        manage_equip_anything()

    if 'playsitself' in activated_codes:
        manage_full_umaro()
        for c in commands.values():
            if c.id not in [0x01, 0x08, 0x0E, 0x0F, 0x15, 0x19]:
                c.allow_while_berserk(outfile)
        whelkhead = get_monster(0x134)
        whelkhead.stats['hp'] = 1
        whelkhead.write_stats(outfile)
        whelkshell = get_monster(0x100)
        whelkshell.stats['hp'] = 1
        whelkshell.write_stats(outfile)

    for item in get_ranked_items(allow_banned=True):
        if item.banned:
            assert not dummy_item(item)

    rewrite_title(text="FF6 BC %s" % seed)
    rewrite_checksum()

    print "\nWriting log..."
    for c in sorted(characters, key=lambda c: c.id):
        c.associate_command_objects(commands.values())
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

    print "Randomization successful. Output filename: %s\n" % outfile

    if 'bingoboingo' in activated_codes:
        manage_bingo()


if __name__ == "__main__":
    args = list(argv)
    if len(argv) > 3 and argv[3].strip().lower() == "test" or TEST_ON:
        randomize()
        exit()
    try:
        randomize()
        raw_input("Press enter to close this program. ")
    except Exception, e:
        print "ERROR: %s" % e
        if outfile is not None:
            print "Please try again with a different seed."
            raw_input("Press enter to delete %s and quit. " % outfile)
            os.remove(outfile)
        else:
            raw_input("Press enter to quit. ")
