from utils import (hex2int, write_multi, read_multi, ITEM_TABLE,
                   utilrandom as random)
from skillrandomizer import SpellBlock
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
        self.heavy = bool(self.equippable & 0x8000)

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

        self.confirm_heavy()
        write_multi(f, self.equippable, length=2)

        s = "".join(map(chr, [self.features[key] for key in ITEM_STATS]))
        f.write(s)

        write_multi(f, self.price, length=2)
        f.close()

    def confirm_heavy(self):
        if self.heavy and self.equippable:
            self.equippable |= 0x8000
        else:
            self.equippable &= 0x7FFF

    def equippable_by(self, charid):
        return self.equippable & (1 << charid)

    def unrestrict(self):
        if self.is_weapon:
            self.itemtype |= 0x10
            self.features['otherproperties'] |= 0x82

    @property
    def has_disabling_status(self):
        if (self.features['statusacquire2'] & 0xf9):
            return True
        if (self.features['statusacquire3'] & 0x14):
            return True
        return False

    @property
    def imp_only(self):
        return self.equippable & 0x4000

    @property
    def prevent_encounters(self):
        return bool(self.features['fieldeffect'] & 0x02)

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

    def pick_a_spell(self, magic_only=False, custom=None):
        if magic_only:
            spells = filter(lambda s: s.spellid in range(0, 36), all_spells)
        else:
            spells = all_spells

        if custom:
            spells = filter(custom, spells)

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

    def mutate_feature(self, feature=None):
        if self.is_consumable or self.is_tool:
            return

        if feature is None:
            feature = random.choice(STATPROTECT.keys())
        self.features[feature] = bit_mutate(self.features[feature], op="on",
                                            nochange=STATPROTECT[feature])

    def mutate_break_effect(self):
        global effects_used
        if self.is_consumable:
            return

        success = False
        for _ in xrange(100):
            spell, _ = self.pick_a_spell(custom=lambda x: x.spellid < 0x3F)
            if spell.spellid not in effects_used:
                effects_used.append(spell.spellid)
                success = True
                break

        if not success:
            return

        self.features['breakeffect'] = spell.spellid
        if not self.is_weapon or random.randint(1, 2) == 2:
            # always make armors usable in battle; weapons, only sometimes
            self.itemtype = self.itemtype | 0x20

        # flag to break when used as an item
        if random.randint(1, 20) == 20:
            self.features['breakeffect'] &= 0x7F
        else:
            self.features['breakeffect'] |= 0x80

        # flag to set chance to proc a spell
        if self.is_weapon and (not self.itemtype & 0x20 or random.randint(1, 2) == 2):
            self.features['breakeffect'] |= 0x40
        else:
            self.features['breakeffect'] &= 0xBF

        self.features['targeting'] = spell.targeting & 0xef

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
            learnrate = min(learnrate, 5)
        except ZeroDivisionError:
            learnrate = 5

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
        if not self.heavy and random.randint(1, 20) == 20:
            self.heavy = True

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

            if self.features['special1'] & 0x08:
                bl += 400

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


NUM_CHARS = 14
CHAR_MASK = 0x3fff
IMP_MASK = 0x4000
UMARO_ID = 13


def reset_equippable(items, numchars=NUM_CHARS):
    prevents = filter(lambda i: i.prevent_encounters, items)
    for item in prevents:
        if not CHAR_MASK & item.equippable:
            continue

        while True:
            test = 1 << random.randint(0, numchars-1)
            if item.itemid == 0xDE:
                item.equippable = test
                break

            if test & item.equippable:
                test |= IMP_MASK
                item.equippable &= test
                break

    items = filter(lambda i: not (i.is_consumable or i.is_tool or i.prevent_encounters), items)
    new_weaps = range(numchars)
    random.shuffle(new_weaps)
    new_weaps = dict(zip(range(numchars), new_weaps))
    for item in items:
        if numchars == 14 and random.randint(1, 10) == 10:
            # for umaro's benefit
            item.equippable |= 0x2000

        if item.is_weapon:
            equippable = item.equippable
            item.equippable &= IMP_MASK
            for i in range(numchars):
                if equippable & (1 << i):
                    item.equippable |= (1 << new_weaps[i])
        elif item.is_relic:
            if random.randint(1, 10) == 10:
                if random.randint(1, 5) == 5:
                    item.equippable = 1 << (random.randint(0, numchars-1))
                else:
                    item.equippable = random.randint(1, CHAR_MASK)
            else:
                item.equippable = CHAR_MASK

    charequips = []
    valid_items = filter(lambda i: (not i.is_weapon and not i.is_relic
                                    and not i.equippable & 0x4000), items)
    for c in range(numchars):
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
    for c in range(numchars):
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
            item.equippable |= (1 << random.randint(0, numchars-1))

    return items


sperelic = {0x04: (0x25456, 0x2545B),
            0x08: (0x25455, 0x2545A),
            0x10: (0x25454, 0x25459),
            0x20: (0x25453, 0x25458),
            0x40: (0x25452, 0x25457)}

invalid_commands = [0x00, 0x04, 0x14, 0x15, 0x19, 0xFF]


def reset_special_relics(items, characters, filename):
    f = open(filename, 'r+b')
    characters = [c for c in characters if c.id < 14]
    for item in items:
        if (item.is_consumable or item.is_tool or
                not item.features['special1'] & 0x7C):
            continue

        item.equippable &= IMP_MASK
        item.equippable |= 1 << 12  # gogo
        for flag in [0x04, 0x08, 0x10, 0x20, 0x40]:
            if flag & item.features['special1']:
                before, after = sperelic[flag]
                while True:
                    bcomm = random.randint(0, 0x1D)
                    if bcomm in [0x04, 0x14, 0x15, 0x19]:
                        continue

                    if bcomm == 0:
                        tempchars = [c for c in characters]
                    else:
                        tempchars = [c for c in characters if bcomm in c.battle_commands]

                    if not tempchars:
                        continue

                    unused = set(range(0, 0x1E)) - set(invalid_commands)
                    if len(tempchars) <= 4:
                        for t in tempchars:
                            unused = unused - set(t.battle_commands)

                    if not unused:
                        continue

                    acomm = random.choice(sorted(unused))
                    f.seek(before)
                    f.write(chr(bcomm))
                    f.seek(after)
                    f.write(chr(acomm))
                    for t in tempchars:
                        item.equippable |= (1 << t.id)

                    item.write_stats(filename)
                    break

    f.close()


def reset_rage_blizzard(items, umaro_risk, filename):
    for item in items:
        if item.itemid not in [0xC5, 0xC6]:
            continue

        item.equippable = 1 << (umaro_risk.id)
        item.write_stats(filename)


def get_ranked_items(filename):
    from randomizer import items_from_table
    items = items_from_table(ITEM_TABLE)
    for i in items:
        i.read_stats(filename)

    items = sorted(items, key=lambda i: i.rank())
    for n, i in enumerate(items):
        i.set_degree(n / float(len(items)))

    return items
