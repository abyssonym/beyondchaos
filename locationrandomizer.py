from utils import (read_multi, write_multi, battlebg_palettes,
                   utilrandom as random)


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

if __name__ == "__main__":
    for i in xrange(415):
        print "%x" % i,
        l = Location(i)
        l.read_data("program.rom")
        print "%x %x %x" % (l.pointer, l.battlebg, l.field_palette)
