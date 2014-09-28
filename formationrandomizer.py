from utils import read_multi, write_multi, utilrandom as random
from math import log


class Formation():
    def __init__(self, formid):
        self.formid = formid
        self.pointer = 0xf6200 + (formid*15)
        self.auxpointer = 0xf5900 + (formid*4)

    def __repr__(self):
        counter = {}
        for e in self.present_enemies:
            if e.name not in counter:
                counter[e.name] = 0
            counter[e.name] += 1
        s = ""
        for name, count in sorted(counter.items()):
            s = ', '.join([s, "%s x%s" % (name, count)])
        s = s[2:]
        #return s
        return "%s (%x)" % (s, self.formid)

    @property
    def pincer_prohibited(self):
        return self.misc1 & 0x40

    def read_data(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.pointer)
        self.mouldbyte = ord(f.read(1))
        self.mould = self.mouldbyte >> 4
        self.enemies_present = ord(f.read(1))
        self.enemy_ids = map(ord, f.read(6))
        self.enemy_pos = map(ord, f.read(6))
        self.bosses = ord(f.read(1))

        f.seek(self.auxpointer)
        self.misc1 = ord(f.read(1))
        self.misc2 = ord(f.read(1))
        self.eventscript = ord(f.read(1))
        self.misc3 = ord(f.read(1))
        f.close()

    @property
    def mould(self):
        return self.mouldbyte >> 4

    @property
    def has_event(self):
        return bool(self.misc2 & 0x80)

    @property
    def present_enemies(self):
        return [e for e in self.enemies if e]

    def set_attack_type(self, normal=True, back=False,
                        pincer=False, side=False):
        self.misc1 &= 0x0F
        self.misc1 |= 0x10 if not normal else 0
        self.misc1 |= 0x20 if not back else 0
        self.misc1 |= 0x40 if not pincer else 0
        self.misc1 |= 0x80 if not side else 0

    def set_music(self, value):
        # BATTLE THEMES
        # 0 regular
        # 1 boss
        # 2 atmaweapon
        # 3 returners theme
        # 4 minecart
        # 5 dancing mad
        # 6-7 no change
        self.misc3 &= 0b11000111
        self.misc3 |= (value << 3)

    def set_music_appropriate(self):
        music = random.randint(1, 6) if self.rank() > 35 else random.choice([1, 3, 4, 6])
        self.set_music(music)

    def set_fanfare(self, value=False):
        if value:
            self.misc1 &= 0xFE
        else:
            self.misc1 |= 1

    def set_event(self, value=False):
        if value:
            self.misc2 |= 0x80
        else:
            self.misc2 &= 0x7F
            self.eventscript = 0

    def set_windows(self, value=True):
        if value:
            self.misc3 |= 0x04
        else:
            self.misc3 &= 0xFB

    def set_appearing(self, value):
        # 0 none
        # 1 smoke
        # 2 dropdown
        # 3 from left
        # 4 splash from below
        # 5 float down
        # 6 splash from below (sand?)
        # 7 from left (fast?)
        # 8 fade in (top-bottom)
        # 9 fade in (bottom-top)
        # 10 fade in (wavey)
        # 11 fade in (slicey)
        # 12 none
        # 13 blink in
        # 14 stay below screen
        # 15 slowly fall, play Dancing Mad
        self.misc1 &= 0xF0
        self.misc1 |= value
        if value == 15:
            self.set_music(6)

    def write_data(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.pointer)
        f.write(chr(self.mouldbyte))
        f.write(chr(self.enemies_present))
        f.write("".join(map(chr, self.enemy_ids)))
        f.write("".join(map(chr, self.enemy_pos)))
        f.write(chr(self.bosses))

        f.seek(self.auxpointer)
        f.write(chr(self.misc1))
        f.write(chr(self.misc2))
        f.write(chr(self.eventscript))
        f.write(chr(self.misc3))
        f.close()

    def lookup_enemies(self, monsterdict):
        self.enemies = []
        self.big_enemy_ids = []
        for i, eid in enumerate(self.enemy_ids):
            if eid == 0xFF and not self.enemies_present & (1 << i):
                self.enemies.append(None)
                continue
            if self.enemies_present & (1 << i) and self.bosses & (1 << i):
                eid += 0x100
            self.big_enemy_ids.append(eid)
            self.enemies.append(monsterdict[eid])
            enemy_pos = self.enemy_pos[i]
            x, y = enemy_pos >> 4, enemy_pos & 0xF
            self.enemies[i].update_pos(x, y)
        for e in self.enemies:
            if not e:
                continue
            e.add_mould(self.mould)

    def set_big_enemy_ids(self, eids):
        self.bosses = 0
        self.enemy_ids = []
        for n, eid in enumerate(eids):
            if eid & 0x100:
                self.bosses |= (1 << n)
            if not self.enemies_present & (1 << n):
                self.bosses |= (1 << n)
            self.enemy_ids.append(eid & 0xFF)

    def read_mould(self, filename):
        mouldspecsptrs = 0x2D01A
        f = open(filename, 'r+b')
        pointer = mouldspecsptrs + (2*self.mould)
        f.seek(pointer)
        pointer = read_multi(f, length=2) | 0x20000
        for i in xrange(6):
            f.seek(pointer + (i*4))
            a, b = tuple(map(ord, f.read(2)))
            width = ord(f.read(1))
            height = ord(f.read(1))
            enemy = self.enemies[i]
            if enemy:
                enemy.update_size(width, height)

    def copy_data(self, other):
        attributes = [
            "mouldbyte", "enemies_present", "enemy_ids",
            "enemy_pos", "bosses", "misc1", "misc2", "eventscript",
            "misc3"]
        for attribute in attributes:
            value = getattr(other, attribute)
            value = type(value)(value)
            setattr(self, attribute, value)

    def rank(self, levels=None):
        if levels is None:
            levels = [e.stats['level'] for e in self.present_enemies if e]
        balance = sum(levels) / (log(len(levels))+1)
        average = sum(levels) / len(levels)+1
        score = (max(levels) + balance + average) / 3.0
        return int(score)

    def oldrank(self):
        levels = [e.oldlevel for e in self.present_enemies if e]
        return self.rank(levels)

    @property
    def exp(self):
        return sum(e.stats['xp'] for e in self.present_enemies)


class FormationSet():
    def __init__(self, setid):
        baseptr = 0xf4800
        self.setid = setid
        self.pointer = baseptr + (setid * 8)

    def __repr__(self):
        s = ""
        s += "SET ID %x\n" % self.setid
        for f in self.formations:
            s += "%s " % f.formid
            for i in range(8):
                    s += '* ' if f.misc1 & (1 << i) else '  '
            s += str([e.name for e in f.present_enemies]) + "\n"
        return s

    def read_data(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.pointer)
        self.formids = []
        for i in xrange(4):
            self.formids.append(read_multi(f, length=2))
        f.close()

    def write_data(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.pointer)
        for value in self.formids:
            write_multi(f, value, length=2)
        f.close()

    def mutate_formations(self, candidates, verbose=False, test=False):
        if test:
            for i in range(4):
                chosen = random.choice(candidates)
                self.formations[i] = chosen
                self.formids[i] = chosen.formid
            return self.formations

        if random.randint(1, 4) != 4:
            return []

        low = max(fo.oldrank() for fo in self.formations)
        high = low * 1.25
        while random.randint(1, 3) == 3:
            high = high * 1.25

        candidates = filter(lambda c: low <= c.rank() <= high, candidates)
        candidates = sorted(candidates, key=lambda c: c.rank())
        if not candidates:
            return []

        slots = [3]
        chosens = []
        for i in slots:
            halfway = max(0, len(candidates)/2)
            index = random.randint(0, halfway) + random.randint(0, halfway)
            index = min(index, len(candidates)-1)
            chosen = candidates[index]
            candidates.remove(chosen)
            self.formations[i] = chosen
            self.formids[i] = chosen.formid
            chosens.append(chosen)
            if not candidates:
                break

        if verbose:
            for fo in self.formations:
                print [e.name for e in fo.present_enemies]
            print

        return chosens

    def set_formations(self, formations):
        self.formations = []
        for i in self.formids:
            if i & 0x8000:
                i &= 0x7FFF
            f = [j for j in formations if j.formid == i]
            f = f[0]
            self.formations.append(f)

    def swap_formations(self, other):
        if len(set(self.formids)) == 1 or len(set(other.formids)) == 1:
            return

        formations = self.formations + other.formations
        formids = self.formids + other.formids
        random.shuffle(formids)
        self.formids = formids[:4]
        other.formids = formids[4:]
        self.set_formations(formations)
        other.set_formations(formations)

    def shuffle_formations(self):
        random.shuffle(self.formids)
        self.set_formations(list(self.formations))

    def rank(self):
        return sum(f.rank() for f in self.formations) / 4.0
