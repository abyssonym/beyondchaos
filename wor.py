import dataclasses

from chestrandomizer import get_event_items
from character import get_character, get_characters
from locationrandomizer import get_location, get_locations
from monsterrandomizer import change_enemy_name
from utils import (WOB_TREASURE_TABLE, WOR_ITEMS_TABLE, WOB_EVENTS_TABLE,
                   read_multi, Substitution, utilrandom as random, write_multi, get_dialogue_pointer, dialogue_to_bytes)


def dir_to_camera_moves(dir):
    x = dir[0]
    y = dir[1]
    
    left = x < 0
    down = y < 0
    if left: x = -x
    if down: y = -y
    out = []
    
    while x != 0 and y !=0:
        if x == y:
            diag = 0xA0
            if left:
                diag += 2
            if down != left:
                diag += 1
            out.append(diag)
            x -= 1
            y -= 1
        else:
            if x > y:
                diag = 0xA5
                if left:
                    diag += 4
                if down != left:
                    diag += 1
                out.append(diag)
                x -= 2
                y -= 1
            else:
                diag = 0xA4
                if left:
                    diag += 4
                if down != left:
                    diag += 3
                out.append(diag)
                x -= 1
                y -= 2

    if x == 0 and y == 0:
        return out

    if x != 0:
        dir_add = 3 if left else 1
        dist = x
    else:
        dir_add = 2 if down else 0
        dist = y
    ortho = 0x80 + (dist << 2) + dir_add
    out.append(ortho)

    return out


def recruit_mog_insert(fout, recruit_info):
    maybe_name_location = 0x304000
    maybe_name_low = maybe_name_location & 0xFF
    maybe_name_mid = (maybe_name_location >> 8) & 0xFF
    maybe_name_high = maybe_name_location >> 16
    
    name_location = 0x304010
    name_low = name_location & 0xFF
    name_mid = (name_location >> 8) & 0xFF
    name_high = name_location >> 16
    
    fout.seek(recruit_info.name_pointer)
    extra_bytes = fout.read(recruit_info.num_name_bytes)
    maybe_name_sub = Substitution()
    maybe_name_sub.set_location(maybe_name_location)
    maybe_name_sub.bytestring = bytes([
        0xC0, 0x9F, 0x02, name_low, name_mid, name_high - 0x0A,
    ]) + extra_bytes + bytes([0xFE])
    maybe_name_sub.write(fout)
    
    name_jump = Substitution()
    name_jump.set_location(recruit_info.name_pointer)
    name_jump.bytestring = bytes([0xB2, maybe_name_low, maybe_name_mid, maybe_name_high - 0x0A] + [0xFD] * (recruit_info.num_name_bytes-4))
    name_jump.write(fout)
    
    palette = get_character(0xA).palette
    name_sub = Substitution()
    name_sub.set_location(name_location)
    mog_npc = recruit_info.location_npcs[0][1] + 0x10
    hide_npcs = []
    show_npcs = []
    if recruit_info.name_camera == (0,0):
        name_camera = []
        name_camera_reverse = []
    else:
        c = dir_to_camera_moves(recruit_info.name_camera)
        d = dir_to_camera_moves((-recruit_info.name_camera[0],-recruit_info.name_camera[1]))
        name_camera = [0x38, 0x30, 0x82 + len(c), 0xC1] + c + [0xFF]
        name_camera_reverse = [0x30, 0x82 + len(d), 0xC2] + d +[0xFF, 0x39]
    for npc in recruit_info.name_npcs:
        hide_npcs +=[0x42, 0x10 + npc]
        show_npcs +=[0x41, 0x10 + npc]

    name_sub.bytestring = bytes([
        0x40, 0x0A, 0x0A, # assign mog properties to mog
        0x3D, 0x0A, # create mog
        0x37, 0x0A, 0x0A, # assign mog graphics to mog
        0x43, 0x0A, palette, # assign mog palette to mog
        0xD4, 0xEA, # Add Mog to shops/Gogo
        0x45, # refresh objects
        0x92, # pause for 30 frames
        mog_npc, 0x82, # begin queue for mog npc
        0x1F, 0xFF, # Do graphic action 1F, end
        0x94, # pause for 60 frames
        mog_npc, 0x82, # begin queue for mog npc
        0xCE, 0xFF, # Turn down for what?, end
        0x42, 0x31, # Hide party
        0x42, 0x32, # Hide party
        0x42, 0x33, # Hide party
        0x42, 0x34, # Hide party
        ] + hide_npcs +
        [0xB2, 0x0F, 0xD0, 0x00, # Darken background
        ] + name_camera +
        [0x4B, 0xE0, 0xC6, # SLAM-dancing Moogle text
        0x92, # Pause for 30 frames
        mog_npc, 0x82, # begin queue for mog npc
        0x1D, 0xFF, # do graphical action 1D, end
        0x94, # pause for 60 frames
        0x97, # fade to black
        0x5C, # Pause until fade is complete
        0x7F, 0x0A, 0x0A, # change mog's name to mog
        0x98, 0x0A, # name change screen for mog
        0x41, 0x31, # show party
        0x41, 0x32, # show party
        0x41, 0x33, # show party
        0x41, 0x34, # show party
        ] + show_npcs + recruit_info.name_extra +
        [0x45, # refresh objects
        0x96, # unfade
        0x5C, # wait until unfade is complete
        ] + name_camera_reverse +
        [0xB2, 0x15, 0xD0, 0x00, # Lighten background
        0x92, # pause for 30 frames
        0x3E, 0x0A, # Delete object 0A
        0x45, # refresh objects
    ]) + extra_bytes + bytes([0xFE])
    name_sub.write(fout)


def recruit_umaro_insert(fout, recruit_info):
    name_location = 0x304400
    name_low = name_location & 0xFF
    name_mid = (name_location >> 8) & 0xFF
    name_high = name_location >> 16
    
    fout.seek(recruit_info.name_pointer)
    extra_bytes = fout.read(recruit_info.num_name_bytes)
    
    name_jump = Substitution()
    name_jump.set_location(recruit_info.name_pointer)
    name_jump.bytestring = bytes([0xB2, name_low, name_mid,name_high - 0x0A] + [0xFD] * (recruit_info.num_name_bytes-4))
    name_jump.write(fout)
    
    palette = get_character(0xD).palette
    name_sub = Substitution()
    name_sub.set_location(name_location)
    umaro_npc = recruit_info.location_npcs[0][1] + 0x10
    hide_npcs = []
    show_npcs = []
    if recruit_info.name_camera == (0,0):
        name_camera = []
        name_camera_reverse = []
    else:
        c = dir_to_camera_moves(recruit_info.name_camera)
        d = dir_to_camera_moves((-recruit_info.name_camera[0],-recruit_info.name_camera[1]))
        name_camera = [0x38, 0x30, 0x82 + len(c), 0xC1] + c + [0xFF]
        name_camera_reverse = [0x30, 0x82 + len(d), 0xC2] + d +[0xFF, 0x39]
    for npc in recruit_info.name_npcs:
        hide_npcs +=[0x42, 0x10 + npc]
        show_npcs +=[0x41, 0x10 + npc]

    name_sub.bytestring = bytes([
        0x40, 0x0D, 0x0D, # assign umaro properties to umaro
        0x3D, 0x0D, # create umaro
        0x37, 0x0D, 0x0D, # assign umaro graphics to umaro
        0x43, 0x0D, palette, # assign umaro palette to umaro
        0xD4, 0xED, # Add umaro to shops/Gogo
        0x45, # refresh objects
        0x92, # pause for 30 frames
        umaro_npc, 0x82, # begin queue for umaro npc
        0xCE, 0xFF, # Turn down for what?, end
        0x42, 0x31, # Hide party
        0x42, 0x32, # Hide party
        0x42, 0x33, # Hide party
        0x42, 0x34, # Hide party
        ] + hide_npcs +
        [0xB2, 0x0F, 0xD0, 0x00, # Darken background
        ] + name_camera +
        [0x4B, 0xF9, 0xC5, # Admirer of bone-carvings text
        0x92, # Pause for 30 frames
        umaro_npc, 0x82, # begin queue for umaro npc
        0x16, 0xFF, # do graphical action 16, end
        0x92, # pause for 30 frames
        0x97, # fade to black
        0x5C, # Pause until fade is complete
        0x7F, 0x0D, 0x0D, # change umaro's name to umaro
        0x98, 0x0D, # name change screen for umaro
        0x41, 0x31, # show party
        0x41, 0x32, # show party
        0x41, 0x33, # show party
        0x41, 0x34, # show party
        ] + show_npcs + recruit_info.name_extra +
        [0x45, # refresh objects
        0x96, # unfade
        0x5C, # wait until unfade is complete
        ] + name_camera_reverse +
        [0xB2, 0x15, 0xD0, 0x00, # Lighten background
        0x92, # pause for 30 frames
        0x3E, 0x0D, # Delete object 0D
        0x45, # refresh objects
    ]) + extra_bytes + bytes([0xFE])
    name_sub.write(fout)


def recruit_gogo_insert(fout, recruit_info):
    name_location = 0x304800
    name_low = name_location & 0xFF
    name_mid = (name_location >> 8) & 0xFF
    name_high = name_location >> 16
    
    fout.seek(recruit_info.name_pointer)
    extra_bytes = fout.read(recruit_info.num_name_bytes)
    
    name_jump = Substitution()
    name_jump.set_location(recruit_info.name_pointer)
    name_jump.bytestring = bytes([0xB2, name_low, name_mid,name_high - 0x0A] + [0xFD] * (recruit_info.num_name_bytes-4))
    name_jump.write(fout)
    
    palette = get_character(0xD).palette
    name_sub = Substitution()
    name_sub.set_location(name_location)
    gogo_npc = recruit_info.location_npcs[0][1] + 0x10
    hide_npcs = []
    show_npcs = []
    if recruit_info.name_camera == (0,0):
        name_camera = []
        name_camera_reverse = []
    else:
        c = dir_to_camera_moves(recruit_info.name_camera)
        d = dir_to_camera_moves((-recruit_info.name_camera[0],-recruit_info.name_camera[1]))
        name_camera = [0x38, 0x30, 0x82 + len(c), 0xC1] + c + [0xFF]
        name_camera_reverse = [0x30, 0x82 + len(d), 0xC2] + d +[0xFF, 0x39]
    for npc in recruit_info.name_npcs:
        hide_npcs +=[0x42, 0x10 + npc]
        show_npcs +=[0x41, 0x10 + npc]

    name_sub.bytestring = bytes([
        gogo_npc, 0x82, # begin queue for gogo npc
        0xCE, 0xFF, # Turn down for what?, end
        0x42, 0x31, # Hide party
        0x42, 0x32, # Hide party
        0x42, 0x33, # Hide party
        0x42, 0x34, # Hide party
        ] + hide_npcs +
        [0xB2, 0x0F, 0xD0, 0x00, # Darken background
        ] + name_camera +
        [0x4B, 0x0D, 0xCA, # Shrouded in odd clothing text
        0x92, # Pause for 30 frames
        0x40, 0x0C, 0x0C, # assign gogo properties to gogo
        0x3D, 0x0C, # create gogo
        0x37, 0x0C, 0x0C, # assign gogo graphics to gogo
        0x43, 0x0C, palette, # assign gogo palette to gogo
        0xD4, 0xEC, # Add gogo to shops/Gogo
        0x7F, 0x0C, 0x0C, # change gogo's name to gogo
        0x98, 0x0C, # name change screen for gogo
        0x50, 0xBC, # tint screen
        0x59, 0x10, # unfade screen at speed $10
        0x92, # pause for 30 frames
        0xB2, 0x15, 0xD0, 0x00, # Lighten background
        0x41, 0x31, # show party
        0x41, 0x32, # show party
        0x41, 0x33, # show party
        0x41, 0x34, # show party
        ] + show_npcs + recruit_info.name_extra +
        [0x45, # refresh objects
        ] + name_camera_reverse +
        [0x93, # pause for 45 frames
        0x3E, 0x0D, # Delete object 0D
        0x45, # refresh objects
    ]) + extra_bytes + bytes([0xFE])
    name_sub.write(fout)


class WoRRecruitInfo(object):
    def __init__(self, label, event_pointers, recruited_bit_pointers, location_npcs,
                 dialogue_pointers, name_pointer, num_name_bytes,
                 shop_menu_bit_pointers=[], palette_pointers=[],
                 caseword_pointers=None, prerequisite=None, special=None,
                 name_npcs=[], name_extra=[], name_camera=(0,0)):
        self.label = label
        self.event_pointers = event_pointers
        self.recruited_bit_pointers = recruited_bit_pointers
        self.location_npcs = location_npcs
        self.dialogue_pointers = dialogue_pointers
        self.name_pointer = name_pointer
        self.num_name_bytes = num_name_bytes
        self.caseword_pointers = caseword_pointers
        self.shop_menu_bit_pointers = shop_menu_bit_pointers
        self.palette_pointers = palette_pointers
        self.prerequisite = prerequisite
        self.special = special
        self.name_npcs = name_npcs
        self.name_extra = name_extra
        self.name_camera = name_camera

    def write_data(self, fout):
        assert(self.char_id is not None)
        for event_pointer in self.event_pointers:
            fout.seek(event_pointer)
            fout.write(bytes([self.char_id]))
        for recruited_bit_pointer in self.recruited_bit_pointers:
            fout.seek(recruited_bit_pointer)
            fout.write(bytes([0xf0 + self.char_id]))
        for shop_menu_bit_pointer in self.shop_menu_bit_pointers:
            fout.seek(shop_menu_bit_pointer)
            fout.write(bytes([0xe0 + self.char_id]))
        palette = get_character(self.char_id).palette
        for palette_pointer in self.palette_pointers:
            fout.seek(palette_pointer)
            fout.write(bytes([palette]))
        for location_id, npc_id in self.location_npcs:
            location = get_location(location_id)
            npc = location.npcs[npc_id]
            npc.graphics = self.char_id
            npc.palette = get_character(self.char_id).palette
        for index, offset in self.dialogue_pointers:
            fout.seek(get_dialogue_pointer(fout, index) + offset)
            fout.write(bytes([self.char_id + 2]))
        if self.caseword_pointers:
            for location in self.caseword_pointers:
                fout.seek(location)
                byte = ord(fout.read(1))
                fout.seek(location)
                fout.write(bytes([byte & 0x0F | (self.char_id << 4)]))

        if self.special:
            self.special(fout, self.char_id)

        if self.char_id == 0xA and self.special != moogle_cave_recruit:
            recruit_mog_insert(fout, self)
        if self.char_id == 0xC and self.special not in [sasquatch_cave_recruit, moogle_cave_recruit, zoneeater_recruit]:
            recruit_gogo_insert(fout, self)
        if self.char_id == 0xD and self.special not in [sasquatch_cave_recruit, moogle_cave_recruit, zoneeater_recruit]:
            recruit_umaro_insert(fout, self)


def falcon_recruit(fout, char_id):
    falcon_recruit_sub = Substitution()
    falcon_recruit_sub.set_location(0xA5324)
    falcon_recruit_sub.bytestring = bytes([0xD5, 0xFB])
    falcon_recruit_sub.write(fout)

    falcon_recruit_sub.set_location(0xA5310 + 2 * char_id - (2 if char_id > 6 else 0))
    falcon_recruit_sub.bytestring = bytes([0xD4, 0xF0 + char_id])
    falcon_recruit_sub.write(fout)


def moogle_cave_recruit(fout, char_id):
    if char_id == 0x0A:
        return

    if char_id in [0x0C, 0x0D]:
        # Gogo and Umaro always get renamed, so jump to
        # the never-got-Mog-in-WoB part
        moogle_cave_recruit_sub = Substitution()
        moogle_cave_recruit_sub.set_location(0xC3975)
        moogle_cave_recruit_sub.bytestring = bytes([0x2F, 0x02])
        moogle_cave_recruit_sub.write(fout)
        
        moogle_cave_recruit_sub.set_location(0xC3AA0)
        if char_id == 0x0C:
            moogle_cave_recruit_sub.bytestring = bytes([0x4B, 0x0D, 0xCA]) # shrouded in odd clothing
        else :
            moogle_cave_recruit_sub.bytestring = bytes([0x4B, 0xF9, 0xC5]) # Admirer of bone-carvings text
        moogle_cave_recruit_sub.write(fout)
        return

    # Don't rename, stay in got-Mog-in-WoB part
    moogle_cave_recruit_sub = Substitution()
    moogle_cave_recruit_sub.set_location(0xC3974)
    moogle_cave_recruit_sub.bytestring = bytes([0xFD] * 7)
    moogle_cave_recruit_sub.write(fout)

    
def sasquatch_cave_recruit(fout, char_id):
    assert(char_id != 0x0A)

    umaro_name = get_character(char_id).newname
    for umaro_id in [0x10f, 0x110]:
        change_enemy_name(fout, umaro_id, umaro_name)

    if char_id == 0x0C:
        gogo_sub = Substitution()
        gogo_sub.set_location(0xCD811)
        gogo_sub.bytestring = bytes([0x4B, 0x0D, 0xCA]) # shrouded in odd clothing
        gogo_sub.write(fout)
        return

    if char_id == 0x0D:
        return
        
    # Skip over rename
    sasquatch_cave_recruit_sub = Substitution()
    sasquatch_cave_recruit_sub.set_location(0xCD7F5)
    sasquatch_cave_recruit_sub.bytestring = bytes([0xC0, 0x27, 0x01, 0x40, 0xD8, 0x02])
    sasquatch_cave_recruit_sub.write(fout)


def zoneeater_recruit(fout, char_id):
    if char_id == 0x0C:
        return

    if char_id == 0x0D:
        umaro_sub = Substitution()
        umaro_sub.set_location(0xB81D6)
        umaro_sub.bytestring = bytes([0x4B, 0xF9, 0xC5]), # Admirer of bone-carvings text
        return

    prefix = [0xFD] * 4 if char_id == 0x0A else []

    # Skip over rename
    zoneeater_recruit_sub = Substitution()
    zoneeater_recruit_sub.set_location(0xB81CF)
    zoneeater_recruit_sub.bytestring = bytes(prefix + [0x3D, char_id, 0xC0, 0x27, 0x01, 0x00, 0x82, 0x01])
    zoneeater_recruit_sub.write(fout)


def manage_wor_recruitment(fout, random_treasure, include_gau, include_gogo):
    candidates = [0x00, 0x01, 0x02, 0x05, 0x07, 0x08, 0x0A, 0x0D]
    locke_event_pointers = [0xc2c48, 0xc2c51, 0xc2c91, 0xc2c9d, 0xc2c9e, 0xc2caf, 0xc2cb8, 0xc2cc5, 0xc2cca, 0xc2cd8, 0xc2ce3, 0xc2ce9, 0xc2cee, 0xc2cf4, 0xc2cfa, 0xc2d0b, 0xc2d33, 0xc2e32, 0xc2e4a, 0xc2e80, 0xc2e86, 0xc2e8b, 0xc2e91, 0xc2ea5, 0xc2eb1, 0xc2ec4, 0xc2f0b, 0xc2fe1, 0xc3102, 0xc3106, 0xc3117, 0xc311d, 0xc3124, 0xc3134, 0xc313d, 0xc3163, 0xc3183, 0xc3185, 0xc3189, 0xc318b, 0xc318e, 0xc3191, 0xc3197, 0xc31c7, 0xc31cb, 0xc31e2, 0xc31e8, 0xc31ed, 0xc31f2, 0xc31f8, 0xc3210, 0xc3215, 0xc321d, 0xc3229, 0xc322f, 0xc3235, 0xc323b]
    locke_event_pointers_2 = [0xc3244, 0xc324a, 0xc324f, 0xc3258, 0xc326a]
    if random_treasure:
        locke_event_pointers_2 = [p + 12 for p in locke_event_pointers_2]
    recruit_info = [
        WoRRecruitInfo(
            label = "Phoenix Cave",
            event_pointers=locke_event_pointers + locke_event_pointers_2,
            recruited_bit_pointers=[0xc3195],
            location_npcs=[(0x139, 0)],
            dialogue_pointers=[(0x984, 0x6), (0x984, 0x44), (0x988, 0x0), (0x989, 0x2), (0xa20, 0x0), (0xa21, 0x0), (0xa22, 0x16), (0xa23, 0x2), (0xa24, 0x0), (0xa28, 0x0), (0xa2a, 0x7), (0xa2c, 0x7), (0xa2c, 0x2d), (0xa2d, 0x0), (0xa2d, 0xc), (0xa2d, 0x6c), (0xa2e, 0x0), (0xa2e, 0xc5), (0xa2f, 0x0), (0xa30, 0x2), (0xa31, 0x0), (0xa34, 0x0), (0xa35, 0x0)],
            name_pointer=0xC2B81,
            num_name_bytes=4),
        WoRRecruitInfo(
            label = "Mt. Zozo",
            event_pointers=[0xc429c, 0xc429e, 0xc42a2, 0xc42a4, 0xc42a7, 0xc42aa],
            recruited_bit_pointers=[0xc42ae],
            location_npcs=[(0xb5, 2), (0xb4, 8)],
            dialogue_pointers=[(0x9f2, 0x1b), (0x9f9, 0x0), (0x9fb, 0x0), (0x9fd, 0x0), (0x9fe, 0x0), (0x9ff, 0x0), (0xa00, 0x0), (0xa01, 0x0), (0xa02, 0x0), (0xa03, 0x0), (0xa04, 0x0), (0xa05, 0x0), (0xa06, 0x0), (0xa08, 0x138), (0xa0b, 0x0), (0xa0c, 0xb)],
            name_pointer=0xC402A,
            num_name_bytes=4),
        WoRRecruitInfo(
            label = "Collapsing House",
            event_pointers=[0xa6c0e, 0xc5aa8, 0xc5aaa, 0xc5aae, 0xc5ab0, 0xc5ab3, 0xc5ab6],
            recruited_bit_pointers=[0xc5aba],
            location_npcs=[(0x131, 1)],
            dialogue_pointers=[(0x8a7, 0x2), (0x8a7, 0x5), (0x8a7, 0x1d), (0x8a8, 0x1), (0x8a8, 0x5), (0x8a9, 0x0), (0x8aa, 0x0), (0x8ab, 0x0), (0x8ac, 0x2), (0x8ad, 0x0), (0x8ae, 0x0), (0x8b1, 0x0), (0x954, 0x0), (0x95a, 0x0)],
            caseword_pointers=[0xa6af1, 0xa6b0c, 0xa6bbd],
            name_pointer=0xC590B,
            num_name_bytes=7,
            name_npcs=[0] + list(range(2,17))),
        WoRRecruitInfo(
            label = "Fanatics' Tower",
            event_pointers=[0xc5418, 0xc541a, 0xc541e, 0xc5420, 0xc5423, 0xc5426],
            recruited_bit_pointers=[0xc542a],
            location_npcs=[(0x16a, 3)],
            prerequisite=0x08,
            dialogue_pointers=[(0x8c2, 0x0), (0x8c3, 0x18), (0x8c4, 0x0), (0x8c5, 0x0)],
            name_pointer=0xC5316,
            name_npcs=list(range(3)) + list(range(4,10)),
            num_name_bytes=4),
        WoRRecruitInfo(
            label = "Owzer's House",
            event_pointers=[0xb4e09, 0xb4e0b, 0xb4e0f, 0xb4e11, 0xb4e14, 0xb4e17],
            recruited_bit_pointers=[0xb4e1b],
            location_npcs=[(0x161, 3), (0x15d, 21), (0xd0, 3)],
            dialogue_pointers=[(0xa18, 0x0), (0xa8d, 0x0), (0xa99, 0x7), (0xa9d, 0x0), (0xa9d, 0x11), (0xa9e, 0x0), (0xa9f, 0x3b), (0xaa0, 0xb0), (0xabd, 0x55), (0xabe, 0x10), (0xabe, 0x95), (0xac0, 0x7), (0xac1, 0x0), (0xac2, 0x0)],
            name_pointer=0xB4D0D,
            num_name_bytes=5,
            name_npcs=list(range(3)) + list(range(4,6))),
        WoRRecruitInfo(
            label = "Mobliz",
            event_pointers=[0xc49d1, 0xc49d3, 0xc49da, 0xc49de, 0xc49e2, 0xc4a01, 0xc4a03, 0xc4a0c, 0xc4a0d, 0xc4a2b, 0xc4a37, 0xc4a3a, 0xc4a43, 0xc4a79, 0xc4a7b, 0xc4ccf, 0xc4cd1, 0xc4cd5, 0xc4cd7, 0xc4cdb, 0xc4cde, 0xc4ce1, 0xc4ce5, 0xc4cf4, 0xc4cf6, 0xc5040, 0xc5042, 0xc5048, 0xc504a, 0xc504d, 0xc5050], 
            recruited_bit_pointers=[0xc4cd9, 0xc4cfa, 0xc5046],
            location_npcs=[(0x09A, 1), (0x09A, 2), (0x096, 0), (0x09E, 13)],
            dialogue_pointers=[(0x8cf, 0x0), (0x8d1, 0x0), (0x8d2, 0x1), (0x8d2, 0x2a), (0x8d3, 0x0), (0x8d4, 0x0), (0x8d5, 0x0), (0x8d6, 0x11), (0x8d7, 0x2b), (0x8d8, 0x0), (0x8d9, 0x0), (0x8db, 0x0), (0x8dc, 0x0), (0x8dd, 0x0), (0x8df, 0x0), (0x8df, 0x44), (0x8e0, 0x0), (0x8e5, 0x0), (0x8eb, 0x0), (0x8ec, 0x0), (0x8f0, 0x0), (0x8f6, 0xb), (0x8f7, 0x5), (0x8f8, 0x0), (0x8f9, 0x0), (0x8fa, 0x0), (0x8fb, 0x1f), (0x8fc, 0x0), (0x8fe, 0x12), (0x900, 0xb), (0x903, 0xf), (0x906, 0x9), (0x90b, 0x14)],
            name_pointer=0xC446F,
            num_name_bytes=4,
            name_npcs=[0] + list(range(2,20)),
            name_extra=[0x73, 0x32, 0x33, 0x01, 0x02, 0x04, 0x14], # Keep door open
            name_camera=(-2,4)),
        WoRRecruitInfo(
            label = "Moogle Cave",
            event_pointers=[0xC3A2D, 0xC3A2F, 0xC3A33, 0xC3A35, 0xC3A38, 0xC3A3B, 0xC3A4D, 0xC3A4E, 0xC3A50, 0xC3A52, 0xC3A53, 0xC3A55, 0xC3AAD, 0xC3AAE, 0xC3AB0, 0xC3ACC, 0xC3AD9, 0xC3ADB, 0xC3ADF, 0xC3AE2, 0xC3AE5],
            recruited_bit_pointers=[0xC3A3F, 0xC3A58],
            shop_menu_bit_pointers=[0xC3A5A],
            location_npcs=[(0x02C,0)],
            dialogue_pointers=[],
            palette_pointers=[0xC3A56],
            special=moogle_cave_recruit,
            name_pointer=None,
            num_name_bytes=None
        ),
        WoRRecruitInfo(
            label = "Sasquatch Cave",
            event_pointers=[0xCD79E, 0xCD7A0, 0xCD7A1, 0xCD7A4, 0xCD81D, 0xCD820],
            recruited_bit_pointers=[0xCD7A6],
            shop_menu_bit_pointers=[0xCD7A8],
            location_npcs=[(0x11B, 1), (0x15, 1)],
            dialogue_pointers=[(0x5fa, 0x6), (0x5fa, 0x20)],
            palette_pointers=[0xCD7A3],
            prerequisite=0x0A,
            special=sasquatch_cave_recruit,
            name_pointer=None,
            num_name_bytes=None
        )
    ]

    if include_gau:
        candidates.append(0x0B)
        recruit_info.append(WoRRecruitInfo("Falcon", [], [], [], dialogue_pointers=[(0xa07, 0xc)], special=falcon_recruit, name_pointer=None, num_name_bytes=None))
    
    if include_gogo:
        candidates.append(0x0C)
        recruit_info.append(
            WoRRecruitInfo(
                label="ZoneEater",
                event_pointers=[0xB81DB, 0xB81DC, 0xB81DE, 0xB81E0, 0xB81E1, 0xB81E3, 0xB81E6, 0xB81E7, 0xB81E9, 0xB81EB, 0xB81EF, 0xB81F2, 0xB824A, 0xB824E], 
                recruited_bit_pointers=[0xB823E],
                shop_menu_bit_pointers=[0xB823C],
                location_npcs=[(0x116, 0)],
                dialogue_pointers=[(0xa0e, 0xd), (0xa0f, 0x0), (0xa10, 0x0)],
                palette_pointers=[0xB81E4],
                special=zoneeater_recruit,
                name_pointer=0xB81CF,
                num_name_bytes=4
            ))

    prerequisite_info = [info for info in recruit_info if info.prerequisite]
    noname_info = [info for info in recruit_info if info.special == falcon_recruit]
    unrestricted_info = [info for info in recruit_info if info not in prerequisite_info and info not in noname_info]
    random.shuffle(prerequisite_info)
    recruit_info = prerequisite_info + noname_info + unrestricted_info
    prerequisite_dict = dict()
    for info in prerequisite_info:
        prerequisite_dict[info.prerequisite] = []
    wor_free_char = 0xB  # gau

    for info in recruit_info:
        valid_candidates = candidates
        if info.prerequisite:
            valid_candidates = [c for c in candidates
                                if c != info.prerequisite and c not in prerequisite_dict[info.prerequisite]]
        if (not info.name_pointer) and info.special not in [moogle_cave_recruit, sasquatch_cave_recruit, zoneeater_recruit]:
            valid_candidates = [c for c in valid_candidates if c not in [0xA, 0xC, 0xD]]
        candidate = random.choice(valid_candidates)
        candidates.remove(candidate)
        info.char_id = candidate
        if info.prerequisite:
            prerequisite_dict[info.prerequisite].append(candidate)
        if info.special == falcon_recruit:
            wor_free_char = candidate
        
        info.write_data(fout)
        get_character(candidate).wor_location = info.label
        
    return wor_free_char


def manage_wor_skip(fout, wor_free_char=0xB, airship=False, dragon=False):
    characters = get_characters()

    # jump to FC end cutscene for more space
    startsub0 = Substitution()
    startsub0.bytestring = bytes([0xB2, 0x1E, 0xDD, 0x00, 0xFE])
    startsub0.set_location(0xC9A4F)
    startsub0.write(fout)

    # change code at start of game to warp to wor
    wor_sub = Substitution()
    wor_sub.bytestring = bytes([0x6C, 0x01, 0x00, 0x91, 0xD3, 0x02, # make WoR the parent map
                          0x88, 0x00, 0x00, 0x00,  # remove Magitek from Terra
                          0xD5, 0xF0,  # flag Terra as unobtained
                          0xD5, 0xE0,  # flag Terra as unobtained
                          0x3F, 0x00, 0x00,  # remove Terra from party
                          0x3F, 0x0E, 0x00,  # remove Vicks from party
                          0x3F, 0x0F, 0x00,  # remove Wedge from party
                          0x3E, 0x00,  # delete Terra
                          0x3E, 0x0E,  # delete Vicks
                          0x3E, 0x0F,  # delete Wedge

                          # there's no command to set a char's level, so I'ma
                          # do something hacky and continually set Mog/Strago's
                          # properties.  Each of them will consider the other's
                          # level as the "party average".  Strago will be
                          # boosted 2 levels above this average, and Mog will
                          # be boosted 5 levels, which effectively see-saws
                          # their levels upwards until they are around the
                          # level I want Celes to be at.
                          0xD4, 0xF7,  # flag Strago as obtained
                          0xD4, 0xE7,  # flag Strago as obtained
                          0xD4, 0xFA,  # flag Mog as obtained
                          0xD4, 0xEA,  # flag Mog as obtained
                          0x40, 0x0A, 0x0A,  # give Mog properties
                          0x40, 0x07, 0x07,  # give Strago properties
                          0x40, 0x0A, 0x0A,  # give Mog properties
                          0x40, 0x07, 0x07,  # give Strago properties
                          0x40, 0x0A, 0x0A,  # give Mog properties
                          0x40, 0x07, 0x07,  # give Strago properties
                          0x40, 0x0A, 0x0A,  # give Mog properties
                          0x40, 0x07, 0x07,  # give Strago properties
                          0x40, 0x0A, 0x0A,  # give Mog properties
                          0x40, 0x07, 0x07,  # give Strago properties
                          0x40, 0x0A, 0x0A,  # give Mog properties
                          0x40, 0x07, 0x07,  # give Strago properties
                          ]) + bytes([
                                0x40, 0x0A, 0x0A,  # give Mog properties
                            ] if dragon else []
                          ) + bytes([0x40, 0x06, 0x06,  # give Celes properties
                          0xD5, 0xF7,  # flag Strago as unobtained
                          0xD5, 0xE7,  # flag Strago as unobtained
                          0xD5, 0xFA,  # flag Mog as unobtained
                          0xD5, 0xEA,  # flag Mog as unobtained

                          0xD4, 0xF6,  # flag Celes as obtained
                          0xD4, 0xE6,  # flag Celes as obtained
                          0x3D, 0x06,  # create Celes
                          0x3F, 0x06, 0x01,  # add Celes to party

                          0x40, 0x0C, 0x1B,  # give Gogo the properties of Kamog
                          0x40, 0x0D, 0x1C,  # give Umaro the properties of Mog (three scenario party selection)
                          0x8D, 0x0C,  # unequip Kamog
                          0x8D, 0x0D,  # unequip fake Mog

                          0x40, 0x01, 0x01,  # give Locke properties
                          0x40, 0x02, 0x02,  # give Cyan properties
                          0x40, 0x03, 0x03,  # give Shadow properties
                          0x40, 0x04, 0x04,  # give Edgar properties
                          0x40, 0x05, 0x05,  # give Sabin properties
                          0x40, 0x07, 0x07,  # give Strago properties
                          0x40, 0x08, 0x08,  # give Relm properties
                          0x40, 0x09, 0x09,  # give Setzer properties
                          0x40, 0x0A, 0x0A,  # give Mog properties
                          0x40, 0x0B, 0x0B,  # give Gau properties

                          0x37, 0x01, 0x01,  # give Locke graphics
                          0x37, 0x02, 0x02,  # give Cyan graphics
                          0x37, 0x03, 0x03,  # give Shadow graphics
                          0x37, 0x04, 0x04,  # give Edgar graphics
                          0x37, 0x05, 0x05,  # give Sabin graphics
                          0x37, 0x06, 0x06,  # give Celes graphics
                          0x37, 0x07, 0x07,  # give Strago graphics
                          0x37, 0x08, 0x08,  # give Relm graphics
                          0x37, 0x09, 0x09,  # give Setzer graphics
                          0x37, 0x0A, 0x0A,  # give Mog graphics
                          0x37, 0x0B, 0x0B,  # give Gau graphics

                          0x7F, 0x00, 0x00,  # give Terra name
                          0x7F, 0x01, 0x01,  # give Locke name
                          0x7F, 0x02, 0x02,  # give Cyan name
                          0x7F, 0x03, 0x03,  # give Shadow name
                          0x7F, 0x04, 0x04,  # give Edgar name
                          0x7F, 0x05, 0x05,  # give Sabin name
                          0x7F, 0x06, 0x06,  # give Celes name
                          0x7F, 0x07, 0x07,  # give Strago name
                          0x7F, 0x08, 0x08,  # give Relm name
                          0x7F, 0x09, 0x09,  # give Setzer name
                          0x7F, 0x0A, 0x0A,  # give Mog name
                          0x7F, 0x0B, 0x0B,  # give Gau name

                          0x84, 0x50, 0xC3,  # give party 50K Gil

                          0x86, 0x36,  # give Ramuh
                          0x86, 0x37,  # give Ifrit
                          0x86, 0x38,  # give Shiva
                          0x86, 0x39,  # give Siren
                          0x86, 0x3B,  # give Shoat
                          0x86, 0x3C,  # give Maduin
                          0x86, 0x3D,  # give Bismark
                          0x86, 0x3E,  # give Stray
                          0x86, 0x47,  # give Kirin
                          0x86, 0x49,  # give Carbunkl
                          0x86, 0x4A,  # give Phantom
                          0x86, 0x4D,  # give Unicorn

                          0xB8, 0x42,  # allow Morph
                          0xB8, 0x43,  # display AP
                          0xB8, 0x49,  # Gau handed Meat
                          0xB8, 0x4B,  # Shadow can't leave
                          0xE8, 0x06, 0x08, 0x00,  # set up 8 dragons
                          ])

    # assign a palette to each character
    partymembers = [c for c in characters if 1 <= c.id <= 12]
    for character in partymembers:
        id = character.id
        palette = character.palette
        wor_sub.bytestring += bytes([0x43, id, palette])

    # obtain all locations with WoB treasures
    wobtreasurelocs = []
    for line in open(WOB_TREASURE_TABLE):
        line = line.strip()
        wobtreasurelocs.append(line)

    # obtain a list of all treasures in these areas
    wobtreasures = []
    for l in get_locations():
        if not l.chests:
            continue
        if l.area_name.upper() in wobtreasurelocs:
            wobtreasures.extend(l.treasure_ids)

    # give the items to the player via event code
    for t in wobtreasures:
        wor_sub.bytestring += bytes([0x80, t])

    # give WoB event items
    event_items = get_event_items()
    for l in event_items:
        if l.upper() in wobtreasurelocs + ["FIGARO CASTLE"]:
            for e in event_items[l]:
                if e.contenttype == 0x40 and not e.multiple:
                    wor_sub.bytestring += bytes([0x80, e.contents])

    # give the player a basic set of items.  These items are intended to
    # reflect the items a player would probably have by the time they get this
    # far, so that they aren't missing basic supplies they would have in almost any seed.
    for line in open(WOR_ITEMS_TABLE):
        line = line.strip().split(',')
        for i in range (0, int(line[1])):
            wor_sub.bytestring += bytes([0x80, int(line[0], 16)])

    # jump to overwriting the Ramuh cutscene because we need even more space
    wor_sub.bytestring += bytes([0xB2, 0x49, 0x97, 0x00,
                           0xFE
                          ])
    wor_sub.set_location(0xADD1E)
    wor_sub.write(fout)
    wor_sub2 = Substitution()
    wor_sub2.bytestring = bytearray([])

    # set most of the event bits that would have been set in the WoB
    for line in open(WOB_EVENTS_TABLE):
        line = line.strip().split(',')
        setbit = int(line[1], 16)  # if 1, set the bit from the txt file
        bit = line[0]  # the bit to set/clear from the txt file
        if bit == "2FB":
            bit = "2F" + hex(wor_free_char)[2]
        firstbyte = 0xD1 + int(bit[0:1], 16) * 2 - setbit
        lastbyte = int(bit[1:], 16)
        wor_sub2.bytestring += bytearray([firstbyte, lastbyte])
        
    if airship:
        wor_sub2.bytestring += bytearray([0xD2, 0xB9])  # airship appears in WoR

    if dragon:
        wor_sub2.bytestring += bytearray([
            0xD0, 0xA7,  # Talked to crimson robber
            0xD0, 0xA8,  # Talked to crimson robber
            0xD0, 0xA9,  # Talked to crimson robber
            0xD0, 0xAA,  # Talked to crimson robber
            0xD0, 0xAB,  # crimson robber left cafe
            0xD7, 0x74,
            0xD0, 0xAC,  # boarded the crimson robbers' ship
            0xD7, 0xFE,
            0xD7, 0x77,
            0xD7, 0x78,
            0xD7, 0x7E,  # talked to gerad in s figaro inn
            0xD7, 0x7A,
            0xD6, 0x99,
            0xD2, 0x23,  # Can jump on turtle in figaro cave
            0xD4, 0x6E,  # Saw Gerad help the injured guy
            0xD0, 0xC6,  # recruited Edgar in WoR
            0xD4, 0xF4,  # flag Edgar as obtained
            0xD4, 0xE4,  # flag Edgar as obtained
            0x3D, 0x04,  # create Edgar
            0x3F, 0x04, 0x01,  # add Edgar to party
            0xD7, 0xF0,
            0xD7, 0xF1,
            0xD7, 0xF2,
            0xD7, 0x82,
            0xD7, 0x97,
            0xD6, 0x81,
            0xD0, 0xC7,  # Saw Figaro Castle rise after tentacles
            0xD5, 0xB7,  # prison door is not open
            0xD0, 0xDC,  # Figaro castle is in Western desert
            0xD4, 0xF9,  # flag Setzer as obtained
            0xD4, 0xE9,  # flag Setzer as obtained
            0x3D, 0x09,  # create Setzer
            0x3F, 0x09, 0x01,  # add Setzer to party
            0xDD, 0x7F,
            0xDD, 0xB6,
            0xD0, 0xCA,  # recruited Setzer in WoR
            0xD0, 0xCB,  # opened Daryl's tomb
            0xD4, 0xB1,  # opened the door
            0xD4, 0xB3,  # raised the water
            0xD4, 0xB5,  # raised the water 2
            0xD4, 0xB8,  # opened the door 2
            0xD4, 0xB2,  # defeated dullahan
            0xD7, 0xF3,
            0x04, 0x05,
            0xD5, 0x11, 0x08,
            0xCF,
            0xFF,
            0x06, 0x05,
            0xD5, 0x12, 0x07,
            0xCF,
            0xFF,
            0x41, 0x04,
            0x41, 0x06,
            0x41, 0x09,
            0xB2, 0x7B, 0x47, 0x00, # Falcon rising out of water
            0xFE,
        ])
            
        text = "<SETZER>: But first we need to kill the dragons!"
        dragon_text_sub = Substitution()
        dragon_text_sub.bytestring = dialogue_to_bytes(text)
        dragon_text_sub.set_location(get_dialogue_pointer(fout, 0x9AF))
        dragon_text_sub.write(fout)
        print(len(dragon_text_sub.bytestring), get_dialogue_pointer(fout, 0x9B0) - get_dialogue_pointer(fout, 0x9AF))
            
    else:
        wor_sub2.bytestring += bytearray([0x6B, 0x01, 0x00, 0x91, 0xD3, 0x00]) # go to WoR

        if airship:
            wor_sub2.bytestring += bytearray([0xC7, 0x91, 0xD3])  # place airship
        
        wor_sub2.bytestring += bytearray([
            0xFF,  # end map script
            0xFE,  # return
            ])

    wor_sub2.set_location(0xA9749)
    wor_sub2.write(fout)

    # set more Lores as starting Lores
    odds = [True, True, False]
    address = 0x26F564
    fout.seek(address)
    extra_known_lores = read_multi(fout, length=3)
    for i in range(24):
        if random.choice(odds):
            extra_known_lores |= (1 << i)
        if random.choice([True, False, False]):
            odds.append(False)
    fout.seek(address)
    write_multi(fout, extra_known_lores, length=3)
    
    if dragon:
        set_alternate_dragon_locations(fout)


def set_alternate_dragon_locations(fout):
    # TODO: Add more locations and randomly pick two?
    # These NPCs happen to match the NPC numbers of the dragons
    # in Kefka's tower so we can jump into the same event.
    # A more general solution would need to copy the event
    # after dragons have been randomized.
    # Or just abandon the option of going into Kefka's tower
    # to fight them.
    
    # gold dragon: zone eater
    zone_eater = get_location(0x114)
    gold_dragon = zone_eater.npcs[0]
    gold_dragon.palette = 2
    gold_dragon.graphics = 57
    gold_dragon.membit = 3
    gold_dragon.memaddr = 0x1F56 - 0x1EE0
    gold_dragon.event_addr = 0x218F3
    

    # skull dragon: Owzer's mansion
    owzer = get_location(0xd1)
    # Hide the emperor and replace Ultros
    # since his NPC number matches the skull dragon's.
    emperor = owzer.npcs[3]
    emperor.membit = 2
    emperor.memaddr = 0x1F1E - 0x1EE0
    skull_dragon = owzer.npcs[4]
    skull_dragon.palette = 4
    skull_dragon.graphics = 57
    skull_dragon.membit = 4
    skull_dragon.memaddr = 0x1F56 - 0x1EE0
    skull_dragon.event_addr = 0x5EB3
    
    skull_dragon_event = Substitution()
    skull_dragon_event.set_location(0xB4B62) 
    skull_dragon_event.bytestring = bytes([
    0xC0, 0xB4, 0x86, 0x20, 0x19, 0x02,  # If haven't beat this dragon, branch to $CC1920
    0xFE # return
    ])
    skull_dragon_event.write(fout)