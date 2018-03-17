from utils import hex2int, int2bytes, Substitution, utilrandom as random
from skillrandomizer import get_ranked_spells, get_spell

items = None

rankbounds = {0: 25,
              1: 50,
              2: 80,
              3: 105,
              4: None}

bonus_ranks = {0: [0xFF, 0x0, 0x3, 0xD],
               1: [0x9, 0xB, 0xF],
               2: [0x1, 0x4, 0xA, 0xC, 0xE],
               3: [0x2, 0x5, 0x8, 0x10],
               4: [0x6]}  # Lv -1 bonus decided elsewhere

bonus_strings = {0: "HP + 10%",
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
    lower_bound, upper_bound = None, None
    if myrank in rankbounds:
        upper_bound = rankbounds[myrank]
    if upper_bound is None:
        upper_bound = 999

    if myrank-1 in rankbounds and set_lower:
        lower_bound = rankbounds[myrank-1]
    else:
        lower_bound = 0
    candidates = filter(lambda s: s.rank() in
                        range(lower_bound, upper_bound), spells)
    fresh = filter(lambda s: s not in used, candidates)
    if not fresh:
        fresh = candidates

    return fresh

def allocate_espers(ancient_cave, espers, characters, fout):
    char_ids = range(12) + [13] # everyone but Gogo
    
    characters = [c for c in characters if c.id in char_ids]
    
    chars_for_esper = [[random.choice(char_ids)] for e in espers]
    
    if not ancient_cave:
        chars_for_esper[12] = chars_for_esper[11]   # make Odin and Raiden equippable by the same person
    
    char_mask_for_esper = [ 
        reduce( lambda x, y: x | y,
                [1 << char_id for char_id in chars_for_esper[e.id]]
                ) for e in espers
    ]

    for e in espers:
        e.chars = ", ".join([c.newname for c in characters if c.id in chars_for_esper[e.id]])
    
    # do substitution
    esper_allocator_sub = Substitution()
    esper_allocator_sub.set_location(0x31B61)
    esper_allocator_sub.bytestring = [0x20,0x00,0xF8]
    esper_allocator_sub.write(fout)
    
    esper_allocator_sub.set_location(0x35524)
    esper_allocator_sub.bytestring = [0x20,0x07,0xF8]
    esper_allocator_sub.write(fout)
    
    esper_allocator_sub.set_location(0x358E1)
    esper_allocator_sub.write(fout)
    
    esper_allocator_sub.set_location(0x359B1)
    esper_allocator_sub.write(fout)
    
    esper_allocator_sub.set_location(0x35593)
    esper_allocator_sub.bytestring = [0xA9,0x2C]
    esper_allocator_sub.write(fout)
    
    esper_allocator_sub.set_location(0x355B2)
    esper_allocator_sub.bytestring = [0x20,0x2E,0xF8]
    esper_allocator_sub.write(fout)
    
    esper_allocator_sub.set_location(0x358E8)
    esper_allocator_sub.bytestring = [0xC9,0x20,0xF0,0x16]
    esper_allocator_sub.write(fout)
    
    esper_allocator_sub.set_location(0x3F800)
    
    esper_allocator_sub.bytestring = [0xAA, 0xB5, 0x69, 0x8D, 0xF8, 0x1C, 0x60, 0xDA, 0x08, 0x85, 0xE0, 0x0A, 0xAA, 0xE2, 0x10, 0xDA, 0xAD, 0xF8, 0x1C, 0x0A, 0xAA, 0xC2, 0x20, 0xBF, 0x67, 0x9C, 0xC3, 0xFA, 0x3F, 0x58, 0xF8, 0xC3, 0xF0, 0x05, 0x28, 0xFA, 0x4C, 0x76, 0x55, 0x28, 0xFA, 0xA9, 0x28, 0x4C, 0x95, 0x55, 0xBD, 0x02, 0x16, 0xC9, 0x80, 0xB0, 0x0F, 0xFA, 0xA6, 0x00, 0xBF, 0x4B, 0xF8, 0xC3, 0xF0, 0x07, 0x8D, 0x80, 0x21, 0xE8, 0x80, 0xF4, 0x60, 0x9C, 0x80, 0x21, 0x4C, 0xD9, 0x7F, 0x82, 0x9A, 0xA7, 0xC3, 0xAD, 0xFF, 0x9E, 0xAA, 0xAE, 0xA2, 0xA9, 0xBE, 0x00] + [i for sublist in map(int2bytes, char_mask_for_esper) for i in sublist]
    esper_allocator_sub.write(fout)
    
class EsperBlock:
    def __init__(self, pointer, name, rank):
        self.pointer = hex2int(pointer)
        self.name = name
        self.rank = int(rank)

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
        for i in xrange(5):
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
            fout.write(chr(learnrate))
            fout.write(chr(spell.spellid))
        for i in xrange(5 - len(self.spells)):
            fout.write(chr(0x0))
            fout.write(chr(0xFF))
        fout.write(chr(self.bonus))

    def get_candidates(self, rank, set_lower=True):
        candidates = get_candidates(rank, set_lower=set_lower)
        quick = [s for s in candidates if s.name == "Quick"]
        if quick:
            quick = quick[0]
            candidates.remove(quick)
        return candidates

    def generate_spells(self):
        global used

        self.spells, self.learnrates = [], []
        rank = self.rank
        if random.randint(1, 5) == 5:
            rank += 1
        rank = min(rank, max(rankbounds.keys()))

        if random.randint(1, 10) != 10:
            candidates = self.get_candidates(rank)
            if candidates:
                s = random.choice(candidates)
                self.spells.append(s)
                used.add(s)

        rank = self.rank
        for _ in xrange(random.randint(0, 2) + random.randint(0, 2)):
            candidates = self.get_candidates(rank, set_lower=False)
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
        spellrates = zip(self.spells, self.learnrates)
        if len(spellrates) == 5:
            spellrates = sorted(spellrates, key=lambda (s, l): s.rank())
            spellrates = spellrates[1:]
        spellrates.append((spell, learnrate))
        spellrates = sorted(spellrates, key=lambda (s, l): s.spellid)
        self.spells, self.learnrates = zip(*spellrates)
