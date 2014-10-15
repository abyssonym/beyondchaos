from utils import hex2int, utilrandom as random
from skillrandomizer import get_ranked_spells

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

spells = None
used = set([])


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
    fresh = []
    while not fresh:
        fresh = filter(lambda s: s not in used, candidates)
        if not fresh:
            used = used - set(candidates)

    return fresh


class EsperBlock:
    def __init__(self, pointer, name, rank):
        self.pointer = hex2int(pointer)
        self.name = name
        self.rank = int(rank)

    def set_id(self, esperid):
        self.id = esperid

    def read_data(self, filename):
        global spells
        f = open(filename, 'r+b')
        f.seek(self.pointer)
        f.close()
        if spells is None:
            spells = get_ranked_spells(filename, magic_only=True)

    def write_data(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.pointer)
        for learnrate, spell in zip(self.learnrates, self.spells):
            f.write(chr(learnrate))
            f.write(chr(spell.spellid))
        for i in xrange(5 - len(self.spells)):
            f.write(chr(0x0))
            f.write(chr(0xFF))
        f.write(chr(self.bonus))
        f.close()

    def get_candidates(self, rank, set_lower=True):
        candidates = get_candidates(rank, set_lower=set_lower)
        ultima = [s for s in candidates if s.name == "Ultima"]
        if ultima:
            ultima = ultima[0]
            candidates.remove(ultima)
        return candidates

    def generate_spells(self):
        global used

        self.spells = []
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

    def add_spell(self, spellid, learnrate):
        spell = [s for s in spells if s.spellid == spellid][0]
        spellrates = zip(self.spells, self.learnrates)
        spellrates.append((spell, learnrate))
        if len(spellrates) > 5:
            spellrates = sorted(spellrates, key=lambda (s, l): s.rank())
            spellrates = spellrates[1:]
        spellrates = sorted(spellrates, key=lambda (s, l): s.spellid)
        self.spells, self.learnrates = zip(*spellrates)
