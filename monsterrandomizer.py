import copy

from utils import (write_multi, read_multi, ENEMY_TABLE,
                   name_to_bytes, get_palette_transformer, mutate_index,
                   make_table, utilrandom as random)
from skillrandomizer import get_spell, get_ranked_spells
from itemrandomizer import get_ranked_items, get_item
from namerandomizer import generate_attack, generate_name


# Dummied Umaro, Dummied Kefka, Colossus, CzarDragon, ???, ???
REPLACE_ENEMIES = [0x10f, 0x136, 0x137]

stat_order = ['speed', 'attack', 'hit%', 'evade%', 'mblock%',
              'def', 'mdef', 'mpow']

shortnames = {'level': 'lv',
              'attack': 'atk',
              'speed': 'spd',
              'hit%': 'hit',
              'evade%': 'evd',
              'mblock%': 'mblk'}

metamorphs = None
all_spells = None
HIGHEST_LEVEL = 77
xps = []
gps = []
AICODES = {0xF0: 3, 0xF1: 1, 0xF2: 3, 0xF3: 2,
           0xF4: 3, 0xF5: 3, 0xF6: 3, 0xF7: 1,
           0xF8: 2, 0xF9: 3, 0xFA: 3, 0xFB: 2,
           0xFC: 3, 0xFD: 0, 0xFE: 0, 0xFF: 0
           }
monsterdict = {}

globalweights, avgs = None, {}

statusdict = {
    "blind": (0, 0x01),
    "zombie": (0, 0x02),
    "poison": (0, 0x04),
    "magitek": (0, 0x08),
    "vanish": (0, 0x10),
    "imp": (0, 0x20),
    "petrify": (0, 0x40),
    "death": (0, 0x80),
    "condemned": (1, 0x01),
    "near death": (1, 0x02),
    "image": (1, 0x04),
    "mute": (1, 0x08),
    "berserk": (1, 0x10),
    "confuse": (1, 0x20),
    "seizure": (1, 0x40),
    "sleep": (1, 0x80),
    "float": (2, 0x01),
    "regen": (2, 0x02),
    "slow": (2, 0x04),
    "haste": (2, 0x08),
    "stop": (2, 0x10),
    "shell": (2, 0x20),
    "protect": (2, 0x40),
    "reflect": (2, 0x80),
    "cover": (3, 0x01),
    "runic": (3, 0x02),
    "reraise": (3, 0x04),
    "morph": (3, 0x08),
    "casting": (3, 0x10),
    "disappear": (3, 0x20),
    "interceptor": (3, 0x40),
    "floating": (3, 0x80)}
reverse_statusdict = {value: key for (key, value) in list(statusdict.items())}

early_bosses = [
    308, # head
    333, # ipooh
    341, # rizopas
    262, # ghosttrain
    300  # ultros 1
]

elemlist = ["fire", "ice", "bolt", "bio", "wind", "pearl", "earth", "water"]

ranked = ["casting", "near death", "floating", "regen", "poison", "blind",
          "shell", "protect", "vanish", "image", "hp drain", "haste",
          "reflect", "mp drain", "seizure",
          "condemned", "slow", "mute", "imp", "berserk", "reraise",
          "sleep", "confuse", "stop", "petrify", "zombie",
          "morph", "frozen", "death", "interceptor", "magitek",
          "rage", "dance", "disappear"]
specialdict = [k for (k, v) in sorted(statusdict.items(),
                                      key=lambda k_v: k_v[1])]
specialdict = {k: i for (i, k) in enumerate(specialdict)}
specialdict["rage"] = 0x18
specialdict["dance"] = 0x10
del specialdict["float"]
del specialdict["cover"]
specialdict["frozen"] = 0x19
specialdict["hp drain"] = 0x30
specialdict["mp drain"] = 0x31
reverse_specialdict = {v: k for (k, v) in specialdict.items()}
ranked = [specialdict[key] for key in ranked]


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


def read_ai_table(table):
    aiscripts = {}
    name = None
    for line in open(table):
        line = line.strip()
        if not line or line[0] == '#':
            continue
        elif line[0] == '!':
            name = line.strip('!').strip()
            aiscripts[name] = []
        else:
            line = line.split()
            line = [int(i, 0x10) for i in line]
            aiscripts[name].append(line)
    for key, aiscript in list(aiscripts.items()):
        aiscript = [bytearray(action) for action in aiscript]
        aiscripts[key] = aiscript
    return aiscripts


def get_item_normal():
    items = get_ranked_items()
    base = ((len(items)-1) // 2)
    index = random.randint(0, base) + random.randint(0, base)
    if len(items) > (base * 2) + 1:
        index += random.randint(0, 1)
    ranked_items = sorted(items, key=lambda i: i.rank())
    item = ranked_items[index]
    return item


class MonsterBlock:
    def __init__(self, name, monster_id):
        self.name = name
        self.graphicname = self.name
        self.pointer = 0xF0000 + (0x20 * monster_id)
        self.itemptr = 0xF3000 + (0x4 * monster_id)
        self.controlptr = 0xF3D00 + (0x4 * monster_id)
        self.sketchptr = 0xF4300 + (0x2 * monster_id)
        self.rageptr = 0xF4600 + (0x2 * monster_id)
        self.aiptr = 0xF8400 + (0x2 * monster_id)
        self.stats = {}
        self.moulds = set([])
        self.width, self.height = None, None
        self.miny, self.maxy = None, None
        self.aiscript = None
        self.ambusher = False
        self.set_id(monster_id)
        self.attackname = "Special"
        self.graphics = None
        self.morph = 0
        self.misc1 = 0
        self.misc2 = 0
        self.immunities = []
        self.absorb = 0
        self.null = 0
        self.weakness = 0
        self.attackanimation = 0
        self.statuses = []
        self.special = 0
        self.oldlevel = 0
        self.items = []
        self.original_drops = []

    def determine_location(self):
        from formationrandomizer import get_formations, get_fsets
        from locationrandomizer import get_locations, get_zones
        formations = {f for f in get_formations()
                      if self in f.present_enemies}
        fsets = [fs for fs in get_fsets() if len(fs.formations) == 4]
        fsets = [fs for fs in fsets if formations & set(fs.formations)]
        if not fsets:
            return ""

        def score_location(location):
            from locationrandomizer import Zone
            score = 0
            fsets = location.fsets
            for fset in fsets:
                for formation in fset.formations[:3]:
                    if self in formation.present_enemies:
                        if isinstance(location, Zone):
                            score += 5
                            break
                        else:
                            score += 5 * formation.present_enemies.count(self)
                if score and isinstance(location, Zone):
                    continue
                formation = fset.formations[3]
                if self in formation.present_enemies:
                    if isinstance(location, Zone):
                        score += 1
                        continue
                    else:
                        score += 1 * formation.present_enemies.count(self)
            score = score / float(len(fsets))
            return score

        locations = get_locations()
        fsets = set(fsets)
        locations = [l for l in get_locations()
                     if l.attacks and l.setid != 0 and set(l.fsets) & fsets]

        areas = []
        if locations:
            locations = sorted(locations, key=score_location, reverse=True)
            for l in locations:
                try:
                    if l.area_name not in areas:
                        areas.append(l.area_name)
                except Exception:
                    continue
        zones = [z for z in get_zones()[:0x80]
                 if z.valid and set(z.fsets) & fsets]

        if zones:
            zones = sorted(zones, key=score_location, reverse=True)
            for z in zones:
                areas.append(z.get_area_name())

        areas = [a for a in areas if a.lower() != "bad"]
        if len(areas) > 1 and areas[0] == "Final Dungeon":
            areas.remove("Final Dungeon")
            areas.insert(1, "Final Dungeon")

        return ", ".join(areas[:2])

    @property
    def special_effect_str(self):
        special = self.special
        if self.physspecial:
            power = ((self.special & 0x2F) - 0x20) + 2
            if power % 2:
                power = (power // 2) + 1
            else:
                power = str(power // 2) + ".5"
            s = "attack x%s" % power
        elif special & 0x3F > 0x31:
            s = "reflect break?"
        else:
            s = ""
            if not self.special & 0x40:
                s += "damage + "
            s += reverse_specialdict[special & 0x3F]
        if self.special & 0x80:
            s += " (unblockable)"
        return s

    @property
    def statuses_str(self):
        full24 = bin(self.immunities[0] | (self.immunities[1] << 8) |
                     (self.immunities[2] << 16))
        full24 = full24[2:]
        full24 = "{0:0>24}".format(full24)
        if full24.count("1") > full24.count("0"):
            # show vulnerabilities
            s = "VULNERABLE: "
            on_equals = False
        else:
            # show immunities
            s = "IMMUNE: "
            on_equals = True
        statuses = []
        for index, byte in enumerate(self.immunities):
            for i in range(8):
                bit = 1 << i
                if bool(byte & bit) == on_equals:
                    statcode = (index, bit)
                    statuses.append(reverse_statusdict[statcode])
        if not statuses:
            statuses = ["Nothing"]
        s += ", ".join(sorted(statuses)) + "\n"
        statuses = []
        for index, byte in enumerate(self.statuses):
            for i in range(8):
                bit = 1 << i
                if bool(byte & bit) is True:
                    statcode = (index, bit)
                    statuses.append(reverse_statusdict[statcode])
        if statuses:
            s += "AUTO: "
            s += ", ".join(sorted(statuses))
        return s.strip()

    @property
    def elements_str(self):
        nullify = self.absorb | self.null
        weak = self.weakness
        s = ""
        elements = []
        for i in range(8):
            if nullify & (1 << i):
                elements.append(elemlist[i])
        if elements:
            s += "NULLIFY: "
            s += ", ".join(elements)
        elements = []
        for i in range(8):
            if nullify & (1 << i):
                continue
            if weak & (1 << i):
                elements.append(elemlist[i])
        if elements:
            if s:
                s += ";  "
            s += "WEAK: "
            s += ", ".join(elements)
        return s.strip()

    def get_description(self, changed_commands=None):
        if changed_commands is None:
            changed_commands = []
        s = ("~" * 40) + "\n"
        s += self.display_name + " (Level %s)" % self.stats['level'] + "\n"

        def make_column(statnames):
            rows = []
            newnames = [shortnames[name] if name in shortnames else name
                        for name in statnames]
            namewidth = max(len(name) for name in newnames) + 1

            def get_shortname(name):
                return shortnames.get(name, name)

            values = {}
            for name in statnames:
                newname = get_shortname(name)
                value = self.stats[name]
                values[newname] = value

            valuewidth = max(len(str(v)) for v in values.values())
            substr = "{0:%s} {1:%s}" % (namewidth, valuewidth)
            for name in statnames:
                name = get_shortname(name)
                value = values[name]
                rows.append(substr.format(
                    name.upper() + ":", value))

            width = max(len(row) for row in rows)
            for i, row in enumerate(rows):
                while len(row) < width:
                    row += " "
                rows[i] = row
            return rows

        cols = []
        cols.append(make_column(['hp', 'mp', 'xp', 'gp']))
        cols.append(make_column(['attack', 'def', 'mpow', 'mdef']))
        cols.append(make_column(['speed', 'hit%', 'evade%', 'mblock%']))
        s += make_table(cols) + "\n"
        elements_str = self.elements_str
        if elements_str:
            s += elements_str + "\n"
        s += self.statuses_str + "\n"

        others = {"humanoid": self.humanoid,
                  "undead": self.undead,
                  "ambusher": self.ambusher,
                  "can't escape": self.cantrun,
                  "difficult to run": self.hardrun,
                  "dies at MP zero": self.mpdeath}
        if any(others.values()):
            others = sorted([key for key in others if others[key]])
            s += "OTHER: " + ", ".join(others) + "\n"

        s += 'SPECIAL "%s": %s\n' % (self.attackname,
                                     self.special_effect_str)

        skills = self.get_skillset(ids_only=False)
        skills = [z for z in skills
                  if z.spellid not in [0xEE, 0xEF, 0xFE, 0xFF]]
        if skills:
            names = sorted([z.name for z in skills])
            s += "SKILLS: %s\n" % ", ".join(names)

        if self.rages and 0x10 not in changed_commands:
            rages = [get_spell(r).name for r in self.rages]
            rages = [r if r != "Special" else self.attackname for r in rages]
            s += "RAGE: %s\n" % ", ".join(rages)

        lores = self.get_lores()
        if lores and 0x0C not in changed_commands:
            s += "LORE: %s\n" % ", ".join([l.name for l in lores])

        if not self.is_boss and 0x0E not in changed_commands:
            controls = [get_spell(c).name for c in self.controls if c != 0xFF]
            controls = [r if r != "Special" else self.attackname for r in controls]
            s += "CONTROL: %s\n" % ", ".join(sorted(controls))

        if 0x0D not in changed_commands:
            sketches = [get_spell(c).name for c in self.sketches]
            sketches = [r if r != "Special" else self.attackname for r in sketches]
            s += "SKETCH: %s\n" % ", ".join(sketches)

        steals = [i.name for i in self.steals if i]
        drops = [i.name for i in self.drops if i]
        s += ("STEAL: %s" % ", ".join(steals)).strip() + "\n"
        s += ("DROPS: %s" % ", ".join(drops)).strip() + "\n"

        if not self.cantmorph:
            s += "MORPH (%s%%): %s\n" % (self.morphrate, ", ".join(
                sorted([i.name for i in self.get_morph_items()])))
        s += ("LOCATION: %s" % self.display_location).strip() + "\n"

        return s.strip()

    @property
    def display_location(self):
        location = self.determine_location()
        if not location.strip():
            if hasattr(self, "auxloc"):
                location = self.auxloc
            elif not self.is_boss:
                location = "Missing %x" % self.id
        return location

    @property
    def display_name(self):
        if hasattr(self, "changed_name"):
            return self.changed_name.strip('_')
        return self.name.strip('_')

    @property
    def inescapable(self):
        return self.misc2 & 0x08

    @property
    def steals(self):
        steals = self.items[:2]
        return [get_item(i) for i in steals]

    @property
    def drops(self):
        drops = self.items[2:]
        return [get_item(i) for i in drops]

    @property
    def is_boss(self):
        return self.pointer > 0xF1FC0

    @property
    def boss_death(self):
        return (bytearray([0xF5, 0x0C, 0x01, 0xFF]) in self.aiscript or
                bytearray([0xF5, 0x0C, 0x01, 0x00]) in self.aiscript)

    @property
    def battle_event(self):
        return 0xf7 in [s[0] for s in self.aiscript]

    @property
    def pretty_aiscript(self):
        hexify = lambda c: "%x" % ord(c)
        output = ""
        for action in self.aiscript:
            output += " ".join(map(hexify, action)) + "\n"
        return output.strip()

    @property
    def throws_item(self):
        for action in self.aiscript:
            if ord(action[0]) == 0xF6 and ord(action[1]) != 0x00:
                return True
        return False

    def set_id(self, i):
        self.id = i
        self.specialeffectpointer = 0xF37C0 + self.id
        monsterdict[self.id] = self

    def update_size(self, width, height):
        if not self.width or not self.height:
            self.width, self.height = width, height
        else:
            self.width, self.height = min(self.width, width), min(self.height, height)

    def update_pos(self, x, y):
        if not self.miny or not self.maxy:
            self.miny, self.maxy = y, y
        self.miny = min(self.miny, y)
        self.maxy = max(self.miny, y)

    def add_mould(self, mould):
        self.moulds.add(mould)

    def set_graphics(self, pointer=None, graphics=None):
        if graphics:
            self.graphics = graphics
        elif pointer:
            self.graphics = MonsterGraphicBlock(pointer, self.name)

    def choose_graphics(self, candidates):
        #candidates = [c for c in candidates if c.moulds & self.moulds]
        candidates = [c for c in candidates if c.graphics.large == self.graphics.large]
        candidates = [c for c in candidates if c.miny and c.maxy]
        candidates = [c for c in candidates if
                      c.width == self.width and c.height == self.height]
        candidates = [c for c in candidates if c.graphics.graphics not in [0, 0x5376]]
        candidates = [c for c in candidates if c.name != "_"*10]

        if not self.graphics.large:
            if self.miny <= 3:
                candidates = [c for c in candidates if c.miny <= 4]
            else:
                candidates = [c for c in candidates if c.miny >= 3]

            if self.maxy >= 13:
                candidates = [c for c in candidates if c.maxy >= 13]
            else:
                candidates = [c for c in candidates if c.maxy <= 12]

        if not candidates:
            return self

        chosen = random.choice(candidates)
        return chosen

    def randomize_boost_level(self, limit=99):
        level = self.stats['level']
        diff = limit - level
        level += random.randint(0, diff//2) + random.randint(0, diff//2)
        if diff % 2 == 1:
            level += random.randint(0, 1)
        assert self.stats['level'] <= level <= limit
        self.stats['level'] = level

    def increase_enemy_difficulty(self, limit=99):
        level = self.stats['level']
        diff = limit - level

        level_add = diff//2
        if level <= 7:
            level_add = diff//16
        elif level <= 15:
            level_add = diff//8
        elif level <= 30:
            level_add = diff//4

        factors = {
            'mpow': 5/4,
            'attack': 5/4,
            'def': 5/4,
            'mdef': 5/4,
            'speed': 5/4,
            'evade%': 5/4,
            'mblock%': 9/8,
        }

        hp_add = (750, 1500) if level <= 30 else (2500, 5000)
        if level <= 15:
            hp_add = (0, 0) if level <= 7 else (100, 250)
            factors = {}

        if self.is_boss and self.id not in early_bosses:
            hp_add = (0, 0)
            factors = {
                'hp': 5/2,
                'mpow': 3/2,
                'attack': 3/2,
                'def': 5/4,
                'mdef': 5/4,
                'speed': 3/2,
                'evade%': 4/4,
                'mblock%': 9/8,
            }

        for stat in self.stats:
            self.stats[stat] = int(self.stats[stat] * factors.get(stat, 1))

        if self.stats['evade%'] == 0:
            self.stats['evade%'] = level//2

        if self.stats['mblock%'] == 0:
            self.stats['mblock%'] = level//4

        stat_max = {
            'hp': 65535,
            'speed': 235
        }

        for stat in ['hp', 'mpow', 'attack', 'def', 'mdef', 'speed', 'evade%', 'mblock%']:
            self.stats[stat] = min(stat_max.get(stat, 255), self.stats[stat])

        if diff % 2 == 1:
            level += random.randint(0, 1)

        level += random.randint(0, level_add) + random.randint(0, level_add)
        self.stats['level'] = min(level, limit)

        if hp_add[1] > 0 and hp_add[1] > hp_add[0]:
            self.stats['hp'] += random.randint(*hp_add) + random.randint(*hp_add)

    def randomize_special_effect(self, fout):
        attackpointer = 0xFD0D0 + (self.id * 10)
        fout.seek(attackpointer)
        attack = generate_attack()
        self.attackname = attack
        attack = name_to_bytes(attack, 10)
        fout.write(attack)

        fout.seek(self.specialeffectpointer)
        fout.write(bytes(random.randint(0, 0x21)))

        candidates = sorted(set(range(0, 0x5A)) - set([0, 0x1C]))
        self.attackanimation = random.choice(candidates)

    def mutate_graphics_swap(self, candidates):
        chosen = self.choose_graphics(candidates)
        #print "SWAP %s (%s) <-> %s (%s)" % (self.name, self.graphicname,
        #                                    chosen.name, chosen.graphicname)
        a, b = self.graphicname, chosen.graphicname
        self.graphicname, chosen.graphicname = b, a

        self.graphics.swap_data(chosen.graphics)
        self.swap_visible(chosen)

    def mutate_graphics_copy(self, candidates):
        chosen = self.choose_graphics(candidates)
        #print "BOSSCOPY %s %s" % (self.name, chosen.name)
        #print chosen.graphics.graphics
        self.graphics.copy_data(chosen.graphics)
        self.copy_visible(chosen)

    def read_stats(self, filename):
        global all_spells
        global HIGHEST_LEVEL

        f = open(filename, 'r+b')
        f.seek(self.pointer)
        for key in stat_order:
            self.stats[key] = ord(f.read(1))
        self.stats['hp'] = read_multi(f, length=2)
        self.stats['mp'] = read_multi(f, length=2)
        self.stats['xp'] = read_multi(f, length=2)
        self.stats['gp'] = read_multi(f, length=2)
        self.stats['level'] = ord(f.read(1))
        self.oldlevel = self.stats['level']
        if self.stats['xp'] > 0:
            xps.append((self.oldlevel, self.stats['xp']))
        if self.stats['gp'] > 0:
            gps.append((self.oldlevel, self.stats['gp']))

        self.morph = ord(f.read(1))
        self.misc1 = ord(f.read(1))
        self.misc2 = ord(f.read(1))

        f.seek(self.pointer + 20)
        self.immunities = list(f.read(3))
        self.absorb = ord(f.read(1))
        self.null = ord(f.read(1))
        self.weakness = ord(f.read(1))

        f.seek(self.pointer + 26)
        self.attackanimation = ord(f.read(1))

        f.seek(self.pointer + 27)
        self.statuses = list(f.read(4))
        self.special = ord(f.read(1))

        f.seek(self.itemptr)
        self.items = list(f.read(4))
        self.original_drops = self.drops

        f.seek(self.controlptr)
        self.controls = list(f.read(4))

        f.seek(self.sketchptr)
        self.sketches = list(f.read(2))

        if not self.is_boss:
            f.seek(self.rageptr)
            self.rages = list(f.read(2))
        else:
            self.rages = None

        f.seek(self.aiptr)
        self.ai = read_multi(f, length=2)

        if all_spells is None:
            all_spells = get_ranked_spells(filename)

        f.close()

        self.read_ai(filename)

    def get_skillset(self, ids_only=True):
        skillset = set([])
        skillset.add(0xEE)
        skillset.add(0xEF)
        skillset.add(0xFE)
        for action in self.aiscript:
            if action[0] & 0xF0 == 0xF0:
                if action[0] == 0xF0:
                    for s in action[1:]:
                        skillset.add(s)
            else:
                skillset.add(action[0])

        if not ids_only:
            skillset = [s for s in all_spells if s.spellid in skillset]
        return skillset

    def get_lores(self):
        skills = self.get_skillset()
        skills = [get_spell(s) for s in skills if s in range(0x8B, 0xA3)]
        return sorted(skills, key=lambda s: s.name)

    def set_minimum_mp(self):
        skillset = self.get_skillset(ids_only=False)
        factor = random.uniform(1.0, 2.0)
        self.stats['mp'] = int(
            round(max(self.stats['mp'], factor * max(s.mp for s in skillset))))

    def mutate_ai(self, options_, change_skillset=True, safe_solo_terra=True):
        itembreaker = options_.is_code_active("collateraldamage")
        if self.name[:2] == "L." and not options_.is_code_active("randombosses"):
            change_skillset = False
        elif "guardian" in self.name.lower():
            return

        skillset = set(self.get_skillset())

        def similar(s1, s2):
            a = s1.target_enemy_default == s2.target_enemy_default
            b = s1.target_everyone == s2.target_everyone
            c = s1.target_dead == s2.target_dead
            d = s1.healing == s2.healing
            e = s1.unreflectable == s2.unreflectable
            f = s1.abort_on_allies == s2.abort_on_allies
            return a and b and c and d and e and f
        if options_.mode.name == "katn":
            restricted = [0xEA, 0xC8]
        elif options_.is_code_active("madworld"):
            restricted = []
        else:
            restricted = [0x13, 0x14]

        banned = restricted
        # No blizzard, mega volt, or tek laser in solo terra
        if safe_solo_terra:
            from formationrandomizer import get_fset
            for id in [0x39, 0x3A]:
                fset = get_fset(id)
                for f in fset.formations:
                    if self in f.present_enemies:
                        banned.extend([0xB5, 0xB8, 0xBA])
                        break

        oldskills = sorted([s for s in all_spells if s.spellid in skillset],
                           key=lambda s: s.rank())
        if change_skillset:
            skillmap = {}
            for skill in oldskills:
                if skill.spellid in [0xEE, 0xEF, 0xFE]:
                    continue
                if not skill.valid:
                    continue
                if skill.spellid in restricted:
                    newskill = skill
                else:
                    skillset.remove(skill.spellid)
                    candidates = [s for s in all_spells if similar(s, skill)]
                    candidates = [s for s in candidates if not
                                  (s.is_blitz or s.is_swdtech or s.is_esper
                                   or s.is_slots)]
                    if random.choice([True, False]):
                        candidates = [c for c in candidates if c.valid]
                    candidates = [c for c in candidates if
                                  c.spellid not in banned]
                    if skill not in candidates:
                        candidates.append(skill)
                    candidates = sorted(candidates, key=lambda s: s.rank())

                    if self.is_boss or self.boss_death:
                        index = candidates.index(skill)
                        if index >= 1 and random.randint(1, 10) != 10:
                            candidates = candidates[index:]
                    index = candidates.index(skill)
                    index = mutate_index(index, len(candidates), [False, True],
                                         (-2, 3), (-2, 2))
                    newskill = candidates[index]
                skillset.add(newskill.spellid)
                skillmap[skill.spellid] = newskill.spellid

        sortedskills = sorted([s for s in all_spells if s.spellid in skillset],
                              key=lambda s: s.rank())

        def mutate_action_skill(spellid):
            skill = [s for s in oldskills if s.spellid == spellid]
            if not skill:
                return spellid
            skill = skill[0]
            if not skill.valid:
                return spellid

            a = [s for s in oldskills if similar(s, skill)]
            b = [s for s in sortedskills if similar(s, skill)]
            if restricted and random.choice([True, True, False]):
                b = [s for s in b if s.spellid not in restricted]
            index = a.index(skill)
            index = mutate_index(index, len(b), [False, True],
                                 (-1, 2), (-1, 1))
            if index is None:
                return spellid
            newskill = b[index]
            if not newskill.valid:
                return spellid
            return newskill.spellid

        targeting = None
        newscript = []
        for action in self.aiscript:
            if action[0] & 0xF0 == 0xF0:
                if action[0] in [0xFC, 0xF1]:
                    targeting = random.choice([True, None])
                    if action[0] == 0xFC and random.randint(1, 3) != 3:
                        if action[1] == 0x04:
                            # hit by element
                            nulled = self.absorb | self.null
                            if action[2] & nulled:
                                if self.weakness:
                                    action[2] = self.weakness
                                else:
                                    action[2] = 0xFF ^ nulled
                        if action[1] == 0x06:
                            # hp below value
                            value = action[3]
                            boost = (self.stats['level'] / 100.0) + 1
                            value = value * boost
                            step = int(value * 5 / 7.0)
                            value = step + random.randint(0, step)
                            value = min(0xFF, max(0, value))
                            action[3] = value
                        if action[1] in [0x0B, 0x16]:
                            # battle timer greater than value
                            # global timer greater than value
                            value = action[2]
                            step = value // 2
                            value = (step + random.randint(0, step) +
                                     random.randint(0, step//2))
                            value = min(0xFF, max(0, value))
                            action[2] = value
                        if action[1] in [0x0C, 0x0D]:
                            # variable lt/gte value
                            value = action[3]
                            if value >= 3:
                                value += random.randint(-2, 1)
                            action[3] = value
                elif action[0] == 0xF6 and not itembreaker:
                    items = get_ranked_items()
                    if action[1] == 0x00:
                        candidates = [i for i in items if i.itemtype & 0x20 and not i.features['targeting'] & 0x40]
                        candidates = sorted(candidates, key=lambda c: c.rank())
                    else:
                        candidates = [i for i in items if i.itemtype & 0x10 and i.is_weapon]
                        candidates = sorted(candidates, key=lambda c: c.features['power'])

                    first, second = action[2], action[3]
                    first = get_item(first) or candidates[0]
                    second = get_item(second) or candidates[0]
                    for i, a in enumerate([first, second]):
                        index = candidates.index(a)
                        index = mutate_index(index, len(candidates),
                                             [False, True, True],
                                             (-1, 4), (-1, 4))
                        action[i+2] = candidates[index].itemid

                elif action[0] in [0xFD, 0xFE, 0xFF]:
                    targeting = None
                elif targeting:
                    pass
                elif action[0] == 0xF0:
                    if itembreaker and len(action) == 4:
                        action[0] = 0xF6
                        items = get_ranked_items()
                        if random.randint(1, 5) != 5:
                            action[1] = 0x00
                            candidates = [i for i in items if i.itemtype & 0x20]
                            candidates = sorted(candidates, key=lambda c: c.rank())
                        else:
                            action[1] = 0x01
                            candidates = [i for i in items if i.itemtype & 0x10 and i.is_weapon]
                            candidates = sorted(candidates, key=lambda c: c.features['power'])
                        monsters = get_ranked_monsters()
                        index = int((monsters.index(self) / float(len(monsters))) * len(candidates))
                        index = mutate_index(index, len(candidates),
                                             [False, False, False, True],
                                             (-3, 3), (-2, 2))
                        c1 = candidates[index]
                        index = mutate_index(index, len(candidates),
                                             [False, False, False, True],
                                             (-3, 3), (-2, 2))
                        c2 = candidates[index]
                        action[2], action[3] = c1.itemid, c2.itemid
                    else:
                        if len(set(action[1:])) != 1 or change_skillset:
                            for j in range(100):
                                newaction = bytearray(action)
                                for i in range(1, 4):
                                    a = newaction[i]
                                    if a == 0xFE:
                                        a = random.choice(action[1:])
                                    value = mutate_action_skill(a)
                                    newaction[i] = value
                                if len(set(newaction[1:])) != 1:
                                    action = newaction
                                    break
                        assert 0x81 not in action
            elif len(action) == 1 and change_skillset:
                s = action[0]
                if s in skillmap:
                    s = skillmap[s]
                    action[0] = s
                assert 0x81 not in action
            newscript.append(action)

        assert len(b"".join(newscript)) == len(b"".join(self.aiscript))
        self.aiscript = newscript

    def read_ai(self, filename):
        f = open(filename, 'r+b')
        pointer = self.ai + 0xF8700
        f.seek(pointer)
        seen = False
        script = []
        while True:
            value = f.read(1)
            try:
                numargs = AICODES[ord(value)]
                args = f.read(numargs)
            except KeyError:
                args = b""
            script.append(bytearray(value + args))
            if ord(value) == 0xFF:
                if seen:
                    break
                else:
                    seen = True

        self.aiscript = script

        if self.id == 0xF3:
            # account for brown Mag Roader bug
            self.aiscript = self.aiscript[:4]

        return self.aiscript

    def set_relative_ai(self, pointer):
        self.ai = pointer - 0xF8700

    @property
    def aiscriptsize(self):
        return len(b"".join(self.aiscript))

    def write_ai(self, fout):
        for (i, action) in enumerate(self.aiscript):
            if (len(action) == 4 and action[0] == 0xf0 and
                    action[1] == 0x55):
                # fix Cyan's AI at imperial camp
                action = bytearray([0xF0, 0xEE, 0xEE, 0xEE])
                self.aiscript[i] = action
        fout.seek(self.aiptr)
        write_multi(fout, self.ai, length=2)
        pointer = self.ai + 0xF8700
        fout.seek(pointer)
        fout.write(b"".join(self.aiscript))

    @property
    def humanoid(self):
        return self.misc1 & 0x10

    @property
    def undead(self):
        return self.misc1 & 0x80

    @property
    def cantrun(self):
        return self.misc2 & 0x08

    @property
    def hardrun(self):
        if self.cantrun:
            return 0
        return self.misc2 & 0x01

    @property
    def mpdeath(self):
        return self.misc1 & 0x01

    @property
    def cantmorph(self):
        return self.morph & 0xE0 == 0xE0

    @property
    def morphrate(self):
        missrate = (self.morph & 0xE0) >> 5
        hitrate = {0: 99,
                   1: 75,
                   2: 50,
                   3: 25,
                   4: 12,
                   5: 6,
                   6: 3,
                   7: 0}[missrate]
        return hitrate

    def get_morph_items(self):
        morphpack = self.morph & 0x1F
        morphpack = [mm for mm in get_metamorphs() if mm.id == morphpack][0]
        return [get_item(i) for i in morphpack.items]

    @property
    def floating(self):
        return self.statuses[2] & 0x1

    def swap_visible(self, other):
        if self.humanoid != other.humanoid:
            self.misc1 ^= 0x10
            other.misc1 ^= 0x10
        if self.undead != other.undead:
            self.misc1 ^= 0x80
            other.misc1 ^= 0x80
        if self.floating != other.floating:
            self.statuses[2] ^= 0x1
            other.statuses[2] ^= 0x1

    def copy_visible(self, other):
        if self.humanoid != other.humanoid:
            self.misc1 ^= 0x10
        if self.undead != other.undead:
            self.misc1 ^= 0x80
        if self.floating != other.floating:
            self.statuses[2] ^= 0x1

    def write_stats(self, fout):
        self.set_minimum_mp()

        fout.seek(self.pointer)
        for key in stat_order:
            fout.write(bytes([self.stats[key]]))
        write_multi(fout, self.stats['hp'], length=2)
        write_multi(fout, self.stats['mp'], length=2)
        write_multi(fout, self.stats['xp'], length=2)
        write_multi(fout, self.stats['gp'], length=2)
        fout.write(bytes([self.stats['level']]))

        fout.write(bytes([self.morph]))
        fout.write(bytes([self.misc1]))
        fout.write(bytes([self.misc2]))

        fout.seek(self.pointer + 20)
        for i in self.immunities:
            fout.write(bytes([i]))
        fout.write(bytes([self.absorb]))
        fout.write(bytes([self.null]))
        fout.write(bytes([self.weakness]))

        fout.seek(self.pointer + 26)
        fout.write(bytes([self.attackanimation]))

        fout.seek(self.pointer + 27)
        for s in self.statuses:
            fout.write(bytes([s]))
        fout.write(bytes([self.special]))

        fout.seek(self.itemptr)
        fout.write(bytes(self.items))

        fout.seek(self.controlptr)
        fout.write(bytes(self.controls))

        fout.seek(self.sketchptr)
        fout.write(bytes(self.sketches))

        if not self.is_boss:
            fout.seek(self.rageptr)
            fout.write(bytes(self.rages))

        self.write_ai(fout)

    def screw_tutorial_bosses(self, old_vargas_fight=False):
        name = self.name.lower().strip('_')
        tutmessage = None
        if name == 'vargas':
            if old_vargas_fight:
                self.stats['hp'] = 900 + random.randint(0, 100) + random.randint(0, 100)
            else:
                self.stats['hp'] = 1500 + random.randint(0, 150) + random.randint(0, 150)
                tutmessage = bytearray([0xF7, 0x08])
                # trigger phase change at 640 or 768 HP
                for i, a in enumerate(self.aiscript):
                    if a[0:3] == bytearray([0xFC, 0x06, 0x36]):
                        self.aiscript[i] = bytearray([0xFC, 0x06, 0x36, random.randint(5, 6)])
                        break
        if name == 'tunnelarmr':
            self.stats['hp'] = 1000 + random.randint(0, 150) + random.randint(0, 150)
            self.aiscript = self.aiscript[4:]
        if name == "leader":
            self.stats['hp'] = 400 + random.randint(0, 50) + random.randint(0, 50)
        if name in ("merchant", "officer"):
            stealmessage = bytearray([0xFC, 0x01, 0x05, 0x05])
            deathmessage = bytearray([0xFC, 0x12, 0x00, 0x00])
            index = self.aiscript.index(stealmessage)
            self.aiscript[index] = deathmessage

        if name == 'whelk':
            self.aiscript = self.aiscript[4:]

        if tutmessage:
            self.aiscript = [a for a in self.aiscript if a != tutmessage]

    @property
    def has_blaze(self):
        return self.ai == 0x356

    def relevel_specifics(self):
        if self.id == 0x4f:
            self.stats['level'] += random.randint(2, 6)
        if self.id == 0xbd:
            self.stats['level'] += random.randint(30, 50)
        if self.id == 0xad:
            self.stats['level'] += random.randint(10, 30)

    def mutate_misc(self):
        # invert "escapable" bit
        if self.is_boss:
            if random.randint(1, 500) == 500:
                self.misc2 = self.misc2 ^ 0x08
        elif random.randint(1, 20) == 20:
            if self.stats['level'] > 10 and random.choice([True, False]):
                self.misc2 = self.misc2 ^ 0x08
            else:
                self.ambusher = True
                self.misc2 |= 0x01

        if random.randint(1, 10) == 10:
            self.misc2 = self.misc2 ^ 0x10  # invert scan bit

        if self.undead:
            if random.randint(1, 3) == 3:
                self.misc1 = self.misc1 ^ 0x80
        elif self.is_boss:
            if random.randint(1, 150) == 150:
                self.misc1 = self.misc1 ^ 0x80  # invert undead bit
        else:
            if random.randint(1, 20) == 20:
                self.misc1 = self.misc1 ^ 0x80

    def tweak_fanatics(self):
        if self.name[:2] == "L.":
            level = int(self.name[2:4])
            self.stats['level'] = level
        elif self.name.lower() == "magimaster":
            self.treasure_boost()
            level = 99
            self.stats['level'] = level
            self.stats['xp'] = 0
        else:
            return False

    def mutate_stats(self):
        level = self.stats['level']

        def level_boost(value, limit=0xFF):
            low = value
            high = int(value + (value * (level / 100.0)))
            diff = high - low
            value += -diff//4 + random.randint(0, diff) + random.randint(0, diff)
            if value & 0xFF == 0xFF:
                value = value - 1

            return min(value, limit)

        for stat in stat_order:
            if stat == 'speed':
                limit = 230
            else:
                limit = 0xFF
            boosted = level_boost(self.stats[stat], limit=limit)
            if stat in ['def', 'mdef']:
                boosted = (self.stats[stat] + boosted) // 2
            self.stats[stat] = boosted

        self.stats['hp'] = level_boost(self.stats['hp'], limit=0x10000)
        if self.stats['hp'] == 0x10000:
            self.statuses[3] |= 0x04  # reraise
            self.stats['hp'] = 0xFFFF

        self.stats['mp'] = level_boost(self.stats['mp'], limit=0xFFFE)

        def fuddle(value, limit=0xFFFF):
            low = value // 2
            value = low + random.randint(0, low) + random.randint(0, low)
            if value & 0xFF == 0xFF:
                value = value - 1

            return min(value, limit)

        self.stats['xp'] = fuddle(self.stats['xp'])
        self.stats['gp'] = fuddle(self.stats['gp'])

        if random.randint(1, 5) == 10:
            if not self.is_boss or random.randint(1, 4) == 4:
                level += random.choice([1, -1])
                if random.randint(1, 5) == 5:
                    level += random.choice([1, -1])
        level = min(level, 99)
        level = max(level, 0)
        self.stats['level'] = level

    def mutate_statuses(self):
        immcount = sum([bin(v).count('1') for v in self.immunities])
        immcount += 1
        while random.randint(1, 5) == 5:
            immcount += random.choice([1, -1])
        immcount = min(16, max(immcount, 0))

        stacount = sum([bin(v).count('1') for v in self.statuses])
        stacount += 1
        while random.randint(1, 5) == 5:
            stacount += random.choice([1, -1])
        stacount = min(16, max(stacount, 0))

        new_immunities = [0x00] * 3
        new_statuses = [0x00] * 4
        bitdict = dict((y, x) for (x, y) in statusdict.items())

        for _ in range(100):
            if stacount <= 0:
                break

            byte = random.randint(0, 3)
            bit = 1 << random.randint(0, 7)
            if new_statuses[byte] & bit:
                continue

            status = bitdict[(byte, bit)]
            if status in ["zombie", "magitek", "petrify", "death", "disappear"]:
                if self.is_boss or random.randint(1, 1000) != 1000:
                    continue
            if status in ["condemned", "mute", "berserk",
                          "stop", "confuse", "sleep"]:
                if self.is_boss and random.randint(1, 100) != 100:
                    continue
                elif not self.is_boss and random.randint(1, 10) != 10:
                    continue
            if status in ["reraise", "runic", "cover", "image"]:
                if random.randint(1, 10) != 10:
                    continue
            if status in ["blind", "poison", "imp", "seizure", "slow"]:
                if self.is_boss and random.randint(1, 10) != 10:
                    continue
                elif not self.is_boss and random.choice([True, False]):
                    continue
            if status in ["vanish", "image"]:
                if self.stats["level"] < 22 or self.id in [0x11a, 0x12a]:
                    continue
                elif random.choice([True, False]):
                    continue

            new_statuses[byte] |= bit
            stacount += -1

        for _ in range(100):
            if immcount <= 0:
                break

            byte = random.randint(0, 2)
            bit = 1 << random.randint(0, 7)

            status = bitdict[(byte, bit)]
            if new_immunities[byte] & bit:
                continue
            if new_statuses[byte] & bit:
                continue

            new_immunities[byte] |= bit
            immcount += -1

        self.statuses = new_statuses
        if self.is_boss and random.randint(1, 20) != 20:
            index = random.randint(0, 2)
            bit = 1 << random.randint(0, 7)
            self.immunities[index] ^= bit
            for i in range(len(self.immunities)):
                self.immunities[i] |= new_immunities[i]
        else:
            self.immunities = new_immunities

    def mutate_affinities(self, odds=10):
        abscount = bin(self.absorb).count('1') + 1
        while random.randint(1, odds) == odds:
            abscount += random.choice([1, -1])
        abscount = min(8, max(abscount, 0))

        nullcount = bin(self.null).count('1') + 1
        while random.randint(1, odds) == odds:
            nullcount += random.choice([1, -1])
        nullcount = min(8, max(nullcount, 0))

        weakcount = bin(self.weakness).count('1')
        while random.randint(1, odds) == odds:
            weakcount += random.choice([1, -1])
        weakcount = min(8, max(weakcount, 0))

        self.absorb, self.null, self.weakness = 0, 0, 0
        while abscount > 0:
            bit = 1 << random.randint(0, 7)
            if self.absorb & bit:
                continue

            self.absorb = self.absorb | bit
            abscount += -1

        while nullcount > 0:
            bit = 1 << random.randint(0, 7)
            if self.null & bit:
                continue
            self.null = self.null | bit
            nullcount += -1

        while weakcount > 0:
            bit = 1 << random.randint(0, 7)
            if self.weakness & bit:
                continue
            self.weakness = self.weakness | bit
            weakcount += -1

        nullify = self.null | self.absorb
        if self.stats['level'] < 20 and nullify & 0x7 == 0x7:
            denullify = 0xFF ^ (1 << random.randint(0, 2))
            self.null &= denullify
            self.absorb &= denullify

    def mutate_items(self):
        if random.choice([True, False]):
            random.shuffle(self.items)

        items = get_ranked_items()
        itemids = [i.itemid for i in items]
        new_items = []
        for i in self.items:
            if i == 0xFF:
                i = random.choice(self.items + [0xFF])
                if i == 0xFF:
                    new_items.append(0xFF)
                    continue

            if i not in itemids:
                index = 0
            else:
                index = itemids.index(i)
            index = mutate_index(index, len(itemids),
                                 [False, False, False, True],
                                 (-3, 3), (-2, 2))

            new_items.append(itemids[index])

        new_items = [get_item(i) for i in new_items]
        steals, drops = (new_items[:2], new_items[2:])
        steals = sorted(steals, key=lambda i: i.rank() if i else 0, reverse=True)
        drops = sorted(drops, key=lambda i: i.rank() if i else 0, reverse=True)

        if self.boss_death and None in drops:
            temp = [d for d in drops if d]
            if temp:
                drops = temp * 2
        new_items = [i.itemid if i else 0xFF for i in steals + drops]
        if self.is_boss or self.boss_death:
            pass
        else:
            if random.randint(1, 5) != 5:
                if (new_items[2] != new_items[3] or
                        random.choice([True, False])):
                    new_items[3] = 0xFF

        self.items = new_items
        assert len(self.items) == 4

    def level_rank(self):
        level = self.stats['level']
        rank = float(level) / HIGHEST_LEVEL
        return rank

    def get_item_appropriate(self):
        items = get_ranked_items()
        rank = self.level_rank()
        index = int(len(items) * rank)
        index = mutate_index(index, len(items),
                             [False, True],
                             (-3, 3), (-2, 2))

        ranked_items = sorted(items, key=lambda i: i.rank())
        item = ranked_items[index]
        #print "%s/%s" % (self.stats['level'], HIGHEST_LEVEL), item.name
        return item

    def get_spell_appropriate(self, spell_list=None):
        spell_list = spell_list or get_ranked_spells()
        index = int(self.level_rank() * len(spell_list))
        index = mutate_index(index, len(spell_list), [False, True],
                             (-10, 10), (-5, 5))
        spell = spell_list[index]
        return spell

    def get_xp_appropriate(self):
        rank = self.level_rank()
        temp = [b for (a, b) in xps if a >= self.stats['level'] and b > 0]
        temp.sort()
        index = int(len(temp) * rank)
        index = mutate_index(index, len(temp),
                             [False, True],
                             (-2, 2), (-1, 1))

        return temp[index] if index is not None else 40000

    def get_gp_appropriate(self):
        rank = self.level_rank()
        temp = [b for (a, b) in xps if a >= self.stats['level'] and b > 0]
        temp.sort()
        index = int(len(temp) * rank)
        index = mutate_index(index, len(temp),
                             [False, True],
                             (-2, 2), (-1, 1))

        return temp[index] if index is not None else 50000

    def treasure_boost(self):
        def fuddle(value, limit=0xFFFF):
            low = value // 2
            value = low + random.randint(0, low) + random.randint(0, low)
            while random.choice([True, True, False]):
                value += random.randint(0, low)

            if value & 0xFF == 0xFF:
                value = value - 1

            return min(value, limit)

        self.stats['xp'] = self.stats['xp'] or self.get_xp_appropriate()
        self.stats['gp'] = self.stats['gp'] or self.get_gp_appropriate()
        self.stats['xp'] = fuddle(self.stats['xp'])
        self.stats['gp'] = fuddle(self.stats['gp'])

        items = get_ranked_items()
        itemids = [i.itemid for i in items]
        new_items = []
        for i in self.items:
            if i == 0xFF:
                i = self.get_item_appropriate().itemid
                candidates = self.items + new_items + [i]
                candidates = [i for i in candidates if i != 0xFF]
                i = random.choice(sorted(candidates))

            index = itemids.index(i)
            index = mutate_index(index, len(itemids),
                                 [False, True],
                                 (-2, 4), (-1, 2))

            new_items.append(itemids[index])

        self.items = new_items
        assert 0xFF not in self.items

    def mutate_metamorph(self):
        # mutates both metamorph template and miss ratio
        self.morph = random.randint(0, 0xEF)
        if self.immunities[0] & 0x80 and random.randint(1, 50) != 50:
            self.morph |= 0xE0

    def mutate_control(self):
        # shuffle skills between control, sketch, rage
        candidates = self.get_skillset()
        candidates = set(candidates)
        candidates.add(0xEE)
        candidates.add(0xEF)
        if 0xFF in candidates:
            candidates.remove(0xFF)
        if 0xFE in candidates:
            candidates.remove(0xFE)

        valid_spells = [s for s in get_ranked_spells() if s.valid]
        if random.randint(1, 10) >= 9:
            sb = self.get_spell_appropriate(valid_spells)
            candidates.add(sb.spellid)

        candidates = sorted(candidates)
        self.controls = random.sample(candidates, min(4, len(candidates)))
        while len(self.controls) < 4:
            self.controls += [random.choice(candidates)]
        if 0xEE not in self.controls and 0xEF not in self.controls:
            self.controls[random.randint(0, 3)] = random.choice([0xEE, 0xEF])
        self.controls = [c if c not in list(range(0x7D, 0x83)) else 0xEE
                         for c in self.controls]
        self.controls = sorted(self.controls)

        valid_spells = [v for v in valid_spells if not v.unrageable]

        def get_good_selection(candidates, numselect, minimum=2,
                               highpower=False):
            candidates = [c for c in candidates if not get_spell(c).unrageable]
            if highpower:
                candidates = sorted(candidates,
                                    key=lambda c: get_spell(c).rank())
                for c in list(candidates)[:-2]:
                    if len(candidates) <= 2:
                        break
                    if random.randint(1, len(candidates)*2) >= 4:
                        candidates.remove(c)
                    else:
                        break
            candidates += [0xEF, 0xEE]
            if self.deadspecial and 0xEF in candidates:
                candidates.remove(0xEF)
            if highpower and len(candidates) >= 3:
                candidates.remove(0xEE)
            while True:
                if len(candidates) >= minimum:
                    break
                elif len(candidates) == 2 and not self.physspecial:
                    break
                spell = self.get_spell_appropriate(valid_spells)
                value = spell.spellid
                candidates.append(value)
                candidates = sorted(set(candidates))
            for _ in range(2):
                selection = random.sample(candidates, numselect)
                if not self.physspecial:
                    break
                if set(selection) != set([0xEE, 0xEF]):
                    break
            return sorted(selection)

        self.sketches = get_good_selection(candidates, 2, highpower=True)
        random.shuffle(self.sketches)
        if not self.is_boss:
            self.rages = get_good_selection(candidates, 2, minimum=3)

        while len(self.controls) < 4:
            self.controls.append(0xFF)

    @property
    def goodspecial(self):
        good = set(range(0x10, 0x1F))
        good.remove(0x12)  # slow
        good.remove(0x14)  # stop
        good.remove(0x19)  # frozen
        good.remove(0x1D)  # disappear
        good.add(0x04)  # vanish
        good.add(0x0A)  # image
        return self.special & 0x3f in good

    @property
    def physspecial(self):
        return bool(self.special & 0x20 and
                    self.special & 0x30 != 0x30)

    @property
    def deadspecial(self):
        return (self.special & 0x3F) in [0x07, 0x10, 0x18]

    def mutate_special(self, darkworld=False, narshesafe=False):
        if self.goodspecial:
            return

        branch = random.randint(1, 10)
        if darkworld:
            branches = [3, 5]
        else:
            branches = [7, 9]
        if branch <= branches[0]:
            # regular special
            valid = set(range(0, 0x0F))
            if narshesafe and not darkworld:
                valid = [0, 2, 3, 5, 8, 9, 0xb, 0xc, 0xd, 0xe, 0xf,
                         0x10, 0x12, 0x14, 0x18, 0x30, 0x31, 0x80]
            else:
                valid = [0, 1, 2, 3, 5, 6, 7, 8, 9, 0xb, 0xc, 0xd, 0xe, 0xf,
                         0x10, 0x12, 0x14, 0x18, 0x19, 0x30, 0x31, 0x80]
            if random.randint(1, 1000) != 1000:
                valid.remove(0x03)  # Magitek
            if random.randint(1, 5) != 5:
                valid.remove(0x10)  # dance
                valid.remove(0x18)  # rage
            valid = [r for r in ranked if r in valid]
            index = int(self.level_rank() * len(valid))
            index = mutate_index(index, len(valid), [False, True],
                                 (-5, 5), (-3, 3), disregard_multiplier=True)
            special = valid[index]
            if special == 0x07 or (special not in [0x30, 0x31] and
                                   random.choice([True, False])):
                special |= 0x40  # no HP damage
        elif branches[0] < branch <= branches[1]:
            # physical special
            factor = int(self.stats['level'] * 16 / 99.0) + 1
            power = random.randint(0, factor) + random.randint(0, factor)
            power = max(power, 0x00)
            power = min(power, 0x0F)
            special = 0x20 + power
        elif branch > branches[1]:
            # bonus special
            valid = set(range(10, 0x1F))
            if not self.is_boss or random.randint(1, 1000) != 1000:
                valid.remove(0x1D)  # disappear
                valid.remove(0x1E)  # Interceptor
            valid.remove(0x10)  # dance
            valid.remove(0x18)  # rage
            valid.remove(0x12)  # slow
            valid.remove(0x14)  # stop
            valid.remove(0x19)  # frozen
            valid.add(0x04)  # vanish
            valid.add(0x0A)  # image
            special = random.choice(sorted(valid))

        unblockable_score = random.randint(0, self.stats['level'])
        while random.choice([True, False]):
            unblockable_score += random.randint(0, self.stats['level'])
        if unblockable_score >= 60:
            special |= 0x80  # unblockable

        self.special = special

    def mutate(self, options_, change_skillset=None, safe_solo_terra=True):
        randombosses = options_.is_code_active("randombosses")
        darkworld = options_.is_code_active("darkworld")
        madworld = options_.is_code_active("madworld")

        if change_skillset is None:
            change_skillset = randombosses or not (self.is_boss or self.boss_death)
            manual_change = False
        else:
            manual_change = True
        self.mutate_stats()
        self.mutate_misc()
        if madworld or random.randint(1, 10) > 5:
            self.mutate_statuses()
        if madworld or random.randint(1, 10) > 5:
            self.mutate_affinities(odds=5 if madworld else 10)
        if options_.mode.name == 'katn':
            self.mutate_special(darkworld=darkworld, narshesafe=True)
        elif madworld or random.randint(1, 10) > 5:
            # do this before mutate_control
            narshesafe = self.stats['level'] <= 7
            self.mutate_special(darkworld=darkworld, narshesafe=narshesafe)
        if manual_change and change_skillset:
            value = 10
        else:
            value = random.randint(1, 10)
        if value > 1:
            if value == 2:
                self.mutate_ai(options_=options_, change_skillset=False,
                               safe_solo_terra=safe_solo_terra)
            else:
                self.mutate_ai(options_=options_, change_skillset=change_skillset,
                               safe_solo_terra=safe_solo_terra)
        self.mutate_control()

    def swap_ai(self, other):
        if self.boss_death != other.boss_death:
            return
        for attribute in ["ai", "aiscript", "controls", "sketches",
                          "rages", "special"]:
            a, b = getattr(self, attribute), getattr(other, attribute)
            setattr(self, attribute, b)
            setattr(other, attribute, a)

    def swap_stats(self, other):
        attributes = ["stats", "misc2", "absorb", "null",
                      "weakness", "morph", "items"]
        samplesize = random.randint(1, len(attributes))
        sample = random.sample(attributes, samplesize)
        for attribute in sample:
            a, b = getattr(self, attribute), getattr(other, attribute)
            setattr(self, attribute, b)
            setattr(other, attribute, a)

    def copy_all(self, other, everything=True):
        attributes = [
            "ai", "aiscript", "controls", "sketches", "stats",
            "absorb", "null", "weakness", "special", "morph", "items",
            "misc1", "misc2", "immunities", "statuses", "attackanimation"]
        if "aiptr" in attributes:
            attributes.remove("aiptr")  # don't copy this, yo
        if not everything:
            samplesize = random.randint(0, len(attributes))
            attributes = random.sample(attributes, samplesize)
            attributes = sorted(set(attributes) -
                                set(["ai", "aiptr", "aiscript"]))

        for attribute in attributes:
            value = getattr(other, attribute)
            if value is not None:
                value = type(value)(value)
            # deep copy so changes to the target's ai don'table
            # affect the source
            setattr(self, attribute, copy.deepcopy(value))

        if self.rages is not None and other.rages is not None and random.choice([True, False]):
            self.rages = type(other.rages)(other.rages)

    def rank(self, weights=None):
        global globalweights
        funcs = {}
        funcs['level'] = lambda m: m.stats['level']
        funcs['hp'] = lambda m: m.stats['hp']
        funcs['defense'] = lambda m: max(1, m.stats['def'] + m.stats['mdef'])
        funcs['offense'] = lambda m: max(1, m.stats['attack'], m.stats['mpow'])
        funcs['evasion'] = lambda m: max(1, m.stats['evade%'] +
                                         m.stats['mblock%'])
        funcs['speed'] = lambda m: m.stats['speed']
        funcs['elements'] = lambda m: max(1, bin(m.absorb | m.null).count('1'))
        funcs['immunities'] = lambda m: max(1, sum(bin(i).count('1')
                                                   for i in m.immunities))

        if not avgs:
            monsters = get_monsters()
            monsters = [m for m in monsters if not (m.is_boss or m.boss_death)]
            for key in funcs:
                avgs[key] = (sum(funcs[key](m) for m in monsters) /
                             float(len(monsters)))

        if weights is None:
            if globalweights is None:
                globalweights = {k:_randomweight(k) for k in avgs}
            weights = globalweights
        elif isinstance(weights, int):
            weights = {k:50 for k in avgs}

        LEVELFACTOR, HPFACTOR = len(avgs)*2, len(avgs)
        total = 0
        for key in sorted(avgs):
            weighted = weights[key] * funcs[key](self) / avgs[key]
            if key == "level":
                weighted *= LEVELFACTOR
            elif key == "hp":
                weighted *= HPFACTOR
            total += weighted

        if self.has_blaze:
            total *= 1.5

        return total

    def dummy_item(self, item):
        if item.itemid in self.items:
            self.items = [i if i != item.itemid else 0xFF for i in self.items]
            return True
        return False

def _randomweight(key: str):
    ranges = {'level': (50, 100),
              'hp': (30, 100)}
    min_weight, max_weight = ranges.get(key, (2, 100))
    delta = max_weight - min_weight
    return min_weight + random.randint(0, delta/2 + delta%2) + random.randint(0, delta/2)

def monsters_from_table(tablefile):
    monsters = []
    for i, line in enumerate(open(tablefile)):
        line = line.strip()
        if line[0] == '#':
            continue

        while '  ' in line:
            line = line.replace('  ', ' ')
        line = line.split(',')
        name = line[0]
        c = MonsterBlock(name, i)
        monsters.append(c)
    return monsters


def get_monsters(filename=None):
    if monsterdict:
        return sorted(list(monsterdict.values()), key=lambda m: m.id)

    get_ranked_items(filename)
    monsters = monsters_from_table(ENEMY_TABLE)
    for m in monsters:
        m.read_stats(filename)

    mgs = []
    for j, m in enumerate(monsters):
        mg = MonsterGraphicBlock(pointer=0x127000 + (5*j), name=m.name)
        mg.read_data(filename)
        m.set_graphics(graphics=mg)
        mgs.append(mg)

    return monsters


def get_monster(monster_id):
    global monsterdict
    return monsterdict[monster_id]


def get_ranked_monsters(filename=None, bosses=True):
    monsters = get_monsters(filename=filename)
    if not bosses:
        monsters = [m for m in monsters if m.id <= 0xFF]
    monsters = sorted(monsters, key=lambda m: m.rank())
    return monsters


def shuffle_monsters(monsters, safe_solo_terra=True):
    monsters = sorted(monsters, key=lambda m: m.rank())
    monsters = [m for m in monsters if m.name.strip('_')]
    monsters = [m for m in monsters if m.display_name[:2] != "L."]
    bosses = [m for m in monsters if m.is_boss or m.boss_death]
    nonbosses = [m for m in monsters if m not in bosses]
    for m in monsters:
        if m.is_boss or m.boss_death:
            candidates = bosses
        else:
            candidates = nonbosses
        index = candidates.index(m)

        candidates = [c for c in candidates
                      if abs(c.stats["level"] - m.stats["level"]) <= 20]

        def get_swap_index(to_swap):
            to_swap = mutate_index(index, len(candidates),
                                   [False, False, True],
                                   (-5, 5), (-3, 3), disregard_multiplier=True)
            return to_swap

        if m.is_boss and random.randint(1, 100) != 100:
            pass
        else:
            to_swap = get_swap_index(index)
            m.swap_stats(candidates[to_swap])

        if m.is_boss or m.boss_death:
            pass
        else:
            to_swap = get_swap_index(index)
            n = candidates[to_swap]

            if not safe_solo_terra:
                m.swap_ai(n)
                continue

            # No blizzard, mega volt, or tek laser in solo terra
            banned_narshe_skills = [0xB5, 0xB8, 0xBA]

            banned_from_narshe = any(b in m.get_skillset()
                                     for b in banned_narshe_skills)
            banned_from_narshe |= any(b in n.get_skillset()
                                      for b in banned_narshe_skills)

            if banned_from_narshe:
                in_narshe_caves = False

                for id in [0x39, 0x3A]:
                    from formationrandomizer import get_fset
                    fset = get_fset(id)
                    for f in fset.formations:
                        if m in f.present_enemies or n in f.present_enemies:
                            in_narshe_caves = True
                            break

            if not banned_from_narshe or not in_narshe_caves:
                m.swap_ai(n)


palette_pools = {}


class MonsterGraphicBlock:
    def __init__(self, pointer, name=None):
        self.pointer = pointer
        self.name = name
        self.graphics = None
        self.palette = None
        self.large = False
        self.palette_index = None
        self.palette_pointer = None
        self.size_template = None
        self.palette_data = []
        self.palette_values = []

    def read_data(self, filename):
        global palette_pools
        f = open(filename, 'r+b')
        f.seek(self.pointer)
        self.graphics = read_multi(f, length=2)
        f.seek(self.pointer+2)
        self.palette = read_multi(f, length=2, reverse=False)
        self.large = bool(self.palette & 0x8000)
        self.palette_index = self.palette & 0x3FF
        self.palette_pointer = 0x127820 + (self.palette_index * 16)
        f.seek(self.pointer+4)
        self.size_template = ord(f.read(1))

        f.seek(self.palette_pointer)
        numcolors = 0x20

        for i in range(numcolors):
            color = read_multi(f, length=2)
            blue = (color & 0x7c00) >> 10
            green = (color & 0x03e0) >> 5
            red = color & 0x001f
            self.palette_data.append(color)
            self.palette_values.append(int(round(sum([red, green, blue])/3.0)))
        self.palette_data = tuple(self.palette_data)
        f.close()

        if self.graphics not in palette_pools:
            palette_pools[self.graphics] = set([])
        for p in palette_pools[self.graphics]:
            if all([a_b[0] == a_b[1] for a_b in zip(self.palette_data, p)]):
                return
        palette_pools[self.graphics].add(self.palette_data)

    def swap_data(self, other):
        for attribute in ["graphics", "size_template", "palette_data"]:
            a, b = getattr(self, attribute), getattr(other, attribute)
            setattr(self, attribute, b)
            setattr(other, attribute, a)

    def copy_data(self, other):
        for attribute in ["graphics", "size_template", "palette_data", "large"]:
            value = getattr(other, attribute)
            if isinstance(value, list):
                value = list(value)
            elif isinstance(value, tuple):
                value = tuple(value)

            setattr(self, attribute, value)

    def set_palette_pointer(self, palette_pointer):
        self.palette_pointer = palette_pointer
        palette = (palette_pointer - 0x127820) // 0x10
        self.palette = palette

    def write_data(self, fout, palette_pointer=None, no_palette=False):
        if palette_pointer is None:
            palette_pointer = self.palette_pointer
            palette = self.palette
        else:
            self.set_palette_pointer(palette_pointer)
            palette = (palette_pointer - 0x127820) // 0x10

        if self.large:
            palette |= 0x8000
        else:
            palette &= 0x7FFF

        if palette_pointer > 0x12a800:
            raise Exception("Palette pointer out of bounds.")

        fout.seek(self.pointer)
        write_multi(fout, self.graphics, length=2)
        fout.seek(self.pointer+2)
        write_multi(fout, palette, length=2, reverse=False)
        fout.seek(self.pointer+4)
        fout.write(bytes([self.size_template]))
        if no_palette:
            return

        fout.seek(palette_pointer)
        for color in self.palette_data:
            write_multi(fout, color, length=2)

    def mutate_palette(self, alternatives=None):
        transformer = get_palette_transformer(basepalette=self.palette_data)
        self.palette_data = transformer(self.palette_data)


class MetamorphBlock:
    def __init__(self, pointer):
        self.pointer = pointer
        self.items = []

    def read_data(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.pointer)
        self.items = list(f.read(4))
        f.close()

    def write_data(self, fout):
        fout.seek(self.pointer)
        fout.write(bytes(self.items))

    def mutate_items(self):
        for i in range(4):
            self.items[i] = get_item_normal().itemid

    def dummy_item(self, item):
        if item.itemid in self.items:
            while item.itemid in self.items:
                self.items = [i for i in self.items if i != item.itemid]
                if self.items == []:
                    self.items = [get_item_normal().itemid for _ in range(4)]

            while len(self.items) < 4:
                self.items.append(random.choice(self.items))
            return True

        return False


def get_metamorphs(filename=None):
    global metamorphs
    if metamorphs is not None:
        return metamorphs

    metamorphs = []
    for i in range(32):
        address = 0x47f40 + (i*4)
        mm = MetamorphBlock(pointer=address)
        mm.read_data(filename)
        mm.id = i
        metamorphs.append(mm)
    return get_metamorphs()


def get_collapsing_house_help_skill():
    status_specials = []
    all_skills = []
    from formationrandomizer import get_fset
    for id in [0x80]:
        fset = get_fset(id)
        for f in fset.formations:
            for m in f.present_enemies:
                if not m.physspecial and not m.goodspecial:
                    status_specials.append(m.special & 0x3F)
                skills = m.get_skillset(ids_only=False)
                all_skills.extend([z for z in skills
                                   if (z.target_enemy_default or
                                       (z.target_everyone and not z.target_one_side_only)) and
                                   z.spellid not in [0xEE, 0xEF, 0xFE, 0xFF]])

    if status_specials:
        sleep_index = ranked.index(specialdict["sleep"])
        worst_special = max(status_specials, key=ranked.index)
        worst_special_index = ranked.index(worst_special)
        if worst_special_index >= sleep_index or not all_skills or random.choice([True, False]):
            status = reverse_specialdict[worst_special]
            if status == "zombie":
                status = "zombify"
            elif status[-2:] == "ed":
                status = status[:-2]
            elif status[-1] == "e":
                status = status[:-1]
            return status

    if all_skills:
        worst_skill = max(all_skills, key=lambda s: s.rank())
        return worst_skill.name + "-"

    return "battl"
