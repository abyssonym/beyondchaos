from utils import (hex2int, write_multi, read_multi, ENEMY_TABLE,
                   mutate_index, utilrandom as random)
from skillrandomizer import SpellBlock
from itemrandomizer import get_ranked_items


stat_order = ['speed', 'attack', 'hit%', 'evade%', 'mblock%',
              'def', 'mdef', 'mpow']
all_spells = None
valid_spells = None
items = None
itemids = None
unrageable = [0x7E, 0x7F, 0x80, 0x81]
HIGHEST_LEVEL = 77
xps = []
gps = []


def get_item_normal():
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

    @property
    def is_boss(self):
        return self.pointer > 0xF1FC0

    @property
    def boss_death(self):
        return "".join(map(chr, [0xF5, 0x0C, 0x01, 0xFF])) in self.aiscript

    @property
    def battle_event(self):
        return chr(0xF7) in self.aiscript

    def set_id(self, i):
        self.id = i

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
        global all_spells, valid_spells, items, itemids, HIGHEST_LEVEL

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
        valid_spells = filter(lambda sb: sb.spellid not in unrageable and
                              not sb.abort_on_allies, all_spells)

        f.close()

        self.read_ai(filename)

        if items is None:
            items = get_ranked_items(filename)
            itemids = [i.itemid for i in items]

    def read_ai(self, filename):
        f = open(filename, 'r+b')
        pointer = self.ai + 0xF8700
        f.seek(pointer)
        seen = False
        script = ""
        while True:
            value = f.read(1)
            script += value
            if ord(value) == 0xFF:
                if 0xFC in map(ord, script[-4:]):
                    continue
                if 0xF5 in map(ord, script[-4:]):
                    continue
                #if script[-4:] == "".join(map(chr, [0xF5, 0x0C, 0x01, 0xFF])):
                #    continue
                if seen:
                    break
                else:
                    seen = True
        self.aiscript = script
        return script

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

        f.seek(self.aiptr)
        write_multi(f, self.ai, length=2)

        f.close()

    def screw_vargas(self):
        if 'vargas' in self.name.lower():
            self.stats['hp'] = 1000 + random.randint(0, 400) + random.randint(0, 400)

    def mutate_misc(self):
        # invert "escapable" bit
        if self.is_boss:
            if random.randint(1, 200) == 200:
                self.misc2 = self.misc2 ^ 0x08
        elif random.randint(1, 30) == 30:
            self.misc2 = self.misc2 ^ 0x08

        if random.randint(1, 10) == 10:
            self.misc2 = self.misc2 ^ 0x10  # invert scan bit

        if random.randint(1, 20) == 20:
            self.misc1 = self.misc1 ^ 0x80  # invert undead bit

    def mutate_stats(self):
        level = self.stats['level']

        def level_boost(value, limit=0xFE):
            low = value
            high = int(value + (value * (level / 100.0)))
            diff = high - low
            value = value + random.randint(0, diff) + random.randint(0, diff)
            if value & 0xFF == 0xFF:
                value = value - 1

            return min(value, limit)

        for stat in ['speed', 'attack', 'hit%', 'evade%', 'mblock%',
                     'def', 'mdef', 'mpow']:
            boosted = level_boost(self.stats[stat])
            if stat in ['def', 'mdef']:
                boosted = (self.stats[stat] + boosted) / 2.0
            self.stats[stat] = int(boosted)

        self.stats['hp'] = level_boost(self.stats['hp'], limit=0x10000)
        if self.stats['hp'] == 0x10000:
            self.statuses[3] |= 0x04  # life3
            self.stats['hp'] = 0xFEFE

        self.stats['mp'] = level_boost(self.stats['mp'], limit=0xFEFE)

        def fuddle(value, limit=0xFEFE):
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
                if self.stats["level"] < 22:
                    continue
                elif random.choice([True, False]):
                    continue

            new_statuses[byte] |= bit
            stacount += -1

        for _ in xrange(100):
            if immcount <= 0:
                break

            byte = random.choice([0, 1])
            bit = 1 << random.randint(0, 7)

            status = bitdict[(byte, bit)]
            if new_immunities[byte] & bit:
                continue
            if new_statuses[byte] & bit:
                continue

            new_immunities[byte] |= bit
            immcount += -1

        self.statuses = new_statuses
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

        new_items = []
        for i in self.items:
            if i == 0xFF:
                i = random.choice(self.items + ([0xFF] * 4))
                if i == 0xFF:
                    new_items.append(0xFF)
                    continue

            index = itemids.index(i)
            index = mutate_index(index, len(itemids),
                                 [False, False, False, True],
                                 (-3, 3), (-2, 2))

            new_items.append(itemids[index])

        self.items = new_items

    def level_rank(self):
        level = self.stats['level']
        rank = float(level) / HIGHEST_LEVEL
        return rank

    def get_item_appropriate(self):
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

        return temp[index]

    def get_gp_appropriate(self):
        rank = self.level_rank()
        temp = [b for (a, b) in xps if a >= self.stats['level'] and b > 0]
        temp.sort()
        index = int(len(temp) * rank)
        index = mutate_index(index, len(temp),
                             [False, True],
                             (-2, 2), (-1, 1))

        return temp[index]

    def treasure_boost(self):
        def fuddle(value, limit=0xFEFE):
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

        new_items = []
        for i in self.items:
            if i == 0xFF:
                i = self.get_item_appropriate().itemid
                i = random.choice(sorted(set(self.items + new_items + [i, 0xFF])))
                if i == 0xFF:
                    new_items.append(0xFF)
                    continue

            index = itemids.index(i)
            index = mutate_index(index, len(itemids),
                                 [False, True],
                                 (-1, 3), (-1, 2))

            new_items.append(itemids[index])

        self.items = new_items

    def mutate_metamorph(self):
        # mutates both metamorph template and miss ratio
        self.morph = random.randint(0, 0xEF)
        if self.immunities[0] & 0x80 and random.randint(1, 50) != 50:
            self.morph |= 0xE0

    def mutate_control(self):
        # shuffle skills between control, sketch, rage
        candidates = self.controls + self.sketches
        if not self.is_boss:
            candidates += self.rages
        candidates = set(candidates)
        candidates.add(0xEE)
        candidates.add(0xEF)
        if 0xFF in candidates:
            candidates.remove(0xFF)

        if random.randint(1, 10) >= 9:
            index = None
            while index is None or index in unrageable:
                median = len(valid_spells) / 2
                index = random.randint(0, median) + random.randint(0, median)
                index = min(index, len(valid_spells) - 1)
                sb = valid_spells[index]
            candidates.add(sb.spellid)

        candidates = sorted(candidates)
        self.controls = sorted(random.sample(candidates,
                                             min(4, len(candidates))))
        self.sketches = random.sample(candidates, 2)
        if not self.is_boss:
            self.rages = random.sample(candidates, 2)

        while len(self.controls) < 4:
            self.controls.append(0xFF)

    def mutate_special(self):
        branch = random.randint(1, 10)
        if branch <= 7:
            # regular special
            valid = set(range(0, 0x0F))
            if random.randint(1, 1000) != 1000:
                valid.remove(0x03)  # Magitek
            valid.remove(0x0A)  # image
            valid.add(0x19)  # frozen
            valid = valid | set([0x40 | v for v in list(valid)])  # no damage
            valid.add(0x30)  # absorb HP
            valid.add(0x31)  # absorb MP
            special = random.choice(sorted(valid))
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
            valid.remove(0x19)  # frozen
            valid.add(0x0A)  # image
            special = random.choice(sorted(valid))
        self.special = special

    def mutate(self):
        self.mutate_stats()
        self.mutate_misc()
        self.mutate_control()
        if random.randint(1, 10) > 7:
            self.mutate_statuses()
        if random.randint(1, 10) > 6:
            self.mutate_affinities()
        if random.randint(1, 10) > 5:
            self.mutate_special()

    def swap_ai(self, other):
        if self.boss_death != other.boss_death:
            return
        for attribute in ["ai", "controls", "sketches", "rages"]:
            a, b = getattr(self, attribute), getattr(other, attribute)
            setattr(self, attribute, b)
            setattr(other, attribute, a)

    def swap_stats(self, other):
        attributes = ["stats", "misc2", "absorb", "null",
                      "weakness", "special", "morph", "items"]
        samplesize = random.randint(1, len(attributes))
        for attribute in random.sample(attributes, samplesize):
            a, b = getattr(self, attribute), getattr(other, attribute)
            setattr(self, attribute, b)
            setattr(other, attribute, a)

    def copy_all(self, other, everything=True):
        attributes = [
            "ai", "controls", "sketches", "stats", "misc2", "absorb",
            "null", "weakness", "special", "morph", "items", "misc1",
            "immunities", "statuses"]
        if not everything:
            samplesize = random.randint(0, len(attributes))
            attributes = random.sample(attributes, samplesize)
            if "ai" in attributes:
                attributes.remove("ai")

        for attribute in attributes:
            value = getattr(other, attribute)
            if value is not None:
                value = type(value)(value)
            setattr(self, attribute, value)

        if self.rages is not None and other.rages is not None and random.choice([True, False]):
            self.rages = type(other.rages)(other.rages)


def get_ranked_monsters(filename, bosses=True):
    from randomizer import monsters_from_table
    monsters = monsters_from_table(ENEMY_TABLE)
    for m in monsters:
        m.read_stats(filename)

    if not bosses:
        monsters = filter(lambda m: m.id <= 0xFF, monsters)
    monsters = sorted(monsters, key=lambda i: i.stats['level'])

    return monsters


def shuffle_monsters(monsters):
    monsters = sorted(monsters, key=lambda i: i.stats['level'])
    monsters = [m for m in monsters if m.name.strip('_')]
    bosses = [m for m in monsters if m.is_boss]
    nonbosses = [m for m in monsters if not m.is_boss]
    for m in monsters:
        if m.is_boss:
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

        if m.is_boss:
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
            self.negabit = color & 0x8000
            self.palette_data.append((red, green, blue))
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
        for red, green, blue in self.palette_data:
            color = 0x00
            color |= red
            color |= (green << 5)
            color |= (blue << 10)
            write_multi(f, color, length=2)
        f.close()

    def mutate_palette(self, alternatives=None):
        numcolors = len(self.palette_data)
        assert len(self.palette_data) == numcolors
        colorsets = {}
        palette_dict = dict(enumerate(self.palette_data))
        for n, (red, green, blue) in palette_dict.items():
            key = (red >= green, red >= blue, green >= blue)
            if key not in colorsets:
                colorsets[key] = []
            colorsets[key].append(n)

        pastswap = []
        for key in colorsets:
            degree = random.randint(-75, 75)

            while True:
                swapcode = random.randint(0, 7)
                if swapcode not in pastswap or random.randint(1, 10) == 10:
                    break

            pastswap.append(swapcode)
            f = lambda w: w
            g = lambda w: w
            h = lambda w: w
            if swapcode & 1:
                f = lambda (x, y, z): (y, x, z)
            if swapcode & 2:
                g = lambda (x, y, z): (z, y, x)
            if swapcode & 4:
                h = lambda (x, y, z): (x, z, y)
            swapfunc = lambda w: f(g(h(w)))

            for n in colorsets[key]:
                red, green, blue = palette_dict[n]
                low, medium, high = tuple(sorted([red, green, blue]))
                if degree < 0:
                    value = low
                else:
                    value = high
                degree = abs(degree)
                a = (1 - (degree/90.0)) * medium
                b = (degree/90.0) * value
                medium = a + b
                medium = int(round(medium))
                assert low <= medium <= high
                palette_dict[n] = swapfunc((low, medium, high))

        self.palette_data = tuple([palette_dict[i] for i in range(len(palette_dict))])


class MetamorphBlock:
    def __init__(self, pointer):
        self.pointer = pointer

    def read_data(self, filename):
        global items
        if items is None:
            items = get_ranked_items(filename)

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
