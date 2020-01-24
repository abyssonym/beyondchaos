from utils import (hex2int, int2bytes, Substitution, SPELL_TABLE,
                   SPELLBANS_TABLE, name_to_bytes, utilrandom as random)

spelldict = {}
spellnames = {}
f = open(SPELL_TABLE)
for line in f:
    line = line.strip()
    while '  ' in line:
        line = line.replace('  ', ' ')
    value, strength, name = tuple(line.split(','))
    spellnames[hex2int(value)] = name
f.close()

spellbans = {}
f = open(SPELLBANS_TABLE)
for line in f:
    line = line.strip()
    if line[0] == '#':
        continue
    spellid, modifier, name, ban = tuple(line.split(','))
    if ban == "ban":
        modifier = int(modifier) * -1
    spellbans[hex2int(spellid)] = int(modifier)
f.close()


class SpellBlock:
    def __init__(self, spellid, filename):
        self.spellid = spellid
        if self.spellid in spellbans and spellbans[self.spellid] < 0:
            self.valid = False
        else:
            self.valid = True
        self.name = spellnames[self.spellid]
        self.pointer = 0x46AC0 + (14 * spellid)
        f = open(filename, 'r+b')

        f.seek(self.pointer)
        targeting = ord(f.read(1))
        self.targeting = targeting
        self.target_random = targeting & 0x80
        self.target_enemy_default = targeting & 0x40
        self.target_group = targeting & 0x20
        self.target_auto = targeting & 0x10
        self.target_group_default = targeting & 0x08
        self.target_everyone = targeting & 0x04
        self.target_one_side_only = targeting & 0x02
        self.target_one = targeting & 0x01

        f.seek(self.pointer+1)
        self.elements = ord(f.read(1))
        self.elemental = self.elements > 0

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

        f.seek(self.pointer+3)
        self.dmgtype = ord(f.read(1))
        self.outsidebattle = self.dmgtype & 0x01
        self.unreflectable = self.dmgtype & 0x02
        self.learnifcast = self.dmgtype & 0x04
        self.enablerunic = self.dmgtype & 0x08
        self.unknown = self.dmgtype & 0x10
        self.retargetdead = self.dmgtype & 0x20
        self.casterdies = self.dmgtype & 0x40
        self.concernsmp = self.dmgtype & 0x80

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
        f.seek(self.pointer+8)
        self.accuracy = ord(f.read(1))
        f.seek(self.pointer+9)
        self.special = ord(f.read(1))
        f.seek(self.pointer+10)
        statuses = list(f.read(4))
        self.death = statuses[0] & 0x80
        self.petrify = statuses[0] & 0x40
        self.condemned = statuses[1] & 0x1
        self.statuses = statuses
        self.has_status = sum([bin(b).count("1") for b in statuses])
        f.close()

        self._rank = None

    def __cmp__(self, other):
        if other is None:
            return 1
        return self.spellid - other.spellid

    def __hash__(self):
        return self.spellid

    @property
    def unrageable(self):
        return (self.is_blitz or self.is_swdtech or self.is_slots or
                not self.valid)

    @property
    def is_blitz(self):
        return self.spellid in range(0x5D, 0x65)

    @property
    def is_swdtech(self):
        return self.spellid in range(0x55, 0x5D)

    @property
    def is_esper(self):
        return self.spellid in range(0x36, 0x51)

    @property
    def is_slots(self):
        return self.spellid in range(0x7D, 0x83)

    def fix_reflect(self, fout):
        self.dmgtype |= 0x02
        fout.seek(self.pointer+3)
        fout.write(bytes([self.dmgtype]))

    def rank(self):
        if self._rank is not None:
            return self._rank
        if self.power >= 1 and not self.percentage and not self.draining:
            power = self.power
            baseline = power
        else:
            power = None
            baseline = 20

        if self.accuracy:
            baseline = baseline * 0.9

        if self.target_enemy_default or \
                (self.target_everyone and not
                 self.target_one_side_only):
            if power:
                if self.ignore_defense:
                    baseline = baseline * 2
                if self.elemental:
                    baseline = baseline * 0.75
                if self.no_split_damage:
                    baseline = baseline * 1.5
                if self.invert_undead:
                    baseline = baseline * 0.75
                if self.uses_stamina:
                    baseline = baseline * 0.75

            if self.power and self.draining:
                baseline = baseline * 2

            if self.physical:
                baseline = baseline * 0.6
            if self.unblockable:
                baseline = baseline * 1.25
            if self.has_status:
                baseline = baseline * 1.25

            if self.miss_if_death_prot:
                if self.death:
                    baseline = baseline * 3.5
                elif self.petrify:
                    baseline = baseline * 3
                elif self.condemned:
                    baseline = baseline * 1
                elif self.percentage:
                    baseline = baseline * 1
                else:
                    baseline = baseline * 2
            elif self.petrify and not power:
                baseline = baseline * 3
            elif self.petrify:
                baseline = baseline * 1.5

        else:
            if self.death:
                baseline = baseline * 0.1

        if self.healing or not self.target_enemy_default:
            baseline = baseline * 0.5
        if self.level_spell:
            baseline = baseline * 0.25

        if self.spellid in spellbans:
            baseline += abs(spellbans[self.spellid])

        self._rank = int(baseline)

        return self._rank


class CommandBlock:
    def __init__(self, pointer, start, end, menu, textptr, name, target):
        self.pointer = hex2int(pointer)
        self.start = hex2int(start)
        self.end = hex2int(end)
        self.menu = hex2int(menu)
        self.textptr = hex2int(textptr)
        self.name = name.lower()
        self.target = target.lower()
        self.id = None

    @property
    def size(self):
        return self.end - self.start

    def set_id(self, i):
        self.id = i
        self.proppointer = 0xFFE00 + (i*2)

    @property
    def usable_as_imp(self):
        return self.properties & 0x4

    @property
    def can_be_mimicked(self):
        return self.properties & 0x2

    @property
    def usable_by_gogo(self):
        return self.properties & 0x1

    def read_properties(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.proppointer)
        self.properties = ord(f.read(1))
        assert not self.properties & 0xF0
        self.targeting = ord(f.read(1))
        f.close()

    def write_properties(self, fout):
        fout.seek(self.proppointer)
        fout.write(bytes([self.properties]))
        fout.write(bytes([self.targeting]))

    def setpointer(self, value, fout):
        fout.seek(self.pointer)
        bytestring = bytes(int2bytes(value, length=2))
        fout.write(bytestring)

    def unsetmenu(self, fout):
        fout.seek(self.menu)
        bytestring = bytes([0x95, 0x77])
        fout.write(bytestring)

    def newname(self, text, fout):
        text = text.strip().replace(' ', '')
        text = text[:7]
        self.name = text
        text = name_to_bytes(text, 7)

        fout.seek(self.textptr)
        fout.write(bytes(text))

    def set_bit(self, pointer, fout, unset=False):
        bit = self.id % 8
        byte = 1 << bit
        offset = self.id // 8
        fout.seek(pointer + offset)
        old = ord(fout.read(1))
        if unset:
            byte = old & (0xFF ^ byte)
        else:
            byte = old | byte
        fout.seek(pointer + offset)
        fout.write(bytes([byte]))

    def unset_retarget(self, fout):
        self.set_bit(0x24E46, fout, unset=True)

    def set_retarget(self, fout):
        self.set_bit(0x24E46, fout)

    def allow_while_confused(self, fout):
        self.set_bit(0x204D0, fout)

    def allow_while_berserk(self, fout):
        self.set_bit(0x204D4, fout)

    def disallow_while_berserk(self, fout):
        self.set_bit(0x204D4, fout, unset=True)


def get_ranked_spells(filename=None, magic_only=False):
    if spelldict:
        spells = sorted(list(spelldict.values()), key=lambda s: s.spellid)
    else:
        spells = [SpellBlock(i, filename) for i in range(0xFF)]
        for s in spells:
            spelldict[s.spellid] = s

    if magic_only:
        spells = [s for s in spells if s.spellid < 0x36]

    spells = sorted(spells, key=lambda i: i.rank())
    return spells


def get_spell(spellid):
    return spelldict[spellid]


class SpellSub(Substitution):
    def __init__(self, spellid):
        self.spellid = spellid
        self.bytestring = bytes([0xA9, self.spellid, 0x85, 0xB6, 0xA9,
                                 0x02, 0x85, 0xB5, 0x4C, 0x5F, 0x17])

    def __repr__(self):
        return "Use the skill '{0}'".format(spellnames[self.spellid])

wildspells = None

def get_spellsets(spells=None):
    """Create various thematic groups of spells."""
    global wildspells
    spellsets = {}
    spellset_bans = []
    spells = [s for s in spells if s.spellid not in spellset_bans]
    # Each spellset is a tuple of (description, spell list)
    spellsets['Chaos'] = ('skill (including broken and glitchy skills)', [])
    if wildspells is None:
        wildspells = random.sample(spells, 8)
    spellsets['Wild'] = ('random set of spells', wildspells)
    spellsets['Magic'] = ('magic spell', list(range(0, 0x36)))
    spellsets['Black'] = ('black magic spell', list(range(0, 0x18)))
    spellsets['White'] = ('white magic spell', list(range(0x2D, 0x36)))
    spellsets['Gray'] = ('gray magic spell', list(range(0x18, 0x2D)))
    spellsets['Esper'] = ('Esper summon', list(range(0x36, 0x51)))
    spellsets['Sword'] = ('SwdTech skill', list(range(0x55, 0x5D)))
    spellsets['Blitz'] = ('Blitz', list(range(0x5D, 0x65)))
    spellsets['Geo'] = ('geomancer-type Dance move', list(range(0x65, 0x75)))
    spellsets['Beast'] = ('beast-summoning Dance move', list(range(0x75, 0x7D)))
    spellsets['Lore'] = ('Lore', list(range(0x8B, 0xA3)))
    spellsets['Rare'] = ('rare effect (Slots, Super Ball, non-Lore monster skill)',
                         list(range(0x7D, 0x83)) + list(range(0xA3, 0xEE)))
    elementals = [s for s in spells if bin(s.elements).count('1') == 1]
    spellsets['Fire'] = ('fire-elemental skill',
                         [s for s in elementals if s.elements & 1])
    spellsets['Ice'] = ('ice-elemental skill',
                        [s for s in elementals if s.elements & 2])
    spellsets['Bolt'] = ('lightning-elemental skill',
                         [s for s in elementals if s.elements & 4])
    spellsets['Bio'] = ('poison-elemental skill',
                        [s for s in elementals if s.elements & 8])
    spellsets['Wind'] = ('wind-elemental skill',
                         [s for s in elementals if s.elements & 0x10])
    spellsets['Pearl'] = ('holy-elemental skill',
                          [s for s in elementals if s.elements & 0x20])
    spellsets['Earth'] = ('earth-elemental skill',
                          [s for s in elementals if s.elements & 0x40])
    spellsets['Water'] = ('water-elemental skill',
                          [s for s in elementals if s.elements & 0x80])
    spellsets['Elem'] = ('elemental skill (excluding black magic spells)',
                         [s for s in spells if s.elements and
                          s.spellid not in list(range(0, 0x18))])
    # Skills that deal non-elemental magic damage - Meteor, Ultima, Crusader...
    # This includes most desperation attacks as well.
    # TODO: also includes Drain, Rasp, Osmose, Empowerer - a bug?
    spellsets['Nuke'] = ('non-elemental magic damage skill',
                         [s for s in spells if s.power and not any(
                             [s.elements, s.percentage, s.physical, s.healing])])
    spellsets['Heal'] = ('HP- and/or MP-restoring skill',
                         [s for s in spells if s.healing])
    spellsets['Phys'] = ('physical skill', [s for s in spells if s.physical])
    spellsets['Curse'] = (
        'enemy harmful-status skill',
        [s for s in spells if all(
            [s.target_enemy_default, not s.miss_if_death_prot, not s.power])])
    # Explicitly exclude Clear (0xA4) as that's actually a debuff
    spellsets['Bless'] = (
        'ally beneficial-status skill',
        [s for s in spells if not any(
            [s.target_enemy_default, s.power, s.spellid == 0xA4])])
    spellsets['Drain'] = ('HP- and/or MP-draining skill',
                          [s for s in spells if s.draining or s.concernsmp])
    # Death Skills.
    # All status-inflicting spells that are blocked by death protection.
    # Plus some specific death spells that ignore death protection:
    spellsets['Death'] = (
        'instant-death skill',
        ([s for s in spells if s.miss_if_death_prot and
          not s.percentage and s.has_status] +
         # these ignore death protection -  Ragnarok, Mind Blast, Dread, Soul Out
         [get_spell(s) for s in [0x46, 0xC4, 0xE2, 0xE5]]))
    # Demi, Quartr, W Wind, Cave In, Shimsham, Launcher, etc.
    spellsets['Heavy'] = ('percentage-damage skill',
                          [s for s in spells if s.miss_if_death_prot and
                           s.percentage])
    # Quake, W Wind, Crusader, Merton, ForceField
    spellsets['All'] = ('skill targeting allies and enemies alike',
                        [s for s in spells if s.target_everyone and
                         not s.target_one_side_only])
    # Includes Haste2, Big Guard, Pearl Wind, and a bunch of defensive Espers
    spellsets['Party'] = ('full-party buff',
                          [s for s in spells if s.target_group_default and
                           not s.target_enemy_default])
    spellsets['Tek'] = ('Magitek or other tech-themed skill',
                        ([0x18, 0x6E, 0x70, 0x7D, 0x7E] + list(range(0x86, 0x8B)) +
                         [0xA7, 0xB1] + list(range(0xB4, 0xBA)) + [0x91, 0x9A] +
                         [0xBF, 0xCD, 0xD1, 0xD4, 0xD7, 0xDD, 0xE3]))
    spellsets['Time'] = ('time mage skill (a la FF5)',
                         [0x10, 0x11, 0x12, 0x13, 0x19, 0x1B, 0x1F, 0x20, 0x22,
                          0x26, 0x27, 0x28, 0x2A, 0x2B, 0x34, 0x89, 0x9B, 0xA0,
                          0xC9, 0xDF])
    spellsets['Level'] = ('level-based skill',
                          [s for s in spells if s.level_spell])
    spellsets['Miss'] = ('skill with low accuracy',
                         [s for s in spells if not s.unblockable and not s.level_spell and 0 < s.accuracy < 90])

    for key, desc_and_spellset in list(spellsets.items()):
        if not desc_and_spellset:
            continue
        desc, spellset = desc_and_spellset
        if not spellset:
            continue
        # Convert lists of spell IDs into lists of spells
        if isinstance(spellset[0], int):
            spellset = [s for s in spells if s.spellid in spellset]
        # Sort the spell set by spell ID
        spellset = sorted(set(spellset), key=lambda s: s.spellid)
        spellsets[key] = (desc, spellset)

    return spellsets


class RandomSpellSub(Substitution):
    @property
    def template(self):
        if self.wild:
            return self.get_wild()
        template = bytearray(
            [0x20, 0x5A, 0x4B,        # get random number
             0x29, 0x00,              # AND the result
             0xAA,                    # TAX
             0xBF, 0x00, 0x00, 0x00,  # load byte from $addr + X
             0x85, 0xB6, 0xA9, 0x02, 0x85, 0xB5,
             0x64, 0xB8, 0x64, 0xB9,  # clear targets
             0x20, 0xC1, 0x19,  # JSR $19C1
             0x20, 0x51, 0x29,  # JSR $2951
             0x4C, 0x5F, 0x17,
            ])
        return template

    def get_wild(self):
        template = bytearray(
            [0x20, 0x5A, 0x4B,        # get random number
             0x85, 0xB6, 0xA9, 0x02, 0x85, 0xB5,
             0x64, 0xB8, 0x64, 0xB9,  # clear targets
             0x20, 0xC1, 0x19,  # JSR $19C1
             0x20, 0x51, 0x29,  # JSR $2951
             0x4C, 0x5F, 0x17,
            ])
        return template

    @property
    def size(self):
        if self.wild:
            return len(self.template)
        return len(self.template) + len(self.spells)

    def generate_bytestring(self):
        self.bytestring = self.template
        if self.wild:
            return self.bytestring

        pointer = self.location + len(self.bytestring)
        self.bytestring[4] = len(self.spells) - 1
        assert self.bytestring[4] in [(2**i)-1 for i in range(1, 8)]
        a, b, c = pointer >> 16, (pointer >> 8) & 0xFF, pointer & 0xFF
        self.bytestring[7:10] = bytearray([c, b, a])
        self.bytestring += bytearray(sorted([s.spellid for s in self.spells]))

    def write(self, fout):
        super(RandomSpellSub, self).write(fout)

    def set_spells(self, valid_spells, spellsets=None, spellclass=None):
        spellsets = spellsets or get_spellsets(spells=valid_spells)
        spellclass = spellclass or random.choice(list(spellsets.keys()))
        self.name = spellclass
        desc, spellset = spellsets[spellclass]
        self.spells_description = desc
        if spellclass.lower() in ["chaos"] or len(valid_spells) == 0:
            self.wild = True
            self.spells = []
            return
        else:
            self.wild = False

        spellset = sorted([s for s in spellset if s in valid_spells],
                          key=lambda s: s.spellid)
        if len(spellset) < 3:
            raise ValueError("Spellset %s not big enough." % spellclass)

        for setlength in [8, 16, 32]:
            if len(spellset) <= setlength:
                spells = spellset
                while len(spells) < setlength:
                    spells.append(random.choice(spellset))
                break
        else:
            assert setlength == 32
            spells = random.sample(spellset,
                                   min(setlength, len(spellset)))
            while len(spells) < setlength:
                spells.append(random.choice(spellset))
            assert len(set(spells)) > 16

        self.spells = spells

        return self.spells

    @property
    def spells_string(self):
        unique_spells = sorted(set(self.spells), key=lambda s: s.name)
        if not self.spells:
            return ""
        if len(self.spells) == len(unique_spells):
            # No repetition of spells - all equal chances
            return ("Equal chance of any of the following:\n  " +
                    ", ".join(spell.name for spell in unique_spells))
        # Else, let's try to pretty-print things a bit...
        descs = []
        last_count = -1
        # Sort by descending probability
        unique_spells.sort(key=lambda s: self.spells.count(s), reverse=True)
        for unique_s in unique_spells:
            desc = unique_s.name
            c = self.spells.count(unique_s)
            if c != last_count:
                desc = "\n  ({0}/{1} chance each)  {2}".format(c, len(self.spells), desc)
                last_count = c
            else:
                desc = ", " + desc
            descs.append(desc)
        return ''.join(descs)

    def __repr__(self):
        return "Use a random {0}.\n{1}".format(self.spells_description,
                                               self.spells_string)


class ComboSpellSub(Substitution):
    def __init__(self, spells):
        self.spells = spells
        self.spellsubs = []
        self.random_order = random.choice([True, False, False])
        for s in self.spells:
            self.spellsubs.append(SpellSub(spellid=s.spellid))

    @property
    def size(self):
        return sum([s.size for s in self.spellsubs]) + self.get_overhead()

    def get_overhead(self):
        return (9 * len(self.spellsubs)) + 1 - 4

    def generate_bytestring(self):
        subpointer = self.location + self.get_overhead()

        offset = 0
        self.bytestring = bytearray([])
        for (i, s) in enumerate(self.spellsubs):
            spointer = subpointer + offset
            s.set_location(spointer)
            low = spointer & 0xFF
            high = (spointer >> 8) & 0xFF
            offset += len(s.bytestring)
            if i > 0:
                self.bytestring += bytearray([
                    0xA9, 0x01,
                    0x04, 0xB2,
                    ])
            self.bytestring += bytearray([
                0x5A,
                0x20, low, high,
                0x7A,
                ])
        self.bytestring.append(0x60)
        assert len(self.bytestring) == self.get_overhead()

    def write(self, fout):
        super(ComboSpellSub, self).write(fout)
        for s in self.spellsubs:
            s.write(fout)

    def __repr__(self):
        return "Use the combo {0}.".format(
            " + ".join([s.name for s in self.spells]))



class MultiSpellSubMixin(Substitution):
    @property
    def size(self):
        return self.spellsub.size + self.get_overhead()

    def set_spells(self, spells):
        if isinstance(spells, int):
            self.spellsub = SpellSub(spellid=spells)
        elif isinstance(spells, list) or isinstance(spells, set):
            self.spellsub = RandomSpellSub()
            self.spellsub.set_spells(spells)
            self.name = self.spellsub.name
            self.spells = self.spellsub.spells
        else:
            self.spellsub = spells
            self.name = self.spellsub.name
            self.spells = self.spellsub.spells

    def write(self, fout):
        self.spellsub.write(fout)
        super(MultiSpellSubMixin, self).write(fout)


class ChainSpellSub(MultiSpellSubMixin):
    def get_overhead(self):
        return 19

    def generate_bytestring(self):
        subpointer = self.location + self.get_overhead()
        self.spellsub.set_location(subpointer)
        if not self.spellsub.bytestring:
            self.spellsub.generate_bytestring()
        high, low = (subpointer >> 8) & 0xFF, subpointer & 0xFF

        self.bytestring = bytearray([
            0xA9, 0x01,
            0x04, 0xB2,
            0x5A,                           # PHY
            0x20, low, high,                # call spell sub
            0x7A,                           # PLY
            0x20, 0x5A, 0x4B,               # get random number
            0x29, 0x01,                     # AND the result
            0xC9, 0x00,                     # CMP #0
            0xD0, 0x00,                     # BNE start of bytestring
            ])
        length = len(self.bytestring)
        self.bytestring[-1] = (0x100 - length)
        self.bytestring += bytearray([0x60])
        assert len(self.bytestring) == self.get_overhead()
        self.bytestring += self.spellsub.bytestring

    def __repr__(self):
        if isinstance(self.spellsub, RandomSpellSub):
            return "??? times, use a random {0}.\n{1}".format(
                self.spellsub.spells_description,
                self.spellsub.spells_string)
        elif isinstance(self.spellsub, ComboSpellSub):
            return "??? times, use the combo {0}.".format(
                " + ".join([s.name for s in self.spellsub.spells]))
        else:
            return "??? times, use the skill '{0}'".format(
                spellnames[self.spellsub.spellid])


class MultipleSpellSub(MultiSpellSubMixin):
    def get_overhead(self):
        if isinstance(self.spellsub, RandomSpellSub):
            if self.count <= 3:
                return ((self.count - 1) * 9) + 4
            else:
                return 20
        else:
            if self.count <= 3:
                return ((self.count - 1) * 5) + 4
            else:
                return 16

    def set_count(self, count):
        self.count = count

    def generate_bytestring(self):
        subpointer = self.location + self.get_overhead()
        self.spellsub.set_location(subpointer)
        if not self.spellsub.bytestring:
            self.spellsub.generate_bytestring()
        high, low = (subpointer >> 8) & 0xFF, subpointer & 0xFF
        if isinstance(self.spellsub, RandomSpellSub):
            if self.count <= 3:
                self.bytestring = bytearray([0x5A, 0x20, low, high, 0x7A, 0xA9, 0x01, 0x04, 0xb2] * (self.count - 1) + [0x20, low, high])
            else:
                self.bytestring = bytearray([0xA9, self.count - 1, 0x48, 0x5A, 0x20, low, high, 0x7A, 0xA9, 0x01, 0x04, 0xb2, 0x68, 0x3A, 0xD0, 0xF2, 0x20, low, high])
        else:
            if self.count <= 3:
                self.bytestring = bytearray([0x5A, 0x20, low, high, 0x7A] * (self.count - 1) + [0x20, low, high])
            else:
                self.bytestring = bytearray([0xA9, self.count - 1, 0x48, 0x5A, 0x20, low, high, 0x7A, 0x68, 0x3A, 0xD0, 0xF6, 0x20, low, high])
        self.bytestring += bytearray([0x60])
        self.bytestring += self.spellsub.bytestring

    def __repr__(self):
        if isinstance(self.spellsub, RandomSpellSub):
            return "{0} times, use a random {1}.\n{2}".format(
                self.count, self.spellsub.spells_description,
                self.spellsub.spells_string)
        elif isinstance(self.spellsub, ComboSpellSub):
            return "{0} times, use the combo {1}.".format(
                self.count,
                " + ".join([s.name for s in self.spellsub.spells]))
        else:
            return "{0} times, use the skill '{1}'".format(
                self.count, spellnames[self.spellsub.spellid])
