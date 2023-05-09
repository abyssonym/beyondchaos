import copy
from typing import Callable, Iterable, List, Tuple, TypeVar

from locationrandomizer import get_location, get_locations
from utils import Substitution, write_multi, utilrandom as random


T = TypeVar('T')

def partition(items: Iterable[T], pred: Callable[[T],bool])-> Tuple[List[T], List[T]]:
    trues = []
    falses =[]

    for i in items:
        if pred(i):
            trues.append(i)
        else:
            falses.append(i)
    return trues, falses


def activate_strange_journey(fout, sourcefile):

    _manage_strange_events(fout)
    _create_dimensional_vortex(fout, sourcefile)


def _manage_strange_events(fout):
    shadow_recruit_sub = Substitution()
    shadow_recruit_sub.set_location(0xB0A9F)
    shadow_recruit_sub.bytestring = bytes([0x42, 0x31]) # hide party member in slot 0

    shadow_recruit_sub.write(fout)
    shadow_recruit_sub.set_location(0xB0A9E)
    shadow_recruit_sub.bytestring = bytes([
        0x41, 0x31, # show party member in slot 0
        0x41, 0x11, # show object 11
        0x31 # begin queue for party member in slot 0
    ])
    shadow_recruit_sub.write(fout)

    shadow_recruit_sub.set_location(0xB0AD4)
    shadow_recruit_sub.bytestring = bytes([0xB2, 0x29, 0xFB, 0x05, 0x45]) # Call subroutine $CFFB29, refresh objects
    shadow_recruit_sub.write(fout)

    shadow_recruit_sub.set_location(0xFFB29)
    shadow_recruit_sub.bytestring = bytes([
        0xB2, 0xC1, 0xC5, 0x00, # Call subroutine $CAC5C1 (set CaseWord bit corresponding to number of characters in party)
        0xC0, 0xA3, 0x81, 0x38, 0xFB, 0x05, #If ($1E80($1A3) [$1EB4, bit 3] is set), branch to $CFFB38
        0x3D, 0x03, # Create object $03
        0x3F, 0x03, 0x01, #Assign character $03 (Actor in stot 3) to party 1
        0xFE #return
    ])
    shadow_recruit_sub.write(fout)

    # Always remove the boxes in Mobliz basement
    mobliz_box_sub = Substitution()
    mobliz_box_sub.set_location(0xC50EE)
    mobliz_box_sub.bytestring = bytes([0xC0, 0x27, 0x81, 0xB3, 0x5E, 0x00])
    mobliz_box_sub.write(fout)

    # Always show the door in Fanatics Tower level 1,
    # and don't change commands.
    fanatics_sub = Substitution()
    fanatics_sub.set_location(0xC5173)
    fanatics_sub.bytestring = bytes([0x45, 0x45, 0xC0, 0x27, 0x81, 0xB3, 0x5E, 0x00])
    fanatics_sub.write(fout)


def _create_dimensional_vortex(fout, sourcefile):
    entrancesets = [l.entrance_set for l in get_locations()]
    entrances = []
    for e in entrancesets:
        e.read_data(sourcefile)
        entrances.extend(e.entrances)

    entrances = sorted(set(entrances), key=lambda x: (x.location.locid, x.entid if (hasattr(x, "entid") and x.entid is not None) else -1))

    # Don't randomize certain entrances
    def should_be_vanilla(k):
        if ((k.location.locid == 0x1E and k.entid == 1) # leave Arvis's house
                or (k.location.locid == 0x14 and (k.entid == 10 or k.entid == 14)) # return to Arvis's house or go to the mines
                or (k.location.locid == 0x32 and k.entid == 3) # backtrack out of the mines
                or (k.location.locid == 0x2A) # backtrack out of the room with Terrato while you have Vicks and Wedge
                or (0xD7 < k.location.locid < 0xDC) # esper world
                or (k.location.locid == 0x137 or k.dest & 0x1FF == 0x137) # collapsing house
                or (k.location.locid == 0x180 and k.entid == 0) # weird out-of-bounds entrance in the sealed gate cave
                or (k.location.locid == 0x3B and k.dest & 0x1FF == 0x3A) # Figaro interior to throne room
                or (k.location.locid == 0x19A and k.dest & 0x1FF == 0x19A) # Kefka's Tower factory room (bottom level) conveyor/pipe
           ):
            return True
        return False

    entrances = [k for k in entrances if not should_be_vanilla(k)]

    # Make two entrances next to each other (like in the phantom train)
    # that go to the same place still go to the same place.
    # Also make matching entrances from different versions of maps
    # (like Vector pre/post esper attack) go to the same place
    duplicate_entrance_dict = {}
    equivalent_map_dict = {0x154:0x157, 0x155:0x157, 0xFD:0xF2}

    for i, c in enumerate(entrances):
        for d in entrances[i+1:]:
            c_locid = c.location.locid & 0x1FF
            d_locid = d.location.locid & 0x1FF
            if ((c_locid == d_locid
                 or (d_locid in equivalent_map_dict and equivalent_map_dict[d_locid] == c_locid)
                 or (c_locid in equivalent_map_dict and equivalent_map_dict[c_locid] == d_locid))
                    and (c.dest & 0x1FF) == (d.dest & 0x1FF)
                    and c.destx == d.destx and c.desty == d.desty
                    and (abs(c.x - d.x) + abs(c.y - d.y)) <= 3):
                if c_locid in equivalent_map_dict:
                    duplicate_entrance_dict[c] = d
                else:
                    if c in duplicate_entrance_dict:
                        duplicate_entrance_dict[d] = duplicate_entrance_dict[c]
                    else:
                        duplicate_entrance_dict[d] = c

    wor_locations = (
        {0x10} | set(range(0x18,0x1E)) | set(range(0x20,0x27)) | {0x2C, 0x44, 0x4A,  0x5A, 0x5B, 0x83, 0x9E} |
        set(range(0xB0, 0xB6)) | {0xBD,0xBF, 0xC4} | set(range(0x114, 0x11D)) | set(range(0x11E, 0x143)) |
        {0x144, 0x149, 0x14B} | set(range(0x14D, 0x154)) | set(range(0x14D, 0x154)) | {0x158} |
        set(range(0x160, 0x173)) | set(range(0x18C, 0x19F)))
        
    available_entrances = {copy.deepcopy(k) for k in entrances if k not in duplicate_entrance_dict}
    branching_entrances = [e for e in available_entrances if len(e.reachable_entrances) > 2]
    entrances_to_unreachable_branches = []
    for e in branching_entrances:
        loc_id = e.dest & 0x1FF
        if loc_id == 0x1FF:
            loc_id = 1 if (e.location.locid & 0x1FF) in wor_locations else 0
        entrances_to_unreachable_branches.extend([i for i in available_entrances if i.location.locid == loc_id and abs(i.x - e.destx) + abs(i.y - e.desty)])
    
    entrances_to_unreachable_branches
    start = get_location(0x1E).entrances[0]
    open_entrances = {start}
    reachable_entrances = {start}
 
    while open_entrances and available_entrances:
        e = open_entrances.pop()
        if len(open_entrances) < 4 and entrances_to_unreachable_branches:
            e2 = random.choice(entrances_to_unreachable_branches)
            entrances_to_unreachable_branches.remove(e2)
            available_entrances.remove(e2)
        else:
            e2 = available_entrances.pop()
        e.dest, e.destx, e.desty = e2.dest, e2.destx, e2.desty

        loc_id = e.dest & 0x1FF
        if loc_id == 0x1FF:
            loc_id = 1 if (e.location.locid & 0x1FF) in wor_locations else 0
        e3 = [i for i in available_entrances if i.location.locid == loc_id and abs(i.x - e.destx) + abs(i.y - e.desty)]
        
        entrances = e3[0].reachable_entrances if e3 else get_location(loc_id).entrances
        # This is overbroad
        entrances_to_unreachable_branches = [ent for ent in entrances_to_unreachable_branches if (ent.dest & 0x1FF) != loc_id]
        for r in entrances:
            if not should_be_vanilla(r) and r not in duplicate_entrance_dict and r not in reachable_entrances:
                open_entrances.add(r)
            reachable_entrances.add(r)


    assert not available_entrances

    open2 = list(copy.deepcopy(open_entrances))
    random.shuffle(open2)
    for o, o2 in zip(open_entrances, open2):
        o.dest, o.destx, o.desty = o2.dest, o2.destx, o2.desty

    for r in duplicate_entrance_dict:
        s = duplicate_entrance_dict[r]
        r.dest, r.destx, r.desty = s.dest, s.destx, s.desty

    entrancesets = entrancesets[:0x19F]
    nextpointer = 0x1FBB00 + (len(entrancesets) * 2)
    longnextpointer = 0x2DF480 + (len(entrancesets) * 2) + 2
    total = 0
    for e in entrancesets:
        total += len(e.entrances)
        nextpointer, longnextpointer = e.write_data(fout, nextpointer,
                                                    longnextpointer)
    fout.seek(e.pointer + 2)
    write_multi(fout, (nextpointer - 0x1fbb00), length=2)
    fout.seek(e.longpointer + 2)
    write_multi(fout, (longnextpointer - 0x2df480), length=2)