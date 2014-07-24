from utils import hex2int, write_multi, read_multi
from skillrandomizer import SpellBlock
import random
# future blocks: chests, morphs, shops

ITEM_STATS = ["learnrate", "learnspell", "fieldeffect",
              "statusprotect1", "statusprotect2", "statusacquire3",
              "statboost1", "special1", "statboost2", "special2",
              "special3", "targeting", "elements", "vigorspeed",
              "stammag", "breakeffect", "otherproperties", "power",
              "hitmdef", "elemabsorbs", "elemnulls", "elemweaks",
              "statusacquire2", "evademblock", "specialaction"]

STATPROTECT = {"fieldeffect": 0x7c,
               "statusprotect1": 0x18,
               "statusprotect2": 0x06,
               "statusacquire3": 0x00,
               "statboost1": 0x00,
               "special1": 0x03,
               "statboost2": 0x0e,
               "special2": 0x80,
               "special3": 0x60,
               "otherproperties": 0xdf,
               "statusacquire2": 0x00}

all_spells = None
effects_used = []


def bit_mutate(byte, op="on", nochange=0x00):
    if op == "on":
        bit = 1 << random.randint(0, 7)
        if bit & nochange:
            return byte
        byte = byte | bit
    elif op == "off":
        bit = 1 << random.randint(0, 7)
        if bit & nochange:
            return byte
        bit = 0xff ^ bit
        byte = byte & bit
    elif op == "invert":
        bit = 1 << random.randint(0, 7)
        if bit & nochange:
            return byte
        byte = byte ^ bit
    return byte


class ItemBlock:
    def __init__(self, itemid, pointer, name):
        self.itemid = hex2int(itemid)
        self.pointer = hex2int(pointer)
        self.name = name
        self.degree = None

    def set_degree(self, value):
        self.degree = value

    def read_stats(self, filename):
        global all_spells

        f = open(filename, 'r+b')
        f.seek(self.pointer)
        self.itemtype = ord(f.read(1))

        itemtype = self.itemtype & 0x0f
        (self.is_tool, self.is_weapon, self.is_armor, self.is_relic,
            self.is_consumable) = (False, False, False, False, False)
        self.is_shield, self.is_helm, self.is_body_armor = False, False, False
        if itemtype == 0x00:
            self.is_tool = True
        elif itemtype == 0x01:
            self.is_weapon = True
        elif itemtype in [2, 3, 4]:
            self.is_armor = True
            if itemtype == 3:
                self.is_shield = True
            elif itemtype == 4:
                self.is_helm = True
            elif itemtype == 2:
                self.is_body_armor = True
        elif itemtype == 0x05:
            self.is_relic = True
        elif itemtype == 0x06:
            self.is_consumable = True

        #throwable = self.itemtype & 0x10
        #usable_battle = self.itemtype & 0x20
        #usable_field = self.itemtype & 0x40

        self.equippable = read_multi(f, length=2)

        stats = map(ord, f.read(len(ITEM_STATS)))
        self.features = dict(zip(ITEM_STATS, stats))

        self.price = read_multi(f, length=2)

        if all_spells is None:
            all_spells = sorted([SpellBlock(i, filename) for i in xrange(0xFF)],
                                key=lambda s: s.rank())
            all_spells = filter(lambda s: s.valid, all_spells)

        f.close()

    def write_stats(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.pointer)
        f.write(chr(self.itemtype))

        write_multi(f, self.equippable, length=2)

        f.write("".join(map(chr, [self.features[key] for key in ITEM_STATS])))

        write_multi(f, self.price, length=2)
        f.close()

    def equippable_by(self, charid):
        return self.equippable & (1 << charid)

    def unrestrict(self):
        if self.is_weapon:
            self.itemtype |= 0x10
            self.features['otherproperties'] |= 0x82

    @property
    def imp_only(self):
        return self.equippable & 0x4000

    @property
    def evade(self):
        evademblock = self.features['evademblock']
        evade = evademblock & 0x0f
        return evade

    @property
    def mblock(self):
        evademblock = self.features['evademblock']
        mblock = (evademblock & 0xf0) >> 4
        return mblock

    def pick_a_spell(self, magic_only=False):
        if magic_only:
            spells = filter(lambda s: s.spellid in range(0, 36), all_spells)
        else:
            spells = all_spells

        normal = len(spells)
        if self.degree is not None:
            normal = int(normal * self.degree)
        else:
            normal = int(normal / 4.0)

        right = False
        if normal > len(spells) / 2.0:
            right = True
            normal = len(spells) - normal

        normal = max(normal, 2)
        index = random.randint(0, normal) + random.randint(0, normal)
        while random.randint(1, 10) == 10:
            index = index + random.randint(0, normal)
        index = min(index, len(spells)-1)
        if right:
            index = len(spells) - index - 1
        spell = spells[index]
        return spell, index / float(len(spells))

    def mutate_feature(self):
        if self.is_consumable or self.is_tool:
            return

        feature = random.choice(STATPROTECT.keys())
        self.features[feature] = bit_mutate(self.features[feature], op="on",
                                            nochange=STATPROTECT[feature])

    def mutate_break_effect(self):
        global effects_used
        if self.is_consumable:
            return

        for _ in xrange(100):
            spell, _ = self.pick_a_spell(magic_only=True)
            if spell.spellid not in effects_used:
                effects_used.append(spell.spellid)
                break
        self.features['breakeffect'] = spell.spellid
        if not self.is_weapon or random.randint(1, 2) == 2:
            self.itemtype = self.itemtype | 0x20
        self.features['targeting'] = spell.targeting & 0xef
        #print self.name, spell.name

    def mutate_elements(self):
        if self.is_consumable or self.is_tool:
            return

        def elemshuffle(elements):
            elemcount = bin(elements).count('1')
            while random.randint(1, 5) == 5:
                elemcount += random.choice([-1, 1])
            elemcount = max(0, min(elemcount, 8))
            elements = 0
            while elemcount > 0:
                elements = elements | (1 << random.randint(0, 7))
                elemcount += -1
            return elements

        self.features['elements'] = elemshuffle(self.features['elements'])

        if self.is_weapon:
            return

        self.features['elemabsorbs'] = elemshuffle(self.features['elemabsorbs'])
        self.features['elemnulls'] = elemshuffle(self.features['elemnulls'])
        self.features['elemweaks'] = elemshuffle(self.features['elemweaks'])

    def mutate_learning(self):
        if not self.is_armor and not self.is_relic:
            return

        spell, rank = self.pick_a_spell(magic_only=True)
        if self.degree:
            learnrate = self.degree
        else:
            learnrate = 0.25

        try:
            learnrate = int(learnrate / rank) + 1
            learnrate = min(learnrate, 20)
        except ZeroDivisionError:
            learnrate = 20

        self.features['learnrate'] = learnrate
        self.features['learnspell'] = spell.spellid

    def mutate_special_action(self):
        if not self.is_weapon:
            return

        new_action = random.randint(1, 0xf)
        if new_action == 8:
            return

        self.features['specialaction'] = new_action

    def mutate_stats(self):
        if self.is_consumable:
            return

        def mutate_power_hitmdef():
            diff = min(self.features['power'], 0xFF-self.features['power'])
            diff = diff / 3
            self.features['power'] = self.features['power'] - diff
            self.features['power'] = self.features['power'] + random.randint(0, diff) + random.randint(0, diff)
            self.features['power'] = int(min(0xFF, max(0, self.features['power'])))

            diff = min(self.features['hitmdef'], 0xFF-self.features['hitmdef'])
            diff = diff / 3
            self.features['hitmdef'] = self.features['hitmdef'] - diff
            self.features['hitmdef'] = self.features['hitmdef'] + random.randint(0, diff) + random.randint(0, diff)
            self.features['hitmdef'] = int(min(0xFF, max(0, self.features['hitmdef'])))

        mutate_power_hitmdef()
        while random.randint(0, 10) == 10:
            mutate_power_hitmdef()

        def mutate_nibble(byte, left=False, limit=7):
            if left:
                nibble = (byte & 0xf0) >> 4
                byte = byte & 0x0f
            else:
                nibble = byte & 0x0f
                byte = byte & 0xf0

            value = nibble & 0x7
            if nibble & 0x8:
                value = value * -1

            while random.randint(1, 6) == 6:
                value += random.choice([1, -1])

            value = max(-limit, min(value, limit))
            nibble = abs(value)
            if value < 0:
                nibble = nibble | 0x8

            if left:
                return byte | (nibble << 4)
            else:
                return byte | nibble

        self.features['vigorspeed'] = mutate_nibble(self.features['vigorspeed'])
        self.features['vigorspeed'] = mutate_nibble(self.features['vigorspeed'], left=True)
        self.features['stammag'] = mutate_nibble(self.features['stammag'])
        self.features['stammag'] = mutate_nibble(self.features['stammag'], left=True)

        evade, mblock = self.evade, self.mblock

        def evade_is_screwed_up(value):
            while random.randint(1, 8) == 8:
                if value == 0:
                    choices = [1, 6]
                elif value in [5, 0xA]:
                    choices = [-1]
                elif value == 6:
                    choices = [1, -6]
                else:
                    choices = [1, -1]
                value += random.choice(choices)
            return value

        evade = evade_is_screwed_up(evade)
        mblock = evade_is_screwed_up(mblock)
        self.features['evademblock'] = evade | (mblock << 4)

    def mutate_price(self, undo_priceless=False):
        if self.price <= 2:
            if undo_priceless:
                self.price = self.rank()
            else:
                return

        normal = self.price / 2
        self.price += random.randint(0, normal) + random.randint(0, normal)
        while random.randint(1, 10) == 10:
            self.price += random.randint(0, normal) + random.randint(0, normal)

        zerocount = 0
        while self.price > 100:
            self.price = self.price / 10
            zerocount += 1

        while zerocount > 0:
            self.price = self.price * 10
            zerocount += -1

    def mutate(self):
        self.mutate_stats()
        self.mutate_price()
        broken, learned = False, False
        while random.randint(1, 5) == 5:
            x = random.randint(0, 99)
            if x < 10:
                self.mutate_special_action()
            elif x < 20 and not learned:
                self.mutate_learning()
            elif x < 50 and not broken:
                self.mutate_break_effect()
                broken = True
            elif x < 75:
                self.mutate_elements()
            else:
                self.mutate_feature()

    def rank(self):
        if self.price > 2:
            return self.price

        bl = 0
        baseline = 25000

        if self.is_consumable:
            baseline = 0

        if self.features['specialaction']:
            bl += 50

        if not self.is_consumable:
            if self.imp_only:
                baseline = 0

            if not self.is_tool and not self.is_relic:
                power = self.features['power']
                if power < 2:
                    power = 250
                bl += power

                if self.evade in range(1, 6):
                    bl += self.evade * 50

                if self.mblock in range(1, 6):
                    bl += self.mblock * 50

                if (self.is_armor and (self.features['elemabsorbs'] or
                                       self.features['elemnulls'])):
                    bl += 100

            if self.features['statboost1'] & 0x4b:
                bl += 25

            if self.features['statboost2'] & 0x40:
                bl += 400

            if self.features['special1'] & 0x88:
                bl += 100

            if self.features['special2'] & 0x31:
                bl += 200

            if self.features['special3'] & 0x08:
                bl += 300

            if self.features['fieldeffect'] & 0x02:
                bl += 300

            if self.features['statusacquire3'] & 0xeb:
                bl += 50 * bin(self.features['statusacquire3']).count('1')

            if self.features['statusacquire2'] & 0xf9:
                bl += -50 * bin(self.features['statusacquire2']).count('1')

        baseline += (bl * 100)

        return int(baseline)


NUM_CHARS = 13
CHAR_MASK = 0x1fff
IMP_MASK = 0x4000


def reset_equippable(items):
    items = filter(lambda i: not i.is_consumable and not i.is_tool, items)
    new_weaps = range(NUM_CHARS)
    random.shuffle(new_weaps)
    new_weaps = dict(zip(range(NUM_CHARS), new_weaps))
    for item in items:
        if item.is_weapon:
            equippable = item.equippable
            item.equippable = 0x00
            for i in range(NUM_CHARS):
                if equippable & (1 << i):
                    item.equippable |= (1 << new_weaps[i])
        elif item.is_relic:
            item.equippable = CHAR_MASK

    charequips = []
    valid_items = filter(lambda i: (not i.is_weapon and not i.is_relic
                                    and not i.equippable & 0x4000), items)
    for c in range(NUM_CHARS):
        myequips = []
        for i in valid_items:
            if i.equippable & (1 << c):
                myequips.append(True)
            else:
                myequips.append(False)
        random.shuffle(myequips)
        charequips.append(myequips)

    for item in valid_items:
        item.equippable &= 0xc000

    random.shuffle(charequips)
    for c in range(NUM_CHARS):
        assert len(valid_items) == len(charequips[c])
        for equippable, item in zip(charequips[c], valid_items):
            if equippable:
                item.equippable |= (1 << c)

    if random.randint(1, 3) == 3:
        weaponstoo = True
    else:
        weaponstoo = False

    for item in items:
        if item.equippable == 0:
            if not weaponstoo:
                continue
            item.equippable |= (1 << random.randint(0, NUM_CHARS-1))

    return items


def get_ranked_items(filename):
    from randomizer import items_from_table
    items = items_from_table('tables/itemcodes.txt')
    for i in items:
        i.read_stats(filename)

    items = sorted(items, key=lambda i: i.rank())
    for n, i in enumerate(items):
        i.set_degree(n / float(len(items)))

    return items
