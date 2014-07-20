from utils import hex2int, int2bytes

texttable = {}
f = open("tables/text.txt")
for line in f:
    line = line.strip()
    char, value = tuple(line.split())
    texttable[char] = value
f.close()

spellnames = {}
f = open("tables/spellcodes.txt")
for line in f:
    line = line.strip()
    while '  ' in line:
        line = line.replace('  ', ' ')
    value, strength, name = tuple(line.split(','))
    spellnames[hex2int(value)] = name
f.close()

spellbans = {}
f = open("tables/spellbans.txt")
for line in f:
    line = line.strip()
    if line[0] == '#':
        continue
    spellid, modifier, name = tuple(line.split(','))
    spellbans[hex2int(spellid)] = int(modifier)
f.close()

restriction_enemy = lambda s: s.target_enemy_default and not s.target_group_default
SELF_ALLOW = [0x2a, 0x2b, 0x4c, 0x63, 0x3f, 0x9a]
SELF_RESTRICT = [0x30, 0x31, 0x27, 0x28, 0x51, 0x52, 0x53]
restriction_self = (
    lambda s: ((s.target_one and not s.target_group_default and not s.target_enemy_default)
               or (s.target_enemy_default and s.target_one_side_only)
               or (s.target_everyone and not s.target_one_side_only)
               or s.spellid in SELF_ALLOW) and s.spellid not in SELF_RESTRICT)
ALLIES_ALLOW = [0xab]
ALLIES_RESTRICT = [0x63]
restriction_allies = (
    lambda s: ((s.target_group and not s.target_enemy_default)
               or s.spellid in ALLIES_ALLOW) and s.spellid not in ALLIES_RESTRICT and not restriction_self(s))
restriction_enemies = (lambda s: s.target_group and s.target_enemy_default)
restriction_random_ally = lambda s: False
restrictions = {'self': restriction_self,
                'allies': restriction_allies,
                'enemies': restriction_enemies,
                'enemy': restriction_enemy,
                'randally': restriction_random_ally}


class SpellBlock:
    def __init__(self, spellid, filename):
        self.spellid = spellid
        if self.spellid in spellbans and spellbans[self.spellid] == 0:
            self.valid = False
        else:
            self.valid = True
        self.name = spellnames[self.spellid]
        self.pointer = 0x46AC0 + (14 * spellid)
        f = open(filename, 'r+b')

        f.seek(self.pointer)
        targetting = ord(f.read(1))
        self.target_random = targetting & 0x80
        self.target_enemy_default = targetting & 0x40
        self.target_group = targetting & 0x20
        self.target_auto = targetting & 0x10
        self.target_group_default = targetting & 0x08
        self.target_everyone = targetting & 0x04
        self.target_one_side_only = targetting & 0x02
        self.target_one = targetting & 0x01

        f.seek(self.pointer+1)
        elements = ord(f.read(1))
        self.elemental = elements > 0

        f.seek(self.pointer+2)
        effect1 = ord(f.read(1))
        self.physical = effect1 & 0x01
        self.miss_if_death_prot = effect1 & 0x02
        self.target_dead = effect1 & 0x04
        self.invert_undead = effect1 & 0x08
        self.randomize_target = effect1 & 0x10
        self.ignore_defense = effect1 & 0x20
        self.no_split_damage = effect1 & 0x40
        self.abort_on_allies = effect1 & 0x80

        f.seek(self.pointer+4)
        effect2 = ord(f.read(1))
        self.healing = effect2 & 0x01
        self.draining = effect2 & 0x02
        self.cure_status = effect2 & 0x04
        self.invert_status = effect2 & 0x08
        self.uses_stamina = effect2 & 0x10
        self.unblockable = effect2 & 0x20
        self.level_spell = effect2 & 0x40
        self.percentage = effect2 & 0x80

        f.seek(self.pointer+5)
        self.mp = ord(f.read(1))
        f.seek(self.pointer+6)
        self.power = ord(f.read(1))
        f.seek(self.pointer+7)
        self.accuracy = ord(f.read(1))
        f.seek(self.pointer+10)
        self.special = ord(f.read(1))
        f.seek(self.pointer+11)
        statuses = map(ord, f.read(4))
        self.death = statuses[0] & 0x80
        self.petrify = statuses[0] & 0x40
        self.condemned = statuses[0] & 0x1
        self.statuses = sum([bin(b).count("1") for b in statuses])
        f.close()

    def rank(self):
        if self.power >= 1 and not self.percentage and not self.draining:
            baseline = self.power
        else:
            baseline = 20

        if self.accuracy:
            baseline = baseline * 0.9
        if self.ignore_defense and not self.draining and self.power >= 1:
            baseline = baseline * 2
        if self.power and self.elemental:
            baseline = baseline * 0.75
        if self.power and self.no_split_damage:
            baseline = baseline * 1.5
        if self.power and self.invert_undead:
            baseline = baseline * 0.75
        if self.healing or not self.target_enemy_default:
            baseline = baseline * 0.5
        if self.power and self.draining:
            baseline = baseline * 2
        if self.level_spell:
            baseline = baseline * 0.25
        if self.miss_if_death_prot and self.target_enemy_default:
            if self.death:
                baseline = baseline * 8
            elif self.petrify:
                baseline = baseline * 4
            elif self.condemned:
                baseline = baseline * 1
            elif self.percentage:
                baseline = baseline * 2
            else:
                baseline = baseline * 6
        elif self.petrify and self.target_enemy_default and not self.power:
            baseline = baseline * 3
        if self.uses_stamina:
            baseline = baseline * 0.75
        if self.physical:
            baseline = baseline * 0.75
        if self.unblockable:
            baseline = baseline * 1.25
        if self.statuses and not self.cure_status and not self.invert_status:
            baseline = baseline * 1.5
        if self.spellid in spellbans:
            baseline += spellbans[self.spellid]
        return int(baseline)


class CommandBlock:
    def __init__(self, pointer, start, end, menu, textptr, name, target):
        self.pointer = hex2int(pointer)
        self.start = hex2int(start)
        self.end = hex2int(end)
        self.menu = hex2int(menu)
        self.textptr = hex2int(textptr)
        self.name = name.lower()
        self.target = target.lower()
        self.set_targeting_restriction(restrictions[self.target])
        self.id = None

    @property
    def size(self):
        return self.end - self.start

    def set_id(self, i):
        self.id = i

    def set_targeting_restriction(self, restriction):
        self.restriction = restriction

    def set_retarget(self, spellblock, filename):
        if self.target != "self":
            return

        bit = self.id % 8
        byte = 1 << bit

        offset = self.id / 8
        f = open(filename, 'r+b')
        f.seek(0x24E46 + offset)
        old = ord(f.read(1))
        if not spellblock.target_enemy_default and not spellblock.target_everyone:
            byte = old & ~byte
        else:
            byte = old | byte
        f.seek(0x24E46 + offset)
        f.write(chr(byte))

    def setpointer(self, value, filename):
        f = open(filename, 'r+b')
        f.seek(self.pointer)
        bytestring = "".join(map(chr, int2bytes(value, length=2)))
        f.write(bytestring)
        f.close()

    def unsetmenu(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.menu)
        bytestring = "".join(map(chr, [0x95, 0x77]))
        f.write(bytestring)
        f.close()

    def newname(self, text, filename):
        text = text.strip().replace(' ', '')
        if len(text) > 7:
            text = text.replace('-', '')
            text = text.replace('.', '')
        text = text[:7]
        self.name = text
        text = map(lambda c: hex2int(texttable[c]), text)
        while len(text) < 7:
            text.append(0xFF)
        text = "".join(map(chr, text))

        f = open(filename, 'r+b')
        f.seek(self.textptr)
        f.write(text)
        f.close()
