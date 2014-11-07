from utils import read_multi, write_multi, mutate_index, utilrandom as random
from itemrandomizer import get_ranked_items

items = None
itemids = None
lastid = None


def get_valid_chest_id():
    global lastid
    if lastid is None:
        lastid = 0
        return lastid
    lastid += 1
    return lastid


class ChestBlock:
    def __init__(self, pointer, location):
        self.pointer = pointer
        self.location = location

    def read_data(self, filename):
        global items, itemids

        f = open(filename, 'r+b')
        f.seek(self.pointer)
        self.position = read_multi(f, length=2)
        self.memid = ord(f.read(1))
        self.contenttype = ord(f.read(1))
        self.contents = ord(f.read(1))
        f.close()
        self.oldid = self.memid | ((self.contenttype & 1) << 8)

        if items is None:
            items = get_ranked_items(filename)
            itemids = [i.itemid for i in items]

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
        global lastid
        nextid = get_valid_chest_id()
        if nextid >= 0x100:
            if nextid >= 0x200:
                raise Exception("Too many chests.")
            self.contenttype |= 1
        else:
            self.contenttype &= 0xFE
        self.memid = nextid & 0xFF

        if nextid > lastid:
            lastid = nextid

    def write_data(self, filename, nextpointer):
        global lastid
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

        if self.effective_id > lastid:
            lastid = self.effective_id

    def get_current_value(self, guideline=None):
        if self.treasure:
            index = itemids.index(self.contents)
            value = items[index].rank() / 100
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

    def mutate_contents(self, guideline=None, fsets=None):
        value = self.get_current_value(guideline=guideline)
        if self.treasure:
            index = itemids.index(self.contents)
        else:
            lowpriced = [i for i in items if i.rank() <= value]
            index = max(0, len(lowpriced)-1)

        chance = random.randint(1, 50)
        if 1 <= chance <= 1:
            # empty
            self.set_content_type(0x10)
        elif 2 <= chance <= 3:
            # gold
            self.set_content_type(0x80)
            value = value / 2
            value += (random.randint(0, value) + random.randint(0, value))
            self.contents = min(0xFF, max(1, value))
        elif 4 <= chance <= 6 and fsets:
            # monster
            self.set_content_type(0x20)
            index = mutate_index(index, len(items), [False, True],
                                 (-2, 2), (-1, 1))
            index = (float(index) / len(items)) * len(fsets)
            index = min(int(index), len(fsets)-1)
            # only 2-packs are allowed
            self.contents = fsets[index].setid & 0xFF
        else:
            # treasure
            self.set_content_type(0x40)
            index = mutate_index(index, len(items), [False, True],
                                 (-4, 2), (-2, 2))
            self.contents = items[index].itemid
