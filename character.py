from itemrandomizer import get_ranked_items
from utils import CHAR_TABLE, hex2int, utilrandom as random


equip_offsets = {"weapon": 15,
                 "shield": 16,
                 "helm": 17,
                 "armor": 18,
                 "relic1": 19,
                 "relic2": 20}

CHARSTATNAMES = ["hp", "mp", "vigor", "speed", "stamina", "m.power",
                 "attack", "defense", "m.def", "evade", "mblock"]


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
        self.natural_magic = []
        self.palette = None
        self.wor_location = None
        self.command_objs = []
        self.stats = {}

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
        if self.wor_location is not None:
            s += "World of Ruin location: %s\n" % self.wor_location
        if self.natural_magic:
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

    def mutate_stats(self, fout, start_in_wor, read_only=False):

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
            run_chance = random.randint(0, 99)
            for i, prob in enumerate(run_map[run]):
                run_chance -= prob
                if prob < 0:
                    run = i
                    break

            # Don't randomize level average values if worringtriad is active
            # Also don't randomize Terra's level because it gets added for
            # every loop through the title screen, apparently.
            if not start_in_wor and self.id != 0:
                level_chance = random.randint(0, 99)
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
