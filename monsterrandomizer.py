from utils import hex2int, write_multi, read_multi, ENEMY_TABLE
from skillrandomizer import SpellBlock
from itemrandomizer import get_ranked_items
from itertools import izip
import random


stat_order = ['speed', 'attack', 'hit%', 'evade%', 'mblock%',
              'def', 'mdef', 'mpow']
all_spells = None
valid_spells = None
items = None
itemids = None
unrageable = [0x7E, 0x7F, 0x80, 0x81]


class MonsterBlock:
    def __init__(self, name, pointer, itemptr, controlptr, sketchptr, rageptr):
        self.name = name
        self.pointer = hex2int(pointer)
        self.itemptr = hex2int(itemptr)
        self.controlptr = hex2int(controlptr)
        self.sketchptr = hex2int(sketchptr)
        self.rageptr = hex2int(rageptr)
        self.is_boss = self.pointer > 0xF1FC0
        self.stats = {}

    def set_id(self, i):
        self.id = i

    def read_stats(self, filename):
        global all_spells, valid_spells, items, itemids

        f = open(filename, 'r+b')
        f.seek(self.pointer)
        for key in stat_order:
            self.stats[key] = ord(f.read(1))
        self.stats['hp'] = read_multi(f, length=2)
        self.stats['mp'] = read_multi(f, length=2)
        self.stats['xp'] = read_multi(f, length=2)
        self.stats['gp'] = read_multi(f, length=2)
        self.stats['level'] = ord(f.read(1))

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

        f.seek(self.rageptr)
        self.rages = map(ord, f.read(2))

        if all_spells is None:
            all_spells = sorted([SpellBlock(i, filename) for i in xrange(0xFF)],
                                key=lambda s: s.rank())
        valid_spells = filter(lambda sb: sb.spellid not in unrageable and
                              not sb.abort_on_allies, all_spells)

        f.close()

        if items is None:
            items = get_ranked_items(filename)
            itemids = [i.itemid for i in items]

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

        f.seek(self.rageptr)
        f.write(''.join(map(chr, self.rages)))

        f.close()

    def screw_vargas(self):
        if 'vargas' in self.name.lower():
            self.stats['hp'] = 1000 + random.randint(0, 400) + random.randint(0, 400)

    def mutate_misc(self):
        # invert "escapable" bit
        if self.is_boss:
            if random.randint(1, 200) == 100:
                self.misc2 = self.misc2 ^ 0x08
        elif random.randint(1, 15) == 15:
            self.misc2 = self.misc2 | 0x08

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
        while random.randint(1, 5) == 5:
            immcount += random.choice([1, -1])
        immcount = min(24, max(immcount, 0))

        stacount = sum([bin(v).count('1') for v in self.statuses])
        stacount += 1
        while random.randint(1, 5) == 5:
            stacount += random.choice([1, -1])
        stacount = min(29, max(immcount, 0))

        new_immunities = [0x00] * 3
        new_statuses = [0x00] * 4
        while stacount > 0:
            byte = random.randint(0, 3)
            bit = 1 << random.randint(0, 7)
            if byte == 0 and bit in [0x02, 0x08, 0x40, 0x80]:
                # zombie, magitek, petrify, dead
                continue

            if new_statuses[byte] & bit:
                continue

            new_statuses[byte] = new_statuses[byte] ^ bit
            if byte <= 2 and random.randint(1, 10) > 3:
                new_immunities[byte] = new_immunities[byte] | bit
            stacount += -1

        while immcount > 0:
            byte = random.randint(0, 2)
            bit = 1 << random.randint(0, 7)
            new_immunities[byte] = new_immunities[byte] | bit
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
                    continue

            index = itemids.index(i)
            while random.randint(1, 4) == 4:
                index += random.randint(-3, 3)
                index = max(0, min(index, len(itemids)-1))

            new_items.append(itemids[index])

        self.items = new_items

    def mutate_metamorph(self):
        # mutates both metamorph template and miss ratio
        self.morph = random.randint(0, 0xFF)

    def mutate_control(self):
        # shuffle skills between control, sketch, rage
        candidates = set(self.controls + self.sketches + self.rages)
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

        candidates = list(candidates)
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
            valid.remove(0x03)
            valid.remove(0x0A)
            valid.add(0x19)
            valid.add(0x30)
            valid.add(0x31)
            special = random.choice(list(valid))
        if branch <= 9:
            # physical special
            factor = int(self.stats['level'] * 16 / 99.0) + 2
            power = random.randint(0, factor) + random.randint(0, factor)
            power = max(power, 0x00)
            power = min(power, 0x0F)
            special = 0x20 + power
        elif branch >= 10:
            # bonus special
            valid = set(range(10, 0x1F))
            valid.remove(0x1E)
            valid.remove(0x19)
            valid.add(0x0A)
            special = random.choice(list(valid))
        self.special = special

    def mutate(self):
        self.mutate_stats()
        self.mutate_misc()
        self.mutate_control()
        if random.randint(1, 10) > 8:
            self.mutate_statuses()
        if random.randint(1, 10) > 8:
            self.mutate_affinities()
        if random.randint(1, 10) > 8:
            self.mutate_special()


def get_ranked_monsters(filename, bosses=True):
    from randomizer import monsters_from_table
    monsters = monsters_from_table(ENEMY_TABLE)
    for m in monsters:
        m.read_stats(filename)

    if not bosses:
        monsters = filter(lambda m: m.id <= 0xFF, monsters)
    monsters = sorted(monsters, key=lambda i: i.stats['level'])

    return monsters


palette_pools = {}
palette_cand_pools = {}


def equalize_pools(mgblocks):
    global palette_pools
    global palette_cand_pools

    def chain_union(key):
        values = palette_pools[key]
        for key2 in list(palette_pools[key]):
            values |= palette_pools[key2]
        for key2 in list(palette_pools[key]):
            palette_pools[key2] |= values
        if values == palette_pools[key]:
            return
        else:
            for key2 in list(palette_pools[key]):
                chain_union(key2)
            chain_union(key)

    for key in palette_pools:
        chain_union(key)

    palette_cand_pools = {}
    for key, graphics in palette_pools.items():
        if key not in palette_cand_pools:
            palette_cands = [m.palette_data for m in mgblocks if m.graphics in graphics]
            palette_cands2 = []
            for p in palette_cands:
                if p in palette_cands2:
                    continue
                palette_cands2.append(p)
            for g in graphics:
                palette_cand_pools[g] = palette_cands2


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
        self.palette_index = self.palette & 0x3FF
        self.palette_pointer = 0x127820 + (self.palette_index * 16)
        f.seek(self.palette_pointer)
        self.palette_data = []
        self.palette_values = []
        for i in xrange(16):
            color = read_multi(f, length=2)
            blue = (color & 0x7c00) >> 10
            green = (color & 0x03e0) >> 5
            red = color & 0x001f
            self.palette_data.append((red, green, blue))
            self.palette_values.append(int(round(sum([red, green, blue])/3.0)))
        self.palette_data = tuple(self.palette_data)
        if self.graphics not in palette_pools:
            palette_pools[self.graphics] = set([])
        palette_pools[self.graphics].add(self.graphics)
        f.close()

    @property
    def poolsize(self):
        global palette_cand_pools
        return len(palette_cand_pools[self.graphics])

    def unite_palette_pools(self, other):
        global palette_pools
        palette_pools[self.graphics] |= palette_pools[other.graphics]
        palette_pools[other.graphics] |= palette_pools[self.graphics]

    def compare_palette_values(self, other, tolerance=3):
        if other.graphics == self.graphics:
            return False

        valmin = min(other.palette_values)
        values = map(lambda x: x - valmin, other.palette_values)
        valmin2 = min(self.palette_values)
        values2 = map(lambda x: x - valmin2, self.palette_values)
        zipped = []
        for a, b in izip(values, values2):
            if abs(a-b) <= tolerance and False:
                avg = (a + b) / 2
                zipped.append((avg, avg))
            else:
                zipped.append((a, b))
        sortzipped = sorted(zipped, key=lambda (x, y): x)
        sortzipped2 = sorted(sortzipped, key=lambda (x, y): y)
        for i, ((a, b), (c, d)) in enumerate(zip(sortzipped, sortzipped2)):
            if a != c or b != d:
                index2 = sortzipped2.index((a, b))
                if abs(i - index2) > (tolerance-1):
                    return False
        palette_pools[self.graphics].add(other.graphics)
        return True

    def write_data(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.palette_pointer)
        for red, green, blue in self.palette_data:
            color = 0x00
            color |= red
            color |= (green << 5)
            color |= (blue << 10)
            write_multi(f, color, length=2)
        f.close()

    def mutate_palette(self, alternatives=None):
        global palette_cand_pools
        self.palette_data = random.choice(palette_cand_pools[self.graphics])
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
        base = ((len(items)-1) / 2)
        for i in xrange(4):
            index = random.randint(0, base) + random.randint(0, base)
            item = items[index]
            self.items[i] = item.itemid
