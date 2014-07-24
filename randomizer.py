import random
from time import time
from sys import argv
from os import system
from utils import hex2int, int2bytes
from skillrandomizer import SpellBlock, CommandBlock
from monsterrandomizer import MonsterBlock, get_ranked_monsters
from itemrandomizer import ItemBlock, reset_equippable, get_ranked_items
from chestrandomizer import ChestBlock, shuffle_locations, shuffle_monster_boxes

seed = time()
random.seed(seed)
print seed

NEVER_REPLACE = ["fight", "item", "magic", "row", "def", "magitek", "lore", "jump", "mimic", "xmagic", "summon"]
# note: x-magic targets random party member
# replacing lore screws up enemy skills
# replacing jump makes the character never come back down
# replacing mimic screws up enemy skills too
ALWAYS_REPLACE = ["leap", "possess", "revert", "health", "shock"]


class Substitution(object):
    location = None

    @property
    def size(self):
        return len(self.bytestring)

    def set_location(self, location):
        self.location = location

    def write(self, filename):
        f = open(filename, 'r+b')
        bs = "".join(map(chr, self.bytestring))
        f.seek(self.location)
        f.write(bs)
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
        super(AutoRecruitGauSub, self).write(filename)


class SpellSub(Substitution):
    def __init__(self, spellid):
        self.spellid = spellid
        self.bytestring = [0xA9, self.spellid, 0x85, 0xB6, 0xA9,
                           0x02, 0x85, 0xB5, 0x4C, 0x5F, 0x17]


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


equip_offsets = {"weapon": 15,
                 "shield": 16,
                 "helm": 17,
                 "armor": 18,
                 "relic1": 19,
                 "relic2": 20}


class CharacterBlock:
    def __init__(self, address, name):
        self.address = hex2int(address)
        self.name = name.lower()
        self.battle_commands = [None, None, None, None]
        self.id = None

    def set_battle_command(self, slot, command=None, command_id=None):
        if command:
            command_id = command.id
        self.battle_commands[slot] = command_id

    def write_battle_commands(self, filename):
        f = open(filename, 'r+b')
        for i, command in enumerate(self.battle_commands):
            if command is None:
                continue
            f.seek(self.address + 2 + i)
            f.write(chr(command))
        f.close()

    def write_default_equipment(self, filename, equipid, equiptype):
        f = open(filename, 'r+b')
        f.seek(self.address + equip_offsets[equiptype])
        f.write(chr(equipid))
        f.close()

    def set_id(self, i):
        self.id = i


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


def monsters_from_table(tablefile):
    monsters = []
    for i, line in enumerate(open(tablefile)):
        line = line.strip()
        if line[0] == '#':
            continue

        while '  ' in line:
            line = line.replace('  ', ' ')
        c = MonsterBlock(*line.split(','))
        c.set_id(i)
        monsters.append(c)
    return monsters


def characters_from_table(tablefile):
    characters = []
    for i, line in enumerate(open(tablefile)):
        line = line.strip()
        if line[0] == '#':
            continue

        while '  ' in line:
            line = line.replace('  ', ' ')
        c = CharacterBlock(*line.split(','))
        c.set_id(i)
        characters.append(c)
    return characters


def items_from_table(tablefile):
    items = []
    for i, line in enumerate(open(tablefile)):
        line = line.strip()
        if line[0] == '#':
            continue

        while '  ' in line:
            line = line.replace('  ', ' ')
        c = ItemBlock(*line.split(','))
        items.append(c)
    return items


def chests_from_table(tablefile):
    items = []
    for i, line in enumerate(open(tablefile)):
        line = line.strip()
        if line[0] == '#':
            continue

        while '  ' in line:
            line = line.replace('  ', ' ')
        c = ChestBlock(*line.split(','))
        items.append(c)
    return items


def randomize_colosseum(filename, pointer):
    item_objs = get_ranked_items(filename)
    monster_objs = get_ranked_monsters(filename, bosses=False)
    items = [i.itemid for i in item_objs]
    monsters = [m.id for m in monster_objs]
    f = open(filename, 'r+b')
    for i in range(0xFF):
        #if i == 0x29:
        #    continue  # striker

        index = items.index(i)
        trade = index
        while index == trade:
            trade = index
            while random.randint(1, 3) < 3:
                trade += random.randint(-3, 3)
                trade = max(0, min(trade, len(items)-1))

        opponent = trade
        while random.randint(1, 3) < 3:
            opponent += random.randint(-1, 1)
            opponent = max(0, min(opponent, len(monsters)-1))

        trade = items[trade]
        opponent = monsters[opponent]
        wager_obj = [j for j in item_objs if j.itemid == i][0]
        opponent_obj = [m for m in monster_objs if m.id == opponent][0]
        win_obj = [j for j in item_objs if j.itemid == trade][0]
        print wager_obj.name, opponent_obj.name, win_obj.name
        f.seek(pointer + (i*4))
        f.write(chr(opponent))
        f.seek(pointer + (i*4) + 2)
        f.write(chr(trade))
        if abs(wager_obj.rank() - win_obj.rank()) >= 5000 and random.randint(1, 2) == 2:
            f.write(chr(0xFF))
        else:
            f.write(chr(0x00))
    f.close()


def randomize_slots(filename, pointer):
    from skillrandomizer import get_ranked_spells
    spells = get_ranked_spells(filename)
    spells = [s.spellid for s in spells if s.target_enemy_default]
    f = open(filename, 'r+b')
    for i in xrange(7):
        if i == 2:
            continue
        else:
            if i in [1, 2, 4]:
                index = random.randint(len(spells)/2, len(spells)-1)
            else:
                index = random.randint(0, len(spells)-1)
            value = spells[index]
        f.seek(pointer+i)
        f.write(chr(value))
    f.close()

if __name__ == "__main__":
    sourcefile = argv[1]
    outfile = sourcefile.rsplit('.', 1)
    outfile = '.'.join([outfile[0], "rand", outfile[1]])
    system("cp %s %s" % (sourcefile, outfile))

    alrs = AutoLearnRageSub(require_gau=False)
    alrs.set_location(0x23b73)
    alrs.write(outfile)

    args = AutoRecruitGauSub()
    args.set_location(0xcfe1a)
    args.write(outfile)

    autosprint = Substitution()
    autosprint.set_location(0x4E2D)
    autosprint.bytestring = [0x80, 0x00]
    autosprint.write(outfile)

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
    learn_swdtech_sub.bytestring = [0xEA] * 2
    learn_swdtech_sub.set_location(0x261C9)
    learn_swdtech_sub.write(outfile)

    learn_blitz_sub = Substitution()
    learn_blitz_sub.bytestring = [0xEA] * 2
    learn_blitz_sub.set_location(0x261E5)
    learn_blitz_sub.write(outfile)

    #NOTE: Break's Gau's rages that cast magic
    #m_m_magic_sub = Substitution()
    #m_m_magic_sub.bytestring = [0x80, 0x19]
    #m_m_magic_sub.set_location(0x2174A)
    #m_m_magic_sub.write(outfile)

    recruit_gau_sub = Substitution()
    recruit_gau_sub.bytestring = [0x89, 0xFF]
    recruit_gau_sub.set_location(0x24856)
    recruit_gau_sub.write(outfile)

    eems = EnableEsperMagicSub()
    eems.set_location(0x3F091)
    eems.write(outfile)

    flashback_skip_sub = Substitution()
    flashback_skip_sub.bytestring = [0xB2, 0xB8, 0xA5, 0x00, 0xFE]
    flashback_skip_sub.set_location(0xAC582)
    flashback_skip_sub.write(outfile)

    # Prevent Runic, SwdTech, and Capture from being disabled/altered
    protect_battle_commands_sub = Substitution()
    protect_battle_commands_sub.bytestring = [0x03, 0xFF, 0xFF, 0x0C,
                                              0x17, 0x02, 0xFF, 0x00]
    protect_battle_commands_sub.set_location(0x252E9)
    protect_battle_commands_sub.write(outfile)

    commands = commands_from_table('tables/commandcodes.txt')
    commands = dict([(c.name, c) for c in commands])

    freespaces = []
    freespaces.append(FreeBlock(0x2A65A, 0x2A800))
    freespaces.append(FreeBlock(0x2FAAC, 0x2FC6D))

    used = []
    all_spells = [SpellBlock(i, sourcefile) for i in xrange(0xFF)]
    for c in commands.values():
        if c.name in NEVER_REPLACE:
            continue

        if c.name not in ALWAYS_REPLACE:
            if random.randint(1, 100) > 75:
                continue
            if c.target == "self" and random.randint(1, 100) > 50:
                continue

        POWER_LEVEL = 100
        MULLIGAN_LEVEL = 15
        while True:
            power = POWER_LEVEL / 2
            while True:
                power += random.randint(0, POWER_LEVEL)
                if random.choice([True, False]):
                    break

            def spell_is_valid(s):
                if not s.valid:
                    return False
                if s.spellid in used:
                    return False
                if not c.restriction(s):
                    return False
                return s.rank() <= power

            valid_spells = filter(spell_is_valid, all_spells)
            if not valid_spells:
                continue

            sb = random.choice(valid_spells)
            used.append(sb.spellid)
            c.set_retarget(sb, outfile)
            s = SpellSub(spellid=sb.spellid)
            print power, sb.rank(), sb.name
            break

        myfs = None
        for fs in freespaces:
            if fs.size > s.size:
                myfs = fs
                break

        freespaces.remove(myfs)
        s.set_location(myfs.start)
        s.write(outfile)
        c.setpointer(s.location, outfile)
        fss = myfs.unfree(s.location, s.size)
        freespaces.extend(fss)

        c.newname(sb.name, outfile)
        c.unsetmenu(outfile)

    characters = characters_from_table('tables/charcodes.txt')
    valid = set(list(commands))
    valid = list(valid - set(["row", "def"]))

    def populate_unused():
        unused_commands = set(commands.values())
        invalid_commands = set([c for c in commands.values() if c.name in
                                ["fight", "item", "magic", "xmagic",
                                 "def", "row", "summon"]])
        unused_commands = list(unused_commands - invalid_commands)
        return unused_commands

    unused = populate_unused()
    xmagic_taken = False
    random.shuffle(characters)
    for c in characters:
        #print c.name,
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
            for i, command in enumerate(reversed(using)):
                #print command.name,
                c.set_battle_command(i+1, command=command)
            if c.id == 11:
                #Fixing Gau
                c.set_battle_command(0, commands["fight"])
        else:
            c.set_battle_command(1, command_id=0xFF)
            c.set_battle_command(2, command_id=0xFF)
        c.write_battle_commands(outfile)
        #print

    monsters = monsters_from_table('tables/enemycodes.txt')
    for m in monsters:
        m.read_stats(sourcefile)
        m.screw_vargas()
        m.mutate()
        m.write_stats(outfile)

    items = get_ranked_items(sourcefile)
    reset_equippable(items)
    for i in items:
        i.mutate()
        i.unrestrict()
        i.write_stats(outfile)

    for c in characters:
        if c.id > 13:
            continue

        equippable_items = filter(lambda i: i.equippable & (1 << c.id), items)
        equippable_weapons = [i for i in equippable_items if i.is_weapon]
        equippable_shields = [i for i in equippable_items if i.is_shield]
        equippable_helms = [i for i in equippable_items if i.is_helm]
        equippable_body_armors = [i for i in equippable_items if i.is_body_armor]

        weakest_weapon = min(equippable_weapons, key=lambda i: i.rank()).itemid if equippable_weapons else 0xFF
        weakest_shield = min(equippable_shields, key=lambda i: i.rank()).itemid if equippable_shields else 0xFF
        weakest_helm = min(equippable_helms, key=lambda i: i.rank()).itemid if equippable_helms else 0xFF
        weakest_body_armor = min(equippable_body_armors, key=lambda i: i.rank()).itemid if equippable_body_armors else 0xFF

        c.write_default_equipment(outfile, weakest_weapon, "weapon")
        c.write_default_equipment(outfile, weakest_shield, "shield")
        c.write_default_equipment(outfile, weakest_helm, "helm")
        c.write_default_equipment(outfile, weakest_body_armor, "armor")

    chests = chests_from_table("tables/chestcodes.txt")
    for c in chests:
        c.read_data(sourcefile)
        c.mutate_contents()

    shuffle_locations(chests)
    shuffle_monster_boxes(chests)

    for c in chests:
        c.write_data(outfile)

    randomize_colosseum(outfile, 0x1fb600)
    randomize_slots(outfile, 0x24E4A)
