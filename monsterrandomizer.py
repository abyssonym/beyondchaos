from utils import (hex2int, write_multi, read_multi, ENEMY_TABLE,
                   name_to_bytes, get_palette_transformer, mutate_index,
                   utilrandom as random)
from skillrandomizer import SpellBlock, get_spell, get_ranked_spells
from itemrandomizer import get_ranked_items, get_item
from namerandomizer import generate_attack


stat_order = ['speed', 'attack', 'hit%', 'evade%', 'mblock%',
              'def', 'mdef', 'mpow']
all_spells = None
HIGHEST_LEVEL = 77
xps = []
gps = []
AICODES = {0xF0: 3, 0xF1: 1, 0xF2: 3, 0xF3: 2,
           0xF4: 3, 0xF5: 3, 0xF6: 3, 0xF7: 1,
           0xF8: 2, 0xF9: 3, 0xFA: 2, 0xFB: 2,
           0xFC: 3, 0xFD: 0, 0xFE: 0, 0xFF: 0
           }
monsterdict = {}

globalweights, avgs = None, {}


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
            line = map(lambda i: int(i, 0x10), line)
            aiscripts[name].append(line)
    for key, aiscript in aiscripts.items():
        aiscript = ["".join(map(chr, action)) for action in aiscript]
        aiscripts[key] = aiscript
    return aiscripts


def get_item_normal():
    items = get_ranked_items()
    base = ((len(items)-1) / 2)
    index = random.randint(0, base) + random.randint(0, base)
    if len(items) > (base * 2) + 1:
        index += random.randint(0, 1)
    ranked_items = sorted(items, key=lambda i: i.rank())
    item = ranked_items[index]
    return item


class MonsterBlock:
    def __init__(self, name, pointer, itemptr, controlptr,
                 sketchptr, rageptr, aiptr):
        self.name = name
        self.graphicname = self.name
        self.pointer = hex2int(pointer)
        self.itemptr = hex2int(itemptr)
        self.controlptr = hex2int(controlptr)
        self.sketchptr = hex2int(sketchptr)
        self.rageptr = hex2int(rageptr)
        self.aiptr = hex2int(aiptr)
        self.stats = {}
        self.moulds = set([])
        self.width, self.height = None, None
        self.miny, self.maxy = None, None
        self.aiscript = None
        self.ambusher = False

    @property
    def description(self):
        s = "%s (%s)\n" % (self.display_name, self.stats['level'])

        steals = [i.name for i in self.steals if i]
        drops = [i.name for i in self.drops if i]
        s += ("Steal: %s" % ", ".join(steals)).strip() + "\n"
        s += ("Drop: %s" % ", ".join(drops)).strip() + "\n"
        if self.rages:
            rages = [get_spell(r).name for r in self.rages]
            s += "Rage: %s\n" % ", ".join(rages)

        return s

    @property
    def display_name(self):
        if hasattr(self, "changed_name"):
            return self.changed_name.strip('_')
        else:
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
        return "".join(map(chr, [0xF5, 0x0C, 0x01, 0xFF])) in self.aiscript

    @property
    def battle_event(self):
        return chr(0xF7) in [s[0] for s in self.aiscript]

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
        else:
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

    def randomize_special_effect(self, filename):
        attackpointer = 0xFD0D0 + (self.id * 10)
        f = open(filename, 'r+b')
        f.seek(attackpointer)
        attack = generate_attack()
        attack = name_to_bytes(attack, 10)
        f.write("".join(map(chr, attack)))

        f.seek(self.specialeffectpointer)
        f.write(chr(random.randint(0, 0x21)))
        f.close()

        options = sorted(set(range(0, 0x5A)) - set([0, 0x1C]))
        self.attackanimation = random.choice(options)

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
        self.immunities = map(ord, f.read(3))
        self.absorb = ord(f.read(1))
        self.null = ord(f.read(1))
        self.weakness = ord(f.read(1))

        f.seek(self.pointer + 26)
        self.attackanimation = ord(f.read(1))

        f.seek(self.pointer + 27)
        self.statuses = map(ord, f.read(4))
        self.special = ord(f.read(1))

        f.seek(self.itemptr)
        self.items = map(ord, f.read(4))

        f.seek(self.controlptr)
        self.controls = map(ord, f.read(4))

        f.seek(self.sketchptr)
        self.sketches = map(ord, f.read(2))

        if not self.is_boss:
            f.seek(self.rageptr)
            self.rages = map(ord, f.read(2))
        else:
            self.rages = None

        f.seek(self.aiptr)
        self.ai = read_multi(f, length=2)

        if all_spells is None:
            all_spells = sorted([SpellBlock(i, filename) for i in xrange(0xFF)],
                                key=lambda s: s.rank())

        f.close()

        self.read_ai(filename)

    def get_skillset(self, ids_only=True):
        skillset = set([])
        skillset.add(0xEE)
        skillset.add(0xEF)
        skillset.add(0xFE)
        for action in self.aiscript:
            action = map(ord, action)
            if action[0] & 0xF0 == 0xF0:
                if action[0] == 0xF0:
                    for s in action[1:]:
                        skillset.add(s)
            else:
                skillset.add(action[0])

        if not ids_only:
            skillset = [s for s in all_spells if s.spellid in skillset]
        return sorted(skillset)

    def set_minimum_mp(self):
        skillset = self.get_skillset(ids_only=False)
        factor = random.uniform(1.0, 2.0)
        self.stats['mp'] = int(
            round(max(self.stats['mp'], factor * max(s.mp for s in skillset))))

    def mutate_ai(self, change_skillset=True, itembreaker=False):
        if self.name[:2] == "L." or "guardian" in self.name.lower():
            return

        skillset = set(self.get_skillset())

        def similar(s1, s2):
            a = s1.target_enemy_default == s2.target_enemy_default
            b = s1.target_everyone == s2.target_everyone
            c = s1.target_dead == s2.target_dead
            d = s1.healing == s2.healing
            e = s1.unreflectable == s2.unreflectable
            f = s1.abort_on_allies == s2.abort_on_allies
            return (a and b and c and d and e and f)

        oldskills = sorted([s for s in all_spells if s.spellid in skillset],
                           key=lambda s: s.rank())
        if change_skillset:
            for skill in oldskills:
                if skill.spellid in [0xEE, 0xEF, 0xFE]:
                    continue
                if not skill.valid:
                    continue
                skillset.remove(skill.spellid)
                candidates = [s for s in all_spells if similar(s, skill)]
                candidates = [s for s in candidates if not
                              (s.is_blitz or s.is_swdtech or s.is_esper
                               or s.is_slots)]
                if skill not in candidates:
                    candidates.append(skill)
                candidates = sorted(candidates, key=lambda s: s.rank())
                if random.choice([True, False]):
                    candidates = [c for c in candidates if c.valid]

                index = candidates.index(skill)
                index = mutate_index(index, len(candidates), [False, True],
                                     (-2, 3), (-2, 2))
                skill = candidates[index]
                skillset.add(skill.spellid)

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
            index = a.index(skill)
            index = mutate_index(index, len(b), [False, True],
                                 (-1, 2), (-1, 1))
            newskill = b[index]
            if not newskill.valid:
                return spellid
            return newskill.spellid

        targeting = None
        newscript = []
        for action in self.aiscript:
            action = map(ord, action)
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
                            step = value / 2
                            value = (step + random.randint(0, step) +
                                     random.randint(0, step/2))
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
                        newaction = list(action)
                        if len(set(action[1:])) != 1:
                            for i in xrange(1, 4):
                                a = newaction[i]
                                if a == 0xFE:
                                    a = random.choice(action[1:])
                                value = mutate_action_skill(a)
                                newaction[i] = value
                            if len(set(newaction[1:])) == 1:
                                newaction = action
                        action[1:] = sorted(newaction[1:])
                        assert 0x81 not in action
            newscript.append("".join(map(chr, action)))

        assert len("".join(newscript)) == len("".join(self.aiscript))
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
                args = ""
            script.append(value + args)
            if ord(value) == 0xFF:
                if seen:
                    break
                else:
                    seen = True

        self.aiscript = script
        return self.aiscript

    def set_relative_ai(self, pointer):
        self.ai = pointer - 0xF8700

    @property
    def aiscriptsize(self):
        return len("".join(self.aiscript))

    def write_ai(self, filename):
        for (i, action) in enumerate(self.aiscript):
            if (len(action) == 4 and action[0] == chr(0xf0) and
                    action[1] == chr(0x55)):
                # fix Cyan's AI at imperial camp
                action = "".join(map(chr, [0xF0, 0xEE, 0xEE, 0xEE]))
                self.aiscript[i] = action
        f = open(filename, 'r+b')
        f.seek(self.aiptr)
        write_multi(f, self.ai, length=2)
        pointer = self.ai + 0xF8700
        f.seek(pointer)
        f.write("".join(self.aiscript))
        f.close()

    @property
    def humanoid(self):
        return self.misc1 & 0x10

    @property
    def undead(self):
        return self.misc1 & 0x80

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

    def write_stats(self, filename):
        self.set_minimum_mp()

        f = open(filename, 'r+b')
        f.seek(self.pointer)
        for key in stat_order:
            f.write(chr(self.stats[key]))
        write_multi(f, self.stats['hp'], length=2)
        write_multi(f, self.stats['mp'], length=2)
        write_multi(f, self.stats['xp'], length=2)
        write_multi(f, self.stats['gp'], length=2)
        f.write(chr(self.stats['level']))

        f.write(chr(self.morph))
        f.write(chr(self.misc1))
        f.write(chr(self.misc2))

        f.seek(self.pointer + 20)
        for i in self.immunities:
            f.write(chr(i))
        f.write(chr(self.absorb))
        f.write(chr(self.null))
        f.write(chr(self.weakness))

        f.seek(self.pointer + 26)
        f.write(chr(self.attackanimation))

        f.seek(self.pointer + 27)
        for s in self.statuses:
            f.write(chr(s))
        f.write(chr(self.special))

        f.seek(self.itemptr)
        f.write(''.join(map(chr, self.items)))

        f.seek(self.controlptr)
        f.write(''.join(map(chr, self.controls)))

        f.seek(self.sketchptr)
        f.write(''.join(map(chr, self.sketches)))

        if not self.is_boss:
            f.seek(self.rageptr)
            f.write(''.join(map(chr, self.rages)))

        f.close()
        self.write_ai(filename)

    def screw_tutorial_bosses(self):
        name = self.name.lower().strip('_')
        if name == 'vargas':
            self.stats['hp'] = 900 + random.randint(0, 100) + random.randint(0, 100)
        if name == 'tunnelarmr':
            self.stats['hp'] = 1000 + random.randint(0, 150) + random.randint(0, 150)
        if name == "leader":
            self.stats['hp'] = 400 + random.randint(0, 50) + random.randint(0, 50)

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
            value = value + random.randint(0, diff) + random.randint(0, diff)
            if value & 0xFF == 0xFF:
                value = value - 1

            return min(value, limit)

        for stat in ['speed', 'attack', 'hit%', 'evade%', 'mblock%',
                     'def', 'mdef', 'mpow']:
            if stat in ['speed']:
                limit = 230
            else:
                limit = 0xFF
            boosted = level_boost(self.stats[stat], limit=limit)
            if stat in ['def', 'mdef']:
                boosted = (self.stats[stat] + boosted) / 2.0
            self.stats[stat] = int(boosted)

        self.stats['hp'] = level_boost(self.stats['hp'], limit=0x10000)
        if self.stats['hp'] == 0x10000:
            self.statuses[3] |= 0x04  # life3
            self.stats['hp'] = 0xFFFF

        self.stats['mp'] = level_boost(self.stats['mp'], limit=0xFFFF)

        def fuddle(value, limit=0xFFFF):
            low = value / 2
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
        statusdict = {"blind": (0, 0x01),
                      "zombie": (0, 0x02),
                      "poison": (0, 0x04),
                      "magitek": (0, 0x08),
                      "clear": (0, 0x10),
                      "imp": (0, 0x20),
                      "petrify": (0, 0x40),
                      "dead": (0, 0x80),
                      "condemned": (1, 0x01),
                      "critical": (1, 0x02),
                      "image": (1, 0x04),
                      "mute": (1, 0x08),
                      "berserk": (1, 0x10),
                      "muddle": (1, 0x20),
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
                      "true knight": (3, 0x01),
                      "runic": (3, 0x02),
                      "life3": (3, 0x04),
                      "morph": (3, 0x08),
                      "casting": (3, 0x10),
                      "disappear": (3, 0x20),
                      "interceptor": (3, 0x40),
                      "float (rhizopas)": (3, 0x80)}
        bitdict = dict((y, x) for (x, y) in statusdict.items())

        for _ in xrange(100):
            if stacount <= 0:
                break

            byte = random.randint(0, 3)
            bit = 1 << random.randint(0, 7)
            if new_statuses[byte] & bit:
                continue

            status = bitdict[(byte, bit)]
            if status in ["zombie", "magitek", "petrify", "dead", "disappear"]:
                if self.is_boss or random.randint(1, 1000) != 1000:
                    continue
            if status in ["condemned", "mute", "berserk",
                          "stop", "muddle", "sleep"]:
                if self.is_boss and random.randint(1, 100) != 100:
                    continue
                elif not self.is_boss and random.randint(1, 10) != 10:
                    continue
            if status in ["life3", "runic", "true knight", "image"]:
                if random.randint(1, 10) != 10:
                    continue
            if status in ["blind", "poison", "imp", "seizure", "slow"]:
                if self.is_boss and random.randint(1, 10) != 10:
                    continue
                elif not self.is_boss and random.choice([True, False]):
                    continue
            if status in ["clear", "image"]:
                if self.stats["level"] < 22 or self.id in [0x11a, 0x12a]:
                    continue
                elif random.choice([True, False]):
                    continue

            new_statuses[byte] |= bit
            stacount += -1

        for _ in xrange(100):
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
            for i in xrange(len(self.immunities)):
                self.immunities[i] |= new_immunities[i]
        else:
            self.immunities = new_immunities

    def mutate_affinities(self):
        abscount = bin(self.absorb).count('1') + 1
        while random.randint(1, 10) == 10:
            abscount += random.choice([1, -1])
        abscount = min(8, max(abscount, 0))

        nullcount = bin(self.null).count('1') + 1
        while random.randint(1, 10) == 10:
            nullcount += random.choice([1, -1])
        nullcount = min(8, max(nullcount, 0))

        weakcount = bin(self.weakness).count('1')
        while random.randint(1, 10) == 10:
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
            low = value / 2
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
                                 (-1, 3), (-1, 2))

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
            index = None
            while index is None:
                median = len(valid_spells) / 2
                index = random.randint(0, median) + random.randint(0, median)
                index = min(index, len(valid_spells) - 1)
                sb = valid_spells[index]
            candidates.add(sb.spellid)

        candidates = sorted(candidates)
        self.controls = random.sample(candidates, min(4, len(candidates)))
        while len(self.controls) < 4:
            self.controls += [random.choice(candidates)]
        self.controls = sorted(self.controls)

        valid_spells = [v for v in valid_spells if not v.unrageable]

        def get_good_selection(candidates, numselect, minimum=2):
            candidates = [c for c in candidates if not get_spell(c).unrageable]
            if self.deadspecial and 0xEF in candidates:
                candidates.remove(0xEF)
            while True:
                if len(candidates) >= minimum:
                    break
                elif len(candidates) == 2 and not self.physspecial:
                    break
                index = (random.randint(0, len(valid_spells)/2) +
                         random.randint(0, len(valid_spells)/2))
                index = min(index, len(valid_spells) - 1)
                value = valid_spells[index].spellid
                candidates.append(value)
                candidates = sorted(set(candidates))
            for _ in xrange(2):
                selection = random.sample(candidates, numselect)
                if not self.physspecial:
                    break
                if set(selection) != set([0xEE, 0xEF]):
                    break
            return sorted(selection)

        self.sketches = get_good_selection(candidates, 2)
        if not self.is_boss:
            candidates = sorted(set(candidates) | set([0xEE, 0xEF]))
            self.rages = get_good_selection(candidates, 2, minimum=3)

        while len(self.controls) < 4:
            self.controls.append(0xFF)

    @property
    def goodspecial(self):
        good = set(range(10, 0x1F))
        good.remove(0x12)  # slow
        good.remove(0x14)  # stop
        good.remove(0x19)  # frozen
        good.remove(0x1D)  # disappear
        good.add(0x04)  # vanish
        good.add(0x0A)  # image
        return self.special in good

    @property
    def physspecial(self):
        return bool(self.special & 0x20)

    @property
    def deadspecial(self):
        return (self.special & 0x2F) == 0x07

    def mutate_special(self):
        if self.goodspecial:
            return

        branch = random.randint(1, 10)
        if branch <= 7:
            # regular special
            valid = set(range(0, 0x0F))
            if random.randint(1, 1000) != 1000:
                valid.remove(0x03)  # Magitek
            valid.remove(0x04)  # vanish
            valid.remove(0x0A)  # image
            valid.add(0x12)  # slow
            valid.add(0x14)  # stop
            valid.add(0x19)  # frozen
            valid.add(0x30)  # absorb HP
            valid.add(0x31)  # absorb MP
            special = random.choice(sorted(valid))
            if special == 0x07 or (special not in [0x30, 0x31] and
                                   random.choice([True, False])):
                special |= 0x40  # no HP damage
        if branch <= 9:
            # physical special
            factor = int(self.stats['level'] * 16 / 99.0) + 1
            power = random.randint(0, factor) + random.randint(0, factor)
            power = max(power, 0x00)
            power = min(power, 0x0F)
            special = 0x20 + power
        elif branch >= 10:
            # bonus special
            valid = set(range(10, 0x1F))
            if not self.is_boss or random.randint(1, 1000) != 1000:
                valid.remove(0x1D)  # disappear
                valid.remove(0x1E)  # Interceptor
            if random.randint(1, 10) != 10:
                valid.remove(0x10)  # dance
                valid.remove(0x18)  # rage
            valid.remove(0x12)  # slow
            valid.remove(0x14)  # stop
            valid.remove(0x19)  # frozen
            valid.add(0x04)  # vanish
            valid.add(0x0A)  # image
            special = random.choice(sorted(valid))

        if random.randint(1, 4) == 4:
            special |= 0x80  # unblockable
        self.special = special

    def mutate(self, change_skillset=None, itembreaker=False):
        if change_skillset is None:
            change_skillset = not (self.is_boss or self.boss_death)
        self.mutate_stats()
        self.mutate_misc()
        if random.randint(1, 10) > 7:
            self.mutate_statuses()
        if random.randint(1, 10) > 6:
            self.mutate_affinities()
        if random.randint(1, 10) > 5:
            # do this before mutate_control
            self.mutate_special()
        value = random.randint(1, 10)
        if value > 1:
            if value == 2:
                self.mutate_ai(change_skillset=False,
                               itembreaker=itembreaker)
            else:
                self.mutate_ai(change_skillset=change_skillset,
                               itembreaker=itembreaker)
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
            setattr(self, attribute, value)

        if self.rages is not None and other.rages is not None and random.choice([True, False]):
            self.rages = type(other.rages)(other.rages)

    def itemrank(self):
        items = self.items
        items = [get_item(i) for i in items]
        items = [i.rank() if i else 0 for i in items]
        itemrank = items[0] + (items[1]*7) + ((items[2] + (items[3]*7))*2)
        return itemrank / 32.0

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
        funcs['itemrank'] = lambda m: max(1, m.itemrank())

        if not avgs:
            monsters = get_monsters()
            monsters = [m for m in monsters if not (m.is_boss or m.boss_death)]
            for key in funcs:
                avgs[key] = (sum(funcs[key](m) for m in monsters) /
                             float(len(monsters)))

        if weights is None:
            if globalweights is None:
                globalweights = [random.randint(0, 50) + random.randint(0, 50) for _ in avgs]
            weights = globalweights
        elif isinstance(weights, int):
            weights = [50 for _ in avgs]

        weights = dict(zip(sorted(avgs.keys()), weights))
        LEVELFACTOR, HPFACTOR = len(avgs)*2, len(avgs)
        total = 0
        for key in sorted(avgs):
            if key == "level":
                weights[key] = max(50, weights[key])
            weighted = weights[key] * funcs[key](self) / avgs[key]
            if key == "level":
                weighted *= LEVELFACTOR
            elif key == "hp":
                weighted *= HPFACTOR
            total += weighted

        return total

    def dummy_item(self, item):
        if item.itemid in self.items:
            self.items = [i if i != item.itemid else 0xFF for i in self.items]
            return True
        return False


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


def get_monsters(filename=None):
    if monsterdict:
        return sorted(monsterdict.values(), key=lambda m: m.id)

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
        monsters = filter(lambda m: m.id <= 0xFF, monsters)
    monsters = sorted(monsters, key=lambda m: m.rank())
    return monsters


def shuffle_monsters(monsters):
    monsters = sorted(monsters, key=lambda m: m.rank())
    monsters = [m for m in monsters if m.name.strip('_')]
    bosses = [m for m in monsters if m.is_boss or m.boss_death]
    nonbosses = [m for m in monsters if m not in bosses]
    for m in monsters:
        if m.is_boss or m.boss_death:
            candidates = bosses
        else:
            candidates = nonbosses
        index = candidates.index(m)

        def get_swap_index(to_swap):
            to_swap = mutate_index(index, len(candidates),
                                   [False, False, True],
                                   (-5, 5), (-3, 3))
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
            m.swap_ai(candidates[to_swap])


palette_pools = {}


class MonsterGraphicBlock:
    def __init__(self, pointer, name=None):
        self.pointer = pointer
        self.name = name

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
        self.palette_data = []
        self.palette_values = []
        numcolors = 0x20

        for i in xrange(numcolors):
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
            if all(map(lambda (a, b): a == b, zip(self.palette_data, p))):
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

    def write_data(self, filename, palette_pointer=None):
        if palette_pointer is None:
            palette_pointer = self.palette_pointer
            palette = self.palette
        else:
            self.palette_pointer = palette_pointer
            palette = (palette_pointer - 0x127820) / 0x10
            self.palette = palette

        if self.large:
            palette |= 0x8000
        else:
            palette &= 0x7FFF

        if palette_pointer > 0x12a800:
            raise Exception("Palette pointer out of bounds.")

        f = open(filename, 'r+b')
        f.seek(self.pointer)
        write_multi(f, self.graphics, length=2)
        f.seek(self.pointer+2)
        write_multi(f, palette, length=2, reverse=False)
        f.seek(self.pointer+4)
        f.write(chr(self.size_template))
        f.seek(palette_pointer)
        for color in self.palette_data:
            write_multi(f, color, length=2)
        f.close()

    def mutate_palette(self, alternatives=None):
        transformer = get_palette_transformer(basepalette=self.palette_data)
        self.palette_data = transformer(self.palette_data)


class MetamorphBlock:
    def __init__(self, pointer):
        self.pointer = pointer

    def read_data(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.pointer)
        self.items = map(ord, f.read(4))
        f.close()

    def write_data(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.pointer)
        f.write("".join(map(chr, self.items)))
        f.close()

    def mutate_items(self):
        for i in xrange(4):
            self.items[i] = get_item_normal().itemid

    def dummy_item(self, item):
        if item.itemid in self.items:
            while item.itemid in self.items:
                self.items = [i for i in self.items if i != item.itemid]
                if self.items == []:
                    self.items = [get_item_normal().itemid for _ in xrange(4)]

            while len(self.items) < 4:
                self.items.append(random.choice(self.items))
            return True

        return False
