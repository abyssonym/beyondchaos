from utils import (read_multi, write_multi, battlebg_palettes, MAP_NAMES_TABLE,
                   decompress, line_wrap, utilrandom as random)


locations = None
mapnames = {}
for line in open(MAP_NAMES_TABLE):
    key, value = tuple(line.strip().split(':'))
    key = int(key, 0x10)
    mapnames[key] = value


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

    def __repr__(self):
        if self.name:
            return "%x %s" % (self.locid, self.name)
        else:
            return self.altname

    def set_entrance_set(self, eset):
        self.entrance_set = eset

    def get_reachable_entrances(self, x, y):
        entrances = self.entrance_set.entrances
        walkable = self.walkable
        walked = set([])
        unchecked = set([(x, y)])
        while True:
            termval = len(walked)
            for x, y in list(unchecked):
                walked.add((x, y))
                for a, b in [(x, y+1), (x, y-1), (x+1, y), (x-1, y)]:
                    value = walkable[b][a]
                    if value == 0 and (a, b) not in walked:
                        unchecked.add((a, b))
            if termval == len(walked):
                break
        for (x, y) in list(walked):
            walked |= set([(x, y+1), (x, y-1), (x+1, y), (x-1, y)])
        return [e for e in entrances if (e.x, e.y) in walked]

    @property
    def battlebg(self):
        return self._battlebg & 0x7F

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
    def walkable(self):
        indexes = map(ord, self.map1bytes)
        walkables = []
        for i in indexes:
            #i = i * 2
            properties1 = (ord(self.tilebytes[i+1]) << 8) | ord(self.tilebytes[i])
            if properties1 & 0b100:
                walkables.append(1)
            else:
                walkables.append(0)
        return line_wrap(walkables, width=self.layer1width)

    @property
    def pretty_walkable(self):
        walkable = self.walkable
        s = ""
        for line in walkable:
            s += "".join([' ' if i == 0 else '*' for i in line])
            s += "\n"
        return s.strip()

    @property
    def layer1ptr(self):
        return self.mapdata & 0x3FF

    @property
    def layer1width(self):
        width = (self.layer12dimensions & 0xC0) >> 6
        return [16, 32, 64, 128][width]

    @property
    def layer2ptr(self):
        return (self.mapdata >> 10) & 0x3FF

    @property
    def layer3ptr(self):
        return (self.mapdata >> 20) & 0x3FF

    def read_data(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.pointer + 0x2)
        self._battlebg = ord(f.read(1))
        f.seek(self.pointer + 0x5)
        self.attacks = ord(f.read(1))
        f.seek(self.pointer + 0x4)
        self.tileproperties = ord(f.read(1))  # mult by 2
        f.seek(self.pointer + 0xB)
        self.tileformations = read_multi(f, length=2, reverse=True)
        f.seek(self.pointer + 0xD)
        self.mapdata = read_multi(f, length=4)
        f.seek(self.pointer + 0x12)
        self.bgshift = map(ord, f.read(4))
        f.seek(self.pointer + 0x17)
        self.layer12dimensions = ord(f.read(1))
        f.seek(self.pointer + 0x19)
        self.palette_index = read_multi(f, length=3)
        f.seek(self.pointer + 0x1C)
        self.music = ord(f.read(1))
        f.seek(self.pointer + 0x1D)
        self.mystery = ord(f.read(1))
        self.width = ord(f.read(1))
        self.height = ord(f.read(1))
        self.layerpriorities = ord(f.read(1))
        f.seek(self.formationpointer)
        self.formation = ord(f.read(1))

        f.seek(0x19CD90 + (3*self.layer1ptr))
        mapdataptr = 0x19D1B0 + read_multi(f, length=3)
        f.seek(mapdataptr)
        mapsize = read_multi(f, length=2) - 2
        mapdata = f.read(mapsize)
        self.map1bytes = decompress(mapdata, complicated=True)
        f.seek(0x19CD90 + (3*self.layer2ptr))

        mapdataptr = 0x19D1B0 + read_multi(f, length=3)
        f.seek(mapdataptr)
        mapsize = read_multi(f, length=2) - 2
        mapdata = f.read(mapsize)
        self.map2bytes = decompress(mapdata, complicated=True)

        f.seek(0x19CD10 + (2*self.tileproperties))
        tilepropptr = read_multi(f, length=2)
        f.seek(0x19a800 + tilepropptr)
        tilesize = read_multi(f, length=2) - 2
        tiledata = f.read(tilesize)
        self.tilebytes = decompress(tiledata, complicated=True)
        assert len(self.tilebytes) == 512
        f.close()

    def write_data(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.pointer + 0x5)
        f.write(chr(self.attacks))
        f.seek(self.pointer + 0xB)
        write_multi(f, self.tileformations, length=2, reverse=True)
        f.seek(self.pointer + 0x12)
        f.write("".join(map(chr, self.bgshift)))
        f.seek(self.pointer + 0x19)
        write_multi(f, self.palette_index, length=3)
        f.seek(self.pointer + 0x1C)
        f.write(chr(self.music))
        f.seek(self.pointer + 0x1E)
        f.write(chr(self.width))
        f.write(chr(self.height))
        f.write(chr(self.layerpriorities))
        f.seek(self.formationpointer)
        f.write(chr(self.formation))
        f.close()


class Entrance():
    def __init__(self, pointer):
        self.pointer = pointer

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
        self.location = location

    @property
    def signature(self):
        return (self.x, self.y, self.dest, self.destx, self.desty)

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
        if hasattr(self, "_entrances"):
            return self._entrances
        entrances = self.location.get_reachable_entrances(self.x, self.y)
        self._entrances = entrances
        return entrances

    def write_data(self, filename, nextpointer):
        f = open(filename, 'r+b')
        f.seek(nextpointer)
        f.write(chr(self.x))
        f.write(chr(self.y))
        write_multi(f, self.dest, length=2)
        f.write(chr(self.destx))
        f.write(chr(self.desty))
        f.close()

    def __repr__(self):
        return "%x %x %x %x %x %x" % (self.pointer, self.x, self.y,
                                      self.dest & 0x1FF, self.destx, self.desty)


class EntranceSet():
    def __init__(self, entid):
        self.entid = entid
        self.pointer = 0x1fbb00 + (2*entid)
        locations = get_locations()
        self.location = [l for l in locations if l.locid == self.entid]
        if self.location:
            self.location = self.location[0]
            self.location.set_entrance_set(self)
        else:
            self.location = None

    @property
    def destinations(self):
        return set([e.destination for e in self.entrances])

    def read_data(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.pointer)
        self.start = read_multi(f, length=2)
        self.end = read_multi(f, length=2)
        f.close()
        n = (self.end - self.start) / 6
        assert self.end == self.start + (6*n)
        self.entrances = []
        for i in xrange(n):
            e = Entrance(0x1fbb00 + self.start + (i*6))
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


def get_locations(filename=None):
    global locations
    if locations is None:
        locations = [Location(i) for i in range(415)]
        if filename is not None:
            print "Decompressing location data, please wait."
            for l in locations:
                l.read_data(filename)
            print "Decompression complete."
    return locations


if __name__ == "__main__":
    locations = get_locations("program.rom")
    entrancesets = []
    for i in xrange(512):
        e = EntranceSet(i)
        e.read_data("program.rom")
        entrancesets.append(e)
