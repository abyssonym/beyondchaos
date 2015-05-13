from copy import deepcopy, copy
from utils import (ANCIENT_CHECKPOINTS_TABLE, TOWER_CHECKPOINTS_TABLE,
                   TOWER_LOCATIONS_TABLE, TREASURE_ROOMS_TABLE,
                   utilrandom as random)
from locationrandomizer import (get_locations, get_location,
                                get_unused_locations, Entrance,
                                add_location_map)
from formationrandomizer import get_fsets, get_formations
from chestrandomizer import ChestBlock
from itertools import product
from sys import stdout

SIMPLE, OPTIONAL, DIRECTIONAL = 's', 'o', 'd'
MAX_NEW_EXITS = 1000
MAX_NEW_MAPS = None  # 23: 6 more for fanatics tower, 1 more for bonus
ANCIENT = False
PROTECTED = [0, 1, 2, 3, 0xB, 0xC, 0xD, 0x11,
             0x37, 0x81, 0x82, 0x88, 0x9c, 0xb6, 0xb8, 0xbd, 0xbe,
             0xd2, 0xd3, 0xd4, 0xd5, 0xd7, 0xfe, 0xff,
             0x100, 0x102, 0x103, 0x104, 0x105, 0x10c, 0x12e,
             0x131,  # Tzen WoR?
             0x13b,  # Phoenix Cave
             0x13d,  # Three Stooges
             0x144,  # Albrook WoR?
             0x157, 0x158,  # Thamasa?
             #0xcf,   # owzer's mansion
             0xe7, 0xe9,   # opera with dancers?
             0x150, 0x164, 0x165, 0x19a, 0x19e]
PROTECTED += range(359, 371)  # Fanatics Tower


def set_max_maps(num, ancient=False):
    global ANCIENT, MAX_NEW_MAPS
    ANCIENT = ancient
    MAX_NEW_MAPS = (num - 24)

locdict = {}
old_entrances = {}
# dealing with one-ways: when identifying the "from" entrance in a route,
# retroactively add the "to" entrance to earlier in the route?
towerlocids = [int(line.strip(), 0x10) for line in open(TOWER_LOCATIONS_TABLE)]
map_bans = []
newfsets = {}
entrance_candidates = None


class SpecialInstructions:
    def __init__(self):
        self.deadends = set([])
        self.oneways = set([])
        self.nochanges = set([])
        self.removes = set([])

    @property
    def invalid(self):
        return self.nochanges | self.removes

    def add_item(self, item, attribute):
        a, b = item
        item = int(a), int(b)
        getattr(self, attribute).add(item)

    def add_nochange(self, item):
        self.add_item(item, 'nochanges')

    def add_remove(self, item):
        self.add_item(item, 'removes')

    def add_oneway(self, item):
        fro, to = item
        fro = tuple(map(int, fro))
        to = tuple(map(int, to))
        self.oneways.add((fro, to))

    def add_deadend(self, item):
        self.add_item(item, 'deadends')

    def remove_removes(self):
        for mapid, entid in self.removes:
            location = locdict[mapid]
            ents = [e for e in location.entrances if e.entid == entid]
            for ent in ents:
                location.entrance_set.entrances.remove(ent)


si = SpecialInstructions()
locexchange = {}


def connect_segments(sega, segb):
    exits = {}
    for seg in [sega, segb]:
        if seg.addable or seg.ruletype == OPTIONAL:
            entrances = seg.sorted_entrances
            random.shuffle(entrances)
        elif seg.ruletype == DIRECTIONAL:
            entrances = seg.entrances.values()[0]

        for e in entrances:
            shortsig = e.shortsig
            if shortsig not in seg.links:
                exits[seg] = e
                break
        else:
            raise Exception("No exits available.")

    sega.links[exits[sega].shortsig] = exits[segb].signature
    segb.links[exits[segb].shortsig] = exits[sega].signature


def clear_entrances(location):
    if location not in old_entrances:
        old_entrances[location] = set([])
    old_entrances[location] |= set(location.entrances)
    nochanges = [b for (a, b) in si.nochanges if a == location.locid]
    location.entrance_set.entrances = [e for e in location.entrances if
                                       e.entid in nochanges]


def clear_unused_locations():
    from locationrandomizer import unpurpose_repurposed
    for location in get_locations():
        if hasattr(location, "modname"):
            del(location.modname)
        if hasattr(location, "restrank"):
            del(location.restrank)
    unpurpose_repurposed()
    unused_locations = get_unused_locations()
    for u in unused_locations:
        clear_entrances(u)


def get_new_formations(areaname, supplement=True):
    from randomizer import get_namelocdict
    namelocdict = get_namelocdict()
    setids = set([])
    for key in namelocdict:
        if type(key) is str and areaname in key:
            setids |= set(namelocdict[key])

    fsets = [fs for fs in get_fsets() if fs.setid in setids]
    formations = set([])
    for fs in fsets:
        formations |= set(fs.formations)

    if supplement:
        lowest = min(formations, key=lambda f: f.rank()).rank()
        highest = max(formations, key=lambda f: f.rank()).rank()
        supplemental = [f for f in get_formations() if
                        not f.has_boss and lowest < f.rank() <= highest and
                        not f.battle_event]
        supplemental = sorted(supplemental, key=lambda f: f.rank())
        formations |= set([f for f in supplemental if
                           f.ambusher or f.inescapable])
        supplemental = supplemental[len(supplemental)/2:]
        formations |= set(supplemental)

    return sorted(formations, key=lambda f: f.formid)


def get_new_fsets(areaname, number=10, supplement=True):
    if areaname in newfsets:
        return newfsets[areaname]
    newfsets[areaname] = []
    formations = get_new_formations(areaname, supplement=supplement)
    fsets = get_fsets()
    unused = [fs for fs in fsets if fs.unused and len(fs.formations) == 4]
    tempforms = []
    for _ in xrange(number):
        if len(tempforms) < 4:
            tempforms = list(formations)
        setforms = random.sample(tempforms, 4)
        fset = unused.pop()
        fset.formids = [f.formid for f in setforms]
        tempforms = [f for f in tempforms if f not in setforms]
        newfsets[areaname].append(fset)

    return get_new_fsets(areaname)


def get_appropriate_location(loc, flair=None):
    if flair is None:
        flair = not ANCIENT
    unused_locations = get_unused_locations()
    if loc in locexchange:
        return locexchange[loc]
    elif loc.locid in towerlocids:
        clear_entrances(loc)
        locexchange[loc] = loc
        return loc
    elif hasattr(loc, "restrank"):
        clear_entrances(loc)
        locexchange[loc] = loc
        return loc
    else:
        from locationrandomizer import Location
        if ANCIENT:
            for u in locexchange.keys():
                if (u.locid not in towerlocids and u not in unused_locations
                        and u.locid not in PROTECTED):
                    unused_locations.append(u)
        exchange_ids = [l.locid for l in locexchange.values()]
        unused_ids = [l.locid for l in unused_locations
                      if l.locid not in exchange_ids]
        u = Location(unused_ids.pop())
        u.copy(loc)
        u.modname = loc.altname
        u.npcs = []
        u.events = []
        add_location_map("Final Dungeon", u.locid, strict=not ANCIENT)
        u.make_tower_basic()
        if flair:
            u.make_tower_flair()
        u.fill_battle_bg(loc.locid)
        if not ANCIENT:
            u.unlock_chests(200, 1000)
        fsets = get_new_fsets("kefka's tower", 20)
        fset = random.choice(fsets)
        for formation in fset.formations:
            formation.set_music(6)
            formation.set_continuous_music()
        u.setid = fset.setid
        clear_entrances(u)
        try:
            assert not u.entrances
        except:
            import pdb; pdb.set_trace()
        locexchange[loc] = u
        return u
    raise Exception("No appropriate location available.")


def get_inappropriate_location(location):
    reverselocex = dict([(b, a) for (a, b) in locexchange.items()])
    if location in reverselocex:
        return reverselocex[location]
    else:
        return location


def connect_entrances(sig, sig2):
    locid, x, y, _, _, _ = sig
    loc = get_appropriate_location(locdict[locid])
    loc2id, destx, desty, _, _, _ = sig2
    temploc = locdict[loc2id]
    loc2 = get_appropriate_location(temploc)

    # getting correct x/y values for destination
    tempent = temploc.get_nearest_entrance(destx, desty)
    assert abs(tempent.x - destx) + abs(tempent.y - desty) <= 4
    mirror = tempent.mirror
    dest = 0
    if mirror:
        destx, desty = mirror.destx, mirror.desty
        dest = mirror.dest & 0xFE00
    if ((mirror is None or mirror.mirror is None or
            mirror.mirror.location.locid != tempent.location.locid) or
            abs(tempent.x - destx) + abs(tempent.y - desty) > 4):
        destx, desty = tempent.x, tempent.y
    assert abs(tempent.x - destx) + abs(tempent.y - desty) <= 4

    entrance = Entrance(None)
    entrance.set_location(loc.locid)
    entrance.x = x
    entrance.y = y
    entrance.destx = destx
    entrance.desty = desty
    entrance.dest = loc2.locid | dest
    entrance.dest &= 0x3DFF
    effectsigs = [e3.effectsig for e3 in loc.entrances]
    if entrance.effectsig in effectsigs:
        return
    if not loc.is_duplicate_entrance(entrance):
        loc.entrance_set.entrances.append(entrance)
    loc.validate_entrances()


class CheckRoomSet:
    def __init__(self):
        self.entrances = {}
        self.links = {}
        self.addable = True
        self.ruletype = None

    def __repr__(self):
        return str(self.entrances)

    def backup(self):
        self.backup_entrances = copy(self.entrances)

    def load_backup(self):
        self.entrances = copy(self.backup_entrances)

    def establish_entrances(self):
        for mapid in self.entrances:
            for e in self.entrances[mapid]:
                sig = e.signature
                if e.shortsig not in self.links:
                    #print "WARNING: %s not in links." % str(sig)
                    continue
                sig2 = self.links[e.shortsig]
                connect_entrances(sig, sig2)

    def get_must_assign(self):
        musts = []
        backups = []
        for mapid in self.entrances:
            oldlocation = get_location(mapid)
            location = get_appropriate_location(oldlocation)

            coordinates = [(e.x, e.y) for e in self.entrances[mapid]]
            locentrances = [e for e in old_entrances[location] if
                            (e.x, e.y) in coordinates]

            coordinates = [(e.x, e.y) for e in location.entrances]
            locentrances = [e for e in locentrances if
                            (e.x, e.y) in coordinates]

            candidates = sorted([c for c in self.entrances[mapid] if
                                 (c.x, c.y) not in coordinates],
                                key=lambda e: e.entid)

            LARGE_VALUE = 5
            MIN_LARGE = 3
            if ANCIENT:
                LARGE_VALUE = 100
            numentrances = len(self.entrances[mapid])
            if numentrances < LARGE_VALUE and len(locentrances) < numentrances:
                musts.extend(random.sample(
                    candidates, numentrances-len(locentrances)))
            elif numentrances >= LARGE_VALUE and len(locentrances) < MIN_LARGE:
                musts.extend(random.sample(
                    candidates, MIN_LARGE-len(locentrances)))
            backups.extend([c for c in self.entrances[mapid] if
                            c not in musts and (c.x, c.y) not in coordinates])

        taken = []
        pairs = []
        unwed = []
        for e in list(musts):
            if e in taken:
                continue

            strict = lambda c: (c not in taken and
                                c.location.locid != e.location.locid)
            loose = lambda c: c not in taken and c != e
            preferences = [(musts, strict), (musts, loose),
                           (backups, strict), (backups, loose)]
            for candidates, evaluator in preferences:
                candidates = filter(evaluator, candidates)
                if candidates:
                    c = random.choice(candidates)
                    taken.append(e)
                    taken.append(c)
                    pairs.append((e, c))
                    break
            else:
                unwed.append((self, e))
        return pairs, unwed

    @property
    def reachability_factor(self):
        num_entrances = sum([len(self.entrances[k]) for k in self.entrances.keys()])
        num_maps = len(self.entrances.keys())
        if num_entrances - self.numexits < 0:
            return 1000000
        return float(num_maps) / num_entrances

    @property
    def maps(self):
        return self.entrances.keys()

    @property
    def sorted_entrances(self):
        entrances = []
        for es in self.entrances.values():
            entrances.extend(es)
        entrances = sorted(set(entrances),
                           key=lambda e: (e.location.locid, e.entid))
        return entrances

    def generate_reachability_matrix(self):
        from utils import get_matrix_reachability
        entrances = self.sorted_entrances
        edict = dict(zip(entrances, range(len(entrances))))
        basematrix = [0]*len(entrances)
        basematrix = [list(basematrix) for _ in xrange(len(entrances))]
        for e in entrances:
            a = edict[e]
            basematrix[a][a] = 1
            for e2 in self.entrances[e.location.locid]:
                if e2 in edict:
                    b = edict[e2]
                    basematrix[a][b] = 1
                    basematrix[b][a] = 1

        zeroes = sum([row.count(0) for row in basematrix])
        if zeroes == 0:
            if len(basematrix) < self.numexits:
                return None
            self.reachability = basematrix
            return basematrix

        locids = self.entrances.keys()
        for attempts in xrange(5):
            matrix = deepcopy(basematrix)
            candidates = list(entrances)
            random.shuffle(locids)
            done = []
            links = {}
            try:
                for l in locids:
                    if l in done:
                        continue
                    front = [c for c in candidates if c.location.locid == l]
                    c1 = random.choice(front)
                    back = [c for c in candidates if c.location.locid in done]
                    if not back:
                        back = [c for c in candidates if c not in front
                                and len(c.location.entrances) > 1]
                    if not back:
                        back = [c for c in candidates if c not in front]
                    c2 = random.choice(back)
                    done.extend([l, c2.location.locid])
                    candidates.remove(c1)
                    candidates.remove(c2)
                    a, b = edict[c1], edict[c2]
                    matrix[a][b] = 1
                    matrix[b][a] = 1
                    links[c1.shortsig] = c2.signature
                    links[c2.shortsig] = c1.signature
            except IndexError:
                continue

            if len(candidates) < self.numexits:
                return None

            prevones = 0
            reach = deepcopy(matrix)
            for _ in xrange(len(entrances)*2):
                reach = get_matrix_reachability(reach)
                zeroes = sum([row.count(0) for row in reach])
                ones = sum([row.count(1) for row in reach])
                assert zeroes + ones == len(entrances)**2
                if ones == prevones:
                    break

            if zeroes == 0:
                break

        else:
            return None

        self.reachability = matrix
        self.links = links
        return matrix

    def add_rule(self, ruletype, mapid, parameters, reachable=True):
        assert type(parameters) in [list, tuple]
        if self.ruletype in [OPTIONAL, DIRECTIONAL]:
            raise Exception("Already set a rule.")

        self.ruletype = ruletype
        if ruletype == SIMPLE:
            # can add simple rooms arbitrarily
            self.addable = True
        elif ruletype in [OPTIONAL, DIRECTIONAL]:
            assert not self.entrances
            if ruletype == OPTIONAL:
                random.shuffle(parameters)
            else:
                assert len(parameters) == 2
            self.addable = False
        for p in parameters:
            self.add_entrance(mapid, p, reachable=reachable)

    def add_entrance(self, mapid, entid, reachable=True):
        # adding unreachable entrance = asserting it is reachable
        if mapid not in self.entrances:
            self.entrances[mapid] = []
        loc = get_location(mapid)
        if hasattr(loc, "restrank"):
            entrance = loc.entrances[0]
        else:
            try:
                entrance = [e for e in locdict[mapid].entrances if e.entid == entid][0]
            except IndexError:
                import pdb; pdb.set_trace()
        if entrance not in self.entrances[mapid]:
            self.entrances[mapid].append(entrance)
        if reachable:
            for e in entrance.reachable_entrances:
                if (mapid, e.entid) in si.invalid:
                    continue
                if e not in self.entrances[mapid]:
                    self.entrances[mapid].append(e)
        return self.entrances[mapid]

    def remove_entrance(self, mapid, entid):
        if mapid not in self.entrances:
            return
        entrances = self.entrances[mapid]
        for e in entrances:
            if e.entid == entid:
                self.entrances[mapid].remove(e)


class RouteRouter:
    def __init__(self, starting):
        self.set_starting(starting)
        self.checkpoints = []

    def reset_entrance_locations(self):
        for route in self.routes.values():
            for segment in route:
                for entrance in segment.sorted_entrances:
                    locid = entrance.location.locid
                    entrance.location = get_location(locid)

    def backup(self):
        for route in self.routes.values():
            for segment in route:
                segment.backup()

    def load_backup(self):
        for route in self.routes.values():
            for segment in route:
                segment.load_backup()

    @property
    def entrances(self):
        entrances = set([])
        for route in self.routes.values():
            for segment in route:
                for zone in segment.entrances.values():
                    entrances |= set(zone)
        return entrances

    def get_unfilled_segment(self):
        routes = list(self.routes.values())
        random.shuffle(routes)
        for route in routes:
            candidates = filter(lambda c: c.addable and not c.entrances, route)
            if candidates:
                if random.randint(1, 5) != 5:
                    segment = min(candidates, key=lambda c: c.reachability_factor)
                else:
                    segment = random.choice(candidates)
                return segment

    def set_starting(self, starting):
        self.starting = []
        for a, b in starting:
            self.starting.append((SIMPLE, int(a), [int(b)]))

    def set_ending(self, ending):
        self.ending = []
        for a, b in ending:
            self.ending.append((SIMPLE, int(a), [int(b)]))

    def add_checkpoint(self, simple, optional, directional):
        assert len(simple + optional + directional) <= 3
        rule = []
        for a, b in simple:
            a, b = int(a), int(b)
            rule.append((SIMPLE, a, [b]))
        for a, options in optional:
            a, options = int(a), map(int, options)
            rule.append((OPTIONAL, a, options))
        for a, fro, to in directional:
            a, fro, to = int(a), int(fro), int(to)
            rule.append((DIRECTIONAL, a, (fro, to)))
        for subrule in rule:
            assert type(subrule[2]) in [list, tuple]
        self.checkpoints.append(rule)

    def construct_check_routes(self):
        random.shuffle(self.checkpoints)
        routes = dict([(i, []) for i in range(3)])

        for rule in [self.starting] + self.checkpoints + [self.ending]:
            parties = range(3)
            random.shuffle(parties)
            assert len(parties) >= len(rule)
            if rule == self.starting:
                hard = self.hardstart
            elif rule == self.ending:
                hard = self.hardend
            else:
                hard = False
            for party, subrule in zip(parties, rule):
                ruletype, mapid, parameters = subrule
                crs = CheckRoomSet()
                crs.add_rule(ruletype, mapid, parameters, reachable=not hard)
                for p in parameters:
                    for (a, b), (c, d) in si.oneways:
                        if mapid == a and p == b:
                            candidates = filter(lambda crs: crs.addable, routes[party])
                            precrs = random.choice(candidates)
                            precrs.add_rule(SIMPLE, c, [d], reachable=not hard)
                if (routes[party] and not routes[party][-1].addable and
                        not crs.addable):
                    crs2 = CheckRoomSet()
                    routes[party].append(crs2)
                    crs2.numexits = 2

                if rule in [self.starting, self.ending]:
                    crs.numexits = 1
                else:
                    crs.numexits = 2

                routes[party].append(crs)

        for route in routes.values():
            for crs in route:
                for (mapid, entid) in si.removes | si.nochanges:
                    continue
                    crs.remove_entrance(mapid, entid)

        self.routes = routes


def parse_checkpoints():
    rr = None
    rrs = []
    if ANCIENT:
        checkpoints = ANCIENT_CHECKPOINTS_TABLE
    else:
        checkpoints = TOWER_CHECKPOINTS_TABLE
    for line in open(checkpoints):
        line = line.strip()
        if not line:
            continue
        if line[0] in '#&%-' or '>>' in line:
            continue
        elif line[0] == '!':
            # set new dungeon matrix with given positions
            line = line[1:]
            if line[0] == '!':
                line = line[1:]
                hardstart = True
            else:
                hardstart = False
            mappoints = line.split(',')
            mappoints = [tuple(m.split(':')) for m in mappoints]
            rr = RouteRouter(mappoints)
            rr.starter = tuple([(int(a), int(b)) for a, b in mappoints])
            rr.hardstart = hardstart
            rrs.append(rr)
        elif line[0] == '$':
            line = line[1:]
            if line[0] == '$':
                line = line[1:]
                hardend = True
            else:
                hardend = False
            mappoints = line.split(',')
            mappoints = [tuple(m.split(':')) for m in mappoints]
            rr.set_ending(mappoints)
            rr.hardend = hardend
            rr = None
        elif line[0] == 'R':
            rank = int(line[1:])
            restrooms = get_unused_locations()[:3]
            colisseum = get_location(0x19d)
            for r in restrooms:
                r.copy(colisseum)
                r.repurposed = True
                r.restrank = rank
                r.modname = "Rest Room"
                r.npcs = []
                r.events = []
                r.fill_battle_bg(colisseum.locid)
                r.entrance_set.entrances = [e for e in r.entrance_set.entrances
                                            if e.entid == 3]
                r.backup_entrances()
            simple = [(str(r.locid), "3") for r in restrooms]
            rr.add_checkpoint(simple, [], [])
        else:
            items = line.split(',')
            directional = []
            optional = []
            simple = []
            for item in items:
                loc, entrances = tuple(item.split(':'))
                if '>' in entrances:
                    # entrances that must be used, and in a specific order
                    fro, to = tuple(entrances.split('>'))
                    directional.append((loc, fro, to))
                elif '|' in entrances:
                    # entrances that must be used, in no specific order
                    options = entrances.split('|')
                    optional.append((loc, options))
                else:
                    # one entrance
                    simple.append((loc, entrances))
            rr.add_checkpoint(simple, optional, directional)

    for line in open(checkpoints):
        line = line.strip()
        if not line:
            continue
        if line[0] in '#!$':
            continue
        elif line[0] == '&':
            # these entrances and exits must not be changed
            line = line[1:]
            loc, entrances = tuple(line.split(':'))
            entrances = tuple(entrances.split(','))
            for e in entrances:
                si.add_nochange((loc, e))
        elif line[0] == '-':
            # useless entrances to delete
            line = line[1:]
            loc, entrances = tuple(line.split(':'))
            entrances = tuple(entrances.split(','))
            for e in entrances:
                si.add_remove((loc, e))
        elif line[0] == '%':
            # these should lead nowhere, or backwards
            line = line[1:]
            for rr in rrs:
                si.add_deadend(tuple(line.split(':')))
        elif '>>' in line:
            # one way paths
            fro, to = tuple(line.split('>>'))
            fro = tuple(fro.split(':'))
            to = tuple(to.split(':'))
            si.add_oneway((fro, to))

    return rrs


def assign_maps(rrs, maps=None, new_entrances=None):
    if maps is None:
        maps = towerlocids

    location_entrances = []
    for m in maps:
        location = locdict[m]
        location_entrances.append(location.entrances)

    if new_entrances:
        for e in new_entrances:
            location_entrances.append(e.reachable_entrances)

    used_entrances = set([en for rr in rrs for en in rr.entrances])
    for base_entrances in reversed(location_entrances):
        assert len(set([e.location.locid for e in base_entrances])) == 1

        def validate(e):
            if e.location is None:
                return False

            invalid = si.nochanges | si.removes
            if (e.location.locid, e.entid) in invalid:
                return False

            return True
        base2_entrances = copy(base_entrances)
        base2_entrances = set([e for e in base2_entrances if validate(e)])

        while True:
            entrances = base2_entrances - used_entrances
            if not entrances:
                break

            random.shuffle(rrs)
            for rr in rrs:
                segment = rr.get_unfilled_segment()
                if segment is not None:
                    break

            entrances = sorted(entrances,
                               key=lambda e: (e.location.locid, e.entid))
            if segment is None:
                while True:
                    rr = random.choice(rrs)
                    route = random.choice(rr.routes)

                    def validate(c):
                        if not c.addable:
                            return False
                        locid = entrances[0].location.locid
                        if locid in c.entrances:
                            return False
                        return True

                    candidates = filter(validate, route)
                    if not candidates:
                        continue
                    else:
                        segment = random.choice(candidates)
                        break

            e = random.choice(entrances)
            usednow = segment.add_entrance(e.location.locid, e.entid)
            used_entrances |= set(usednow)


def get_all_entrances(filename=None):
    global entrance_candidates
    if entrance_candidates:
        return entrance_candidates
    entrance_candidates = [e for l in get_locations() for e in l.entrances]

    unused_locations = get_unused_locations(filename)

    def validate(e):
        # TODO: remove maps with adjacent entrances
        if e.location.locid <= 2:
            return False
        if e.location.locid in towerlocids:
            return False
        if e.location.locid in unused_locations:
            return False
        if e.location.locid in map_bans:
            return False
        reachable = e.reachable_entrances
        if len(reachable) < 1 + random.randint(0, 2):
            return False
        if (len(reachable) <= 2 and
                len(e.location.chests) <= random.randint(0, 1) and
                random.randint(1, 10) != 10):
            return False
        for e2, e3 in product(reachable, reachable):
            value = abs(e2.x - e3.x) + abs(e2.y - e3.y)
            if value == 1:
                return False
        if (e.x <= 1 or e.y <= 1 or
                e.x == (e.location.layer1width-2) or
                e.y == (e.location.layer1height-2)):
            if e.mirror is None or e.mirror.mirror is None:
                return False
        return True

    entrance_candidates = [e for e in entrance_candidates if validate(e)]
    return get_all_entrances()


def get_new_entrances(filename):
    candidates = get_all_entrances(filename)
    random.shuffle(candidates)
    used_locations = []
    chosen = []
    num_entrances = 0
    for c in candidates:
        locsig = (c.location.layer1ptr, c.location.palette_index)
        if locsig in used_locations:
            continue
        numreach = len(c.reachable_entrances)
        if num_entrances + numreach >= MAX_NEW_EXITS:
            continue
        if numreach == 1 and random.randint(1, 10) != 10:
            continue
        if numreach == 2 and random.randint(1, 2) != 2:
            continue
        if not ANCIENT:
            num_entrances += min(numreach, 5)
        else:
            num_entrances += numreach
        chosen.append(c)
        used_locations.append(locsig)
        if len(chosen) == MAX_NEW_MAPS:
            break

    return chosen


def rank_maps(rrs):
    rrs = sorted(rrs, key=lambda rr: (334, 0) not in rr.starter)
    rank = 1
    done = set([])
    fringe = []
    rr = rrs[0]
    startents = []
    for mapid, entid in rr.starter:
        for route in rr.routes.values():
            beginning = route[0].entrances
            if mapid in beginning:
                ents = beginning[mapid]
                ents = [e for e in ents if e.entid == entid]
                if len(ents) == 1:
                    ent = ents[0]
                    ents = [e for e in ent.location.entrances
                            if e.x == ent.x and e.y == ent.y]
                    startents.append(ents[0])
    assert len(startents) == 3

    def expand_fringe(fringe):
        candidates = []
        for location in fringe:
            for ent in location.entrances:
                if ent.destination not in candidates + fringe:
                    candidates.append(ent.destination)
        fringe.extend(candidates)
        fringe = sorted(set(fringe), key=lambda l: l.locid)
        return fringe

    fringe += [get_location(e.dest & 0x1FF) for e in startents]
    while True:
        candidates = [c for c in fringe if c not in done]
        if not candidates:
            size = len(fringe)
            fringe = expand_fringe(fringe)
            if len(fringe) > size:
                continue
            elif len(fringe) == size:
                break
        chosen = random.choice(candidates)
        if ((hasattr(chosen, "secret_treasure") and chosen.secret_treasure) or
                hasattr(chosen, "restrank")):
            chosen.ancient_rank = 0
            done.add(chosen)
            continue
        chosen.ancient_rank = rank
        rank += 1
        done.add(chosen)

    get_location(334).ancient_rank = 0


def randomize_tower(filename, ancient=False):
    if ancient:
        set_max_maps(200, ancient=True)
    else:
        set_max_maps(47)

    for l in get_locations(filename=filename):
        locdict[l.locid] = l

    def make_matrices():
        for rr in rrs:
            assert len(rr.routes) == 3
            for route in rr.routes.values():
                for segment in route:
                    if segment.addable:
                        m = segment.generate_reachability_matrix()
                        if m is None:
                            return False
        return True

    new_entrances = get_new_entrances(filename=filename)
    counter = 0

    while True:
        clear_unused_locations()
        rrs = parse_checkpoints()
        si.remove_removes()
        for rr in rrs:
            rr.construct_check_routes()

        new_entrances = get_new_entrances(filename=filename)
        assign_maps(rrs, new_entrances=new_entrances)
        done = make_matrices()
        if done:
            break
        counter += 1
        if not counter % 10:
            stdout.write('.')
            stdout.flush()
    print

    usedlinks = set([])
    for rr in rrs:
        for i, route in enumerate(rr.routes.values()):
            for sega, segb in zip(route, route[1:]):
                connect_segments(sega, segb)

            for segment in route:
                links = set(segment.links)
                if usedlinks & links:
                    import pdb; pdb.set_trace()
                    raise Exception("Duplicate entrance detected.")
                usedlinks |= links
                segment.establish_entrances()

    pairs, thirdpairs = [], []
    for rr in rrs:
        for route in rr.routes.values():
            unwed, unwedvals = {}, {}
            thirdwheels = []
            segvals = dict([(b, a) for (a, b) in enumerate(route)])
            for segment in route:
                a, b = segment.get_must_assign()
                pairs.extend(a)
                for seg, u in b:
                    key = segvals[seg]
                    if key not in unwed:
                        unwed[key] = []
                    unwed[key].append(u)
                    unwedvals[u] = key

            for key in sorted(unwed):
                for u in unwed[key]:
                    candidates = []
                    if key-1 in unwed:
                        candidates.extend(unwed[key-1])
                    if key+1 in unwed:
                        candidates.extend(unwed[key+1])
                    if candidates:
                        u2 = random.choice(candidates)
                        pairs.append((u, u2))
                        unwed[unwedvals[u]].remove(u)
                        unwed[unwedvals[u2]].remove(u2)
                    else:
                        thirdwheels.append(u)

            for t in thirdwheels:
                val = unwedvals[t]
                candidates = []
                for segment in route:
                    if segvals[segment] <= val:
                        entrancess = segment.entrances.values()
                        for entrances in entrancess:
                            candidates.extend(entrances)
                realcands = [c for c in candidates if
                             c.location.locid != t.location.locid]
                if len(realcands) == 0:
                    realcands = list(candidates)
                if len(realcands) > 1 and t in realcands:
                    realcands.remove(t)
                c = random.choice(realcands)
                thirdpairs.append((t, c))

    for (a, b) in pairs:
        sig = a.signature
        sig2 = b.signature
        connect_entrances(sig, sig2)
        connect_entrances(sig2, sig)

    for (t, c) in thirdpairs:
        sig = t.signature
        sig2 = c.signature
        connect_entrances(sig, sig2)

    for rr in rrs:
        for route in rr.routes.values():
            for segment in route:
                a, b = segment.get_must_assign()
                for mapid in segment.entrances:
                    loc = get_appropriate_location(locdict[mapid])
                    loc.validate_entrances()
                if a or b:
                    raise Exception("NOPE")

    for a, b in locexchange.items():
        if b.locid != a.locid:
            b.entrance_set.convert_longs()

    make_secret_treasure_room()

    if not ancient:
        randomize_fanatics()

    from locationrandomizer import update_locations
    update_locations(locexchange.values())
    rank_maps(rrs)
    if ANCIENT:
        assert len([l for l in get_locations() if
                    hasattr(l, "restrank")]) == 12


def make_secret_treasure_room():
    from itemrandomizer import get_secret_item
    candidates = []
    for line in open(TREASURE_ROOMS_TABLE):
        locid, entid, chestid = tuple(map(int, line.strip().split(',')))
        location = get_location(locid)
        if location in locexchange:
            continue
        entrance = location.get_entrance(entid)
        chest = location.get_chest(chestid)
        candidates.append((location, entrance, chest))
    location, entrance, chest = random.choice(candidates)
    oldlocation = location
    location = get_appropriate_location(oldlocation, flair=False)

    c = ChestBlock(pointer=None, location=location.locid)
    c.copy(chest)
    c.set_content_type(0x40)
    item = get_secret_item()
    c.contents = item.itemid
    c.set_new_id()
    c.do_not_mutate = True
    c.ignore_dummy = True
    location.chests = [c]
    location.secret_treasure = True

    e = Entrance(None)
    e.copy(entrance)
    #location.entrance_set.entrances = [e]
    e.set_location(location)
    assert len(location.entrances) == 0

    belt = get_location(287)
    e2 = [ee for ee in belt.entrances if ee.x == 36 and ee.y == 25][0]
    belt.entrance_set.entrances.remove(e2)
    sig = entrance.signature
    sig2 = e2.signature
    connect_entrances(sig, sig2)
    connect_entrances(sig2, sig)

    location.attacks = 0
    location.music = 21


def randomize_fanatics():
    stairs = [get_location(i) for i in [363, 359, 360, 361]]
    pitstops = [get_location(i) for i in [365, 367, 368, 369]]
    num_new_levels = random.randint(0, 1) + random.randint(1, 2)
    exchange_ids = [l.locid for l in locexchange.values()]
    unused_locations = get_unused_locations()
    unused_locations = [u for u in unused_locations if
                        u.locid not in exchange_ids]
    fsets = get_new_fsets("fanatics", 10, supplement=False)
    for _ in xrange(num_new_levels):
        stair = unused_locations.pop()
        stop = unused_locations.pop()
        stair.copy(random.choice(stairs[1:-1]))
        stop.copy(random.choice(pitstops[1:]))
        add_location_map("Fanatics Tower", stair.locid)
        add_location_map("Fanatics Tower", stop.locid)
        index = random.randint(1, len(stairs)-1)
        stairs.insert(index, stair)
        pitstops.insert(index, stop)

        chest = stop.chests[0]
        chest.set_new_id()

        entrance = stop.entrances[0]
        entrance.dest = (entrance.dest & 0xFE00) | (stair.locid & 0x1FF)

        entrance = sorted(stair.entrances, key=lambda e: e.y)[1]
        entrance.dest = (entrance.dest & 0xFE00) | (stop.locid & 0x1FF)

        stair.setid = random.choice(fsets).setid
        stop.setid = random.choice(fsets).setid

    for a, b in zip(stairs, stairs[1:]):
        lower = sorted(a.entrances, key=lambda e: e.y)[0]
        upper = sorted(b.entrances, key=lambda e: e.y)[-1]
        lower.dest = (lower.dest & 0xFE00) | (b.locid & 0x1FF)
        upper.dest = (upper.dest & 0xFE00) | (a.locid & 0x1FF)

    for stop in pitstops:
        if random.choice([True, False]):
            continue
        index = pitstops.index(stop)
        if index == 0:
            continue
        index2 = index + random.choice([-1, -1, -2])
        if index2 < 0:
            index2 = 0
        stair = stairs[index2]
        entrance = stop.entrances[0]
        entrance.dest = (entrance.dest & 0xFE00) | (stair.locid & 0x1FF)


if __name__ == "__main__":
    #randomize_tower(filename="program.rom")
    pass
