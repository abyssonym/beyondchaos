#! /usr/bin/env python3

from math import log

from monsterrandomizer import monsterdict, get_monsters
from utils import read_multi, write_multi, utilrandom as random

# Guardian x4, Broken Dirt Drgn, Kefka + Ice Dragon
REPLACE_FORMATIONS = [0x20e, 0x1ca, 0x1e9, 0x1fa]
KEFKA_EXTRA_FORMATION = 0x1FF  # Fake Atma
NOREPLACE_FORMATIONS = [0x232, 0x1c5, 0x1bb, 0x230, KEFKA_EXTRA_FORMATION]

fsetdict = None
formdict = None


class Formation():
    def __init__(self, formid):
        self.formid = formid
        self.pointer = 0xf6200 + (formid*15)
        self.auxpointer = 0xf5900 + (formid*4)
        self.mouldbyte = None
        self.enemies_present = None
        self.enemy_ids = []
        self.enemy_pos = []
        self.bosses = None

        self.misc1 = None
        self.misc2 = None
        self.eventscript = None
        self.misc3 = None

        self.ap = 0
        self.enemies = []
        self.big_enemy_ids = []

    def __repr__(self):
        return self.description()

    def description(self, renamed=False, simple=False):
        counter = {}
        for e in self.present_enemies:
            if renamed:
                name = e.display_name
            else:
                name = e.name
            name = name.strip('_')
            if name not in counter:
                counter[name] = 0
            counter[name] += 1
        s = ""
        for name, count in sorted(counter.items()):
            s = ', '.join([s, "%s x%s" % (name, count)])
        s = s[2:]
        if simple:
            return s
        s = "%s (%x)" % (s, self.formid)
        #s += " " + " ".join(["%x" % e.id for e in self.present_enemies])
        return s

    @property
    def has_boss(self):
        return any([e.is_boss or e.boss_death for e in self.present_enemies])

    @property
    def is_fanatics(self):
        for e in self.present_enemies:
            if e.id in [0x125, 0x12b, 0x130, 0x132, 0x133,
                        0x139, 0x143, 0x163, 0x164]:
                return True
        return False

    def get_guaranteed_drop_value(self, value=0):
        if not self.present_enemies:
            return False

        values = []
        for e in self.present_enemies:
            for d in e.drops:
                value = 1000000
                if d is None:
                    value = 0
                else:
                    value = min(value, d.rank())
            values.append(value)
        return max(values)

    def get_best_drop(self):
        drops = []
        for e in self.present_enemies:
            for d in e.drops:
                if d is not None:
                    drops.append(d)

        if not drops:
            return None
        return max(drops, key=lambda d: d.rank())

    @property
    def veldty(self):
        return self.formid <= 0x1af

    @property
    def pincer_prohibited(self):
        return self.misc1 & 0x40

    @property
    def back_prohibited(self):
        return self.misc1 & 0x20

    @property
    def battle_event(self):
        return any([m.battle_event for m in self.present_enemies])

    def read_data(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.pointer)
        self.mouldbyte = ord(f.read(1))
        self.enemies_present = ord(f.read(1))
        self.enemy_ids = list(f.read(6))
        self.enemy_pos = list(f.read(6))
        self.bosses = ord(f.read(1))

        f.seek(self.auxpointer)
        self.misc1 = ord(f.read(1))
        self.misc2 = ord(f.read(1))
        self.eventscript = ord(f.read(1))
        self.misc3 = ord(f.read(1))

        appointer = 0x1fb400 + self.formid
        if appointer < 0x1fb600:
            f.seek(0x1fb400 + self.formid)
            self.ap = ord(f.read(1))
        else:
            self.ap = None

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

    @property
    def ambusher(self):
        return any([e.ambusher for e in self.present_enemies])

    @property
    def inescapable(self):
        return any([e.inescapable for e in self.present_enemies])

    def set_attack_type(self, normal=True, back=False,
                        pincer=False, side=False):
        self.misc1 &= 0x0F
        self.misc1 |= 0x10 if not normal else 0
        self.misc1 |= 0x20 if not back else 0
        self.misc1 |= 0x40 if not pincer else 0
        self.misc1 |= 0x80 if not side else 0

    def get_music(self):
        return (self.misc3 >> 3) & 0b111

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

    def set_continuous_music(self):
        self.misc3 |= 0x80
        self.misc2 |= 0x02

    def set_music_appropriate(self):
        music = random.randint(1, 5) if self.rank() > 35 else random.choice([1, 3, 4])
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
        if isinstance(value, (list, tuple, set)):
            value = random.choice(sorted(value))
        self.misc1 &= 0xF0
        self.misc1 |= value
        if value == 15:
            self.set_music(6)

    def write_data(self, fout):
        fout.seek(self.pointer)
        fout.write(bytes([self.mouldbyte]))
        fout.write(bytes([self.enemies_present]))
        fout.write(bytes(self.enemy_ids))
        fout.write(bytes(self.enemy_pos))
        fout.write(bytes([self.bosses]))

        fout.seek(self.auxpointer)
        fout.write(bytes([self.misc1]))
        fout.write(bytes([self.misc2]))
        fout.write(bytes([self.eventscript]))
        fout.write(bytes([self.misc3]))

        if self.ap is not None:
            fout.seek(0x1fb400 + self.formid)
            fout.write(bytes([self.ap]))

    def lookup_enemies(self):
        self.enemies = []
        self.big_enemy_ids = []
        for i, eid in enumerate(self.enemy_ids):
            if eid == 0xFF and not self.enemies_present & (1 << i):
                self.enemies.append(None)
                continue
            if self.bosses & (1 << i):
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
        for i in range(6):
            f.seek(pointer + (i*4))
            _, _ = tuple(f.read(2))
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

    def levelrank(self):
        ranks = [e.stats['level'] for e in self.present_enemies if e]
        if not ranks:
            return 0
        balance = sum(ranks) / (log(len(ranks))+1)
        average = sum(ranks) / len(ranks)
        score = (max(ranks) + balance + average) / 3.0
        return score

    def rank(self):
        ranks = [e.rank() for e in self.present_enemies if e]
        if not ranks:
            return 0
        balance = sum(ranks) / (log(len(ranks))+1)
        average = sum(ranks) / len(ranks)
        score = (max(ranks) + balance + average) / 3.0
        return score

    @property
    def exp(self):
        return sum(e.stats['xp'] for e in self.present_enemies)

    def mutate(self, ap=False):
        if ap and self.ap is not None and 0 < self.ap < 100:
            factor = self.levelrank() / 100
            self.ap += int(round(self.ap * factor))
            while random.choice([True, False]):
                self.ap += random.randint(-1, 1)
                self.ap = min(100, max(self.ap, 0))
        if self.ambusher:
            if not (self.pincer_prohibited and self.back_prohibited):
                self.misc1 |= 0x90

    def get_special_ap(self):
        levels = [e.stats['level'] for e in self.present_enemies if e]
        ap = int(sum(levels) // len(levels))
        low = ap // 2
        ap = low + random.randint(0, low) + random.randint(0, low)
        ap = random.randint(0, ap)
        self.ap = min(100, max(ap, 0))


class FormationSet():
    def __init__(self, setid):
        baseptr = 0xf4800
        self.setid = setid
        if self.setid <= 0xFF:
            self.pointer = baseptr + (setid * 8)
        else:
            self.pointer = baseptr + (0x100 * 8) + ((setid - 0x100) * 4)
        self.formids = []
        self.sixteen_pack = False

    def __repr__(self):
        s = ""
        s += "SET ID %x\n" % self.setid
        for f in self.formations:
            s += "%s " % f.formid
            for i in range(8):
                s += '* ' if f.misc1 & (1 << i) else '  '
            s += str([e.name for e in f.present_enemies]) + "\n"
        return s.strip()

    @property
    def formations(self):
        return [formdict[i & 0x7FFF] for i in self.formids]

    @property
    def unused(self):
        if self.setid == 0x100:
            return False
        return all([f.formid == 0 for f in self.formations])

    @property
    def has_boss(self):
        return any([f.has_boss for f in self.formations])

    @property
    def veldty(self):
        return all([f.veldty for f in self.formations])

    def read_data(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.pointer)
        self.formids = []
        if self.setid <= 0xFF:
            num_encounters = 4
        else:
            num_encounters = 2
        for _ in range(num_encounters):
            self.formids.append(read_multi(f, length=2))
        if any([f & 0x8000 for f in self.formids]):
            assert all([f & 0x8000 for f in self.formids])
            self.sixteen_pack = True
        else:
            self.sixteen_pack = False
        f.close()


    def write_data(self, fout):
        fout.seek(self.pointer)
        for value in self.formids:
            if self.sixteen_pack:
                value |= 0x8000
            else:
                value &= 0x7FFF
            write_multi(fout, value, length=2)

    def remove_redundant_formation(self, fsets, replacement=None,
                                   check_only=False):
        result = False
        if len(set(self.formations)) == 1:
            pass
        elif len(set(self.formations)) < 4:
            result = True
            if replacement:
                for i in range(4):
                    if self.formids[i] in self.formids[i+1:]:
                        formid = self.formids[i]
                        self.formids.remove(formid)
                        random.shuffle(self.formids)
                        self.formids.append(replacement.formid)
        else:
            formations = list(self.formations)
            random.shuffle(formations)
            for i in range(4):
                f = self.formations[i]
                for fs2 in fsets:
                    if fs2 != self and f in fs2.formations:
                        result = True
                        if replacement:
                            formid = self.formids[i]
                            self.formids.remove(formid)
                            random.shuffle(self.formids)
                            self.formids.append(replacement.formid)
                            break
                if result is True:
                    break

        if replacement:
            try:
                assert len(self.formations) == 4
                assert self.formations[3] == replacement
            except:
                return False
            return True

        if not check_only and result is False:
            raise Exception("Can't use this formation.")

        return result

    @property
    def swappable(self):
        if len(self.formids) < 4 or len(set(self.formids)) == 1:
            return False
        return True

    def swap_formations(self, other):
        if not (self.swappable and other.swappable):
            return

        highself = max(self.formations, key=lambda f: f.rank())
        highother = max(other.formations, key=lambda f: f.rank())
        candidates = self.formations + other.formations
        if random.randint(1, 7) != 7:
            candidates.remove(highself)
            candidates.remove(highother)
        random.shuffle(candidates)
        formids = [f.formid for f in candidates]
        self.formids = formids[:len(formids)//2]
        other.formids = formids[len(formids)//2:]
        if len(formids) == 6:
            self.formids.append(highself.formid)
            other.formids.append(highother.formid)
        self.shuffle_formations()
        other.shuffle_formations()

    def shuffle_formations(self):
        random.shuffle(self.formids)

    def rank(self):
        return sum(f.rank() for f in self.formations) / 4.0


def get_formation(formid):
    global formdict
    return formdict[formid]


def get_formations(filename=None):
    global formdict
    if formdict:
        return [f for (_, f) in sorted(formdict.items())]

    formdict = {}
    for i in range(576):
        f = Formation(i)
        f.read_data(filename)
        f.lookup_enemies()
        f.read_mould(filename)
        formdict[i] = f

    return get_formations()


def get_fsets(filename=None):
    global fsetdict
    if filename is None or fsetdict:
        fsets = [fs for (_, fs) in sorted(fsetdict.items())]
        return fsets

    fsetdict = {}
    for i in range(512):
        fs = FormationSet(setid=i)
        fs.read_data(filename)
        fsetdict[i] = fs
    return get_fsets()


def get_fset(setid):
    return fsetdict[setid]


if __name__ == "__main__":
    from sys import argv
    filename = argv[1]
    monsters = get_monsters(filename)
    for m in monsters:
        m.read_stats(filename)
    formations = get_formations(filename=filename)
    fsets = get_fsets(filename=filename)
    for f in formations:
        print(f, f.ap)

    #for f in fsets:
    #    print f
    #    print f.formids
