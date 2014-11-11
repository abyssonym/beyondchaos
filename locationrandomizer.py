from utils import (read_multi, write_multi, battlebg_palettes, MAP_NAMES_TABLE,
                   decompress, line_wrap, USED_LOCATIONS_TABLE,
                   UNUSED_LOCATIONS_TABLE, MAP_BATTLE_BG_TABLE,
                   ENTRANCE_REACHABILITY_TABLE,
                   utilrandom as random)
from copy import copy


locations = None
unused_locs = None
reachdict = None
mapnames = {}
locdict = {}
for line in open(MAP_NAMES_TABLE):
    key, value = tuple(line.strip().split(':'))
    key = int(key, 0x10)
    mapnames[key] = value


mapbattlebgs = {}
for line in open(MAP_BATTLE_BG_TABLE):
    a, b = tuple(line.strip().split())
    mapbattlebgs[int(a)] = int(b, 0x10)


#256 zones
class Zone():
    def __init__(self, zoneid):
        self.zoneid = zoneid
        self.pointer = 0xF5400 + (4*zoneid)
        self.ratepointer = 0xF5800 + zoneid
        self.names = {}

    def read_data(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.pointer)
        self.setids = map(ord, f.read(4))
        f.seek(self.ratepointer)
        self.rates = ord(f.read(1))
        f.close()

    @property
    def pretty_rates(self):
        temp = self.rates
        result = []
        for i in reversed(range(4)):
            temp = (self.rates >> (i*2)) & 0x3
            result.append(temp)
        return result

    def set_formation_rate(self, setid, rate):
        for i, s in enumerate(self.setids):
            if setid == s:
                shift = (3-i)*2
                self.rates &= (0xFF ^ (0x3 << shift))
                self.rates |= (rate << shift)

    def write_data(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.pointer)
        f.write("".join(map(chr, self.setids)))
        f.seek(self.ratepointer)
        f.write(chr(self.rates))
        f.close()


# 415 locations
class Location():
    def __init__(self, locid):
        self.locid = locid
        self.pointer = 0x2D8F00 + (33 * locid)
        self.formationpointer = 0xF5600 + locid
        self.name = None
        if self.locid in mapnames:
            self.altname = "%x %s" % (self.locid, mapnames[self.locid])
        else:
            self.altname = "%x" % self.locid
        self.entrance_set = EntranceSet(self.locid)
        self.entrance_set.location = self

    def __repr__(self):
        if self.name:
            return "%x %s" % (self.locid, self.name)
        else:
            return self.altname

    @property
    def chestpointer(self):
        return 0x2D82F4 + (self.locid * 2)

    def validate_entrances(self):
        pairs = [(e.x, e.y) for e in self.entrances]
        if len(pairs) != len(set(pairs)):
            raise Exception("Duplicate entrances found on map.")

    def collapse_entids(self):
        entrances = self.entrances
        for i, e in enumerate(sorted(entrances, key=lambda x: x.entid)):
            e.entid = i

    @property
    def entrances(self):
        return self.entrance_set.entrances

    def set_entrance_set(self, eset):
        self.entrance_set = eset
        eset.location = self

    def backup_entrances(self):
        self.entrancebackups = list(self.entrances)

    def get_nearest_entrance(self, x, y):
        candidates = []
        for e in self.entrancebackups:
            if e.x != x and e.y != y:
                if abs((e.x - x) * (e.y - y)) != 1:
                    continue
            value = max(abs(e.x - x), abs(e.y-y))
            candidates.append((value, e))
        if not candidates:
            return None
        _, entrance = min(candidates)
        return entrance

    @property
    def battlebg(self):
        return self._battlebg & 0x3F

    @property
    def battle_palette(self):
        index = battlebg_palettes[self.battlebg]
        return 0x270150 + (index * 0x60)

        if self.palette_index == 0x2a:
            # starts at 0x270150
            return 0x270510  # to 0x270570

    @property
    def field_palette(self):
        return 0x2dc480 + (256 * (self.palette_index & 0x3F))
        #if self.palette_index == 0x2a:
        #    return 0x2dee80  # to 0x2def60

    @property
    def layer1ptr(self):
        return self.mapdata & 0x3FF

    @property
    def layer1width(self):
        width = (self.layer12dimensions & 0xC0) >> 6
        return [16, 32, 64, 128][width]

    @property
    def layer1height(self):
        height = (self.layer12dimensions & 0x30) >> 4
        return [16, 32, 64, 128][height]

    @property
    def layer2ptr(self):
        return (self.mapdata >> 10) & 0x3FF

    @property
    def layer3ptr(self):
        return (self.mapdata >> 20) & 0x3FF

    def read_data(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.pointer)

        self.name_id = ord(f.read(1))
        self.layers_to_animate = ord(f.read(1))
        self._battlebg = ord(f.read(1))
        self.unknown0 = ord(f.read(1))
        self.tileproperties = ord(f.read(1))  # mult by 2
        self.attacks = ord(f.read(1))
        self.unknown1 = ord(f.read(1))
        self.graphic_sets = map(ord, f.read(4))
        self.tileformations = read_multi(f, length=2, reverse=True)
        self.mapdata = read_multi(f, length=4)
        self.unknown2 = ord(f.read(1))
        self.bgshift = map(ord, f.read(4))
        self.unknown3 = ord(f.read(1))
        self.layer12dimensions = ord(f.read(1))
        self.unknown4 = ord(f.read(1))
        self.palette_index = read_multi(f, length=3)
        self.music = ord(f.read(1))
        self.unknown5 = ord(f.read(1))
        self.width = ord(f.read(1))
        self.height = ord(f.read(1))
        self.layerpriorities = ord(f.read(1))
        assert f.tell() == self.pointer + 0x21

        f.seek(self.formationpointer)
        self.formation = ord(f.read(1))

        f.seek(0xf5600 + self.locid)
        self.setid = ord(f.read(1))

        f.close()
        self.entrance_set.read_data(filename)
        self.backup_entrances()
        self.read_chests(filename)

    def make_tower_flair(self):
        towerloc = get_location(334)
        searchlight = towerloc.unknown1 & 0x3
        layer3index = (((towerloc.graphic_sets[3] & 0xF0) >> 4) |
                       ((towerloc.tileformations & 0x3) << 4))
        layer3map = (towerloc.unknown2 & 0x3F) << 4
        layer3map |= (towerloc.mapdata >> 20)
        layer3dims = towerloc.unknown4 & 0xF0

        self._battlebg = (towerloc._battlebg & 0xC0) | self._battlebg
        self.layers_to_animate = towerloc.layers_to_animate
        self.unknown0 = towerloc.unknown0
        self.attacks = towerloc.attacks
        self.unknown1 = (self.unknown1 & 0xFC) | searchlight
        self.graphic_sets[3] = (self.graphic_sets[3] & 0x0F) | (towerloc.graphic_sets[3] & 0xF0)
        self.tileformations = (self.tileformations & 0xFFFC) | (towerloc.tileformations & 0x3)
        self.mapdata = (self.mapdata & 0xFFFFF) | (towerloc.mapdata & 0x3FF00000)
        self.unknown2 = (self.unknown2 & 0xC0) | (towerloc.unknown2 & 0x3F)
        self.unknown3 = towerloc.unknown3
        self.unknown4 = towerloc.unknown4  # layer 3 bgshift
        self.unknown5 = towerloc.unknown5  # layer 3 priorities?
        self.layerpriorities = towerloc.layerpriorities

    def fill_battle_bg(self, locid=None):
        if locid is None:
            locid = self.locid

        if self.battlebg in [0, 5] and locid in mapbattlebgs:
            if locid in mapbattlebgs:
                battlebg = mapbattlebgs[locid]
                self._battlebg = (self._battlebg & 0xC0) | battlebg

    def write_data(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.pointer)

        def write_attributes(*args):
            for attribute in args:
                attribute = getattr(self, attribute)
                try:
                    attribute = "".join(map(chr, attribute))
                except TypeError:
                    attribute = chr(attribute)
                f.write(attribute)

        write_attributes("name_id", "layers_to_animate", "_battlebg",
                         "unknown0", "tileproperties", "attacks",
                         "unknown1", "graphic_sets")

        write_multi(f, self.tileformations, length=2, reverse=True)
        write_multi(f, self.mapdata, length=4, reverse=True)

        write_attributes(
            "unknown2", "bgshift", "unknown3", "layer12dimensions",
            "unknown4")

        write_multi(f, self.palette_index, length=3)

        write_attributes("music", "unknown5", "width", "height",
                         "layerpriorities")
        assert f.tell() == self.pointer + 0x21

        f.seek(0xf5600 + self.locid)
        f.write(chr(self.setid))

        f.close()

    def copy(self, location):
        attributes = [
            "name_id", "layers_to_animate", "_battlebg", "unknown0",
            "tileproperties", "attacks", "unknown1", "graphic_sets",
            "tileformations", "mapdata", "unknown2", "bgshift", "unknown3",
            "layer12dimensions", "unknown4", "palette_index", "music",
            "unknown5", "width", "height", "layerpriorities"
            ]
        for attribute in attributes:
            value = getattr(location, attribute)
            value = copy(value)
            setattr(self, attribute, value)

        eset = EntranceSet(entid=self.locid)
        self.set_entrance_set(eset)
        eset.copy(location.entrance_set)
        self.copy_chests(location)

    def read_chests(self, filename):
        from chestrandomizer import ChestBlock
        f = open(filename, 'r+b')
        f.seek(self.chestpointer)
        begin = read_multi(f, length=2)
        end = read_multi(f, length=2)
        numchests = (end - begin) / 5
        self.chests = []
        for i in xrange(numchests):
            pointer = begin + (i*5) + 0x2d8634
            c = ChestBlock(pointer, self.locid)
            c.read_data(filename)
            self.chests.append(c)

    def copy_chests(self, location):
        from chestrandomizer import ChestBlock
        self.chests = []
        for chest in location.chests:
            c = ChestBlock(pointer=None, location=self.locid)
            c.copy(chest)
            self.chests.append(c)

    def mutate_chests(self, guideline=None):
        random.shuffle(self.chests)
        for c in self.chests:
            c.mutate_contents(guideline=guideline)
            if guideline is None and hasattr(c, "value") and c.value:
                guideline = value

    def unlock_chests(self, low, high):
        dist = (high - low) / 2
        for c in self.chests:
            c.set_content_type(0x80)
            c.contents = None
            value = low + random.randint(0, dist) + random.randint(0, dist)
            c.value = value
            c.mutate_contents()
            if random.randint(1, 5) >= 4:
                c.set_new_id()

    def write_chests(self, filename, nextpointer):
        f = open(filename, 'r+b')
        f.seek(self.chestpointer)
        write_multi(f, (nextpointer - 0x2d8634), length=2)
        f.close()
        for c in self.chests:
            if nextpointer + 5 > 0x2d8e5a:
                raise Exception("Not enough space for treasure chests.")
            c.write_data(filename, nextpointer)
            nextpointer += 5

        return nextpointer


class Entrance():
    def __init__(self, pointer):
        self.pointer = pointer
        self.entid = None

    def read_data(self, filename):
        f = open(filename, 'r+b')
        #f.seek(self.pointerpointer)
        #self.pointer = read_multi(f, length=2) + 0x1fbb00
        f.seek(self.pointer)
        self.x = ord(f.read(1))
        self.y = ord(f.read(1))
        self.dest = read_multi(f, length=2)
        self.destx = ord(f.read(1))
        self.desty = ord(f.read(1))
        f.close()

    def set_id(self, entid):
        self.entid = entid

    def set_location(self, location):
        if type(location) is int:
            location = get_location(location)
        self.location = location

    @property
    def mirror(self):
        loc = self.destination
        if loc is None:
            return None

        if len(loc.entrancebackups) == 0:
            return None

        entrance = loc.get_nearest_entrance(self.destx, self.desty)
        return entrance

    @property
    def signature(self):
        return (self.location.locid & 0x1ff, self.x, self.y,
                self.dest & 0x1ff, self.destx, self.desty)

    @property
    def shortsig(self):
        return (self.location.locid, self.x, self.y)

    @property
    def effectsig(self):
        return (self.x, self.y, self.dest & 0x1ff, self.destx, self.desty)

    @property
    def destination(self):
        destid = self.dest & 0x1FF
        locations = get_locations()
        try:
            loc = [l for l in locations if l.locid == destid][0]
            return loc
        except IndexError:
            return None

    @property
    def reachable_entrances(self):
        if hasattr(self, "_entrances") and self._entrances is not None:
            return self._entrances
        entrances = lookup_reachable_entrances(self)
        self._entrances = entrances
        return entrances

    def reset_reachable_entrances(self):
        self._entrances = None

    def write_data(self, filename, nextpointer):
        if nextpointer >= 0x1FDA00:
            raise Exception("Not enough room for entrances.")
        f = open(filename, 'r+b')
        f.seek(nextpointer)
        f.write(chr(self.x))
        f.write(chr(self.y))
        write_multi(f, self.dest, length=2)
        f.write(chr(self.destx))
        f.write(chr(self.desty))
        f.close()

    def __repr__(self):
        if hasattr(self, "entid"):
            entid = self.entid
        else:
            entid = None
        return "<%x %s: %s %s>" % (self.location.locid, entid, self.x, self.y)
        #return "%x %x %x %x %x %x" % (self.pointer, self.x, self.y,
        #                              self.dest & 0x1FF, self.destx, self.desty)

    def copy(self, entrance):
        for attribute in ["x", "y", "dest", "destx", "desty"]:
            setattr(self, attribute, getattr(entrance, attribute))


class EntranceSet():
    def __init__(self, entid):
        self.entid = entid
        self.pointer = 0x1fbb00 + (2*entid)
        self.entrances = []

    @property
    def destinations(self):
        return set([e.destination for e in self.entrances])

    def read_data(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.pointer)
        start = read_multi(f, length=2)
        end = read_multi(f, length=2)
        f.close()
        n = (end - start) / 6
        assert end == start + (6*n)
        self.entrances = []
        for i in xrange(n):
            e = Entrance(0x1fbb00 + start + (i*6))
            e.set_id(i)
            self.entrances.append(e)
        for e in self.entrances:
            e.read_data(filename)
            e.set_location(self.location)

    def write_data(self, filename, nextpointer):
        f = open(filename, 'r+b')
        f.seek(self.pointer)
        write_multi(f, (nextpointer - 0x1fbb00), length=2)
        f.close()
        for e in self.entrances:
            if nextpointer + 6 > 0x1fda00:
                raise Exception("Too many entrance triggers.")
            e.write_data(filename, nextpointer)
            nextpointer += 6
        return nextpointer

    def copy(self, eset):
        self.entrances = []
        for e in sorted(eset.entrances, key=lambda x: x.entid):
            e2 = Entrance(e.entid)
            e2.copy(e)
            e2.set_id(e.entid)
            e2.set_location(self.location)
            self.entrances.append(e2)


def get_locations(filename=None):
    global locations
    if locations is None:
        locations = [Location(i) for i in range(415)]
        if filename is None:
            raise Exception("Please supply a filename for new locations.")
        for l in locations:
            l.read_data(filename)
            l.fill_battle_bg()
            locdict[l.locid] = l
    return locations


def get_location(locid):
    global locdict
    if locid not in locdict:
        get_locations()
    return locdict[locid]


def get_unused_locations(filename=None):
    global unused_locs
    if unused_locs:
        return unused_locs

    unused_locs = set([])
    for line in open(UNUSED_LOCATIONS_TABLE):
        locid = int(line.strip(), 0x10)
        loc = get_location(locid)
        unused_locs.add(loc)

    unused_locs = sorted(unused_locs, key=lambda l: l.locid)
    return get_unused_locations()


def lookup_reachable_entrances(entrance):
    global reachdict
    if not reachdict:
        reachdict = {}
        for line in open(ENTRANCE_REACHABILITY_TABLE):
            locid, ents = line.strip().split(':')
            locid = int(locid)
            ents = map(int, ents.split(','))
            for ent in ents:
                if (locid, ent) in reachdict:
                    raise Exception("Duplicate reachability in table.")
                reachdict[(locid, ent)] = ents

    key = entrance.location.locid, entrance.entid
    if key not in reachdict:
        return []

    entrances = entrance.location.entrances
    return [e for e in entrances if e.entid in reachdict[key]]

if __name__ == "__main__":
    from sys import argv
    if len(argv) > 1:
        filename = argv[1]
    else:
        filename = "program.rom"
    from formationrandomizer import get_formations, get_fsets
    from monsterrandomizer import get_monsters
    get_monsters(filename)
    get_formations(filename)
    get_fsets(filename)
    locations = get_locations(filename)
    from formationrandomizer import fsetdict
    for l in locations:
        print l.locid, l.layer1width, l.layer1height
    for l in locations:
        esets = []
        seen = set([])
        for e in l.entrances:
            if e in seen:
                continue
            es = e.reachable_entrances
            seen |= set(es)
            esets.append(es)
        for eset in esets:
            print "%s:%s" % (l.locid, ",".join(["%s" % e.entid for e in eset]))
