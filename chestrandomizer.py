from utils import hex2int, utilrandom as random
from itemrandomizer import get_ranked_items

items = None


class ChestBlock:
    def __init__(self, pointer, location, world):
        self.pointer = hex2int(pointer)
        self.location = hex2int(location)
        self.world = world

    def read_data(self, filename):
        global items

        f = open(filename, 'r+b')
        f.seek(self.pointer+2)
        self.misc = ord(f.read(1))
        self.contenttype = ord(f.read(1))
        self.contents = ord(f.read(1))
        f.close()

        if items is None:
            items = get_ranked_items(filename)
            items = [i.itemid for i in items]

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

    def write_data(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.pointer+2)
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


def shuffle_locations(chests):
    locdict = {}
    for c in chests:
        if c.location not in locdict:
            locdict[c.location] = []
        locdict[c.location].append(c)
    for location, locchests in locdict.items():
        for i in range(len(locchests)):
            candidates = locchests[i:]
            basechest = locchests[i]
            swapchest = random.choice(candidates)
            basechest.contenttype, swapchest.contenttype = swapchest.contenttype, basechest.contenttype
            basechest.contents, swapchest.contents = swapchest.contents, basechest.contents


def shuffle_monster_boxes(chests):
    monster_boxes = [c for c in chests if c.monster]
    for m in monster_boxes:
        valid_chests = [c for c in chests if c.world == m.world]
        swapchest = random.choice(valid_chests)
        m.contenttype, swapchest.contenttype = swapchest.contenttype, m.contenttype
        m.contents, swapchest.contents = swapchest.contents, m.contents
