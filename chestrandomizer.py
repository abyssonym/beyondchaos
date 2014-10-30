from utils import read_multi, write_multi, utilrandom as random
from itemrandomizer import get_ranked_items

items = None


class ChestBlock:
    def __init__(self, pointer, location):
        self.pointer = pointer
        self.location = location

    def read_data(self, filename):
        global items

        f = open(filename, 'r+b')
        f.seek(self.pointer)
        self.unknown = read_multi(f, length=2)
        self.misc = ord(f.read(1))
        self.contenttype = ord(f.read(1))
        self.contents = ord(f.read(1))
        f.close()

        if items is None:
            items = get_ranked_items(filename)
            items = [i.itemid for i in items]

    def copy(self, other):
        self.unknown = other.unknown
        self.misc = other.misc
        self.contenttype = other.contenttype
        self.contents = other.contents

    @property
    def empty(self):
        return self.contenttype == 0x8

    @property
    def treasure(self):
        return self.contenttype in [0x40, 0x41]

    @property
    def gold(self):
        return self.contenttype == 0x80

    @property
    def monster(self):
        return self.contenttype == 0x20

    def write_data(self, filename, nextpointer):
        f = open(filename, 'r+b')
        f.seek(nextpointer)
        write_multi(f, self.unknown, length=2)
        f.write(chr(self.misc))
        f.write(chr(self.contenttype))
        f.write(chr(self.contents))
        f.close()

    def mutate_contents(self):
        if self.treasure:
            index = items.index(self.contents)
            index += random.randint(-4, 4)
            index = max(0, min(index, len(items)-1))
            while random.randint(1, 2) == 2:
                index += random.randint(-2, 2)
                index = max(0, min(index, len(items)-1))
            self.contents = items[index]
        elif self.gold:
            self.contents = self.contents / 2
            self.contents += (random.randint(0, self.contents) +
                              random.randint(0, self.contents))
            self.contents = min(0xFF, max(0, self.contents))
        elif self.empty:
            pass
