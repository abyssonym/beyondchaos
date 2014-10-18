from utils import (read_multi, write_multi, battlebg_palettes, MAP_NAMES_TABLE,
                   utilrandom as random)


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

    def read_data(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.pointer + 0x2)
        self._battlebg = ord(f.read(1))
        f.seek(self.pointer + 0x5)
        self.attacks = ord(f.read(1))
        f.seek(self.pointer + 0x4)
        self.tileproperties = ord(f.read(1))
        f.seek(self.pointer + 0xB)
        self.tileformations = read_multi(f, length=2, reverse=True)
        f.seek(self.pointer + 0xD)
        self.mapdata = read_multi(f, length=4)
        f.seek(self.pointer + 0x12)
        self.bgshift = map(ord, f.read(4))
        f.seek(self.pointer + 0x19)
        self.palette_index = read_multi(f, length=3)
        f.seek(self.pointer + 0x1C)
        self.music = ord(f.read(1))
        f.seek(self.formationpointer)
        self.formation = ord(f.read(1))
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
        f.seek(self.formationpointer)
        f.write(chr(self.formation))
        f.close()


entrance_pool = {}


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
            self.entrances.append(Entrance(0x1fbb00 + self.start + (i*6)))
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


def get_locations():
    global locations
    if locations is None:
        locations = [Location(i) for i in range(415)]
    return locations


if __name__ == "__main__":
    for i in xrange(415):
        print "%x" % i,
        l = Location(i)
        l.read_data("program.rom")
        print "%x %x %x" % (l.pointer, l.battlebg, l.mapdata)
