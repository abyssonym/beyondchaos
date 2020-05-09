import copy
from dataclasses import dataclass, field
from functools import reduce
from itertools import chain, repeat
from typing import List

from dialoguemanager import patch_dialogue, set_dialogue_var, set_location_name
from itemrandomizer import get_item
from monsterrandomizer import change_enemy_name, get_monster, MonsterGraphicBlock
from skillrandomizer import get_ranked_spells, get_spell
from utils import ESPER_TABLE, MAGICITE_TABLE, hex2int, int2bytes, name_to_bytes, Substitution, utilrandom as random

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

def allocate_espers(ancient_cave, espers, characters, fout, replacements=None):
    char_ids = list(range(12)) + [13] # everyone but Gogo

    characters = [c for c in characters if c.id in char_ids]

    chars_for_esper = []
    max_rank = max(espers, key=lambda e: e.rank).rank
    crusader_id = 15
    ragnarok_id = 16
    if replacements:
        crusader_id = replacements[crusader_id].id
        ragnarok_id = replacements[ragnarok_id].id

    for e in espers:
        num_users = 1
        if e.id not in [crusader_id, ragnarok_id] and random.randint(1, 25) >= 25 - max_rank + e.rank:
            num_users += 1
            while num_users < 15 and random.choice([True] + [False] * (e.rank + 2)):
                num_users += 1
        users = random.sample(characters, num_users)
        chars_for_esper.append([c.id for c in users])

    if not ancient_cave:
        odin_id = 11
        raiden_id = 12
        if replacements:
            odin_id = replacements[odin_id].id
            raiden_id = replacements[raiden_id].id

        chars_for_esper[raiden_id] = chars_for_esper[odin_id]   # make Odin and Raiden equippable by the same person/people

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
    def __init__(self, pointer, name, rank, location):
        self.pointer = hex2int(pointer)
        self.name = name
        self.rank = int(rank)
        self.spells = []
        self.learnrates = []
        self.bonus = None
        self.id = None
        self.location = location

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
        s += "\nLOCATION: " + self.location
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


def select_magicite(candidates, esper_ids_to_replace):
    results = {}
    replacements = random.sample(candidates, len(esper_ids_to_replace))
    for esper_id, replacement in zip(esper_ids_to_replace, replacements):
        results[esper_id] = replacement
    return results


def randomize_magicite(fout, sourcefile):
    magicite = []

    # Some espers use 128x128 graphics, and those look like crap in the Ifrit/Shiva fight
    # So make sure Ifrit and Shiva have espers with small graphics. Tritoch also has
    # Issues with large sprites in the cutscene with the MagiTek armor
    espers = get_espers(sourcefile)
    shuffled_espers = {}
    espers_by_name = {e.name: e for e in espers}
    esper_graphics = [MonsterGraphicBlock(pointer=0x127780 + (5*i), name="") for i in range(len(espers))]
    for eg in esper_graphics:
        eg.read_data(sourcefile)

    # Ifrit's esper graphics are large. But he has separate enemy graphics that are fine.
    ifrit_graphics = copy.copy(get_monster(0x109).graphics)
    ifrit_id = espers_by_name["Ifrit"].id
    esper_graphics[ifrit_id] = ifrit_graphics

    # Pick the replacements for Ragnarok/Crusader out of high-rank espers
    high_rank_espers = [e for e in espers if e.rank >= 4]
    replace_ids = [espers_by_name[name].id for name in ["Ragnarok", "Crusader"]]
    special_espers = select_magicite(high_rank_espers, replace_ids)
    shuffled_espers.update(special_espers)

    # Pick replacements for Shiva, Ifrit, and Tritoch, which must not be large
    # Shiva and Ifrit must be picked from rank < 3, Tritoch can be any
    small_espers = [e for e in espers
                    if not esper_graphics[e.id].large and e not in shuffled_espers.values()]
    low_ranked_small_espers = [e for e in small_espers if e.rank < 3]
    replace_ids = [espers_by_name[name].id for name in ["Shiva", "Ifrit"]]
    enemy_espers = select_magicite(low_ranked_small_espers, replace_ids)
    shuffled_espers.update(enemy_espers)

    remaining_small_espers = [e for e in small_espers if e not in enemy_espers.values()]
    replace_ids = [espers_by_name["Tritoch"].id]
    enemy_espers = select_magicite(remaining_small_espers, replace_ids)
    shuffled_espers.update(enemy_espers)

    # TODO: maybe allow tritoch to be big if we skip cutscenes
    #tritoch_id = [e.id for e in espers if e.name == "Tritoch"][0]
    #if esper_graphics[tritoch_id].large:
    #    tritoch_formations = [0x1BF, 0x1C0, 0x1E7, 0x1E8]
    #    for g in tritoch_formations:
    #        f = get_formation(g)
    #        f.mouldbyte = 6 << 4
    #        f.enemy_pos[0] = f.enemy_pos[0] & 0xF0 + 3
    #        f.write_data(fout)

    # Make sure Odin's replacement levels up
    odin_id = espers_by_name["Odin"].id
    raiden_id = espers_by_name["Raiden"].id

    while True:
        odin_candidates = [e for e in espers if e not in shuffled_espers.values() and e.rank <= 3]
        odin_replacement = select_magicite(odin_candidates, [odin_id])
        odin_replacement_rank = odin_replacement[odin_id].rank
        raiden_candidates = [e for e in espers if e not in shuffled_espers.values() and e.rank > odin_replacement_rank]
        if not raiden_candidates:
            continue
        raiden_replacement = select_magicite(raiden_candidates, [raiden_id])
        shuffled_espers.update(odin_replacement)
        shuffled_espers.update(raiden_replacement)
        break

    # Shuffle all remaining espers
    for rank in range(0, 5):
        remaining_keys = [e.id for e in espers if e.id not in shuffled_espers.keys() and e.rank <= rank]
        remaining_values = [e for e in espers if e not in shuffled_espers.values() and e.rank <= max(rank + 1, 2)]
        random.shuffle(remaining_values)
        shuffled_espers.update(zip(remaining_keys, remaining_values))

    assert(sorted([e.id for e in espers], key=id) == sorted(shuffled_espers.keys()))
    assert(sorted(espers, key=id) == sorted(shuffled_espers.values(), key=id))

    locations = [e.location for e in espers]
    for i, e in shuffled_espers.items():
        e.location = locations[i]

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
        new_name = shuffled_espers[m.original_esper_index].name

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

    phoenix_replacement = shuffled_espers[espers_by_name["Phoenix"].id]
    set_location_name(71, f"{phoenix_replacement.name.upper()} CAVE")

    esper_monsters = [(0x108, "Shiva"), (0x109, "Ifrit"), (0x114, "Tritoch"), (0x115, "Tritoch"), (0x144, "Tritoch")]

    for monster_id, name in esper_monsters:
        monster = get_monster(monster_id)
        esper_id = [e.id for e in espers if e.name == name][0]
        replacement = shuffled_espers[esper_id]
        change_enemy_name(fout, monster_id, replacement.name)
        mg = esper_graphics[replacement.id]
        monster.graphics.copy_data(mg)
        monster.graphics.write_data(fout)

    ragnarok = get_item(27)
    ragnarok.dataname = bytes([0xd9]) + name_to_bytes(shuffled_espers[espers_by_name["Ragnarok"].id].name, 12)
    ragnarok.write_stats(fout)

    return shuffled_espers

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
