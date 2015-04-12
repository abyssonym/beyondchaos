from utils import read_multi, write_multi, mutate_index, utilrandom as random
from itemrandomizer import get_ranked_items, get_item
from formationrandomizer import get_formations, get_fsets

valid_ids = range(1, 0x200)
banned_formids = [0]
extra_miabs = []
orphaned_formations = None
used_formations = []

appropriate_formations = None

EVENT_ENEMIES = [0x00, 0x01, 0x02, 0x09, 0x19, 0x1b, 0x22, 0x24, 0x33, 0x38,
                 0x39, 0x3a, 0x42, 0x43, 0x50, 0x59, 0x5e, 0x64, 0x73, 0x7f,
                 0xd1, 0xe3]


def add_orphaned_formation(formation):
    global orphaned_formations
    orphaned_formations.append(formation)


def get_orphaned_formations():
    global orphaned_formations
    if orphaned_formations is not None:
        return orphaned_formations

    orphaned_formations = set([])
    from monsterrandomizer import get_monsters
    monsters = get_monsters()
    extra_miabs = get_extra_miabs(0)
    for m in monsters:
        if m.id in EVENT_ENEMIES:
            m.auxloc = "Event Battle"
            continue
        if not m.is_boss:
            location = m.determine_location()
            if "missing" in location.lower() or not location.strip():
                formations = set([f for f in get_formations()
                                  if m in f.present_enemies
                                  and not f.has_boss])
                formations = sorted(formations, key=lambda f: f.formid)
                try:
                    f = random.choice(formations)
                    orphaned_formations.add(f)
                except IndexError:
                    pass
            for x in extra_miabs:
                if m in x.present_enemies:
                    if x == f:
                        continue
                    ens = set(x.present_enemies)
                    if len(ens) == 1:
                        banned_formids.append(x.formid)

    orphaned_formations = sorted(orphaned_formations, key=lambda f: f.formid)
    return get_orphaned_formations()


def get_appropriate_formations():
    global appropriate_formations
    if appropriate_formations is not None:
        return appropriate_formations

    from randomizer import NOREPLACE_FORMATIONS
    formations = get_formations()
    formations = [f for f in formations if not f.battle_event]
    formations = [f for f in formations if f.formid not in
                  banned_formids + NOREPLACE_FORMATIONS]
    formations = [f for f in formations if len(f.present_enemies) >= 1]
    formations = [f for f in formations if 273 not in
                  [e.id for e in f.present_enemies]]
    formations = [f for f in formations if all(
                  e.display_name.strip('_') for e in f.present_enemies)]

    def get_enames(f):
        return " ".join(sorted([e.display_name for e in f.present_enemies]))

    form_enames = [get_enames(f) for f in formations]
    for f in list(formations):
        enames = get_enames(f)
        assert form_enames.count(enames) >= 1
        if form_enames.count(enames) >= 2:
            if f.get_music() == 0:
                formations.remove(f)
                form_enames.remove(enames)

    appropriate_formations = formations
    return get_appropriate_formations()


def get_2pack(formation):
    fsets = [fs for fs in get_fsets() if fs.setid >= 0x100]
    for fs in fsets:
        if fs.formations[0] == formation and fs.formations[1] == formation:
            return fs

    unused = [fs for fs in fsets if fs.unused][0]
    unused.formids = [formation.formid] * 2
    return unused


def add_extra_miab(setid):
    setid |= 0x100
    fset = [fs for fs in get_fsets() if fs.setid == setid][0]
    formation = fset.formations[0]
    if formation not in extra_miabs:
        extra_miabs.append(fset.formations[0])


def get_extra_miabs(lowest_rank):
    candidates = [f for f in extra_miabs if f.rank() >= lowest_rank and
                  f.formid not in banned_formids]
    return sorted(candidates, key=lambda f: f.rank())


def get_valid_chest_id():
    global valid_ids
    try:
        valid = valid_ids[0]
    except IndexError:
        raise Exception("Not enough chest IDs available.")
    mark_taken_id(valid)
    return valid


def mark_taken_id(taken):
    global valid_ids
    assert 1 <= taken < 0x200
    if taken in valid_ids:
        valid_ids = [i for i in valid_ids if i != taken]


class ChestBlock:
    def __init__(self, pointer, location):
        self.pointer = pointer
        self.location = location
        self.value = None
        self.do_not_mutate = False
        self.ignore_dummy = False
        self.rank = None

    def set_id(self, chestid):
        self.chestid = chestid

    def read_data(self, filename):
        global extra_miabs

        f = open(filename, 'r+b')
        f.seek(self.pointer)
        self.position = read_multi(f, length=2)
        self.memid = ord(f.read(1))
        self.contenttype = ord(f.read(1))
        self.contents = ord(f.read(1))
        f.close()
        self.oldid = self.memid | ((self.contenttype & 1) << 8)

        mark_taken_id(self.effective_id)
        if self.monster:
            add_extra_miab(self.contents)

    def copy(self, other):
        self.position = other.position
        self.memid = other.memid
        self.contenttype = other.contenttype
        self.contents = other.contents
        self.oldid = other.oldid

    def set_rank(self, rank):
        self.rank = rank

    @property
    def empty(self):
        return self.contenttype & 0x18

    @property
    def treasure(self):
        return self.contenttype & 0x40

    @property
    def gold(self):
        return self.contenttype & 0x80

    @property
    def monster(self):
        return self.contenttype & 0x20

    @property
    def effective_id(self):
        return self.memid | ((self.contenttype & 1) << 8)

    @property
    def description(self):
        if self.monster:
            from formationrandomizer import get_fset
            s = "Enemy {0:03d}: ".format(self.effective_id)
            fset = get_fset(self.contents + 0x100)
            s += fset.formations[0].description(renamed=True, simple=True)
        elif self.empty:
            s = "Empty! ({0:03d})".format(self.effective_id)
        else:
            s = "Treasure {0:03d}: ".format(self.effective_id)
            if self.gold:
                s += "%s GP" % (self.contents * 100)
            else:
                item = get_item(self.contents)
                s += item.name
        return s

    def set_content_type(self, contenttype):
        if self.effective_id >= 0x100:
            self.contenttype = contenttype | 1
        else:
            self.contenttype = contenttype

    def set_new_id(self):
        nextid = get_valid_chest_id()
        if nextid >= 0x100:
            if nextid >= 0x200:
                raise Exception("Too many chests.")
            self.contenttype |= 1
        else:
            self.contenttype &= 0xFE
        self.memid = nextid & 0xFF

    def write_data(self, filename, nextpointer):
        f = open(filename, 'r+b')
        f.seek(nextpointer)
        write_multi(f, self.position, length=2)

        if self.memid is None:
            self.set_new_id()

        # TODO: Preserve same IDs on chests like in Figaro Cave
        f.write(chr(self.memid))
        f.write(chr(self.contenttype))
        f.write(chr(self.contents))
        f.close()

    def get_current_value(self, guideline=None):
        if self.treasure:
            items = get_ranked_items()
            itemids = [i.itemid for i in items]
            try:
                index = itemids.index(self.contents)
                value = items[index].rank() / 100
            except ValueError:
                value = 100
        elif self.gold or self.empty:
            if self.empty:
                if guideline is not None:
                    value = guideline / 100
                else:
                    raise Exception("No guideline provided for empty chest.")
            else:
                value = self.contents
        elif self.monster:
            from formationrandomizer import get_fset
            formation = get_fset(self.contents | 0x100).formations[0]
            items = []
            for monster in formation.present_enemies:
                mitems = [i for i in monster.drops if i is not None]
                if mitems:
                    items.append(min(mitems, key=lambda i: i.rank()))
            if items:
                highest = max(items, key=lambda i: i.rank())
                value = highest.rank() / 100
            else:
                value = 1

        assert value < 10000
        return value

    def dummy_item(self, item):
        if self.ignore_dummy:
            return False

        if self.treasure and self.contents == item.itemid:
            self.set_content_type(0x10)
            self.contents = 0
            return True
        return False

    def mutate_contents(self, guideline=None, monster=None):
        global used_formations

        if self.do_not_mutate:
            return

        if self.value:
            value = self.value
        else:
            value = self.get_current_value(guideline=guideline)

        items = get_ranked_items()
        itemids = [i.itemid for i in items]
        if self.treasure:
            try:
                index = itemids.index(self.contents)
            except ValueError:
                index = 0
        else:
            lowpriced = [i for i in items if i.rank() <= value*100]
            index = max(0, len(lowpriced)-1)

        chance = random.randint(1, 50)
        orphaned_formations = get_orphaned_formations()
        orphaned_formations = [f for f in orphaned_formations
                               if f not in used_formations]
        extra_miabs = get_extra_miabs(0)
        if orphaned_formations or extra_miabs:
            chance -= 2
            chance = max(chance, 1)

        if monster is not False and (1 <= chance <= 3 or monster is True):
            # monster
            self.set_content_type(0x20)

            formations = get_appropriate_formations()
            formations = [f for f in formations if
                          f.get_guaranteed_drop_value() >= value * 100]
            rank = self.rank or min(formations, key=lambda f: f.rank()).rank()
            extra_miabs = get_extra_miabs(rank)
            if orphaned_formations or extra_miabs:
                formations = [f for f in formations if f.rank() >= rank]
                formations = formations[:random.randint(0, 2)]

            candidates = (formations + orphaned_formations + extra_miabs)
            candidates = set(candidates)
            candidates = [c for c in candidates if c not in used_formations]
            candidates = [c for c in candidates
                          if c.formid not in banned_formids]
            if not candidates:
                candidates = (formations +
                              get_orphaned_formations() + get_extra_miabs(0))

            candidates = sorted(candidates, key=lambda f: f.rank())
            if orphaned_formations:
                index = max(
                    0, len([c for c in candidates if c.rank() <= rank])-1)
                index = mutate_index(index, len(candidates), [False, True],
                                     (-2, 1), (-1, 1))
            else:
                index = 0
                index = mutate_index(index, len(candidates), [False, True],
                                     (-1, 4), (-1, 1))

            chosen = candidates[index]
            for m in chosen.present_enemies:
                m.auxloc = "Monster-in-a-Box"

            banned_formids.append(chosen.formid)
            used_formations.append(chosen)
            chosen = get_2pack(chosen)
            # only 2-packs are allowed
            self.contents = chosen.setid & 0xFF
        elif 4 <= chance <= 5:
            # gold
            self.set_content_type(0x80)
            value = value / 2
            value += (random.randint(0, value) + random.randint(0, value))
            self.contents = min(0xFF, max(1, value))
            if self.contents == 0xFF:
                self.contents -= random.randint(0, 20) + random.randint(0, 20)
        else:
            # treasure
            self.set_content_type(0x40)
            index = mutate_index(index, len(items), [False, True],
                                 (-4, 2), (-2, 2))
            self.contents = items[index].itemid

        assert self.contents <= 0xFF
        self.value = value
