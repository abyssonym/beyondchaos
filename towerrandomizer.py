#!/usr/bin/env python3

from itertools import zip_longest

from chestrandomizer import ChestBlock
from formationrandomizer import get_fsets, get_formations
from locationrandomizer import (get_locations, get_location, Location,
                                get_unused_locations, Entrance,
                                add_location_map, update_locations)
from utils import (ANCIENT_CHECKPOINTS_TABLE, TOWER_CHECKPOINTS_TABLE,
                   TOWER_LOCATIONS_TABLE, TREASURE_ROOMS_TABLE,
                   ENTRANCE_REACHABILITY_TABLE,
                   utilrandom as random)


SIMPLE, OPTIONAL, DIRECTIONAL = 's', 'o', 'd'
MAX_NEW_EXITS = 1000
MAX_NEW_MAPS = None  # 23: 6 more for fanatics tower, 1 more for bonus
ANCIENT = None
PROTECTED = [0, 1, 2, 3, 0xB, 0xC, 0xD, 0x11,
             0x37, 0x81, 0x82, 0x88, 0x89, 0x8c, 0x8f, 0x90, 0x92, 0x99, 0x9c,
             0xb6, 0xb7, 0xb8, 0xbd, 0xbe,
             0xd2, 0xd3, 0xd4, 0xd5, 0xd7, 0xfe, 0xff,
             0x100, 0x102, 0x103, 0x104, 0x105, 0x10c, 0x12e,
             0x131, 0x132,  # Tzen WoR?
             0x139, 0x13a, 0x13b, 0x13c,  # Phoenix Cave
             0x13d,  # Three Stooges
             0x13e,
             0x141, 0x142,  # Dream train
             0x143, 0x144,  # Albrook
             0x154, 0x155, 0x157, 0x158,  # Thamasa
             0xe7, 0xe9, 0xea, 0xeb,  # opera with dancers?
             0x187,  # sealed gate - layer issues
             0x18f,  # same
             0x189, 0x18a,  # floating continent
             0x150, 0x164, 0x165, 0x19a, 0x19e]
PROTECTED += list(range(359, 371))  # Fanatics Tower
PROTECTED += list(range(382, 387))  # Sealed Gate
FIXED_ENTRANCES, REMOVE_ENTRANCES = [], []

locexchange = {}
old_entrances = {}
towerlocids = [int(line.strip(), 0x10) for line in open(TOWER_LOCATIONS_TABLE)]
map_bans = []
newfsets = {}
clusters = None


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
        formations |= {f for f in supplemental
                       if f.ambusher or f.inescapable}
        supplemental = supplemental[len(supplemental)//2:]
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
    for _ in range(number):
        if len(tempforms) < 4:
            tempforms = list(formations)
        setforms = random.sample(tempforms, 4)
        fset = unused.pop()
        fset.formids = [f.formid for f in setforms]
        tempforms = [f for f in tempforms if f not in setforms]
        newfsets[areaname].append(fset)

    return get_new_fsets(areaname)


def remap_maps(routes):
    conlinks = []
    cononeways = []
    conentrances = []
    conclusters = []
    for route in routes:
        conlinks.extend(route.consolidated_links)
        cononeways.extend(route.consolidated_oneways)
        conentrances.extend(route.consolidated_entrances)
        conclusters.extend(route.consolidated_clusters)
        conclusters = sorted(set(conclusters), key=lambda c: c.clusterid)

    if ANCIENT:
        unused_maps = [l.locid for l in get_locations()
                       if l.locid not in towerlocids
                       and l.locid not in PROTECTED]
        rest_maps = [l.locid for l in get_unused_locations() if l.locid != 414]
    else:
        unused_maps = [l.locid for l in get_unused_locations()]
        rest_maps = []

    for cluster in conclusters:
        if not isinstance(cluster, RestStop):
            continue
        locid = cluster.locid
        newlocid = rest_maps.pop()
        locexchange[(locid, locid)] = newlocid
        try:
            unused_maps.remove(newlocid)
        except:
            import pdb; pdb.set_trace()

    for cluster in conclusters:
        if isinstance(cluster, RestStop):
            continue

        locid = cluster.locid
        if (locid, cluster.clusterid) in locexchange:
            continue

        locclusters = [c for c in conclusters if
                       not isinstance(c, RestStop) and c.locid == locid]
        if locid in towerlocids:
            for c in locclusters:
                locexchange[(locid, c.clusterid)] = locid
        else:
            location = get_location(locid)
            if locid in unused_maps:
                newlocid = locid
                unused_maps = [u for u in unused_maps if u != newlocid]
            else:
                newlocid = unused_maps.pop()
            if location.longentrances:
                locexchange[(locid, cluster.clusterid)] = newlocid
            else:
                for c in locclusters:
                    locexchange[(locid, c.clusterid)] = newlocid

    newlocations = []
    for newlocid in sorted(set(locexchange.values())):
        keys = [key for (key, value) in locexchange.items()
                if value == newlocid]
        assert len(set([a for (a, b) in keys])) == 1
        copylocid = keys[0][0]
        if copylocid >= 1000:
            cluster = [c for c in conclusters if c.locid == copylocid][0]
            copylocid = 413
            location = get_location(413)
            newlocation = Location(locid=newlocid, dummy=True)
            newlocation.copy(location)
            newlocation.events = []
            newlocation.npcs = []
            newlocation.entrance_set.entrances = []
            newlocation.restrank = cluster.rank
        else:
            location = get_location(copylocid)
            entrances = location.entrances
            newlocation = Location(locid=newlocid, dummy=True)
            newlocation.copy(location)
            newlocation.events = []
            newlocation.npcs = []
            newlocation.entrance_set.entrances = []
            fixed = [e for e in entrances
                     if (e.location.locid, e.entid) in FIXED_ENTRANCES]
            newlocation.entrance_set.entrances.extend(fixed)

        locclusters = [c for c in conclusters if
                       locexchange[(c.locid, c.clusterid)] == newlocid]
        clustents = [e for c in locclusters for e in c.entrances]
        clustents = [e for e in clustents if e in conentrances]

        for ent in clustents:
            destent = [(a, b) for (a, b) in conlinks if ent in (a, b)]
            destent += [(a, b) for (a, b) in cononeways if ent == a]
            assert len(destent) == 1
            destent = destent[0]
            destent = [d for d in destent if d != ent][0]
            destclust = [c for c in conclusters
                         if destent in c.entrances]
            assert len(destclust) == 1
            destclust = destclust[0]
            newdestlocid = locexchange[(destclust.locid, destclust.clusterid)]
            if destent.location.locid >= 1000:
                destloc = get_location(413)
                destent = [d for d in destloc.entrances if d.entid == 3][0]
            else:
                destloc = get_location(destent.location.locid)
                destent = [d for d in destloc.entrances
                           if d.entid == destent.entid][0]
            mirror = destent.mirror
            if mirror:
                dest = mirror.dest & 0xFE00
                destx, desty = mirror.destx, mirror.desty
                if abs(destx - destent.x) + abs(desty - destent.y) > 3:
                    mirror = None

            if not mirror:
                dest, destx, desty = 0x2000, destent.x, destent.y
            dest &= 0x3DFF

            dest |= newdestlocid
            entrance = Entrance()
            entrance.x, entrance.y = ent.x, ent.y
            entrance.dest, entrance.destx, entrance.desty = dest, destx, desty
            entrance.set_location(newlocation)
            newlocation.entrance_set.entrances.append(entrance)

        newlocation.setid = 0
        newlocation.ancient_rank = 0
        newlocation.copied = copylocid

        adjents = []
        for ent in newlocation.entrances:
            for clust in locclusters:
                if isinstance(clust, RestStop):
                    continue
                assert clust.locid == newlocation.copied
                if clust.has_adjacent_entrances:
                    x, y = ent.x, ent.y
                    for ent2 in clust.entgroups.keys():
                        if ent2.x == ent.x and ent2.y == ent.y:
                            break
                    else:
                        continue
                    entgroup = clust.entgroups[ent2]
                    for ent3 in entgroup:
                        x3, y3 = ent3.x, ent3.y
                        if x == x3 and y == y3:
                            continue
                        entrance = Entrance()
                        entrance.x, entrance.y = x3, y3
                        entrance.dest, entrance.destx, entrance.desty = (
                            ent.dest, ent.destx, ent.desty)
                        entrance.set_location(newlocation)
                        adjents.append(entrance)
        newlocation.entrance_set.entrances.extend(adjents)

        newlocations.append(newlocation)

    locations = get_locations()
    newlocids = [l.locid for l in newlocations]
    assert len(newlocids) == len(set(newlocids))
    for location in newlocations:
        for e in location.entrances:
            if (location.locid, e.entid) not in FIXED_ENTRANCES:
                assert e.dest & 0x1FF in newlocids
        assert location not in locations
        if location.locid not in towerlocids:
            location.entrance_set.convert_longs()

    # XXX: Unnecessary???
    for i, loc in enumerate(newlocations):
        if loc.locid in towerlocids:
            oldloc = get_location(loc.locid)
            oldloc.entrance_set.entrances = loc.entrances
            oldloc.ancient_rank = loc.ancient_rank
            oldloc.copied = oldloc.locid
            newlocations[i] = oldloc

    ranked_clusters = []
    for n in range(len(routes[0].segments)):
        rankedcsets = [route.segments[n].ranked_clusters for route in routes]
        for tricluster in zip_longest(*rankedcsets, fillvalue=None):
            tricluster = list(tricluster)
            random.shuffle(tricluster)
            for cluster in tricluster:
                if cluster is None:
                    continue
                if cluster.locid not in ranked_clusters:
                    cluster.routerank = n
                    ranked_clusters.append(cluster)

    ranked_locations = []
    for cluster in ranked_clusters:
        locid, clusterid = cluster.locid, cluster.clusterid
        newlocid = locexchange[locid, clusterid]
        newloc = [l for l in newlocations if l.locid == newlocid][0]
        if newloc not in ranked_locations:
            newloc.routerank = cluster.routerank
            ranked_locations.append(newloc)
    assert len(set(ranked_locations)) == len(set(newlocations))

    ranked_locations = [l for l in ranked_locations
                        if not hasattr(l, "restrank")]
    for i, loc in enumerate(ranked_locations):
        loc.ancient_rank = i
        loc.make_tower_basic()
        if not ANCIENT:
            if loc.locid not in towerlocids:
                loc.make_tower_flair()
                from options import options_
                loc.unlock_chests(200, 1000, uncapped_monsters=options_.is_code_active('bsiab'))
                fsets = get_new_fsets("kefka's tower", 20)
                fset = random.choice(fsets)
                for formation in fset.formations:
                    formation.set_music(6)
                    formation.set_continuous_music()
                loc.setid = fset.setid

    switch292, gate292 = (292, 0), (292, 1)
    switch334, gate334 = (334, 5), (334, 3)
    swd = {switch292: None,
           switch334: None,
           gate292: None,
           gate334: None}
    segments = [s for route in routes for s in route.segments]
    for segment in segments:
        for cluster in segment.ranked_clusters:
            for key in list(swd.keys()):
                locid, entid = key
                if cluster.locid == locid and entid in cluster.entids:
                    assert swd[key] is None
                    swd[key] = (segment, cluster)
    assert None not in list(swd.values())

    s292segment, s292cluster = swd[switch292]
    s334segment, s334cluster = swd[switch334]
    g292segment, g292cluster = swd[gate292]
    g334segment, g334cluster = swd[gate334]
    if s292segment == g334segment and s334segment == g292segment:
        assert s292segment != s334segment
        ranked292 = s292segment.ranked_clusters
        ranked334 = s334segment.ranked_clusters
        if (ranked292.index(s292cluster) > ranked292.index(g334cluster) and
                ranked334.index(s334cluster) > ranked334.index(g292cluster)):
            raise Exception("Dungeon cannot be completed with this layout.")

    return newlocations, unused_maps


class Cluster:
    def __init__(self, locid, clusterid):
        self.locid = locid
        self.clusterid = clusterid
        self.entrances = []

    @property
    def singleton(self):
        return len(self.entrances) == 1

    @property
    def has_adjacent_entrances(self):
        if hasattr(self, "_has_adjacent_entrances"):
            return self._has_adjacent_entrances

        for e1 in self.entrances:
            for e2 in self.entrances:
                if e1 == e2:
                    continue
                if e1.x == e2.x and e1.y == e2.y:
                    raise Exception("ERROR: Overlapping entrances")
                if ((e1.x == e2.x and abs(e1.y - e2.y) == 1) or
                        (abs(e1.x - e2.x) == 1 and e1.y == e2.y)):
                    self._has_adjacent_entrances = True
                    return self.has_adjacent_entrances
        self._has_adjacent_entrances = False
        return self.has_adjacent_entrances

    def remove_adjacent_entrances(self):
        if not self.has_adjacent_entrances:
            return

        self.entgroups = {}
        for e in self.entrances:
            self.entgroups[e] = set([e])
        for e1 in self.entrances:
            for e2 in self.entrances:
                if e1 == e2:
                    continue
                if ((e1.x == e2.x and abs(e1.y - e2.y) == 1) or
                        (abs(e1.x - e2.x) == 1 and e1.y == e2.y)):
                    self.entgroups[e1].add(e2)

        for e1 in self.entgroups:
            for e2 in self.entgroups[e1]:
                assert self.entgroups[e1] == self.entgroups[e2]

        entgroups = []
        keys = sorted(list(self.entgroups.keys()), key=lambda k: k.entid)
        entids = [k.entid for k in keys]
        assert len(entids) == len(set(entids))
        for key in keys:
            entgroup = self.entgroups[key]
            if entgroup not in entgroups:
                entgroups.append(entgroup)

        for eg1 in entgroups:
            for eg2 in entgroups:
                if eg1 == eg2:
                    continue
                assert eg1 & eg2 == set([])

        for entgroup in entgroups:
            if len(entgroup) > 1:
                entgroup = sorted(entgroup, key=lambda e: e.entid)
                ent = random.choice(entgroup)
                for e in entgroup:
                    if e != ent:
                        self.entrances.remove(e)

        assert self.has_adjacent_entrances

    def add_entrance(self, entrance):
        e = Entrance()
        e.copy(entrance)
        self.entrances.append(e)

    @property
    def entids(self):
        return [e.entid for e in self.entrances]

    @property
    def free_entrances(self):
        free = [e for e in self.entrances if (e.location.locid, e.entid) not in
                FIXED_ENTRANCES + REMOVE_ENTRANCES]
        return free

    def __repr__(self):
        display = "; ".join([str(e) for e in self.entrances])
        display = "%s %s" % (self.clusterid, display)
        return display


class RestStop(Cluster):
    counter = 0

    def __init__(self, rank):
        self.rank = rank
        e = Entrance()
        e.location = Location(1000 + RestStop.counter, dummy=True)
        self.locid = e.location.locid
        self.clusterid = self.locid
        e.x, e.y = 48, 21
        e.dest, e.destx, e.desty = 0, 0, 0
        e.entid = None
        self.entrances = [e]
        RestStop.counter += 1

    def __repr__(self):
        return "Rest stop rank %s" % self.rank


def get_clusters():
    global clusters
    if clusters is not None:
        return clusters

    clusters = []
    for i, line in enumerate(open(ENTRANCE_REACHABILITY_TABLE)):
        locid, entids = line.strip().split(':')
        locid = int(locid)
        entids = list(map(int, entids.split(',')))
        loc = get_location(locid)
        entrances = [e for e in loc.entrances if e.entid in entids]
        c = Cluster(locid=locid, clusterid=i)
        for e in entrances:
            c.add_entrance(e)
        c.original_entrances = list(c.entrances)
        clusters.append(c)

    return get_clusters()


def get_cluster(locid, entid):
    for c in get_clusters():
        if c.locid == locid and entid in c.entids:
            return c
    return None

class Segment:
    def __init__(self, checkpoints):
        self.clusters = []
        self.entids = []
        for locid, entid in checkpoints:
            if locid == "R":
                c = RestStop(rank=entid)
                self.clusters.append(c)
                self.entids.append(None)
            else:
                c = get_cluster(locid, entid)
                assert c is not None
                self.clusters.append(c)
                self.entids.append(entid)
            c.exiting, c.entering = False, False
        self.intersegments = [InterSegment() for c in self.clusters[:-1]]
        self.original_clusters = list(self.clusters)
        self.oneway_entrances = []

    @property
    def ranked_clusters(self):
        startclust = self.clusters[0]
        done = set([startclust])
        ranked = []
        if startclust not in ranked:
            ranked.append(startclust)
        while True:
            ents = [e for c in done for e in c.entrances]
            relevant_links = [(a, b) for (a, b) in self.consolidated_links
                              if a in ents or b in ents]
            new_ents = set([])
            for a, b in relevant_links:
                if a not in ents:
                    new_ents.add(a)
                if b not in ents:
                    new_ents.add(b)
            if not new_ents:
                break
            newclusts = [c for c in self.consolidated_clusters
                         if set(c.entrances) & new_ents]
            done |= set(newclusts)
            newclusts = sorted(newclusts, key=lambda c: c.clusterid)
            random.shuffle(newclusts)
            for c in newclusts:
                if c not in ranked:
                    ranked.append(c)

        if set(self.consolidated_clusters) != set(ranked):
            import pdb
            pdb.set_trace()
        return ranked

    @property
    def consolidated_links(self):
        links = list(self.links)
        for inter in self.intersegments:
            links.extend(inter.links)
        links = sorted(links, key=lambda e__: (e__[0].location.locid, e__[0].entid))
        return links

    @property
    def consolidated_clusters(self):
        clusters = list(self.clusters)
        for inter in self.intersegments:
            clusters.extend(inter.clusters)
        return clusters

    @property
    def consolidated_entrances(self):
        links = self.consolidated_links
        linked_entrances = []
        for a, b in links:
            linked_entrances.append(a)
            linked_entrances.append(b)
        for e, _ in self.oneway_entrances:
            linked_entrances.append(e)
        return linked_entrances

    def check_links(self):
        linked_entrances = self.consolidated_entrances
        assert len(linked_entrances) == len(set(linked_entrances))

    def interconnect(self):
        links = []
        for segment in self.intersegments:
            segment.interconnect()
        for i, (a, b) in enumerate(zip(self.clusters, self.clusters[1:])):
            aid = self.entids[i]
            bid = self.entids[i+1]
            if a.singleton:
                acands = a.entrances
            elif i == 0:
                acands = [e for e in a.entrances if e.entid == aid]
            else:
                acands = [e for e in a.entrances if e.entid != aid]
            aent = random.choice(acands)
            bcands = [e for e in b.entrances if e.entid == bid]
            bent = bcands[0]
            inter = self.intersegments[i]
            if a.singleton:
                previnter = self.intersegments[i-1] if i > 0 else None
                thresh = 3
                for j in range(thresh):
                    k = thresh-j
                    intercands = []
                    excands = inter.get_external_candidates(num=k, test=True)
                    if excands:
                        intercands.append(inter)
                    k = max(1, k-1)
                    if previnter is not None:
                        excands = previnter.get_external_candidates(num=k,
                                                                    test=True)
                        if excands:
                            intercands.append(previnter)
                    if intercands:
                        break
                else:
                    raise Exception("No available intersegments.")
                chosen = random.choice(intercands)
                excands = (chosen.get_external_candidates(num=1))
                if excands is None:
                    raise Exception("Routing error.")
                links.append((aent, excands[0]))
                a.entering, a.exiting = True, True

                if previnter and not previnter.empty:
                    # TODO: Sometimes this fails
                    for j in range(i, len(self.intersegments)):
                        nextinter = self.intersegments[j]
                        if nextinter.empty:
                            continue
                        c = previnter.get_external_candidates(num=1)[0]
                        d = nextinter.get_external_candidates(num=1)[0]
                        links.append((c, d))
                        break
                    else:
                        raise Exception("No exit segment available.")
            elif not inter.empty:
                if not b.singleton:
                    excands = inter.get_external_candidates(num=2)
                    if excands is None:
                        raise Exception("No exit segment available. (2)")
                    random.shuffle(excands)
                    links.append((bent, excands[1]))
                    b.entering = True
                else:
                    excands = inter.get_external_candidates(num=1)
                links.append((aent, excands[0]))
                a.exiting = True
            elif (inter.empty and not b.singleton):
                links.append((aent, bent))
                a.exiting = True
                b.entering = True
            elif (inter.empty and b.singleton):
                inter2 = self.intersegments[i+1]
                assert not inter2.empty
                excands = inter2.get_external_candidates(num=1)
                links.append((aent, excands[0]))
                a.exiting = True
            else:
                import pdb
                pdb.set_trace()
                assert False

        for i, a in enumerate(self.clusters):
            aid = self.entids[i]
            if not (a.entering or i == 0):
                if a.singleton:
                    aent = a.entrances[0]
                else:
                    acands = [e for e in a.entrances if e.entid == aid]
                    aent = acands[0]
                while i > 0:
                    inter = self.intersegments[i-1]
                    if not inter.empty:
                        break
                    i += -1
                if inter.empty:
                    raise Exception("Routing error.")
                excands = inter.get_external_candidates(num=1)
                links.append((aent, excands[0]))
                a.entering = True

        self.links = links
        self.check_links()

    def fill_out(self):
        entrances = list(self.consolidated_entrances)
        seen = []
        for cluster, inter in zip(self.clusters, self.intersegments):
            if cluster.locid == 334 and 11 in cluster.entids:
                additionals = [e for e in cluster.entrances
                               if e not in self.consolidated_entrances]
                assert len(additionals) == 1
                extra = inter.fill_out(additionals[0])
            else:
                extra = inter.fill_out()
            seen.extend([e for e in cluster.entrances if e in entrances])
            for c in inter.clusters:
                seen.extend([e for e in c.entrances if e in entrances])
            if extra is not None:
                backtrack = random.choice(seen)
                self.oneway_entrances.append((extra, backtrack))

    def add_cluster(self, cluster, need=False):
        self.entids.append(None)
        self.clusters.append(cluster)
        if need:
            self.need -= len(cluster.entrances) - 2

    @property
    def free_entrances(self):
        free = []
        for (entid, cluster) in zip(self.entids, self.clusters):
            if entid is not None:
                clustfree = cluster.free_entrances
                clustfree = [e for e in clustfree if e.entid != entid]
                free.extend(clustfree)
        return free

    @property
    def reserved_entrances(self):
        free = self.free_entrances
        reserved = []
        for cluster in self.clusters:
            if isinstance(cluster, Cluster):
                reserved.extend([e for e in cluster.entrances
                                 if e not in free])
        return reserved

    def determine_need(self):
        for segment in self.intersegments:
            segment.need = 0
        for index, cluster in enumerate(self.clusters):
            if len(cluster.entrances) == 1:
                indexes = [i for i in [index-1, index]
                           if 0 <= i < len(self.intersegments)]
                for i in indexes:
                    self.intersegments[i].need += 1

    def __repr__(self):
        display = ""
        for i, cluster in enumerate(self.clusters):
            entid = self.entids[i]
            if entid is None:
                entid = '?'
            display += "%s %s\n" % (entid, cluster)
            if not isinstance(self, InterSegment):
                if i < len(self.intersegments):
                    display += str(self.intersegments[i]) + "\n"
        display = display.strip()
        if not display:
            display = "."
        if not isinstance(self, InterSegment):
            display += "\nCONNECT %s" % self.consolidated_links
            display += "\nONE-WAY %s" % self.oneway_entrances
        return display


class InterSegment(Segment):
    def __init__(self):
        self.clusters = []
        self.entids = []
        self.links = []
        self.linked_edge = []

    @property
    def empty(self):
        return len(self.clusters) == 0

    @property
    def linked_entrances(self):
        linked = []
        for a, b in self.links:
            linked.append(a)
            linked.append(b)
        for e in self.linked_edge:
            linked.append(e)
        return linked

    def get_entrance_cluster(self, entrance):
        for c in self.clusters:
            if entrance in c.entrances:
                return c
        raise Exception("Could not find related cluster.")

    def calculate_distance(self, a, b):
        reachable = [a]
        done = []
        for i in range(20):
            for r in reachable:
                for c, d in self.links:
                    if c in done or d in done:
                        continue
                    dest = None
                    if c in r.entrances:
                        dest = self.get_entrance_cluster(d)
                    if d in r.entrances:
                        assert dest is None
                        dest = self.get_entrance_cluster(c)
                    if dest == b:
                        return i
                    if dest is not None and dest not in reachable:
                        reachable.append(dest)
        raise Exception("Clusters not connected.")

    def get_max_edge_distance(self, clusters):
        if len(clusters) == 1:
            return random.choice(clusters)
        if not self.linked_edge:
            if len(clusters) == 2:
                return random.choice(clusters)
            linked = [random.choice(clusters)]
            clusters = [c for c in clusters if c not in linked]
        else:
            linked = [self.get_entrance_cluster(e)
                      for e in self.linked_edge]
        scores = {}
        for c in clusters:
            scores[c] = 9999
            for l in linked:
                d = self.calculate_distance(c, l)
                scores[c] = min(d, scores[c])
        hiscore = max(scores.values())
        assert hiscore < 999
        clusters = [c for c in clusters if scores[c] == hiscore]
        return random.choice(clusters)

    def get_external_candidates(self, num=2, test=False):
        if not self.clusters:
            return None
        candidates = []
        linked_clusters = []
        for e in self.linked_entrances:
            for c in self.clusters:
                if e in c.entrances:
                    linked_clusters.append(c)
        done_clusts = set([])
        done_ents = set(self.linked_entrances)

        for _ in range(num):
            candclusts = [c for c in self.clusters
                          if set(c.entrances)-done_ents]
            tempclusts = [c for c in candclusts if c not in done_clusts]
            if tempclusts:
                candclusts = tempclusts
            tempclusts = [c for c in candclusts if
                          not set(c.entrances) & set(self.linked_edge)]
            if tempclusts:
                candclusts = tempclusts
            try:
                #chosen = self.get_max_edge_distance(candclusts)
                chosen = random.choice(candclusts)
            except IndexError:
                return None
            done_clusts.add(chosen)
            choices = [c for c in chosen.entrances if c not in done_ents]
            chosen = random.choice(choices)
            done_ents.add(chosen)
            candidates.append(chosen)
        if not test:
            self.linked_edge.extend(candidates)
        return candidates

    def interconnect(self):
        self.links = []
        if len(self.clusters) < 2:
            return

        starter = max(self.clusters, key=lambda c: len(c.entrances))
        while True:
            links = []
            done_ents = set([])
            done_clusts = [starter]
            clusters = self.clusters
            random.shuffle(clusters)
            for c in clusters:
                if c in done_clusts:
                    continue
                prelim = max(done_clusts,
                             key=lambda c2: len(set(c2.entrances)-done_ents))
                numents = len(set(prelim.entrances) - done_ents)
                if numents == 0:
                    break
                candidates = [c2 for c2 in done_clusts if
                              len(set(c2.entrances)-done_ents) == numents]
                chosen = random.choice(candidates)
                acands = [e for e in c.entrances if e not in done_ents]
                bcands = [e for e in chosen.entrances if e not in done_ents]
                a, b = random.choice(acands), random.choice(bcands)
                if c not in done_clusts:
                    done_clusts.append(c)
                done_ents.add(a)
                done_ents.add(b)
                links.append((a, b))
            if set(done_clusts) == set(self.clusters):
                break
        self.links = links

    def fill_out(self, additional=None):
        linked = self.linked_entrances
        links = []
        unlinked = []
        for cluster in self.clusters:
            entrances = [e for e in cluster.entrances if e not in linked]
            random.shuffle(entrances)
            if ANCIENT:
                unlinked.extend(entrances)
            else:
                if len(cluster.entrances) <= 4:
                    unlinked.extend(entrances)
                else:
                    diff = len(cluster.entrances) - len(entrances)
                    if diff < 3:
                        remaining = 3 - diff
                        unlinked.extend(entrances[:remaining])

        if additional:
            unlinked.append(additional)

        if not unlinked:
            return
        random.shuffle(unlinked)

        locids = [e.location.locid for e in unlinked]
        maxlocid = max(locids, key=locids.count)
        mosts = [e for e in unlinked if e.location.locid == maxlocid]
        lesses = [e for e in unlinked if e not in mosts]
        for m in mosts:
            if not lesses:
                break
            l = random.choice(lesses)
            links.append((m, l))
            lesses.remove(l)
            unlinked.remove(l)
            unlinked.remove(m)

        extra = None
        while unlinked:
            if len(unlinked) == 1:
                extra = unlinked[0]
                break
            u1 = unlinked.pop()
            u2 = unlinked.pop()
            links.append((u1, u2))

        self.links += links
        return extra


class Route:
    def __init__(self, segments):
        self.segments = segments

    @property
    def ranked_clusters(self):
        ranked = []
        for s in self.segments:
            ranked.extend(s.ranked_clusters)
        return ranked

    def determine_need(self):
        for segment in self.segments:
            segment.determine_need()

    @property
    def consolidated_oneways(self):
        consolidated = []
        for segment in self.segments:
            consolidated.extend(segment.oneway_entrances)
        return consolidated

    @property
    def consolidated_clusters(self):
        consolidated = []
        for segment in self.segments:
            consolidated.extend(segment.consolidated_clusters)
        return consolidated

    @property
    def reststops(self):
        return [c for c in self.consolidated_clusters if c.locid >= 1000]

    @property
    def consolidated_links(self):
        consolidated = []
        for segment in self.segments:
            consolidated.extend(segment.consolidated_links)
        return consolidated

    @property
    def consolidated_entrances(self):
        consolidated = []
        for segment in self.segments:
            consolidated.extend(segment.consolidated_entrances)
        return consolidated

    def check_links(self, links=None):
        for segment in self.segments:
            segment.check_links()
        linked = []
        for a, b in self.consolidated_links:
            linked.append(a)
            linked.append(b)
        assert len(linked) == len(set(linked))

    def claim_reststops(self):
        entid = min(self.consolidated_clusters[0].entids)
        ent_to_party = {0: 1, 8: 2, 11: 3}
        party_id = ent_to_party[entid]
        for c in self.reststops:
            loc = get_location(locexchange[c.locid, c.locid])
            loc.party_id = party_id

    def __repr__(self):
        display = "\n---\n".join([str(s) for s in self.segments])

        return display


def parse_checkpoints():
    if ANCIENT:
        checkpoints = ANCIENT_CHECKPOINTS_TABLE
    else:
        checkpoints = TOWER_CHECKPOINTS_TABLE

    def ent_text_to_ints(room, single=False):
        locid, entids = room.split(':')
        locid = int(locid)
        if '|' in entids:
            entids = entids.split('|')
        elif ',' in entids:
            entids = entids.split(',')
        elif '>' in entids:
            entids = entids.split('>')[:1]
        else:
            entids = [entids]
        entids = list(map(int, entids))
        if single:
            assert len(entids) == 1
            entids = entids[0]
        return locid, entids

    done, fixed, remove, oneway = [], [], [], []
    routes = [list([]) for _ in range(3)]
    for line in open(checkpoints):
        line = line.strip()
        if not line or line[0] == '#':
            continue
        if line[0] == 'R':
            rank = int(line[1:])
            for route in routes:
                route[-1].append(("R", rank))
        elif line[0] == '&':
            locid, entids = ent_text_to_ints(line[1:])
            for e in entids:
                fixed.append((locid, e))
        elif line[0] == '-':
            locid, entids = ent_text_to_ints(line[1:])
            for e in entids:
                remove.append((locid, e))
        elif '>>' in line:
            line = line.split('>>')
            line = [ent_text_to_ints(s, single=True) for s in line]
            first, second = tuple(line)
            oneway.append((first, second))
        else:
            if line.startswith("!"):
                line = line.strip("!")
                for route in routes:
                    route.append([])
            elif line.startswith("$"):
                line = line.strip("$")
                for route in routes:
                    subroute = route[-1]
                    head, tail = subroute[0], subroute[1:]
                    random.shuffle(tail)
                    route[-1] = [head] + tail
            else:
                random.shuffle(routes)
            rooms = line.split(',')
            chosenrooms = []
            for room in rooms:
                locid, entids = ent_text_to_ints(room)
                candidates = [(locid, entid) for entid in entids]
                candidates = [c for c in candidates if c not in done]
                chosen = random.choice(candidates)
                chosenrooms.append(chosen)
                done.append(chosen)
            for room, route in zip(chosenrooms, routes):
                route[-1].append(room)

    for first, second in oneway:
        done = False
        for route in routes:
            for subroute in route:
                if first in subroute:
                    index = subroute.index(first)
                    index = random.randint(1, index+1)
                    subroute.insert(index, second)
                    done = True
        if not done:
            raise Exception("Unknown oneway rule")

    for route in routes:
        for i, _ in enumerate(route):
            route[i] = Segment(route[i])

    for index, _ in enumerate(routes):
        routes[index] = Route(routes[index])

    FIXED_ENTRANCES.extend(fixed)
    REMOVE_ENTRANCES.extend(remove)
    return routes


def assign_maps(routes, nummaps=None):
    clusters = get_clusters()
    new_clusters = clusters
    for route in routes:
        for segment in route.segments:
            for cluster in segment.clusters:
                if cluster in new_clusters:
                    new_clusters.remove(cluster)

    for c in new_clusters:
        c.remove_adjacent_entrances()

    similars = []

    def is_too_similar(c):
        if c.locid in towerlocids:
            return False
        if len(c.entrances) == 1:
            return False
        loc = get_location(c.locid)
        layer1 = loc.layer1ptr
        palette = loc.palette_index
        entxys = {(e.x, e.y) for e in c.entrances}
        for l, p, xys in similars:
            if layer1 == l and palette == p:
                if xys & entxys:
                    return True
        similars.append((layer1, palette, entxys))
        return False

    # first phase - bare minimum
    max_new_maps = nummaps
    best_clusters = [c for c in new_clusters if len(c.entrances) >= 3]
    while True:
        random.shuffle(best_clusters)
        done_maps, done_clusters = set([]), set([])
        for cluster in best_clusters:
            location = get_location(cluster.locid)
            if (cluster.locid not in towerlocids and not location.chests
                    and random.choice([True, False])):
                continue
            if cluster.locid in done_maps:
                continue
            chosen = None
            for route in routes:
                for segment in route.segments:
                    for inter in segment.intersegments:
                        if chosen is None or chosen.need < inter.need:
                            chosen = inter
            if chosen.need > 0:
                if is_too_similar(cluster):
                    continue
                chosen.add_cluster(cluster, need=True)
                done_maps.add(cluster.locid)
                done_clusters.add(cluster.clusterid)
        if len(done_maps) <= max_new_maps:
            break
        else:
            for route in routes:
                for segment in route.segments:
                    segment.intersegments = [InterSegment()
                                             for _ in segment.intersegments]

    # second phase -supplementary
    random.shuffle(new_clusters)
    for cluster in new_clusters:
        CAPACITY_RATIO = len(done_maps) / float(max_new_maps)
        if cluster.clusterid in done_clusters:
            continue
        if cluster.locid in done_maps and not ANCIENT:
            continue
        if cluster.locid not in towerlocids:
            if (cluster.locid not in done_maps
                    and len(done_maps) >= max_new_maps):
                continue
            if (cluster.locid in done_maps and len(done_maps) >= max_new_maps
                    and get_location(cluster.locid).longentrances):
                continue
        rank = None
        if cluster.locid in done_maps or cluster.locid in towerlocids:
            for route in routes:
                for segment in route.segments:
                    for c1 in segment.clusters:
                        if c1.locid == cluster.locid:
                            temp = route.segments.index(segment)
                            if rank is None:
                                rank = temp
                            else:
                                rank = min(rank, temp)
                    for inter in segment.intersegments:
                        for c2 in inter.clusters:
                            if c2.locid == cluster.locid:
                                temp = route.segments.index(segment)
                                if rank is None:
                                    rank = temp
                                else:
                                    rank = min(rank, temp)
        location = get_location(cluster.locid)
        if (cluster.locid not in towerlocids and CAPACITY_RATIO > 0.2
                and len(cluster.entrances) <= 2 and not location.chests
                and random.choice([True, False])):
            continue
        if len(cluster.entrances) == 1:
            candidates = []
            for route in routes:
                for (i, segment) in enumerate(route.segments):
                    if rank is not None and i != rank:
                        continue
                    for inter in segment.intersegments:
                        if inter.need < 0:
                            candidates.append(inter)
            if candidates:
                if is_too_similar(cluster):
                    continue
                chosen = random.choice(candidates)
                chosen.add_cluster(cluster, need=True)
                done_maps.add(cluster.locid)
                done_clusters.add(cluster.clusterid)
        elif len(cluster.entrances) >= 2:
            if cluster.locid not in towerlocids:
                if (CAPACITY_RATIO > 0.5 and not location.chests
                        and random.randint(1, 3) == 3):
                    continue
                if is_too_similar(cluster):
                    continue
            route = random.choice(routes)
            if rank is not None:
                segment = route.segments[rank]
            else:
                segment = random.choice(route.segments)
            chosen = random.choice(segment.intersegments)
            chosen.add_cluster(cluster, need=True)
            done_maps.add(cluster.locid)
            done_clusters.add(cluster.clusterid)

    for route in routes:
        for segment in route.segments:
            segment.interconnect()


def randomize_fanatics(unused_locids):
    stairs = [get_location(i) for i in [363, 359, 360, 361]]
    pitstops = [get_location(i) for i in [365, 367, 368, 369]]
    num_new_levels = random.randint(0, 1) + random.randint(1, 2)
    unused_locations = [get_location(l) for l in unused_locids]
    fsets = get_new_fsets("fanatics", 10, supplement=False)
    for _ in range(num_new_levels):
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


def randomize_tower(filename, ancient=False, nummaps=None):
    global ANCIENT
    ANCIENT = ancient
    if nummaps is None:
        nummaps = 23
    routes = parse_checkpoints()
    for route in routes:
        route.determine_need()
    assign_maps(routes, nummaps=nummaps)
    for route in routes:
        for segment in route.segments:
            segment.fill_out()
    for route in routes:
        route.check_links()

    newlocations, unused_maps = remap_maps(routes)
    mapid = unused_maps.pop()
    beltroom = [l for l in newlocations if l.locid == 287][0]
    newlocations.remove(beltroom)
    treasure_room, beltroom = make_secret_treasure_room(mapid, beltroom)
    newlocations.append(treasure_room)
    newlocations.append(beltroom)
    assert treasure_room.chests
    assert len(beltroom.entrances) == 3
    update_locations(newlocations)

    if not ANCIENT:
        randomize_fanatics(unused_maps)

    for route in routes:
        #print route
        route.claim_reststops()

    return routes


def make_secret_treasure_room(mapid, beltroom):
    from itemrandomizer import get_secret_item
    candidates = []
    for line in open(TREASURE_ROOMS_TABLE):
        locid, entid, chestid = tuple(map(int, line.strip().split(',')))
        location = get_location(locid)
        entrance = location.get_entrance(entid)
        chest = location.get_chest(chestid)
        candidates.append((location, entrance, chest))
    location, entrance, chest = random.choice(candidates)
    newlocation = Location(mapid)
    newlocation.copy(location)
    newlocation.make_tower_basic()
    newlocation.entrance_set.entrances = []
    newlocation.events = []
    newlocation.npcs = []

    c = ChestBlock(pointer=None, location=newlocation.locid)
    c.copy(chest)
    c.set_content_type(0x40)
    item = get_secret_item()
    c.contents = item.itemid
    c.set_new_id()
    c.do_not_mutate = True
    c.ignore_dummy = True
    newlocation.chests = [c]
    newlocation.secret_treasure = True
    newlocation.ancient_rank = 0

    e = Entrance(None)
    e.copy(entrance)
    e.set_location(newlocation)
    e.destx, e.desty, e.dest = 36, 27, 287
    newlocation.entrances.append(e)
    assert len(newlocation.entrances) == 1

    e2 = Entrance()
    e2.x = 36
    e2.y = 25
    e2.destx, e2.desty, e2.dest = e.x, e.y, mapid
    beltroom.entrance_set.entrances = [ent for ent in beltroom.entrances
                                       if not (ent.x == 36 and ent.y == 25)]
    beltroom.entrance_set.entrances.append(e2)

    final_room = get_location(411)
    e3 = Entrance()
    e3.x = 109
    e3.y = 46
    e3.destx, e3.desty, e3.dest = 82, 46, 412 | 0x2000
    final_room.entrance_set.entrances.append(e3)

    newlocation.attacks = 0
    newlocation.setid = 0
    newlocation.music = 21
    return newlocation, beltroom


if __name__ == "__main__":
    from randomizer import get_monsters
    get_monsters(filename="program.rom")
    get_formations(filename="program.rom")
    get_fsets(filename="program.rom")
    get_locations(filename="program.rom")

    routes = randomize_tower("program.rom", ancient=True)
    for route in routes:
        print(route)
        print()
        print()
