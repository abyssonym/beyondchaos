from utils import read_multi, write_multi, mutate_index, utilrandom as random
from itemrandomizer import get_ranked_items
from formationrandomizer import get_formations, get_fsets

valid_ids = range(0, 0x200)
banned_formations = [0x1ca, 0x1e9]
former_miabs = []


def get_appropriate_formations():
    formations = get_formations()
    formations = [f for f in formations if not f.battle_event]
    formations = [f for f in formations if f.formid not in banned_formations]
    formations = [f for f in formations if len(f.present_enemies) >= 1]
    formations = [f for f in formations if 273 not in
                  [e.id for e in f.present_enemies]]
    return formations


def get_2pack(formation):
    fsets = [fs for fs in get_fsets() if fs.setid >= 0x100]
    for fs in fsets:
        if fs.setid < 0x100:
            continue
        if formation in fs.formations:
            return fs

    unused = [fs for fs in fsets if fs.unused][0]
    unused.formids = [formation.formid] * 2
    return unused


def add_former_miab(setid):
    setid |= 0x100
    fset = [fs for fs in get_fsets() if fs.setid == setid][0]
    formation = fset.formations[0]
    if formation not in former_miabs:
        former_miabs.append(fset.formations[0])


def add_formers(candidates):
    lowest_rank = candidates[0].rank()
    candidates += [f for f in former_miabs if f.rank() >= lowest_rank and
                   f.formid not in banned_formations]
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
    assert 0 <= taken < 0x200
    if taken in valid_ids:
        valid_ids = [i for i in valid_ids if i != taken]


class ChestBlock:
    def __init__(self, pointer, location):
        self.pointer = pointer
        self.location = location
        self.value = None
        self.do_not_mutate = False
        self.ignore_dummy = False

    def set_id(self, chestid):
        self.chestid = chestid

    def read_data(self, filename):
        global former_miabs

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
            add_former_miab(self.contents)

    def copy(self, other):
        self.position = other.position
        self.memid = other.memid
        self.contenttype = other.contenttype
        self.contents = other.contents
        self.oldid = other.oldid

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
        if self.monster:
            value = 100
        return value

    def set_generic_gold(self, value):
        if value is None:
            value = self.get_current_value(guideline=100)
        self.set_content_type(0x80)
        self.contents = value / 100
        assert self.gold and not (self.treasure or self.empty or self.monster)

    def dummy_item(self, item):
        if self.ignore_dummy:
            return False

        if self.treasure and self.contents == item.itemid:
            self.set_content_type(0x10)
            self.contents = 0
            return True
        return False

    def mutate_contents(self, guideline=None):
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
            lowpriced = [i for i in items if i.rank() <= value]
            index = max(0, len(lowpriced)-1)

        chance = random.randint(1, 50)
        if 1 <= chance <= 1:
            # empty
            self.set_content_type(0x10)
            self.contents = 0
        elif 2 <= chance <= 3:
            # gold
            self.set_content_type(0x80)
            value = value / 2
            value += (random.randint(0, value) + random.randint(0, value))
            self.contents = min(0xFF, max(1, value))
        elif 4 <= chance <= 6:
            formations = get_appropriate_formations()
            # monster
            self.set_content_type(0x20)
            candidates = [f for f in formations if
                          f.get_guaranteed_drop_value() >= value * 100]
            if not candidates:
                self.set_content_type(0x10)
                self.contents = 0
                return

            candidates = sorted(candidates, key=lambda f: f.rank())
            candidates = add_formers(candidates)
            index = min(1, len(candidates)-1)
            index = mutate_index(index, len(candidates), [False, True],
                                 (-2, 2), (-1, 1))
            chosen = candidates[index]
            banned_formations.append(chosen.formid)
            chosen = get_2pack(chosen)
            # only 2-packs are allowed
            self.contents = chosen.setid & 0xFF
        else:
            # treasure
            self.set_content_type(0x40)
            index = mutate_index(index, len(items), [False, True],
                                 (-4, 2), (-2, 2))
            self.contents = items[index].itemid

        self.value = value
