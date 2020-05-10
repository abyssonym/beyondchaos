import math

from dialoguemanager import set_dialogue
from formationrandomizer import get_formations, get_fsets
from itemrandomizer import get_ranked_items, get_item
from utils import read_multi, write_multi, mutate_index, utilrandom as random, Substitution


valid_ids = list(range(1, 0x200))
banned_formids = [0, 0x1d7]
extra_miabs = []
orphaned_formations = None
used_formations = []
done_items = []

appropriate_formations = None

EVENT_ENEMIES = [0x00, 0x01, 0x02, 0x06, 0x09, 0x19, 0x1a, 0x1b, 0x1c, 0x22, 0x24,
                 0x33, 0x38, 0x39, 0x3a, 0x3f, 0x42, 0x43, 0x4f, 0x50, 0x59, 0x60,
                 0x5e, 0x64, 0x65, 0x73, 0x79, 0x7f, 0x9f, 0xaf, 0xb6, 0xcf, 0xd1,
                 0xde, 0xe3]

# Adding to event enemies increases the probability of early hard miabs significantly
# without level limits, so put it back like it used to be.
OLD_EVENT_ENEMIES = [0x00, 0x01, 0x02, 0x09, 0x19, 0x1b, 0x22, 0x24, 0x33, 0x38,
                     0x39, 0x3a, 0x42, 0x43, 0x50, 0x59, 0x5e, 0x64, 0x73, 0x7f,
                     0xd1, 0xe3]

def add_orphaned_formation(formation):
    global orphaned_formations
    orphaned_formations.append(formation)


def get_orphaned_formations(old_version=False):
    global orphaned_formations
    if orphaned_formations is not None:
        return orphaned_formations

    orphaned_formations = set([])
    from monsterrandomizer import get_monsters
    monsters = get_monsters()
    extra_miabs = get_extra_miabs(0)
    event_enemies = OLD_EVENT_ENEMIES if old_version else EVENT_ENEMIES
    for m in monsters:
        if m.id in event_enemies:
            m.auxloc = "Event Battle"
            continue
        if not m.is_boss:
            location = m.determine_location()
            if "missing" in location.lower() or not location.strip():
                formations = {f for f in get_formations()
                              if m in f.present_enemies and not f.has_boss}
                formations = sorted(formations, key=lambda f: f.formid)
                try:
                    f = random.choice(formations)
                    orphaned_formations.add(f)
                except IndexError:
                    pass
            for x in extra_miabs:
                if m in x.present_enemies:
                    if x == f:
                        continue
                    ens = set(x.present_enemies)
                    if len(ens) == 1:
                        banned_formids.append(x.formid)

    orphaned_formations = sorted(orphaned_formations, key=lambda f: f.formid)
    return get_orphaned_formations(old_version)


def get_appropriate_formations():
    global appropriate_formations
    if appropriate_formations is not None:
        return appropriate_formations

    from formationrandomizer import NOREPLACE_FORMATIONS
    formations = get_formations()
    formations = [f for f in formations if not f.battle_event]
    formations = [f for f in formations if f.formid not in
                  banned_formids + NOREPLACE_FORMATIONS]
    formations = [f for f in formations if len(f.present_enemies) >= 1]
    formations = [f for f in formations if 273 not in
                  [e.id for e in f.present_enemies]]
    formations = [f for f in formations
                  if all(e.display_name.strip('_') for e in f.present_enemies)]

    def get_enames(f):
        return " ".join(sorted([e.display_name for e in f.present_enemies]))

    form_enames = [get_enames(f) for f in formations]
    for f in list(formations):
        enames = get_enames(f)
        assert form_enames.count(enames) >= 1
        if form_enames.count(enames) >= 2:
            if f.get_music() == 0:
                formations.remove(f)
                form_enames.remove(enames)

    appropriate_formations = formations
    return get_appropriate_formations()


def get_2pack(formation):
    fsets = [fs for fs in get_fsets() if fs.setid >= 0x100]
    for fs in fsets:
        if fs.formations[0] == formation and fs.formations[1] == formation:
            return fs

    unused = [fs for fs in fsets if fs.unused][0]
    unused.formids = [formation.formid] * 2
    return unused


def add_extra_miab(setid):
    setid |= 0x100
    fset = [fs for fs in get_fsets() if fs.setid == setid][0]
    formation = fset.formations[0]
    if formation not in extra_miabs:
        extra_miabs.append(fset.formations[0])


def get_extra_miabs(lowest_rank):
    candidates = [f for f in extra_miabs if f.rank() >= lowest_rank and
                  f.formid not in banned_formids]
    return sorted(candidates, key=lambda f: f.rank())


def get_valid_chest_id():
    global valid_ids
    try:
        valid = valid_ids[0]
    except IndexError:
        raise Exception("Not enough chest IDs available.")
    mark_taken_id(valid)
    return valid


def mark_taken_id(taken):
    global valid_ids
    assert 1 <= taken < 0x200
    if taken in valid_ids:
        valid_ids = [i for i in valid_ids if i != taken]


def select_monster_in_a_box(rank, value, clock, guarantee_miab_treasure, enemy_limit, old_version):
    formations = get_appropriate_formations()
    formations = [f for f in formations if
                  f.get_guaranteed_drop_value() >= value * 100]
    orphaned_formations = get_orphaned_formations(old_version)
    orphaned_formations = [f for f in orphaned_formations
                           if f not in used_formations]
    extra_miabs = get_extra_miabs(0)

    normal_rank_limit = lambda rank: 9/5 * rank - 150
    special_rank_limit = lambda rank: 5/4000 * rank * rank + 7/4*rank - 300

    if guarantee_miab_treasure:
        extra_miabs = []
        orphaned_formations = []
        candidates = []
    else:
        if len(extra_miabs) > 1:
            extra_miabs = get_extra_miabs(rank)
        if orphaned_formations or extra_miabs:
            max_rank = math.inf if (clock or old_version) else normal_rank_limit(rank)
            formations = [f for f in formations if f.rank() >= rank and f.rank() < max_rank]

            if old_version:
                formations = formations[:random.randint(1, 3)]
            else:
                formations = [f for f in formations if f not in used_formations]
                formations = [f for f in formations if f.formid not in banned_formids]
                formations = formations[:random.randint(2, 6)]
            if not (clock or old_version):
                orphaned_formations = [f for f in orphaned_formations
                                       if f.rank() < normal_rank_limit(rank) and f.get_guaranteed_drop_value() >= value * 20 - 1000]
                max_extra_miab_rank = special_rank_limit(rank)
                extra_miabs = [f for f in extra_miabs if f.rank() <= max_extra_miab_rank]
        candidates = (orphaned_formations + extra_miabs)
        candidates = [c for c in candidates if c not in used_formations]
        candidates = [c for c in candidates
                      if c.formid not in banned_formids]
    candidates = sorted(set(candidates), key=lambda f: f.rank())

    if len(candidates) != 1:
        candidates += formations
    candidates = [c for c in candidates if c not in used_formations]
    candidates = [c for c in candidates
                  if c.formid not in banned_formids]

    if enemy_limit is not None:
        candidates = [f for f in candidates if f.rank() <= enemy_limit]

    rank_multiplier = 1.5
    value_divisor = 8
    while not candidates:
        max_rank = max(rank, rank_multiplier * normal_rank_limit(rank))
        min_value = value * 100/value_divisor - 1500
        orphaned_formations = get_orphaned_formations(old_version)
        orphaned_formations = [f for f in orphaned_formations
                               if f.rank() <= max_rank and f.get_guaranteed_drop_value() >= min_value / 3 - 1200]
        extra_miabs = get_extra_miabs(0)
        max_extra_miab_rank = special_rank_limit(rank)
        extra_miabs = [f for f in extra_miabs if f.rank() <= max_extra_miab_rank * rank_multiplier]
        candidates = (orphaned_formations + extra_miabs)
        candidates = [c for c in candidates if c not in used_formations]
        candidates = [c for c in candidates
                      if c.formid not in banned_formids]
        if len(candidates) != 1:
            formations = [c for c in appropriate_formations
                          if c.rank() <= max_rank and c.get_guaranteed_drop_value() >= min_value]

            formations = [c for c in formations if c not in used_formations]
            formations = [c for c in formations
                          if c.formid not in banned_formids]
            formations = formations[:4]
            candidates += formations

        rank_multiplier *= 1.25
        value_divisor *= 2
        if rank_multiplier < 5 and enemy_limit is not None:
            candidates = [f for f in candidates
                          if f.rank() <= enemy_limit]
            candidates = sorted(candidates, key=lambda f: f.rank())
            half = len(candidates) // 2
            candidates = candidates[half:]
            index = random.randint(0, half) + random.randint(0, half)
            index = min(index, len(candidates)-1)
            candidates = candidates[index:]

    candidates = sorted(candidates, key=lambda f: f.rank())
    if orphaned_formations:
        index = max(
            0, len([c for c in candidates if c.rank() <= rank])-1)
        index = mutate_index(index, len(candidates), [False, True],
                             (-3, 2), (-1, 1))
    else:
        index = 0
        index = mutate_index(index, len(candidates), [False, True],
                             (-1, 4), (-1, 1))

    chosen = candidates[index]
    for m in chosen.present_enemies:
        m.auxloc = "Monster-in-a-Box"

    banned_formids.append(chosen.formid)
    used_formations.append(chosen)
    return chosen


class ChestBlock:
    def __init__(self, pointer, location):
        self.pointer = pointer
        self.location = location
        self.value = None
        self.do_not_mutate = False
        self.ignore_dummy = False
        self.rank = None
        self.contents = None
        self.content_type = None
        self.position = None
        self.chestid = None
        self.memid = None
        self.oldid = None

    def set_id(self, chestid):
        self.chestid = chestid

    def read_data(self, filename):
        global extra_miabs

        f = open(filename, 'r+b')
        f.seek(self.pointer)
        self.position = read_multi(f, length=2)
        self.memid = ord(f.read(1))
        self.content_type = ord(f.read(1))
        self.contents = ord(f.read(1))
        f.close()
        self.oldid = self.memid | ((self.content_type & 1) << 8)

        mark_taken_id(self.effective_id)
        if self.monster:
            add_extra_miab(self.contents)

    def copy(self, other):
        self.position = other.position
        self.memid = other.memid
        self.content_type = other.content_type
        self.contents = other.contents
        self.oldid = other.oldid

    def set_rank(self, rank):
        self.rank = rank

    @property
    def empty(self):
        return self.content_type & 0x18

    @property
    def treasure(self):
        return self.content_type & 0x40

    @property
    def gold(self):
        return self.content_type & 0x80

    @property
    def monster(self):
        return self.content_type & 0x20

    @property
    def effective_id(self):
        return self.memid | ((self.content_type & 1) << 8)

    @property
    def description(self):
        if self.monster:
            from formationrandomizer import get_fset
            s = "Enemy {0:03d}: ".format(self.effective_id)
            fset = get_fset(self.contents + 0x100)
            s += fset.formations[0].description(renamed=True, simple=True)
        elif self.empty:
            s = "Empty! ({0:03d})".format(self.effective_id)
        else:
            s = "Treasure {0:03d}: ".format(self.effective_id)
            if self.gold:
                s += "%s GP" % (self.contents * 100)
            else:
                item = get_item(self.contents)
                s += item.name
        return s

    @property
    def is_clock(self):
        return self.effective_id in [2, 10, 31, 51, 61, 62, 69, 103]

    def set_content_type(self, content_type):
        if self.effective_id >= 0x100:
            self.content_type = content_type | 1
        else:
            self.content_type = content_type

    def set_new_id(self):
        nextid = get_valid_chest_id()
        if nextid >= 0x100:
            if nextid >= 0x200:
                raise Exception("Too many chests.")
            self.content_type |= 1
        else:
            self.content_type &= 0xFE
        self.memid = nextid & 0xFF

    def write_data(self, fout, nextpointer):
        fout.seek(nextpointer)
        write_multi(fout, self.position, length=2)

        if self.memid is None:
            self.set_new_id()

        # TODO: Preserve same IDs on chests like in Figaro Cave
        fout.write(bytes([self.memid]))
        fout.write(bytes([self.content_type]))
        fout.write(bytes([self.contents]))

    def get_current_value(self, guideline=None):
        if self.treasure:
            items = get_ranked_items()
            itemids = [i.itemid for i in items]
            try:
                index = itemids.index(self.contents)
                value = items[index].rank() // 100
            except ValueError:
                value = 100
        elif self.gold or self.empty:
            if self.empty:
                if guideline is not None:
                    value = guideline // 100
                else:
                    raise Exception("No guideline provided for empty chest.")
            else:
                value = self.contents
        elif self.monster:
            from formationrandomizer import get_fset
            formation = get_fset(self.contents | 0x100).formations[0]
            items = []
            for monster in formation.present_enemies:
                mitems = [i for i in monster.original_drops if i is not None]
                if mitems:
                    items.append(min(mitems, key=lambda i: i.rank()))
            if items:
                highest = max(items, key=lambda i: i.rank())
                value = highest.rank() // 100
            else:
                value = 1

        assert value < 10000
        return value

    def dummy_item(self, item):
        if self.ignore_dummy:
            return False

        if self.treasure and self.contents == item.itemid:
            self.set_content_type(0x10)
            self.contents = 0
            return True
        return False

    def mutate_contents(self, guideline=None, monster=None,
                        guarantee_miab_treasure=False, enemy_limit=None,
                        uniqueness=False, crazy_prices=False, uncapped_monsters=False):
        global used_formations, done_items

        if self.do_not_mutate and self.contents is not None:
            return

        if self.value is not None:
            value = self.value
        else:
            value = self.get_current_value(guideline=guideline)

        items = get_ranked_items()
        itemids = [i.itemid for i in items]

        if self.treasure:
            try:
                index = itemids.index(self.contents)
            except ValueError:
                index = 0
            indexed_item = items[index]
        else:
            lowpriced = [i for i in items if i.rank() <= value*100]
            if not lowpriced:
                lowpriced = items[:random.randint(1, 16)]
            index = max(0, len(lowpriced)-1)
            indexed_item = lowpriced[index]

        chance = random.randint(1, 50)
        orphaned_formations = get_orphaned_formations(uncapped_monsters)
        orphaned_formations = [f for f in orphaned_formations
                               if f not in used_formations]
        extra_miabs = get_extra_miabs(0)

        if monster is True:
            chance = 1
        elif monster is False:
            chance += 3
            chance = min(chance, 50)
        else:
            if orphaned_formations or extra_miabs:
                chance -= 2 if uncapped_monsters else 1
                chance = max(chance, 1)

        formations = get_appropriate_formations()
        formations = [f for f in formations if
                      f.get_guaranteed_drop_value() >= value * 100]
        if 1 <= chance <= 3 and (self.rank or formations):
            # monster
            self.set_content_type(0x20)

            from locationrandomizer import get_location
            rank = self.rank

            if self.is_clock or not rank:
                rank = min(formations, key=lambda f: f.rank()).rank() if formations else 0

            chosen = select_monster_in_a_box(rank=rank, value=value, clock=self.is_clock or monster is True, old_version=uncapped_monsters, guarantee_miab_treasure=guarantee_miab_treasure, enemy_limit=enemy_limit)
            chosen = get_2pack(chosen)

            # only 2-packs are allowed
            self.contents = chosen.setid & 0xFF
        elif 4 <= chance <= 5:
            # gold
            self.set_content_type(0x80)
            if crazy_prices:
                value = random.randint(10, 50)
            else:
                value = value // 2
                value += (random.randint(0, value) + random.randint(0, value))
            self.contents = min(0xFF, max(1, value))
            if self.contents == 0xFF:
                self.contents -= random.randint(0, 20) + random.randint(0, 20)
        else:
            # treasure
            self.set_content_type(0x40)
            if uniqueness and random.randint(1, 7) != 7:
                if len(done_items) >= len(items):
                    done_items = []
                temp = [i for i in items
                        if i == indexed_item or i not in done_items]
                if len(temp) > 1:
                    items = temp
                    index = items.index(indexed_item)
                    if indexed_item in done_items:
                        items.remove(indexed_item)
            index = mutate_index(index, len(items), [False, True],
                                 (-4, 2), (-2, 2))
            self.contents = items[index].itemid
            done_items.append(items[index])

        assert self.contents <= 0xFF
        self.value = value

event_mem_id = 281
multiple_event_items = []
class EventItem:
    def __init__(self, content_type, contents, pointer, cutscene_skip_pointer=None, postfix_bytes=[], monster=None, text=True, multiple=False):
        global event_mem_id
        self.content_type = content_type
        self.contents = contents
        self.pointer = pointer
        self.cutscene_skip_pointer = cutscene_skip_pointer
        self.postfix_bytes = postfix_bytes
        self.monster = False if not text else monster
        self.text = text
        self.mem_id = event_mem_id
        if multiple:
            multiple_event_items.append(self.mem_id)
        else:
            event_mem_id += 1
        self.multiple = multiple

    @property
    def description(self):
        c = ChestBlock(0x0, 0x0)
        c.memid = self.mem_id
        c.content_type = self.content_type
        c.contents = self.contents
        desc = c.description
        if self.mem_id in multiple_event_items:
            desc = "*%s" % desc
        return desc

    def mutate_contents(self, cutscene_skip=False, crazy_prices=False, no_monsters=False, uncapped_monsters=False):
        c = ChestBlock(0x0, 0x0)
        c.memid = 0
        c.content_type = self.content_type
        c.contents = self.contents

        cannot_show_text = not self.text or (cutscene_skip and self.cutscene_skip_pointer)
        monster = self.monster
        if no_monsters or cannot_show_text:
            monster = False

        c.mutate_contents(monster=monster, crazy_prices=crazy_prices, uncapped_monsters=uncapped_monsters)
        # If we can't show text, we don't want it to be GP,
        # because that event takes 3 bytes instead of 2,
        # and I'd have to rearrange or remove stuff to fit it.
        # So just make sure it's an item.
        if cannot_show_text:
            while c.content_type != 0x40:
                c.mutate_contents(monster=False, crazy_prices=crazy_prices)

        self.content_type = c.content_type
        self.contents = c.contents

    def write_data(self, fout, cutscene_skip=False):
        content_command_dict = {0x80: 0x6E, 0x40: 0x6D, 0x20: 0x6F}

        event_item_sub = Substitution()
        location = self.cutscene_skip_pointer if cutscene_skip and self.cutscene_skip_pointer else self.pointer
        event_item_sub.set_location(location)
        event_item_sub.bytestring = bytearray([])

        if self.content_type in content_command_dict:
            if not self.text or (cutscene_skip and self.cutscene_skip_pointer):
                event_item_sub.bytestring.append(0x80)
            else:
                event_item_sub.bytestring.append(content_command_dict[self.content_type])
            event_item_sub.bytestring.append(self.contents)
        else:
            event_item_sub.bytestring.extend([0xFD, 0xFD]) # Do nothing
        if not cutscene_skip or not self.cutscene_skip_pointer:
            event_item_sub.bytestring.extend(self.postfix_bytes)
        event_item_sub.write(fout)

        duplicate_dict = duplicate_event_item_skip_dict if cutscene_skip else duplicate_event_item_dict
        if self.pointer in duplicate_dict:
            prev_pointer = self.pointer
            self.pointer = duplicate_dict[self.pointer]
            self.write_data(fout)
            self.pointer = prev_pointer
        elif self.pointer == 0xCD59E:
            event_item_sub.bytestring = bytes([
                0x94, # Pause 60 frames
                0x66 if self.content_type == 0x40 else 0x67, 0xE5, 0xC6, self.contents,  # Show text 0x06E5 at bottom, no text box, with item self.contents
                0xFE]) # return
            event_item_sub.set_location(0x10CF4A)
            event_item_sub.write(fout)

            # Change Lone Wolf text to say item placeholder instead of gold hairpin
            text = ("<line>Grrrr…<line>"
                    "You’ll never get this<line>" +
                    ("“<item>”!" if self.content_type == 0x40 else "“<GP>00 GP”!"))
            set_dialogue(0x6e5, text)

            # Because it takes up more slightly space
            # move Lone Wolf talking into a subroutine
            event_item_sub.bytestring = bytes([0xB2, 0x4A, 0xCF, 0x06])
            event_item_sub.set_location(0xCD581)
            event_item_sub.write(fout)

# TODO: Maybe this should be in a text file
event_items_dict = {
    "Narshe (WoB)" : [
        EventItem(0x40, 0xF6, 0xCA00A, cutscene_skip_pointer=0xC9F87, monster=False, text=False),
        EventItem(0x40, 0xF6, 0xCA00C, cutscene_skip_pointer=0xC9F89, monster=False, text=False),
        EventItem(0x40, 0xCD, 0xCD59E, monster=False),
    ],

    "Figaro Castle":[
        EventItem(0x40, 0xAA, 0xA66B4, cutscene_skip_pointer=0xA6633, monster=False, text=False),
    ],

    "Returner's Hideout" : [
        EventItem(0x40, 0xD0, 0xAFB0B, cutscene_skip_pointer=0xAFAC9, monster=False, multiple=True),
        EventItem(0x40, 0xD1, 0xAFFD2, cutscene_skip_pointer=0xAFDE7, monster=False),
    ],

    "Mobliz (WoB)" : [
        EventItem(0x40, 0xE5, 0xC6883, monster=False),
    ],

    "Crescent Mountain" : [
        EventItem(0x40, 0xE8, 0xBC432, postfix_bytes=[0x45, 0x45, 0x45], monster=False),
    ],

    "Sealed Gate" : [
        EventItem(0x40, 0xAE, 0xB30E5, postfix_bytes=[0xD4, 0x4D, 0xFE]),
        EventItem(0x40, 0xAC, 0xB3103, postfix_bytes=[0xD4, 0x4E, 0xFE]),
        EventItem(0x40, 0xF5, 0xB3121, postfix_bytes=[0xD4, 0x4F, 0xFE]), # in vanilla: says Remedy, gives Soft. Changed to give Remedy.
        EventItem(0x80, 0x14, 0xB313F, postfix_bytes=[0xD4, 0x50, 0xFE]), # in vanilla: says 2000 GP, gives 293 GP. Changed to give 2000 GP.
    ],

    "Vector" : [
        EventItem(0x40, 0xE5, 0xC9257, monster=False),
        EventItem(0x40, 0xDF, 0xC926C, monster=False),
    ],

    "Owzer's Mansion" : [
        EventItem(0x80, 0x14, 0xB4A84, postfix_bytes=[0xD4, 0x59, 0x3A, 0xFE]), # in vanilla: says 2000 GP, gives 293 GP. Changed to give 2000 GP.
        EventItem(0x40, 0xE9, 0xB4AC4, postfix_bytes=[0xD4, 0x5A, 0x3A, 0xFE]), # in vanilla: says Potion, gives Tonic. Changed to give Potion.
        EventItem(0x40, 0xEC, 0xB4B03, postfix_bytes=[0xD4, 0x5B, 0x3A, 0xFE]), # in vanilla: says Ether, gives Tincture. Changed to give Ether.
        EventItem(0x40, 0xF4, 0xB4B42, postfix_bytes=[0xD4, 0x5C, 0x3A, 0xFE]), # in vanilla: says Remedy, gives Soft. Changed to give Remedy.
    ],

    "Doma Castle" : [
        EventItem(0x40, 0x30, 0xB99F4, monster=False, text=False),
    ],

    "Kohlingen" : [
        EventItem(0x40, 0xEA, 0xC3240, monster=False),
        EventItem(0x40, 0xF0, 0xC3242, monster=False),
        EventItem(0x40, 0xED, 0xC3244, monster=False),
        EventItem(0x40, 0xEE, 0xC3246, monster=False),
        EventItem(0x40, 0x60, 0xC3248, monster=False),
        EventItem(0x40, 0x09, 0xC324A, postfix_bytes=[0xFD, 0xFD, 0xFD], monster=False),
        ],

    "Narshe (WoR)" : [
        EventItem(0x40, 0x1B, 0xC0B67, monster=False),
        EventItem(0x40, 0x66, 0xC0B80, postfix_bytes=[0xFD, 0xD0, 0xB8, 0xFD, 0xFD], monster=False),
    ],

    "Fanatics Tower" : [
        EventItem(0x40, 0x21, 0xC5598, postfix_bytes=[0xFD, 0xFD, 0xFD], monster=False),
    ]
    }

duplicate_event_item_dict = {
    0xAFB0B : 0xAFB73,  # Gauntlet from Banon
    0xAFFD2 : 0xAF975   # Genji Glove from returner
    }

duplicate_event_item_skip_dict = {
    0xAFFD2 : 0xAF975   # Genji Glove from returner
    }

def get_event_items():
    return event_items_dict

def mutate_event_items(fout, cutscene_skip=False, crazy_prices=False, no_monsters=False, uncapped_monsters=False):
    event_item_sub = Substitution()
    event_item_sub.set_location(0x9926)
    event_item_sub.bytestring = bytes([0x8A, 0xD6, 0x99, 0xd6]) # pointer to new event commands 66 and 67
    event_item_sub.write(fout)
    event_item_sub.set_location(0x9934)
    event_item_sub.bytestring = bytes([0x13, 0xD6, 0x26, 0xD6, 0x71, 0xD6]) # pointers to new event commands 6D, 6E, and 6F
    event_item_sub.write(fout)

    event_item_sub.set_location(0xD613)
    event_item_sub.bytestring = bytes([
        # 6D : (2 bytes) Give item to party and show message "Received <Item>!"
        0xA5, 0xEB, 0x85, 0x1A, 0x8D, 0x83, 0x05, 0x20, 0xFC, 0xAC, 0x20, 0x06, 0x4D, 0xA9, 0x08, 0x85, 0xEB, 0x80, 0x59,

        # 6E (2 bytes) Give 100 * param GP to party and show message "Found <N> GP!" (It's 100 * param GP because that's what treasure chests do, but it doesn't need to be.)
        0xA5, 0xEB, 0x85, 0x1A, 0x8D, 0x02, 0x42, 0xA9, 0x64, 0x8D, 0x03, 0x42, 0xEA, 0xEA, 0xEA, 0xAC, 0x16, 0x42, 0x84, 0x22, 0x64, 0x24, 0xC2, 0x21, 0x98, 0x6D, 0x60, 0x18, 0x8D, 0x60, 0x18, 0x7B, 0xE2, 0x20, 0x6D, 0x62, 0x18, 0x8D, 0x62, 0x18, 0xC9, 0x98, 0x90, 0x13, 0xAE, 0x60, 0x18, 0xE0, 0x7F, 0x96, 0x90, 0x0B, 0xA2, 0x7F, 0x96, 0x8E, 0x60, 0x18, 0xA9, 0x98, 0x8D, 0x62, 0x18, 0x20, 0x06, 0x4D, 0x20, 0xE5, 0x02, 0xA9, 0x10, 0x85, 0xEB, 0x80, 0x0E,

        # 6F : (2 bytes) Show "Monster-in-a-box!" and start battle with formation from param
        0xA5, 0xEB, 0x85, 0x1A, 0x8D, 0x89, 0x07, 0x20, 0x06, 0x4D, 0xA9, 0x40, 0x85, 0xEB,

        # Common code used by all three functions. Finishes setting parameters to jump into action B2 (call event subroutine)
        0x64, 0xEC, 0xA9, 0x00, 0x85, 0xED, 0xA9, 0x02, 0x4C, 0xA3, 0xB1,

        # 66 : (4 bytes) Show text $AAAA with item name $BB and wait for button press
        0xA5, 0xED, 0x85, 0x1A, 0x8D, 0x83, 0x05, 0xA9, 0x01, 0x20, 0x70, 0x9B, 0x4C, 0xBC, 0xA4,

        # 67 : (4 bytes) Show text $AAAA with number $BB and wait for button press
        0xA5, 0xED, 0x85, 0x1A, 0x85, 0x22, 0x64, 0x24, 0x20, 0xE5, 0x02, 0xA9, 0x01, 0x20, 0x70, 0x9B, 0x4C, 0xBC, 0xA4,
    ])
    event_item_sub.write(fout)

    fout.seek(0xC3243)
    phoenix_events = fout.read(0x3F)
    fout.seek(0xC324F)
    fout.write(phoenix_events)

    # End some text boxes early so they don't show the item.
    early_end_texts = [
        (0x137, "I understand your unease.<line>"
                "But even as we speak, innocent lives are being lost…<page>"
                "Please. We need your abilities.<line>"
                "This relic will keep you safe."),
        (0x13e, "BANON: A lucky charm. Take it!"),
        (0x30e, "I heard…<line>"
                "In my name you send Lola many things…<page>"
                "I wish to thank you.<line>"
                "Please accept this as a token of my appreciation."),
        (0x6ce, "Took the treasure from Lone Wolf, the pickpocket!"),
        (0x752, "And this is from the Emperor himself…"),
        (0x754, "Your behavior at the banquet was impeccable. Please take this as well!")
    ]
    for index, text in early_end_texts:
        set_dialogue(index, text)

    for location in event_items_dict:
        for e in event_items_dict[location]:
            e.mutate_contents(cutscene_skip=cutscene_skip, no_monsters=no_monsters, uncapped_monsters=uncapped_monsters, crazy_prices=crazy_prices)
            e.write_data(fout, cutscene_skip=cutscene_skip)
