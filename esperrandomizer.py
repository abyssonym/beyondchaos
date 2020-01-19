from dataclasses import dataclass, field
from functools import reduce
from itertools import chain, repeat
from typing import List

from dialoguemanager import patch_dialogue, set_dialogue_var
from skillrandomizer import get_ranked_spells, get_spell
from utils import ESPER_TABLE, MAGICITE_TABLE, hex2int, int2bytes, Substitution, utilrandom as random

items = None

rankbounds = {
    0: 25,
    1: 50,
    2: 80,
    3: 105,
    4: None}

bonus_ranks = {
    0: [0xFF, 0x0, 0x3, 0xD],
    1: [0x9, 0xB, 0xF],
    2: [0x1, 0x4, 0xA, 0xC, 0xE],
    3: [0x2, 0x5, 0x8, 0x10],
    4: [0x6]}  # Lv -1 bonus decided elsewhere

bonus_strings = {
    0: "HP + 10%",
    1: "HP + 30%",
    2: "HP + 50%",
    3: "MP + 10%",
    4: "MP + 30%",
    5: "MP + 50%",
    6: "HP + 100%",
    7: "LV - 1",
    8: "LV + 50%",
    9: "STR + 1",
    0xA: "STR + 2",
    0xB: "SPD + 1",
    0xC: "SPD + 2",
    0xD: "STA + 1",
    0xE: "STA + 2",
    0xF: "MAG + 1",
    0x10: "MAG + 2"}

spells = None
used = set([])
used_bonuses = set([])


def get_candidates(myrank, set_lower=True):
    global used
    upper_bound = rankbounds.get(myrank, 999) or 999
    lower_bound = rankbounds.get(myrank-1, 0) if set_lower else 0

    candidates = [s for s in spells
                  if s.rank() in range(lower_bound, upper_bound)]
    if not candidates:
        candidates = spells
    fresh = [s for s in candidates if s not in used]
    if not fresh:
        fresh = candidates

    return fresh

def allocate_espers(ancient_cave, espers, characters, fout):
    char_ids = list(range(12)) + [13] # everyone but Gogo

    characters = [c for c in characters if c.id in char_ids]

    chars_for_esper = []
    max_rank = max(espers, key=lambda e: e.rank).rank
    for e in espers:
        num_users = 1
        if e.id not in [15, 16] and random.randint(1, 25) >= 25 - max_rank + e.rank:
            num_users += 1
            while num_users < 15 and random.choice([True] + [False] * (e.rank + 2)):
                num_users += 1
        users = random.sample(characters, num_users)
        chars_for_esper.append([c.id for c in users])

    if not ancient_cave:
        chars_for_esper[12] = chars_for_esper[11]   # make Odin and Raiden equippable by the same person/people

    char_mask_for_esper = [
        reduce(lambda x, y: x | y,
               [1 << char_id for char_id in chars_for_esper[e.id]]
               ) for e in espers
    ]

    for e in espers:
        e.chars = ", ".join([c.newname for c in characters if c.id in chars_for_esper[e.id]])

    # do substitution
    esper_allocator_sub = Substitution()
    esper_allocator_sub.set_location(0x31B61)
    esper_allocator_sub.bytestring = [0x20, 0x00, 0xF8]
    esper_allocator_sub.write(fout)

    esper_allocator_sub.set_location(0x35524)
    esper_allocator_sub.bytestring = [0x20, 0x07, 0xF8]
    esper_allocator_sub.write(fout)

    esper_allocator_sub.set_location(0x358E1)
    esper_allocator_sub.write(fout)

    esper_allocator_sub.set_location(0x359B1)
    esper_allocator_sub.write(fout)

    esper_allocator_sub.set_location(0x35593)
    esper_allocator_sub.bytestring = [0xA9, 0x2C]
    esper_allocator_sub.write(fout)

    esper_allocator_sub.set_location(0x355B2)
    esper_allocator_sub.bytestring = [0x20, 0x2E, 0xF8]
    esper_allocator_sub.write(fout)

    esper_allocator_sub.set_location(0x358E8)
    esper_allocator_sub.bytestring = [0xC9, 0x20, 0xF0, 0x16]
    esper_allocator_sub.write(fout)

    esper_allocator_sub.set_location(0x3F800)

    esper_allocator_sub.bytestring = [
        0xAA, 0xB5, 0x69, 0x8D, 0xF8, 0x1C, 0x60, 0xDA, 0x08, 0x85, 0xE0, 0x0A, 0xAA, 0xE2, 0x10, 0xDA, 0xAD, 0xF8, 0x1C, 0x0A, 0xAA, 0xC2,
        0x20, 0xBF, 0x67, 0x9C, 0xC3, 0xFA, 0x3F, 0x58, 0xF8, 0xC3, 0xF0, 0x05, 0x28, 0xFA, 0x4C, 0x76, 0x55, 0x28, 0xFA, 0xA9, 0x28, 0x4C,
        0x95, 0x55, 0xBD, 0x02, 0x16, 0xC9, 0x80, 0xB0, 0x0F, 0xFA, 0xA6, 0x00, 0xBF, 0x4B, 0xF8, 0xC3, 0xF0, 0x07, 0x8D, 0x80, 0x21, 0xE8,
        0x80, 0xF4, 0x60, 0x9C, 0x80, 0x21, 0x4C, 0xD9, 0x7F, 0x82, 0x9A, 0xA7, 0xC3, 0xAD, 0xFF, 0x9E, 0xAA, 0xAE, 0xA2, 0xA9, 0xBE, 0x00] + [
            i for sublist in map(int2bytes, char_mask_for_esper) for i in sublist]
    esper_allocator_sub.write(fout)

class EsperBlock:
    def __init__(self, pointer, name, rank):
        self.pointer = hex2int(pointer)
        self.name = name
        self.rank = int(rank)
        self.spells = []
        self.learnrates = []
        self.bonus = None
        self.id = None

    def set_id(self, esperid):
        self.id = esperid

    def __repr__(self):
        assert len(self.spells) == len(self.learnrates)
        s = self.name.upper() + "\n"
        for spell, learnrate in zip(self.spells, self.learnrates):
            s += "{0:6}  x{1}\n".format(spell.name, learnrate)
        s += "BONUS: "
        if self.bonus in bonus_strings:
            s += bonus_strings[self.bonus]
        else:
            s += "None"
        chars = getattr(self, 'chars', None)
        if chars:
            s += "\nEQUIPPED BY: " + chars
        return s

    def read_data(self, filename):
        global spells
        f = open(filename, 'r+b')
        f.seek(self.pointer)
        if spells is None:
            spells = get_ranked_spells(filename, magic_only=True)
        self.spells, self.learnrates = [], []
        for _ in range(5):
            learnrate = ord(f.read(1))
            spell = ord(f.read(1))
            if spell != 0xFF and learnrate != 0:
                self.spells.append(get_spell(spell))
                self.learnrates.append(learnrate)
        self.bonus = ord(f.read(1))
        f.close()

    def write_data(self, fout):
        fout.seek(self.pointer)
        for learnrate, spell in zip(self.learnrates, self.spells):
            fout.write(bytes([learnrate]))
            fout.write(bytes([spell.spellid]))
        for _ in range(5 - len(self.spells)):
            fout.write(b'\x00')
            fout.write(b'\xFF')
        fout.write(bytes([self.bonus]))

    def get_candidates(self, rank, set_lower=True, allow_quick=False):
        candidates = get_candidates(rank, set_lower=set_lower)
        if not allow_quick:
            quick = [s for s in candidates if s.name == "Quick"]
            if quick:
                quick = quick[0]
                candidates.remove(quick)
        return candidates

    def generate_spells(self, tierless=False):
        global used

        self.spells, self.learnrates = [], []
        rank = self.rank
        if random.randint(1, 5) == 5:
            rank += 1
        rank = min(rank, max(rankbounds.keys()))

        if random.randint(1, 10) != 10:
            candidates = self.get_candidates(rank, set_lower=not tierless, allow_quick=tierless)
            if candidates:
                s = random.choice(candidates)
                self.spells.append(s)
                used.add(s)

        rank = self.rank
        for _ in range(random.randint(0, 2) + random.randint(0, 2)):
            candidates = self.get_candidates(rank, set_lower=False, allow_quick=tierless)
            if candidates:
                s = random.choice(candidates)
                if s in self.spells:
                    continue
                self.spells.append(s)
                used.add(s)

        self.spells = sorted(self.spells, key=lambda s: s.spellid)
        self.learnrates = []
        esperrank = rankbounds[self.rank]
        if esperrank is None:
            esperrank = rankbounds[self.rank-1]
        esperrank = esperrank * 3
        for s in self.spells:
            spellrank = s.rank()
            learnrate = int(esperrank / float(spellrank))
            learnrate = random.randint(0, learnrate) + random.randint(0, learnrate)
            while random.randint(1, 3) == 3:
                learnrate += 1
            learnrate = max(1, min(learnrate, 20))
            self.learnrates.append(learnrate)

    def generate_bonus(self):
        rank = self.rank
        candidates = set(bonus_ranks[rank])
        candidates = candidates - used_bonuses
        if candidates:
            candidates = sorted(candidates)
            self.bonus = random.choice(candidates)
            used_bonuses.add(self.bonus)
            return

        if random.randint(1, 2) == 2:
            rank += 1
        while random.randint(1, 10) == 10:
            rank += 1
        rank = min(rank, 4)
        candidates = []
        for i in range(rank+1):
            candidates.extend(bonus_ranks[i])
        if candidates:
            self.bonus = random.choice(candidates)
        used_bonuses.add(self.bonus)

    def add_spell(self, spellid, learnrate):
        spell = [s for s in spells if s.spellid == spellid][0]
        spellrates = list(zip(self.spells, self.learnrates))
        if len(spellrates) == 5:
            spellrates = sorted(spellrates, key=lambda s_l: s_l[0].rank())
            spellrates = spellrates[1:]
        spellrates.append((spell, learnrate))
        spellrates = sorted(spellrates, key=lambda s_l1: s_l1[0].spellid)
        self.spells, self.learnrates = list(zip(*spellrates))

@dataclass
class Magicite:
    address: int
    original_esper_index: int
    epser_index: int = field(init=False)
    dialogue: List[int] = field(default_factory=list)

def randomize_magicite(fout, sourcefile):
    magicite = []

    espers = get_espers(sourcefile)
    shuffled_espers = espers.copy()
    random.shuffle(shuffled_espers)

    with open(sourcefile, 'br') as s:
        for line in open(MAGICITE_TABLE, 'r'):
            line = line.split('#')[0].strip()
            l = line.split(',')
            address = int(l[0], 16)
            dialogue = [int(d, 16) for d in l[1:]]

            s.seek(address)
            instruction = ord(s.read(1))
            esper_index = ord(s.read(1))
            if instruction not in [0x86, 0x87] or esper_index < 0x36 or esper_index > 0x50:
                print("Error in magicite table")
                return
            magicite.append(Magicite(address, esper_index - 0x36, dialogue))

    for m in magicite:
        original_name = espers[m.original_esper_index].name
        m.esper_index = shuffled_espers[m.original_esper_index].id
        new_name = espers[m.esper_index].name
        for d in m.dialogue:
            patch_dialogue(d, original_name, "{"+ original_name + "}")
            patch_dialogue(d, original_name + "'s", "{"+ original_name + "Possessive}")
            dotted_name = "".join(chain(*zip(original_name, repeat('.'))))[:-1]
            patch_dialogue(d, dotted_name, "{" + original_name + "Dotted}")
        set_dialogue_var(original_name, new_name)
        set_dialogue_var(original_name + "Possessive", new_name + "'s")
        dotted_new_name = "".join(chain(*zip(new_name, repeat('.'))))[:-1]
        set_dialogue_var(original_name + "Dotted", dotted_new_name)
        fout.seek(m.address + 1)
        fout.write(bytes([m.esper_index + 0x36]))

all_espers = None

def get_espers(sourcefile):
    global all_espers
    if all_espers:
        return all_espers

    all_espers = []
    for i, line in enumerate(open(ESPER_TABLE)):
        line = line.strip()
        if line[0] == '#':
            continue

        while '  ' in line:
            line = line.replace('  ', ' ')
        c = EsperBlock(*line.split(','))
        c.read_data(sourcefile)
        c.set_id(i)
        all_espers.append(c)
    return get_espers(sourcefile)
