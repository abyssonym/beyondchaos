#!/usr/bin/env python3

from copy import copy
from formationrandomizer import get_fset
from utils import (read_multi, write_multi, battlebg_palettes, MAP_NAMES_TABLE,
                   UNUSED_LOCATIONS_TABLE, MAP_BATTLE_BG_TABLE,
                   ENTRANCE_REACHABILITY_TABLE, LOCATION_MAPS_TABLE,
                   utilrandom as random)


locations = None
zones = None
unused_locs = None
reachdict = None
mapnames = {}
locdict = {}
chest_id_counts = None
mapbattlebgs = {}
maplocations = {}
maplocations_reverse = {}
maplocations_override = {}


def init():
    for line in open(MAP_NAMES_TABLE):
        key, value = tuple(line.strip().split(':'))
        key = int(key, 0x10)
        mapnames[key] = value
    for line in open(MAP_BATTLE_BG_TABLE):
        a, b = tuple(line.strip().split())
        mapbattlebgs[int(a)] = int(b, 0x10)
    for line in open(LOCATION_MAPS_TABLE):
        a, b, *c = line.strip().split(':')
        b = b.strip().strip(',').split(',')
        locids = []
        for locid in b:
            if '+' in locid:
                l = int(locid.strip('+'))
                locids.extend([l, l+1, l+2, l+3])
            else:
                locids.append(int(locid))

        if a not in maplocations_reverse:
            maplocations_reverse[a] = []
        for locid in sorted(locids):
            maplocations[locid] = a
            maplocations_reverse[a].append(locid)
        if c:
            maplocations_override[a] = c[0]

init()

def add_location_map(location_name, mapid):
    assert location_name in maplocations_reverse
    maplocations_reverse[location_name] = sorted(
        maplocations_reverse[location_name] + [mapid])
    maplocations[mapid] = location_name


def get_chest_id_counts():
    global chest_id_counts
    if chest_id_counts is not None:
        return chest_id_counts
    chest_id_counts = {}
    for l in get_locations():
        for c in l.chests:
            if c.effective_id not in chest_id_counts:
                chest_id_counts[c.effective_id] = 0
            chest_id_counts[c.effective_id] += 1
    return get_chest_id_counts()


class NPCBlock():
    def __init__(self, pointer, locid):
        self.pointer = pointer
        self.locid = locid
        self.palette = 0
        self.bg2_scroll = 0
        self.membit = 0
        self.memaddr = 0
        self.event_addr = 0
        self.x = 0
        self.y = 0
        self.show_on_vehicle = 0
        self.speed = 0
        self.graphics = 0
        self.move_type = 0
        self.sprite_priority = 0
        self.vehicle = 0
        self.facing = 0
        self.no_turn_when_speaking = 0
        self.layer_priority = 0
        self.special_anim = 0
        self.npcid = 0

    def set_id(self, npcid):
        self.npcid = npcid

    def read_data(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.pointer)
        value = read_multi(f, length=4)
        self.palette = (value & 0x1C0000) >> 18
        self.bg2_scroll = (value & 0x200000) >> 21
        self.membit = (value & 0x1C00000) >> 22
        self.memaddr = (value & 0xFE000000) >> 25
        self.event_addr = value & 0x3FFFF

        byte4 = ord(f.read(1))
        self.x = byte4 & 0x7f
        self.show_on_vehicle = (byte4 & 0x80) >> 7

        byte5 = ord(f.read(1))
        self.y = byte5 & 0x3F
        self.speed = (byte5 & 0xC0) >> 6

        self.graphics = ord(f.read(1))

        byte7 = ord(f.read(1))
        self.move_type = byte7 & 0xF
        self.sprite_priority = (byte7 & 0x30) >> 4
        self.vehicle = (byte7 & 0xC0) >> 6

        byte8 = ord(f.read(1))
        self.facing = byte8 & 0x03
        self.no_turn_when_speaking = (byte8 & 0x4) >> 2
        self.layer_priority = (byte8 & 0x18) >> 3
        self.special_anim = (byte8 & 0xe0) >> 5
        f.close()

    def write_data(self, fout, nextpointer):
        fout.seek(nextpointer)
        value = (self.event_addr | (self.palette << 18) | (self.bg2_scroll << 21)
                 | (self.membit << 22) | (self.memaddr << 25))
        write_multi(fout, value, length=4)

        byte4 = (self.x & 0x7f) | ((self.show_on_vehicle & 0x1) << 7)
        byte5 = (self.y & 0x3F) | ((self.speed & 0x3) << 6)
        byte6 = self.graphics
        byte7 = (self.move_type & 0xF) | ((self.sprite_priority & 0x3) << 4) | ((self.vehicle & 0x3) << 6)
        byte8 = (self.facing & 0x03) | ((self.no_turn_when_speaking & 0x1) << 2) | ((self.layer_priority & 0x3) << 3) | ((self.special_anim & 0x7) << 5)

        fout.write(bytes([byte4, byte5, byte6, byte7, byte8]))


class EventBlock():
    def __init__(self, pointer, locid):
        self.pointer = pointer
        self.locid = locid
        self.x = 0
        self.y = 0
        self.eventid = 0
        self.event_addr = 0

    def set_id(self, eventid):
        self.eventid = eventid

    def read_data(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.pointer)
        self.x = ord(f.read(1))
        self.y = ord(f.read(1))
        self.event_addr = read_multi(f, length=3)
        f.close()

    def write_data(self, fout, nextpointer):
        fout.seek(nextpointer)
        fout.write(bytes([self.x]))
        fout.write(bytes([self.y]))
        write_multi(fout, self.event_addr, length=3)


#256 zones
class Zone():
    def __init__(self, zoneid):
        self.zoneid = zoneid
        self.pointer = 0xF5400 + (4*zoneid)
        self.ratepointer = 0xF5800 + zoneid
        self.names = {}
        self.setids = []
        self.rates = 0

    def read_data(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.pointer)
        self.setids = list(f.read(4))
        f.seek(self.ratepointer)
        self.rates = ord(f.read(1))
        f.close()

    @property
    def pretty_rates(self):
        temp = self.rates
        result = []
        for i in reversed(list(range(4))):
            temp = (self.rates >> (i*2)) & 0x3
            result.append(temp)
        return result

    @property
    def fsets(self):
        fsets = [get_fset(setid) for setid in self.setids]
        if self.zoneid < 0x40:
            fsets = fsets[:3]
        return fsets

    @property
    def valid(self):
        if set(self.setids) == set([0]) or set(self.setids) == set([0xFF]):
            return False
        return True

    def get_area_name(self, index=None):
        if self.zoneid < 0x80:
            index = self.zoneid % 0x40
            x = index % 8
            y = index // 8
            quadrants = [["NW", "NE"],
                         ["SW", "SE"]]
            quadrant = quadrants[int(y >= 4)][int(x >= 4)]
            x = str(x + 1)
            y = "ABCDEFGH"[y]
            if self.zoneid < 0x40:
                return "World of Balance %s-%s %s" % (y, x, quadrant)
            return "World of Ruin %s-%s %s" % (y, x, quadrant)

        locid = ((self.zoneid % 0x80) * 4) + index
        try:
            location = get_location(locid)
            area_name = location.area_name
        except KeyError:
            area_name = "Unknown"
        return area_name

    def set_formation_rate(self, setid=None, rate=0):
        for i, s in enumerate(self.setids):
            if setid is None or setid == s:
                shift = (3-i)*2
                self.rates &= (0xFF ^ (0x3 << shift))
                self.rates |= (rate << shift)

    def write_data(self, fout):
        # Do not write new set ids... let the locations do that.
        #fout.seek(self.pointer)
        #fout.write("".join(map(chr, self.setids)))
        fout.seek(self.ratepointer)
        fout.write(bytes([self.rates]))


# 415 locations
class Location():
    def __init__(self, locid, dummy=False):
        self.locid = locid
        if dummy:
            self.pointer = None
            self.entrance_set = None
        else:
            self.pointer = 0x2D8F00 + (33 * locid)
            self.entrance_set = EntranceSet(self.locid)
            self.entrance_set.location = self
        self.name = None
        if self.locid in mapnames:
            self.altname = "%x %s" % (self.locid, mapnames[self.locid])
        else:
            self.altname = "%x" % self.locid
        self.events = []

        self.name_id = 0
        self.layers_to_animate = 0
        self._battlebg = 0
        self.unknown0 = 0
        self.tileproperties = 0
        self.attacks = 0
        self.unknown1 = 0
        self.graphic_sets = []
        self.tileformations = 0
        self.mapdata = 0
        self.unknown2 = 0
        self.bgshift = 0
        self.unknown3 = 0
        self.layer12dimensions = 0
        self.unknown4 = 0
        self.palette_index = 0
        self.music = 0
        self.unknown5 = 0
        self.width = 0
        self.height = 0
        self.layerpriorities = 0
        self.entrancebackups = []
        self.setid = 0
        self.chests = []
        self.npcs = []

    def __repr__(self):
        if self.locid in mapnames:
            return self.altname
        if self.name:
            return "%x %s" % (self.locid, self.name)
        return self.altname

    @property
    def chestpointer(self):
        return 0x2D82F4 + (self.locid * 2)

    @property
    def npcpointer(self):
        return 0x41a10 + (self.locid * 2)

    @property
    def eventpointer(self):
        return 0x40000 + (self.locid * 2)

    @property
    def area_name(self):
        if self.locid not in maplocations:
            raise KeyError("Area for location ID %s not known." % self.locid)
        return maplocations[self.locid]

    @property
    def fsets(self):
        fset = get_fset(self.setid)
        fsets = [fset]
        if fset.sixteen_pack:
            f = fset.setid
            fsets.extend([get_fset(i) for i in [f+1, f+2, f+3]])
        return fsets

    @property
    def chest_contents(self):
        enemies = []
        treasures = []
        counts = get_chest_id_counts()
        for c in self.chests:
            try:
                desc = c.description
            except AttributeError:
                continue
            if c.effective_id in counts:
                count = counts[c.effective_id]
            else:
                count = 1
                desc = "?%s" % desc
            if count >= 2:
                desc = "*%s" % desc
            if "Enemy" in desc:
                enemies.append(desc)
            elif "Treasure" in desc:
                treasures.append(desc)
            elif "Empty!" in desc:
                treasures.append(desc)
            else:
                raise Exception("Received unknown chest contents type.")
        s = ""
        for t in sorted(treasures):
            s = "\n".join([s, t])
        for e in sorted(enemies):
            s = "\n".join([s, e])
        return s.strip()

    @property
    def treasure_ids(self):
        treasures = []
        for c in self.chests:
            if c.treasure:
                treasures.append(c.contents)
        return treasures

    def dummy_item(self, item):
        dummied = False
        for c in self.chests:
            dummied = c.dummy_item(item) or dummied
        return dummied

    def get_chest(self, chestid):
        return [c for c in self.chests if c.chestid == chestid][0]

    def get_entrance(self, entid):
        return [e for e in self.entrances if e.entid == entid][0]

    def uniqify_entrances(self):
        new_entrances = []
        done = []
        for e in self.entrances:
            values = (e.x, e.y, e.dest & 0x1FF, e.destx, e.desty)
            if values in done:
                continue
            else:
                new_entrances.append(e)
                done.append(values)
        self.entrance_set.entrances = new_entrances
        self.validate_entrances()

    def is_duplicate_entrance(self, entrance):
        for e in self.entrances:
            if (e.x == entrance.x and e.y == entrance.y and
                    e.dest & 0x1FF == entrance.dest & 0x1FF and
                    e.destx == entrance.destx and e.desty == entrance.desty):
                return True
        return False

    def validate_entrances(self):
        pairs = [(e.x, e.y) for e in self.entrances]
        if len(pairs) != len(set(pairs)):
            raise Exception("Duplicate entrances found on map %s." %
                            self.locid)

    def collapse_entids(self):
        entrances = self.entrances
        for i, e in enumerate(sorted(entrances, key=lambda x: x.entid)):
            e.entid = i

    @property
    def entrances(self):
        return self.entrance_set.entrances

    @property
    def longentrances(self):
        return self.entrance_set.longentrances

    @property
    def reachable_locations(self):
        locs = []
        for e in self.entrances:
            loc = e.destination
            if loc not in locs:
                locs.append(loc)
        return sorted(locs, key=lambda l: l.locid)

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
        _, entrance = min(candidates, key=lambda s: (s[0], s[1].entid))
        return entrance

    @property
    def battlebg(self):
        return self._battlebg & 0x3F

    @property
    def battle_palette(self):
        index = battlebg_palettes[self.battlebg]
        return 0x270150 + (index * 0x60)

        # if self.palette_index == 0x2a:
            # starts at 0x270150
        #    return 0x270510  # to 0x270570

    @property
    def fset(self):
        return get_fset(self.setid)

    @property
    def field_palette(self):
        return 0x2dc480 + (256 * (self.palette_index & 0x3F))
        # if self.palette_index == 0x2a:
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
        self.graphic_sets = list(f.read(4))
        self.tileformations = read_multi(f, length=2, reverse=True)
        self.mapdata = read_multi(f, length=4)
        self.unknown2 = ord(f.read(1))
        self.bgshift = list(f.read(4))
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

        f.seek(0xf5600 + self.locid)
        self.setid = ord(f.read(1))

        f.close()
        self.entrance_set.read_data(filename)
        self.backup_entrances()
        self.read_chests(filename)
        self.read_npcs(filename)
        self.read_events(filename)

    def make_tower_flair(self):
        towerloc = get_location(334)
        searchlight = towerloc.unknown1 & 0x3
        unused_layer3index = (((towerloc.graphic_sets[3] & 0xF0) >> 4) |
                              ((towerloc.tileformations & 0x3) << 4))
        layer3map = (towerloc.unknown2 & 0x3F) << 4
        layer3map |= (towerloc.mapdata >> 20)
        unused_layer3dims = towerloc.unknown4 & 0xF0

        self._battlebg = (towerloc._battlebg & 0xC0) | self._battlebg
        self.layers_to_animate = towerloc.layers_to_animate
        self.unknown0 = towerloc.unknown0
        self.unknown1 = (self.unknown1 & 0xFC) | searchlight
        self.graphic_sets[3] = (self.graphic_sets[3] & 0x0F) | (towerloc.graphic_sets[3] & 0xF0)
        self.tileformations = (self.tileformations & 0xFFFC) | (towerloc.tileformations & 0x3)
        self.mapdata = (self.mapdata & 0xFFFFF) | (towerloc.mapdata & 0x3FF00000)
        self.unknown2 = (self.unknown2 & 0xC0) | (towerloc.unknown2 & 0x3F)
        self.unknown3 = towerloc.unknown3
        self.unknown4 = towerloc.unknown4  # layer 3 bgshift
        self.unknown5 = towerloc.unknown5  # layer 3 priorities?
        self.layerpriorities = towerloc.layerpriorities
        #if random.randint(1, 15) != 15 or self.music == 0:

    def make_tower_basic(self):
        towerloc = get_location(334)
        self.attacks = towerloc.attacks
        self.music = towerloc.music
        self.make_warpable()
        add_location_map("Final Dungeon", self.locid)

    def make_warpable(self):
        self.layers_to_animate |= 2

    def fill_battle_bg(self, locid=None):
        if locid is None:
            locid = self.locid

        if self.battlebg in [0, 5] and locid in mapbattlebgs:
            battlebg = mapbattlebgs[locid]
            self._battlebg = (self._battlebg & 0xC0) | battlebg

    def write_data(self, fout):
        if self.pointer is None:
            self.pointer = 0x2D8F00 + (33 * self.locid)
        fout.seek(self.pointer)

        def write_attributes(*args):
            for attribute in args:
                attribute = getattr(self, attribute)
                try:
                    attribute = bytes([attribute])
                except TypeError:
                    attribute = bytes(attribute)
                fout.write(attribute)

        write_attributes("name_id", "layers_to_animate", "_battlebg",
                         "unknown0", "tileproperties", "attacks",
                         "unknown1", "graphic_sets")

        write_multi(fout, self.tileformations, length=2, reverse=True)
        write_multi(fout, self.mapdata, length=4, reverse=True)

        write_attributes(
            "unknown2", "bgshift", "unknown3", "layer12dimensions",
            "unknown4")

        write_multi(fout, self.palette_index, length=3)

        write_attributes("music", "unknown5", "width", "height",
                         "layerpriorities")
        try:
            assert fout.tell() == self.pointer + 0x21
        except:
            print(fout.tell() - (self.pointer + 0x21))

        fout.seek(0xf5600 + self.locid)
        fout.write(bytes([self.setid]))

    def copy(self, location):
        attributes = [
            "name_id", "layers_to_animate", "_battlebg", "unknown0",
            "tileproperties", "attacks", "unknown1", "graphic_sets",
            "tileformations", "mapdata", "unknown2", "bgshift", "unknown3",
            "layer12dimensions", "unknown4", "palette_index", "music",
            "unknown5", "width", "height", "layerpriorities",
            ]
        for attribute in attributes:
            if not hasattr(location, attribute):
                if hasattr(self, attribute):
                    delattr(self, attribute)
                continue
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
        numchests = (end - begin) // 5
        self.chests = []
        for i in range(numchests):
            pointer = begin + (i*5) + 0x2d8634
            c = ChestBlock(pointer, self.locid)
            c.read_data(filename)
            c.set_id(i)
            self.chests.append(c)

    def read_npcs(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.npcpointer)
        begin = read_multi(f, length=2)
        end = read_multi(f, length=2)
        numnpcs = (end - begin) / 9.0
        assert numnpcs == round(numnpcs)
        numnpcs = int(numnpcs)
        self.npcs = []
        for i in range(numnpcs):
            pointer = begin + (i*9) + 0x41a10
            e = NPCBlock(pointer, self.locid)
            e.read_data(filename)
            e.set_id(i)
            self.npcs.append(e)

    def read_events(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.eventpointer)
        begin = read_multi(f, length=2)
        end = read_multi(f, length=2)
        numevents = (end - begin) / 5.0
        assert numevents == round(numevents)
        numevents = int(numevents)
        self.events = []
        for i in range(numevents):
            pointer = begin + (i*5) + 0x40000
            e = EventBlock(pointer, self.locid)
            e.read_data(filename)
            e.set_id(i)
            self.events.append(e)

    def copy_chests(self, location):
        from chestrandomizer import ChestBlock
        self.chests = []
        for chest in location.chests:
            c = ChestBlock(pointer=None, location=self.locid)
            c.copy(chest)
            self.chests.append(c)

    def rank(self):
        if self.fset.setid == 0:
            return self.locid / 100.0
        return self.fset.rank()

    def mutate_chests(self, guideline=None, crazy_prices=False, no_monsters=False, uncapped_monsters=False):
        if not self.chests:
            return

        rank = None
        override = maplocations_override.get(maplocations[self.locid], None)
        if (self.attacks & 0x80 == 0 or override) and self.locid in maplocations:
            location = maplocations[self.locid]
            if override:
                location = override
            fsets = {get_location(l).fset
                     for l in maplocations_reverse[location]
                     if get_location(l).attacks & 0x80 != 0}
            if fsets:
                rank = min(fsets, key=lambda f: f.rank()).rank()
        else:
            rank = self.rank()
        for c in self.chests:
            c.set_rank(rank)

        if guideline is None:
            if not self.chests:
                values = [c.get_current_value(guideline=100)
                          for c in self.chests]
                average_value = (sum(values)*100) // len(values)
                guideline = average_value
            else:
                guideline = 100

        if self.locid == 0xb4:
            return
        if self.locid == 0x147:
            guideline = random.randint(1820, 4500)

        random.shuffle(self.chests)
        for c in self.chests:
            if self.locid in range(0x139, 0x13d) and c.empty:
                c.mutate_contents(monster=True, guideline=guideline, crazy_prices=crazy_prices, uncapped_monsters=uncapped_monsters)
                continue
            elif self.locid == 0x147:
                pass

            # No monster-in-a-box in the ZoneEater falling ceiling room.
            # It causes problems with the ceiling event.
            in_falling_ceiling_room = self.locid == 280 and c.memid in range(232, 235)
            monster = False if in_falling_ceiling_room or no_monsters else None
            c.mutate_contents(guideline=guideline, crazy_prices=crazy_prices, monster=monster, uncapped_monsters=uncapped_monsters)
            if guideline is None and hasattr(c, "value") and c.value:
                guideline = c.value

    def unlock_chests(self, low, high, monster=False,
                      guarantee_miab_treasure=False, enemy_limit=None, crazy_prices=False, uncapped_monsters=False):
        if len(self.chests) == 1:
            low = (low + high) // 2
        dist = (high - low) // 2
        for c in self.chests:
            c.set_content_type(0x80)
            c.contents = None
            value = low + random.randint(0, dist) + random.randint(0, dist)
            c.value = value
            c.mutate_contents(monster=monster, enemy_limit=enemy_limit,
                              guarantee_miab_treasure=guarantee_miab_treasure,
                              uniqueness=len(self.chests) != 1, crazy_prices=crazy_prices,
                              uncapped_monsters=uncapped_monsters)
            if random.randint(1, 5) >= 4:
                c.set_new_id()

    def write_chests(self, fout, nextpointer):
        fout.seek(self.chestpointer)
        write_multi(fout, (nextpointer - 0x2d8634), length=2)
        for c in self.chests:
            if nextpointer + 5 > 0x2d8e5a:
                raise Exception("Not enough space for treasure chests.")
            c.write_data(fout, nextpointer)
            nextpointer += 5
        fout.seek(self.chestpointer + 2)
        write_multi(fout, (nextpointer - 0x2d8634), length=2)

        return nextpointer

    def write_npcs(self, fout, nextpointer, ignore_order=False):
        fout.seek(self.npcpointer)
        write_multi(fout, (nextpointer - 0x41a10), length=2)
        for i in range(len(self.npcs)):
            if ignore_order:
                e = self.npcs[i]
            else:
                try:
                    e = [v for v in self.npcs if v.npcid == i][0]
                except IndexError:
                    raise Exception("NPCs out of order.")
            if nextpointer + 9 >= 0x46AC0:
                import pdb
                pdb.set_trace()
                raise Exception("Not enough space for npcs.")
            e.write_data(fout, nextpointer)
            nextpointer += 9
        fout.seek(self.npcpointer + 2)
        write_multi(fout, (nextpointer - 0x41a10), length=2)
        return nextpointer

    def write_events(self, fout, nextpointer):
        fout.seek(self.eventpointer)
        write_multi(fout, (nextpointer - 0x40000), length=2)
        for e in self.events:
            if nextpointer + 5 >= 0x41a10:
                import pdb
                pdb.set_trace()
                raise Exception("Not enough space for events.")
            e.write_data(fout, nextpointer)
            nextpointer += 5
        fout.seek(self.eventpointer + 2)
        write_multi(fout, (nextpointer - 0x40000), length=2)
        return nextpointer


class Entrance():
    def __init__(self, pointer=None):
        self.pointer = pointer
        self.entid = None
        self.x = 0
        self.y = 0
        self.dest = 0
        self.destx = 0
        self.desty = 0
        self._entrances = []
        self.location = None

    def read_data(self, filename):
        f = open(filename, 'r+b')
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
        if isinstance(location, int):
            location = get_location(location)
        self.location = location

    @property
    def mirror(self):
        loc = self.destination
        if loc is None:
            return None

        if not loc.entrancebackups:
            return None

        entrance = loc.get_nearest_entrance(self.destx, self.desty)
        if entrance is None:
            return None

        distance = abs(entrance.x - self.destx) + abs(entrance.y - self.desty)
        if distance > 3:
            return None

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

    def write_data(self, fout, nextpointer):
        if nextpointer >= 0x1FDA00:
            raise Exception("Not enough room for entrances.")
        fout.seek(nextpointer)
        fout.write(bytes([self.x]))
        fout.write(bytes([self.y]))
        write_multi(fout, self.dest, length=2)
        fout.write(bytes([self.destx]))
        fout.write(bytes([self.desty]))

    def __repr__(self):
        if hasattr(self, "entid") and self.entid is not None:
            entid = self.entid
        else:
            entid = "?"
        return "<%s %s: %s %s>" % (self.location.locid, entid, self.x, self.y)

    def copy(self, entrance):
        for attribute in ["x", "y", "dest", "destx", "desty",
                          "location", "entid"]:
            setattr(self, attribute, getattr(entrance, attribute))


class LongEntrance(Entrance):
    def read_data(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.pointer)
        self.x = ord(f.read(1))
        self.y = ord(f.read(1))
        self.width = ord(f.read(1))
        self.dest = read_multi(f, length=2)
        self.destx = ord(f.read(1))
        self.desty = ord(f.read(1))
        f.close()

    def write_data(self, fout, nextpointer):
        if nextpointer >= 0x2DFE00:
            raise Exception("Not enough room for long entrances.")
        fout.seek(nextpointer)
        fout.write(bytes([self.x]))
        fout.write(bytes([self.y]))
        fout.write(bytes([self.width]))
        write_multi(fout, self.dest, length=2)
        fout.write(bytes([self.destx]))
        fout.write(bytes([self.desty]))

    def copy(self, entrance):
        for attribute in ["x", "y", "dest", "destx", "desty", "width"]:
            setattr(self, attribute, getattr(entrance, attribute))


class EntranceSet():
    def __init__(self, entid):
        self.entid = entid
        self.pointer = 0x1fbb00 + (2*entid)
        self.longpointer = 0x2df480 + (2*entid)
        self.entrances = []
        self.longentrances = []

    @property
    def destinations(self):
        return {e.destination for e in self.entrances}

    def read_data(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.pointer)
        start = read_multi(f, length=2)
        end = read_multi(f, length=2)
        f.close()
        n = (end - start) // 6
        assert end == start + (6*n)
        self.entrances = []
        for i in range(n):
            e = Entrance(0x1fbb00 + start + (i*6))
            e.set_id(i)
            self.entrances.append(e)
        for e in self.entrances:
            e.read_data(filename)
            e.set_location(self.location)

        f = open(filename, 'r+b')
        f.seek(self.longpointer)
        start = read_multi(f, length=2)
        end = read_multi(f, length=2)
        f.close()
        n = (end - start) // 7
        assert end == start + (7*n)
        self.longentrances = []
        for i in range(n):
            e = LongEntrance(0x2DF480 + start + (i*7))
            e.set_id(i)
            self.longentrances.append(e)
        for e in self.longentrances:
            e.read_data(filename)
            e.set_location(self.location)

        self.location.uniqify_entrances()

    def write_data(self, fout, nextpointer, longnextpointer):
        fout.seek(self.pointer)
        write_multi(fout, (nextpointer - 0x1fbb00), length=2)
        fout.seek(self.longpointer)
        write_multi(fout, (longnextpointer - 0x2df480), length=2)
        self.location.uniqify_entrances()
        for e in self.entrances:
            if nextpointer + 6 > 0x1fda00:
                raise Exception("Too many entrance triggers.")
            e.write_data(fout, nextpointer)
            nextpointer += 6
        for e in self.longentrances:
            if longnextpointer + 7 >= 0x2dfe00:
                raise Exception("Too many long entrance triggers.")
            e.write_data(fout, longnextpointer)
            longnextpointer += 7
        return nextpointer, longnextpointer

    def copy(self, eset):
        self.entrances = []
        for e in sorted(eset.entrances, key=lambda x: x.entid):
            e2 = Entrance(e.entid)
            e2.copy(e)
            e2.set_id(e.entid)
            e2.set_location(self.location)
            self.entrances.append(e2)
        self.longentrances = []
        for e in sorted(eset.longentrances, key=lambda x: x.entid):
            e2 = LongEntrance(e.entid)
            e2.copy(e)
            e2.set_id(e.entid)
            e2.set_location(self.location)
            self.longentrances.append(e2)

    def convert_longs(self):
        for longentrance in self.longentrances:
            longentrance.dest &= 0xFE00
            longentrance.dest |= self.location.locid & 0x1FF
            e = random.choice(self.entrances)
            longentrance.destx = e.x
            longentrance.desty = e.y


def get_locations(filename=None):
    global locations
    if locations is None:
        locations = [Location(i) for i in range(415)]
        if filename is None:
            raise ValueError("Please supply a filename for new locations.")
        for l in locations:
            l.read_data(filename)
            l.fill_battle_bg()
            locdict[l.locid] = l
    return locations


def update_locations(newlocs):
    global locations
    for l in sorted(newlocs, key=lambda o: o.locid):
        if l in locations:
            continue
        original = [o for o in locations if o.locid == l.locid][0]
        index = locations.index(original)
        locations[index] = l
        locdict[l.locid] = l
        l.new = True


def get_zones(filename=None):
    global zones
    if zones is None:
        zones = [Zone(i) for i in range(0x100)]
        if filename is None:
            raise Exception("Please supply a filename for new zones.")
        for z in zones:
            z.read_data(filename)
        return get_zones()
    assert len(zones) == 0x100
    return zones


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
            ents = list(map(int, ents.split(',')))
            for ent in ents:
                if (locid, ent) in reachdict:
                    raise Exception("Duplicate reachability in table.")
                reachdict[(locid, ent)] = ents

    key = entrance.location.locid, entrance.entid
    if key not in reachdict:
        return []

    entrances = entrance.location.entrances
    return [e for e in entrances if e.entid in reachdict[key]]


def get_npcs():
    npcs = []
    for l in get_locations():
        npcs.extend(l.npcs)
    return npcs


def map_entrance_to_exit(entrance, exit):
    x = exit.x
    if exit.y < 10:
        y = exit.y + 1
        exit.facing = 2
    else:
        y = exit.y - 1
        exit.facing = 0
        
    entrance.dest = exit.location.locid
    entrance.destx = x
    entrance.desty = y


def randomize_forest():
    start = get_location(0x84)
    end = get_location(0x87)
    mids = [get_location(x) for x in (0x85, 0x86)]

    location86 = get_location(0x86)
    go_to_train_event = location86.events[0]
    location86.events.remove(go_to_train_event)
    world_location_exit = Entrance()
    world_location_exit.copy(location86.entrances[1])
    
    location = random.choice(mids)
    exit = random.choice(location.entrances)
    map_entrance_to_exit(start.entrances[0], exit)
    location2 = [m for m in mids if m.locid != location.locid][0]
    entrances = [e for e in location.entrances if e != exit]
    entrance = random.choice(entrances)
    exit2 = random.choice(location2.entrances)
    map_entrance_to_exit(entrance, exit2)
    entrances = [e for e in location2.entrances if e != exit]
    entrance2 = random.choice(entrances)
    entrance2.dest = world_location_exit.dest
    entrance2.destx = world_location_exit.destx
    entrance2.desty = world_location_exit.desty
    go_to_train_event.x = entrance2.x
    go_to_train_event.y = entrance2.y
    location2.events.append(go_to_train_event)

    wrong_entrances = [e for m in mids for e in m.entrances if e not in (entrance, entrance2)]
    wrong_exits = [e for m in (mids + [start]) for e in m.entrances]
    for e in wrong_entrances:
        exit = random.choice(wrong_exits)
        map_entrance_to_exit(e, exit)


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
    zones = get_zones(filename)
    for l in locations:
        print("%x" % (l.layers_to_animate & 2), l, end=' ')
        print()
