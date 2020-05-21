import dataclasses

from chestrandomizer import get_event_items
from character import get_character, get_characters
from dialoguemanager import get_dialogue, set_dialogue
from locationrandomizer import get_location, get_locations, NPCBlock
from monsterrandomizer import change_enemy_name
from utils import (WOB_TREASURE_TABLE, WOR_ITEMS_TABLE, WOB_EVENTS_TABLE,
                   read_multi, Substitution, utilrandom as random, write_multi, bytes_to_dialogue)


alt_zone_eater_recruit = None


def _dir_to_camera_moves(dir):
    x = dir[0]
    y = dir[1]

    left = x < 0
    down = y < 0
    if left:
        x = -x
    if down:
        y = -y
    out = []

    while x != 0 and y != 0:
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
    level_average_bytes = bytes([0x77, 0x0A]) if recruit_info.special == zone_eater_recruit else bytes([])
    maybe_name_sub = Substitution()
    maybe_name_sub.set_location(maybe_name_location)
    maybe_name_sub.bytestring = bytes([
        0xC0, 0x9F, 0x02, name_low, name_mid, name_high - 0x0A,
    ]) + extra_bytes + level_average_bytes + bytes([0xFE])
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
    if recruit_info.name_camera == (0, 0):
        name_camera = []
        name_camera_reverse = []
    else:
        c = _dir_to_camera_moves(recruit_info.name_camera)
        d = _dir_to_camera_moves((-recruit_info.name_camera[0], -recruit_info.name_camera[1]))
        name_camera = [0x38, 0x30, 0x82 + len(c), 0xC1] + c + [0xFF]
        name_camera_reverse = [0x30, 0x82 + len(d), 0xC2] + d +[0xFF, 0x39]
    for npc in recruit_info.name_npcs:
        hide_npcs += [0x42, 0x10 + npc]
        show_npcs += [0x41, 0x10 + npc]

    if recruit_info.name_show_full_party:
        hide_party = [
            0x42, 0x31,
            0x42, 0x32,
            0x42, 0x33,
            0x42, 0x34,
        ]
        show_party = [
            0x41, 0x31,
            0x41, 0x32,
            0x41, 0x33,
            0x41, 0x34,
        ]
    else:
        hide_party = [0x42, 0x31]
        show_party = [0x41, 0x31]

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
    ] + hide_party + hide_npcs + [
        0xB2, 0x0F, 0xD0, 0x00, # Darken background
    ] + name_camera + [
        0x4B, 0xE0, 0xC6, # SLAM-dancing Moogle text
        0x92, # Pause for 30 frames
        mog_npc, 0x82, # begin queue for mog npc
        0x1D, 0xFF, # do graphical action 1D, end
        0x94, # pause for 60 frames
        0x97, # fade to black
        0x5C, # Pause until fade is complete
        0x7F, 0x0A, 0x0A, # change mog's name to mog
        0x98, 0x0A, # name change screen for mog
    ] + show_party + show_npcs + recruit_info.name_extra + [
        0x45, # refresh objects
        0x96, # unfade
        0x5C, # wait until unfade is complete
    ] + name_camera_reverse + [
        0xB2, 0x15, 0xD0, 0x00, # Lighten background
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
    name_jump.bytestring = bytes([0xB2, name_low, name_mid, name_high - 0x0A] + [0xFD] * (recruit_info.num_name_bytes-4))
    name_jump.write(fout)

    palette = get_character(0xD).palette
    name_sub = Substitution()
    name_sub.set_location(name_location)
    umaro_npc = recruit_info.location_npcs[0][1] + 0x10
    hide_npcs = []
    show_npcs = []
    if recruit_info.name_camera == (0, 0):
        name_camera = []
        name_camera_reverse = []
    else:
        c = _dir_to_camera_moves(recruit_info.name_camera)
        d = _dir_to_camera_moves((-recruit_info.name_camera[0], -recruit_info.name_camera[1]))
        name_camera = [0x38, 0x30, 0x82 + len(c), 0xC1] + c + [0xFF]
        name_camera_reverse = [0x30, 0x82 + len(d), 0xC2] + d +[0xFF, 0x39]
    for npc in recruit_info.name_npcs:
        hide_npcs += [0x42, 0x10 + npc]
        show_npcs += [0x41, 0x10 + npc]

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
    ] + hide_npcs + [
        0xB2, 0x0F, 0xD0, 0x00, # Darken background
    ] + name_camera + [
        0x4B, 0xF9, 0xC5, # Admirer of bone-carvings text
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
    ] + show_npcs + recruit_info.name_extra + [
        0x45, # refresh objects
        0x96, # unfade
        0x5C, # wait until unfade is complete
    ] + name_camera_reverse + [
        0xB2, 0x15, 0xD0, 0x00, # Lighten background
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
    name_jump.bytestring = bytes([0xB2, name_low, name_mid, name_high - 0x0A] + [0xFD] * (recruit_info.num_name_bytes-4))
    name_jump.write(fout)

    palette = get_character(0xD).palette
    name_sub = Substitution()
    name_sub.set_location(name_location)
    gogo_npc = recruit_info.location_npcs[0][1] + 0x10
    hide_npcs = []
    show_npcs = []
    if recruit_info.name_camera == (0, 0):
        name_camera = []
        name_camera_reverse = []
    else:
        c = _dir_to_camera_moves(recruit_info.name_camera)
        d = _dir_to_camera_moves((-recruit_info.name_camera[0], -recruit_info.name_camera[1]))
        name_camera = [0x38, 0x30, 0x82 + len(c), 0xC1] + c + [0xFF]
        name_camera_reverse = [0x30, 0x82 + len(d), 0xC2] + d +[0xFF, 0x39]
    for npc in recruit_info.name_npcs:
        hide_npcs += [0x42, 0x10 + npc]
        show_npcs += [0x41, 0x10 + npc]

    name_sub.bytestring = bytes([
        gogo_npc, 0x82, # begin queue for gogo npc
        0xCE, 0xFF, # Turn down for what?, end
        0x42, 0x31, # Hide party
        0x42, 0x32, # Hide party
        0x42, 0x33, # Hide party
        0x42, 0x34, # Hide party
    ] + hide_npcs + [
        0xB2, 0x0F, 0xD0, 0x00, # Darken background
    ] + name_camera + [
        0x4B, 0x0D, 0xCA, # Shrouded in odd clothing text
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
    ] + show_npcs + recruit_info.name_extra + [
        0x45, # refresh objects
    ] + name_camera_reverse + [
        0x93, # pause for 45 frames
        0x3E, 0x0D, # Delete object 0D
        0x45, # refresh objects
    ]) + extra_bytes + bytes([0xFE])
    name_sub.write(fout)


class WoRRecruitInfo:
    def __init__(self, label, event_pointers, recruited_bit_pointers, location_npcs,
                 dialogue_pointers, name_pointer, num_name_bytes, old_char_id,
                 shop_menu_bit_pointers=None, palette_pointers=None,
                 caseword_pointers=None, prerequisite=None, special=None,
                 name_npcs=None, name_extra=None, name_camera=(0, 0),
                 name_show_full_party=False):
        self.label = label
        self.event_pointers = event_pointers
        self.recruited_bit_pointers = recruited_bit_pointers
        self.location_npcs = location_npcs
        self.dialogue_pointers = dialogue_pointers
        self.char_id = None
        self.old_char_id = old_char_id
        self.name_pointer = name_pointer
        self.num_name_bytes = num_name_bytes
        self.caseword_pointers = caseword_pointers
        self.shop_menu_bit_pointers = shop_menu_bit_pointers or []
        self.palette_pointers = palette_pointers or []
        self.prerequisite = prerequisite
        self.special = special
        self.name_npcs = name_npcs or []
        self.name_extra = name_extra or []
        self.name_camera = name_camera
        self.name_show_full_party = name_show_full_party

    def write_data(self, fout):
        assert self.char_id is not None
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
        for index in self.dialogue_pointers:
            text = get_dialogue(index)
            old_name_placeholder = bytes_to_dialogue(bytes([self.old_char_id + 2]))
            new_name_placeholder = bytes_to_dialogue(bytes([self.char_id + 2]))
            text = text.replace(old_name_placeholder, new_name_placeholder)
            set_dialogue(index, text)
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
        if self.char_id == 0xC and self.special not in [sasquatch_cave_recruit, moogle_cave_recruit, zone_eater_recruit]:
            recruit_gogo_insert(fout, self)
        if self.char_id == 0xD and self.special not in [sasquatch_cave_recruit, moogle_cave_recruit, zone_eater_recruit]:
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
        else:
            moogle_cave_recruit_sub.bytestring = bytes([0x4B, 0xF9, 0xC5]) # Admirer of bone-carvings text
        moogle_cave_recruit_sub.write(fout)
        return

    # Don't rename, stay in got-Mog-in-WoB part
    moogle_cave_recruit_sub = Substitution()
    moogle_cave_recruit_sub.set_location(0xC3974)
    moogle_cave_recruit_sub.bytestring = bytes([0xFD] * 7)
    moogle_cave_recruit_sub.write(fout)


def sasquatch_cave_recruit(fout, char_id):
    assert char_id != 0x0A

    umaro_name = get_character(char_id).newname
    for umaro_id in [0x10f, 0x110]:
        change_enemy_name(fout, umaro_id, umaro_name)

    if char_id == 0x0C:
        gogo_sub = Substitution()
        gogo_sub.set_location(0xCD811)
        gogo_sub.bytestring = bytes([0x4B, 0x0D, 0xCA]) # shrouded in odd clothing
        gogo_sub.write(fout)

        gogo_sub.set_location(0xCD79A)
        gogo_sub.bytestring = bytes([0x40, 0x0C, 0x0C]) # assign Gogo properties to Gogo
        gogo_sub.write(fout)
        return

    if char_id == 0x0D:
        return

    sasquatch_cave_recruit_sub = Substitution()
    # Level average character instead of setting Umaro's properties
    sasquatch_cave_recruit_sub.set_location(0xCD79A)
    sasquatch_cave_recruit_sub.bytestring = bytes([0x77, char_id, 0xFD])
    sasquatch_cave_recruit_sub.write(fout)

    # Skip over rename
    sasquatch_cave_recruit_sub.set_location(0xCD7F5)
    sasquatch_cave_recruit_sub.bytestring = bytes([

        0xC0, 0x27, 0x01, 0x40, 0xD8, 0x02 # jump
    ])
    sasquatch_cave_recruit_sub.write(fout)


def zone_eater_recruit(fout, char_id):
    if char_id == 0x0C:
        return

    if char_id == 0x0D:
        umaro_sub = Substitution()
        umaro_sub.set_location(0xB81D6)
        umaro_sub.bytestring = bytes([0x4B, 0xF9, 0xC5]) # Admirer of bone-carvings text
        return

    prefix = [0xFD] * 4 if char_id == 0x0A else [0x77, char_id]

    # Skip over rename
    zone_eater_recruit_sub = Substitution()
    zone_eater_recruit_sub.set_location(0xB81CF)
    zone_eater_recruit_sub.bytestring = bytes(prefix + [0x3D, char_id, 0xC0, 0x27, 0x01, 0x00, 0x82, 0x01])
    zone_eater_recruit_sub.write(fout)

def collapsing_house_recruit(unused_fout, unused_char_id):
    pass

def manage_wor_recruitment(fout, shuffle_wor, random_treasure, include_gau, alternate_gogo):
    if alternate_gogo:
        _setup_alternate_zone_eater(fout, include_gau)

    if shuffle_wor:
        wor_free_char, collapsing_house_char = _shuffle_recruit_locations(fout, random_treasure, include_gau, alternate_gogo)
    else:
        wor_free_char = 0x0B
        collapsing_house_char = 0x05

    if alternate_gogo:
        _manage_gogo_recruitment(fout, collapsing_house_char)

    _start_of_wor_event(fout, alternate_gogo)

    return wor_free_char


def _start_of_wor_event(fout, alternate_gogo):
    new_events = [
        # Set names for Mog, Gogo, Umaro in case they appear in text
        0x7F, 0x0C, 0x0C, # Set name for GOGO
        0x7F, 0x0D, 0x0D, # Set name for UMARO
        0xC0, 0x9F, 0x82, 0xB3, 0x5E, 0x00, # If Mog recruited in WoB, jump to return
        0x7F, 0x0A, 0x0A # Set name for MOG
    ]

    if alternate_gogo:
        new_events = [0xDA, 0x4B] + new_events # Set Gogo NPC bit

    # bits that get set at the start of the world of ruin
    wor_bits_sub = Substitution()
    wor_bits_sub.set_location(0x305280)
    wor_bits_sub.bytestring = [
        # These bits are normally set in subroutine CB4B4B
        # We could just call it as a subroutine, but we'll reuse the space later.
        0xD9, 0xF2,
        0xD8, 0x92,
    ] + new_events + [
        0xFE, # Return
    ]
    wor_bits_sub.write(fout)
    next_event = wor_bits_sub.location + len(wor_bits_sub.bytestring)

    # call the new subroutine above in place of CB4B4B
    ptr_low = wor_bits_sub.location & 0xFF
    ptr_mid = (wor_bits_sub.location & 0xFF00) >> 8
    ptr_high = ((wor_bits_sub.location - 0xA0000) & 0xFF0000) >> 16
    wor_bits_sub2 = Substitution()
    wor_bits_sub2.set_location(0xA5334)
    wor_bits_sub2.bytestring = [0xB2, ptr_low, ptr_mid, ptr_high]
    wor_bits_sub2.write(fout)



def _shuffle_recruit_locations(fout, random_treasure, include_gau, alternate_gogo):
    candidates = [0x00, 0x01, 0x02, 0x05, 0x07, 0x08, 0x0A, 0x0D]
    locke_event_pointers = [0xc2c48, 0xc2c51, 0xc2c91, 0xc2c9d, 0xc2c9e, 0xc2caf, 0xc2cb8, 0xc2cc5, 0xc2cca, 0xc2cd8, 0xc2ce3, 0xc2ce9, 0xc2cee, 0xc2cf4, 0xc2cfa, 0xc2d0b, 0xc2d33, 0xc2e32, 0xc2e4a, 0xc2e80, 0xc2e86, 0xc2e8b, 0xc2e91, 0xc2ea5, 0xc2eb1, 0xc2ec4, 0xc2f0b, 0xc2fe1, 0xc3102, 0xc3106, 0xc3117, 0xc311d, 0xc3124, 0xc3134, 0xc313d, 0xc3163, 0xc3183, 0xc3185, 0xc3189, 0xc318b, 0xc318e, 0xc3191, 0xc3197, 0xc31c7, 0xc31cb, 0xc31e2, 0xc31e8, 0xc31ed, 0xc31f2, 0xc31f8, 0xc3210, 0xc3215, 0xc321d, 0xc3229, 0xc322f, 0xc3235, 0xc323b]
    locke_event_pointers_2 = [0xc3244, 0xc324a, 0xc324f, 0xc3258, 0xc326a]
    if random_treasure:
        locke_event_pointers_2 = [p + 12 for p in locke_event_pointers_2]
    recruit_info = [
        WoRRecruitInfo(
            label="Phoenix Cave",
            event_pointers=locke_event_pointers + locke_event_pointers_2,
            recruited_bit_pointers=[0xc3195],
            location_npcs=[(0x139, 0)],
            dialogue_pointers=[0x984, 0x988, 0x989, 0xa20, 0xa21, 0xa22, 0xa23, 0xa24, 0xa28, 0xa2a, 0xa2c, 0xa2d, 0xa2e, 0xa2f, 0xa30, 0xa31, 0xa34, 0xa35],
            old_char_id=1,
            name_pointer=0xC2B81,
            num_name_bytes=4,
            name_show_full_party=True),
        WoRRecruitInfo(
            label="Mt. Zozo",
            event_pointers=[0xc429c, 0xc429e, 0xc42a2, 0xc42a4, 0xc42a7, 0xc42aa],
            recruited_bit_pointers=[0xc42ae],
            location_npcs=[(0xb5, 2), (0xb4, 8)],
            dialogue_pointers=[0x9f2, 0x9f9, 0x9fb, 0x9fd, 0x9fe, 0x9ff, 0xa00, 0xa01, 0xa02, 0xa03, 0xa04, 0xa05, 0xa06, 0xa08, 0xa0b, 0xa0c],
            old_char_id=2,
            name_pointer=0xC402A,
            num_name_bytes=4),
        WoRRecruitInfo(
            label="Collapsing House",
            event_pointers=[0xa6c0e, 0xc5aa8, 0xc5aaa, 0xc5aae, 0xc5ab0, 0xc5ab3, 0xc5ab6],
            recruited_bit_pointers=[0xc5aba],
            location_npcs=[(0x131, 1)],
            dialogue_pointers=[0x8a7, 0x8a8, 0x8a9, 0x8aa, 0x8ab, 0x8ac, 0x8ad, 0x8ae, 0x8b1, 0x954, 0x95a],
            caseword_pointers=[0xa6af1, 0xa6b0c, 0xa6bbd],
            old_char_id=5,
            name_pointer=0xC590B,
            num_name_bytes=7,
            name_npcs=[0, 2, 4, 6, 8, 10],
            special=collapsing_house_recruit),
        WoRRecruitInfo(
            label="Fanatics' Tower",
            event_pointers=[0xc5418, 0xc541a, 0xc541e, 0xc5420, 0xc5423, 0xc5426],
            recruited_bit_pointers=[0xc542a],
            location_npcs=[(0x16a, 3)],
            prerequisite=0x08,
            dialogue_pointers=[0x8c2, 0x8c3, 0x8c4, 0x8c5],
            old_char_id=7,
            name_pointer=0xC5316,
            name_npcs=list(range(3)) + list(range(4, 10)),
            num_name_bytes=4,
            name_show_full_party=True),
        WoRRecruitInfo(
            label="Owzer's House",
            event_pointers=[0xb4e09, 0xb4e0b, 0xb4e0f, 0xb4e11, 0xb4e14, 0xb4e17],
            recruited_bit_pointers=[0xb4e1b],
            location_npcs=[(0x161, 3), (0x15d, 21), (0xd0, 3)],
            dialogue_pointers=[0xa18, 0xa8d, 0xa99, 0xa9d, 0xa9d, 0xa9e, 0xa9f, 0xaa0, 0xabd, 0xabe, 0xabe, 0xac0, 0xac1, 0xac2],
            old_char_id=8,
            name_pointer=0xB4D0D,
            num_name_bytes=5,
            name_npcs=list(range(3)) + list(range(4, 6))),
        WoRRecruitInfo(
            label="Mobliz",
            event_pointers=[0xc49d1, 0xc49d3, 0xc49da, 0xc49de, 0xc49e2, 0xc4a01, 0xc4a03, 0xc4a0c, 0xc4a0d, 0xc4a2b, 0xc4a37, 0xc4a3a, 0xc4a43, 0xc4a79, 0xc4a7b, 0xc4ccf, 0xc4cd1, 0xc4cd5, 0xc4cd7, 0xc4cdb, 0xc4cde, 0xc4ce1, 0xc4ce5, 0xc4cf4, 0xc4cf6, 0xc5040, 0xc5042, 0xc5048, 0xc504a, 0xc504d, 0xc5050],
            recruited_bit_pointers=[0xc4cd9, 0xc4cfa, 0xc5046],
            location_npcs=[(0x09A, 1), (0x09A, 2), (0x096, 0), (0x09E, 13)],
            dialogue_pointers=[0x8cf, 0x8d1, 0x8d2, 0x8d3, 0x8d4, 0x8d5, 0x8d6, 0x8d7, 0x8d8, 0x8d9, 0x8db, 0x8dc, 0x8dd, 0x8df, 0x8e0, 0x8e5, 0x8eb, 0x8ec, 0x8f0, 0x8f6, 0x8f7, 0x8f8, 0x8f9, 0x8fa, 0x8fb, 0x8fc, 0x8fe, 0x900, 0x903, 0x906, 0x90b],
            old_char_id=0,
            name_pointer=0xC446F,
            num_name_bytes=4,
            name_npcs=[0] + list(range(6, 15)),
            name_extra=[0x73, 0x32, 0x33, 0x01, 0x02, 0x04, 0x14], # Keep door open
            name_camera=(-2, 4)),
        WoRRecruitInfo(
            label="Moogle Cave",
            event_pointers=[0xC3A2D, 0xC3A2F, 0xC3A33, 0xC3A35, 0xC3A38, 0xC3A3B, 0xC3A4D, 0xC3A4E, 0xC3A50, 0xC3A52, 0xC3A53, 0xC3A55, 0xC3AAD, 0xC3AAE, 0xC3AB0, 0xC3ACC, 0xC3AD9, 0xC3ADB, 0xC3ADF, 0xC3AE2, 0xC3AE5],
            recruited_bit_pointers=[0xC3A3F, 0xC3A58],
            shop_menu_bit_pointers=[0xC3A5A],
            location_npcs=[(0x02C, 0)],
            dialogue_pointers=[],
            old_char_id=0xA,
            palette_pointers=[0xC3A56],
            special=moogle_cave_recruit,
            name_pointer=None,
            num_name_bytes=None
        ),
        WoRRecruitInfo(
            label="Sasquatch Cave",
            event_pointers=[0xCD79B, 0xCD79C, 0xCD79E, 0xCD7A0, 0xCD7A1, 0xCD7A4, 0xCD81D, 0xCD820],
            recruited_bit_pointers=[0xCD7A6],
            shop_menu_bit_pointers=[0xCD7A8],
            location_npcs=[(0x11B, 1), (0x15, 1)],
            dialogue_pointers=[0x5fa],
            old_char_id=0xD,
            palette_pointers=[0xCD7A4],
            prerequisite=0x0A,
            special=sasquatch_cave_recruit,
            name_pointer=None,
            num_name_bytes=None
        )
    ]

    if include_gau:
        candidates.append(0x0B)
        if alternate_gogo:
            recruit_info.append(alt_zone_eater_recruit)
        else:
            recruit_info.append(WoRRecruitInfo("Falcon", [], [], [], dialogue_pointers=[0xa07], old_char_id=0xB, special=falcon_recruit, name_pointer=None, num_name_bytes=None))

    if not alternate_gogo:
        candidates.append(0x0C)
        recruit_info.append(
            WoRRecruitInfo(
                label="ZoneEater",
                event_pointers=[0xB81DB, 0xB81DC, 0xB81DE, 0xB81E0, 0xB81E1, 0xB81E3, 0xB81E6, 0xB81E7, 0xB81E9, 0xB81EB, 0xB81EF, 0xB81F2, 0xB824A, 0xB824E],
                recruited_bit_pointers=[0xB823E],
                shop_menu_bit_pointers=[0xB823C],
                location_npcs=[(0x116, 0)],
                dialogue_pointers=[0xa0e, 0xa0f, 0xa10],
                old_char_id=0xC,
                palette_pointers=[0xB81E4],
                special=zone_eater_recruit,
                name_pointer=0xB81CF,
                num_name_bytes=4,
            ))

    prerequisite_info = [info for info in recruit_info if info.prerequisite]
    noname_info = [info for info in recruit_info if info.special == falcon_recruit]
    unrestricted_info = [info for info in recruit_info if info not in prerequisite_info and info not in noname_info]
    random.shuffle(prerequisite_info)
    recruit_info = prerequisite_info + noname_info + unrestricted_info
    prerequisite_dict = dict()
    wor_free_char = None
    collapsing_house_char = None

    for info in recruit_info:
        valid_candidates = candidates
        if info.prerequisite:
            valid_candidates = [c for c in candidates
                                if c != info.prerequisite and c not in prerequisite_dict.get(info.prerequisite, [])]
        if (not info.name_pointer) and info.special not in [moogle_cave_recruit, sasquatch_cave_recruit, zone_eater_recruit]:
            valid_candidates = [c for c in valid_candidates if c not in [0xA, 0xC, 0xD]]
        candidate = random.choice(valid_candidates)
        candidates.remove(candidate)
        info.char_id = candidate
        if info.prerequisite:
            prerequisite_dict.setdefault(candidate, []).append(info.prerequisite)
        if info.special == falcon_recruit:
            wor_free_char = candidate
        elif info.special == collapsing_house_recruit:
            collapsing_house_char = candidate

        info.write_data(fout)
        get_character(candidate).wor_location = info.label

    return wor_free_char, collapsing_house_char


def _manage_gogo_recruitment(fout, collapsing_house_char):
    character_specific_locations = {
        0: {'map': 0xE2, 'x': 84, 'y': 17, 'facing': 0, 'move': True}, # Zozo tower top *Terra only*,
        #1: *Locke only*
        2: {'map': 0x120, 'x': 56, 'y': 40, 'facing': 3}, # Maranda inn *Cyan only*,  No move
        5: {'map': 0x80, 'x': 76, 'y': 31, 'facing': 1}, # Duncan's house *Sabin only*, No move
        7: {'map': 0x158, 'x': 54, 'y': 18, 'facing': 0, 'move': True}, # Thamasa exterior *Strago only*,
        8: {'map': 0x161, 'x': 27, 'y': 27, 'facing': 0, 'move': True}, # Cave in the Veldt *Relm only*
        10: {'map': 0x83, 'x': 4, 'y': 11, 'facing': 3, 'move': True}, # Gau's dad's house *Gau only*,
        #11: # *Mog only*,
        #13: # *Umaro only*,
    }

    # Can't be used for collapsing_house_char
    pre_falcon_locations = [
        {'map': 0x14A, 'x': 12, 'y': 24, 'facing': 1}, # Albrook pub No move
        {'map': 0x4E, 'x': 72, 'y': 38, 'facing': 3}, # South Figaro pub, No move
        {'map': 0x3C, 'x': 100, 'y': 16, 'facing': 0, 'move': True}, # Figaro castle library
    ]

    general_locations = [
        {'map': 0x1C, 'x': 11, 'y': 39, 'facing': 2, 'move': True}, # Narshe inn
        {'map': 0xCA, 'x': 51, 'y': 19, 'facing': 0, 'move': True}, # Jidoor relic shop
        {'map': 0xEE, 'x': 99, 'y': 18, 'facing': 3, 'move': True}, # Opera house dressing room
    ]

    candidates = list(set(range(0, 0xd)) - {0x3, 0x4, 0x6, 0x9, 0xc})    # Exclude mandatory chars, Shadow, and Gogo
    char_index = random.choice(candidates)

    location_candidates = [] + general_locations
    if char_index in character_specific_locations:
        location_candidates.append(character_specific_locations[char_index])

    if char_index != collapsing_house_char:
        location_candidates.extend(pre_falcon_locations)

    location = random.choice(location_candidates)
    gogo_location = get_location(location['map'])
    get_character(0xc).wor_location = f"{str(gogo_location)[3:]} as {get_character(char_index).newname}"
    gogo_npc = NPCBlock(None, gogo_location.locid)
    gogo_npc.npcid = len(gogo_location.npcs)

    gogo_npc.palette = get_character(char_index).palette
    gogo_npc.bg2_scroll = 0
    gogo_npc.membit = 3 # Gogo
    gogo_npc.memaddr = 0x49 # Gogo
    gogo_npc.event_addr = 0x2E5EF
    gogo_npc.x = location['x']
    gogo_npc.show_on_vehicle = 0
    gogo_npc.y = location['y']
    gogo_npc.speed = 2 # Normal
    gogo_npc.graphics = char_index
    gogo_npc.move_type = 0 # None
    gogo_npc.sprite_priority = 0 # Normal
    gogo_npc.vehicle = 0
    gogo_npc.facing = location['facing']
    gogo_npc.no_turn_when_speaking = 1
    gogo_npc.layer_priority = 2 # Foreground
    gogo_npc.special_anim = 0

    show_npcs = []
    hide_npcs = []
    for i in range(len(gogo_location.npcs)):
        hide_npcs.extend([0x42, 0x10 + i])
        show_npcs.extend([0x41, 0x10 + i])

    gogo_location.npcs.append(gogo_npc)

    middle = []
    middle2 = []

    if location.get('move', False):
        middle = [
            0xC1, # Slow
            0x83, # Move left 1
            0xE0, 0x02, # Pause for 4 * 2 (8) frames
            0xCC, # Turn up
            0xE0, 0x02, # Pause for 4 * 2 (8) frames
            0xC3, # Fast
            0x85, # Move right 2
            0xCE, # turn down
            0xE0, 0x02, # Pause for 4 * 2 (8) frames
            0x20, # front, head down,
            0xE0, 0x02, # Pause for 4 * 2 (8) frames
            0x01, # Front, standing
            0xE0, 0x02, # Pause for 4 * 2 (8) frames
            0x20, # front, head down,
            0xE0, 0x02, # Pause for 4 * 2 (8) frames
            0xCD, # turn right
            0xE0, 0x0A, # Pause for 4 * 10 (40) frames
            0xC2, # normal speed
            0xC7, # stay still while moving
            0x46, # walking, facing right
            0x83, # move left 1
            0xE0, 0x02, # Pause for 4 * 2 (8) frames
            0x47, # standing facing right
            0xE0, 0x04, # Pause for 4 * 4 (16) frames
            0x48, # walking, facing right 2
            0x83, # move left 1
            0xE0, 0x02, # Pause for 4 * 2 (8) frames
            0x47, # standing facing right
            0xE0, 0x04, # Pause for 4 * 4 (16) frames
            0xDC, # jump (low)
            0x81, # move right 1
            0xE0, 0x02, # Pause for 4 * 2 (8) frames
            0xC6, # walk while moving
            ]
        middle2 = [
            0xC1, # Slow
            0x83, # Move left 1
            0xE0, 0x02, # Pause for 4 * 2 (8) frames
            0xCE, # Turn down
            0xE0, 0x02, # Pause for 4 * 2 (8) frames
            0xC3, # Fast
            0x85, # Move right 2
            0xCC, # turn up
            0xE0, 0x02, # Pause for 4 * 2 (8) frames
            0x21, # back, head down,
            0xE0, 0x02, # Pause for 4 * 2 (8) frames
            0x04, # back, standing
            0xE0, 0x02, # Pause for 4 * 2 (8) frames
            0x21, # back, head down,
            0xE0, 0x02, # Pause for 4 * 2 (8) frames
            0xCD, # turn right
            0xE0, 0x0A, # Pause for 4 * 10 (40) frames
            0xC2, # normal speed
            0xC7, # stay still while moving
            0x46, # walking, facing right
            0x83, # move left 1
            0xE0, 0x02, # Pause for 4 * 2 (8) frames
            0x47, # standing facing right
            0xE0, 0x04, # Pause for 4 * 4 (16) frames
            0x48, # walking, facing right 2
            0x83, # move left 1
            0xE0, 0x02, # Pause for 4 * 2 (8) frames
            0x47, # standing facing right
            0xE0, 0x04, # Pause for 4 * 4 (16) frames
            0xDC, # jump (low)
            0x81, # move right 1
            0xE0, 0x02, # Pause for 4 * 2 (8) frames
            0xC6, # walk while moving
            ]

    recruit_event = Substitution()
    recruit_event.set_location(0xCE5EF)
    recruit_event.bytestring = [0xB2, 0x00, 0x50, 0x26, 0xFE] # Call subroutine, return
    recruit_event.write(fout)

    recruit_event = Substitution()
    recruit_event.set_location(0x305000)
    recruit_event.bytestring = [
        0xDE, # Load caseword with current party
        0xC0, 0xA0 + char_index, 0x01, 0xA6, 0x33, 0x02, # If target character is not in the party, jump to message blowing them off
        0xB2, 0x8D, 0xCA, 0x00, # move party to tile below gogo
        0xB2, 0x34, 0x2E, 0x01, # disable collision for party
        0xB2, 0xAC, 0xC6, 0x00, # Call subroutine CAC6AC

        0x3C, char_index, 0xFF, 0xFF, 0xFF, # Set up the party
        0x45, # Refresh objects

        0x32, 0x04,
        0xC2,  # Set vehicle/entity's event speed to normal
        0xA1,  # move right/down 1x1
        0xCC,  # turn up
        0xFF,

        0x33, 0x04,
        0xC2,  # Set vehicle/entity's event speed to normal
        0xA2,  # move left/down 1x1
        0xCC,  # turn up
        0xFF,

        0x34, 0x04,
        0xC2,  # Set vehicle/entity's event speed to normal
        0x82,  # move down 1
        0xCC,  # turn up
        0xFF,

        char_index, 0x84,
        0xCC,
        0xE0, 0x04,
        0xFF,

        0x94,

        char_index, 0x8B, # begin queue for party character 0,
        0x13, # blink
        0xE0, 0x01, # Pause for 4 * 1 (4) frames
        0xCE, # turn down
        0xE0, 0x01, # Pause for 4 * 1 (4) frames
        0x13, # blink
        0xE0, 0x01, # Pause for 4 * 1 (4) frames
        0xCE, # turn down
        0xFF, # end queue

        0x91, # Pause for 15 frames

        0x10 + gogo_npc.npcid, 0x8B, # begin queue for gogo npc
        0x13, # blink
        0xE0, 0x01, # Pause for 4 * 1 (4) frames
        0xCE, # turn down
        0xE0, 0x01, # Pause for 4 * 1 (4) frames
        0x13, # blink
        0xE0, 0x01, # Pause for 4 * 1 (4) frames
        0xCE, # turn down
        0xFF, # end queue

        0x94, # Pause for 60 frames

        char_index, 0x44 + len(middle), # begin queue for party character 0,
        0x04, # Facing up
        0xE0, 0x04, # Pause for 4 * 4 (16) frames
        0x1B, # Back, right arm raise
        0xE0, 0x01, # Pause for 4 * 1 (4) frames
        0x1C, # Back, right arm raise 2
        0xE0, 0x01, # Pause for 4 * 1 (4) frames
        0x1B, # Back, right arm raise
        0xE0, 0x01, # Pause for 4 * 1 (4) frames
        0x1C, # Back, right arm raise 2
        0xE0, 0x01, # Pause for 4 * 1 (4) frames
        0x1B, # Back, right arm raise
        0xE0, 0x02, # Pause for 4 * 2 (2) frames
        0x04, # Facing up
        0xE0, 0x08, # Pause for 4 * 8 (32) frames
        0x5B, # Back, left arm raise
        0xE0, 0x01, # Pause for 4 * 1 (4) frames
        0x5C, # Back, left arm raise 2
        0xE0, 0x01, # Pause for 4 * 1 (4) frames
        0x5B, # Back, left arm raise
        0xE0, 0x01, # Pause for 4 * 1 (4) frames
        0x5C, # Back, left arm raise 2
        0xE0, 0x01, # Pause for 4 * 1 (4) frames
        0x5B, # Back, left arm raise
        0xE0, 0x02, # Pause for 4 * 2 (2) frames
        0x04, # Facing up
        0xE0, 0x10, # Pause for 4 * 16 (64) frames
        0x23, # Front, head turned left
        0xE0, 0x10, # Pause for 4 * 16 (64) frames
    ] + middle + [
        0x18, # Mad/embarrassed
        0xE0, 0x10, # Pause for 4 * 16 (64) frames
        0x0A, # Attack pose
        0xE0, 0x10, # Pause for 4 * 16 (64) frames
        0x17, # back, arms raised
        0xE0, 0x02, # Pause for 4 * 2 (8) frames
        0xDD, # Jump (high)
        0xE0, 0x08, # Pause for 4 * 8 (32) frames
        0x09, # kneeling
        0xE0, 0x10, # Pause for 4 * 16 (64) frames
        0x04, # facing up
        0xE0, 0x08, # Pause for 4 * 8 (32) frames
        0x04, # facing up
        0xE0, 0x01, # Pause for 4 * 1 (4) frames
        0x04, # facing up
        0xE0, 0x08, # Pause for 4 * 8 (40) frames

        0x1F, # shocked
        0xFF,

        0x10 + gogo_npc.npcid, 0xc4 + len(middle2), # begin queue for gogo, wait until finished
        0x01, # Facing down
        0xE0, 0x04, # Pause for 4 * 4 (16) frames
        0x59, # Front, left arm raise
        0xE0, 0x01, # Pause for 4 * 1 (4) frames
        0x5A, # Front, left arm raise 2
        0xE0, 0x01, # Pause for 4 * 1 (4) frames
        0x59, # Front, left arm raise
        0xE0, 0x01, # Pause for 4 * 1 (4) frames
        0x5A, # Front, left arm raise 2
        0xE0, 0x01, # Pause for 4 * 1 (4) frames
        0x59, # Front, left arm raise
        0xE0, 0x02, # Pause for 4 * 2 (8) frames
        0x01, # Facing down
        0xE0, 0x08, # Pause for 4 * 8 (32) frames
        0x19, # Front, right arm raise
        0xE0, 0x01, # Pause for 4 * 1 (4) frames
        0x1A, # Front, right arm raise 2
        0xE0, 0x01, # Pause for 4 * 1 (4) frames
        0x19, # Front, right arm raise
        0xE0, 0x01, # Pause for 4 * 1 (4) frames
        0x1A, # Front, right arm raise 2
        0xE0, 0x01, # Pause for 4 * 1 (4) frames
        0x19, # Front, right arm raise
        0xE0, 0x02, # Pause for 4 * 2 (2) frames
        0x01, # Facing down
        0xE0, 0x10, # Pause for 4 * 16 (64) frames
        0x04, # Facing up
        0xE0, 0x10, # Pause for 4 * 16 (64) frames
    ] + middle2 + [
        0x04, # Facing up
        0xE0, 0x10, # Pause for 4 * 16 (64) frames
        0x0A, # Attack pose
        0xE0, 0x10, # Pause for 4 * 16 (64) frames
        0x16, # front, arms raised
        0xE0, 0x02, # Pause for 4 * 2 (8) frames
        0xDD, # Jump (high)
        0xE0, 0x08, # Pause for 4 * 8 (32) frames
        0x09, # kneeling
        0xE0, 0x10, # Pause for 4 * 16 (64) frames
        0x01, # facing down
        0xE0, 0x08, # Pause for 4 * 8 (32) frames
        0x14, # wink
        0xE0, 0x01, # Pause for 4 * 1 (4) frames
        0x01, # facing down
        0xE0, 0x08, # Pause for 4 * 8 (40) frames
        0x1F, # shocked
        0xFF,

        0x94,

        0x10 + gogo_npc.npcid, 0x1B, # begin queue for gogo npc
        0x1D,   #laugh 1
        0xE0, 0x02, # Pause for 4 * 2 (8) frames
        0x1E,   #laugh 2
        0xE0, 0x02, # Pause for 4 * 2 (8) frames
        0x1D,   #laugh 1
        0xE0, 0x02, # Pause for 4 * 2 (8) frames
        0x1E,   #laugh 2
        0xE0, 0x02, # Pause for 4 * 2 (8) frames
        0xCD, # turn right
        0xE0, 0x01, # Pause for 4 * 1 (4) frames
        0xCC, # turn up
        0xE0, 0x01, # Pause for 4 * 1 (4) frames
        0xCF, # turn left
        0xE0, 0x01, # Pause for 4 * 1 (4) frames
        0xCE, # turn down
        0xE0, 0x01, # Pause for 4 * 1 (4) frames
        0xFC, 0x0C, # branch backward 12 bytes
        0xFF,

        0x95, # pause for 120 frames
        0x37, 0x10 + gogo_npc.npcid, 0x0C, # Change npc to gogo's sprite
        0x92, # pause 30 frames
        0x10 + gogo_npc.npcid, 0x0D, # begin queue for gogo npc
        0xCD, # turn right
        0xE0, 0x02, # Pause for 4 * 2 (8) frames
        0xCC, # turn up
        0xE0, 0x02, # Pause for 4 * 2 (8) frames
        0xCF, # turn left
        0xE0, 0x02, # Pause for 4 * 2 (8) frames
        0xCE, # turn down
        0xE0, 0x02, # Pause for 4 * 2 (8) frames
        0xFF,

        0x42, 0x31,
        0x42, 0x32,
        0x42, 0x33,
        0x42, 0x34,
    ] + hide_npcs + [
        0xB2, 0xD1, 0x81, 0x01, # Branch to recruit gogo event
        0x32, 0x03,
        0xC2,
        0x83,
        0xFF,

        0x33, 0x03,
        0xC2,
        0x81,
        0xFF,

        0x34, 0x03,
        0xC2,
        0x80,
        0xFF,

        0x93,

        0x42, 0x32,
        0x42, 0x33,
        0x42, 0x34,

        0xB2, 0x34, 0x2E, 0x01, # enable collision
        0xFE, # Return
    ]
    recruit_event.write(fout)
    next_event = recruit_event.location + len(recruit_event.bytestring)

    recruit_event = Substitution()
    recruit_event.bytestring = [0x10 + gogo_npc.npcid]
    for location in [0xB81CA, 0xB8204, 0xB820E, 0xB821C, 0xB8221, 0xB822D, 0xB822F, 0xB8236]:
        recruit_event.set_location(location)
        recruit_event.write(fout)

    # Called after naming Gogo
    ptr_low = next_event & 0xFF
    ptr_mid = (next_event & 0xFF00) >> 8
    ptr_high = ((next_event - 0xA0000) & 0xFF0000) >> 16

    recruit_event = Substitution()
    recruit_event.set_location(0xB81F9)
    recruit_event.bytestring = [
        0xB2, ptr_low, ptr_mid, ptr_high, # Call subroutine below
        0xFD, 0xFD, # NOP
    ]
    recruit_event.write(fout)

    recruit_event = Substitution()
    recruit_event.set_location(next_event)
    recruit_event.bytestring = [
        0xB2, 0x15, 0xD0, 0x00, # Call subroutine to lighten screen
        0x41, 0x31, # show party members 0-3
        0x41, 0x32,
        0x41, 0x33,
        0x41, 0x34,
    ] + show_npcs + [
        0xFE #return
    ]
    recruit_event.write(fout)
    next_event = recruit_event.location + len(recruit_event.bytestring)

    # Turn off Gogo bit at beginning of game
    fout.seek(0xE0A0 + gogo_npc.memaddr)
    value = ord(fout.read(1))
    value &= ~(1 << gogo_npc.membit)
    fout.seek(0xE0A0 + gogo_npc.memaddr)
    fout.write(bytes([value]))


def _setup_alternate_zone_eater(fout, include_gau):
     # replace zone eater gogo with gau, instead of giving him for free on the airship
    zone_eater_loc = get_location(0x116)
    gau_npc = zone_eater_loc.npcs[0]
    gau_npc.graphics = 0xB # Gau
    gau_npc.palette = get_character(0xB).palette
    gau_npc.membit = 3
    gau_npc.memaddr = 0x4D
    gau_npc.event_addr = 0x14B4B

    if not include_gau:
        # TODO: If you turn off flags so that gau is on the veldt, what should be in zone eater instead?
        return

    # Turn on Gau bit at beginning of game
    fout.seek(0xE0A0 + gau_npc.memaddr)
    value = ord(fout.read(1))
    value |= (1 << gau_npc.membit)
    fout.seek(0xE0A0 + gau_npc.memaddr)
    fout.write(bytes([value]))

    text = '<GAU>: Uwao, aooh!<wait 60 frames> I’m <GAU>!<wait 60 frames><line>I’m your friend!<wait 60 frames><line>Let’s travel together!'
    set_dialogue(0x286, text)

    gau_event = Substitution()
    gau_event.set_location(0x305200)
    bytes_1 = [
        0x4B, 0x86, 0x02, # Display text box
        0xB2, 0xC1, 0xC5, 0x00, # Set caseword to number of characters in party
        0xC0, 0xA3, 0x81, 0xFF, 0xFF, 0xFF # Jump to [bytes3, location to be computed shortly]
    ]

    bytes_2 = [
        0x3D, 0x0B, # Create Gau
        0x3F, 0x0B, 0x01, # Add Gau to party
        0x45, # Refresh objects
    ]

    bytes_3 = [
        0x77, 0x0B, # Level average Gau
        0x8B, 0x0B, 0x7F, # Set Gau's HP to max
        0x8C, 0x0B, 0x7F, # Set Gau's MP to max
        0x88, 0x0B, 0x00, 0x00, # Remove all status effects from Gau
        0xD4, 0xFB, # Set Gau as available
        0x78, 0x10, # Enable ability to pass through other objects for NPC $10
        0x10, 0x04, # queue for NPC $10
        0xC2,   # Set vehicle/entity's event speed to normal
        0x82,   # Move vehicle/entity down 1 tile
        0xD1,   # Make vehicle/entity disappear
        0xFF,   # End queue
        0x3E, 0x10, # Delete NPC $10
        0xDB, 0x6B, # Turn off NPC bit
        0x45, # Refresh objects
        0xFE, # Return
    ]

    jump_location = gau_event.location + len(bytes_1) + len(bytes_2)
    ptr_low = jump_location & 0xFF
    ptr_mid = (jump_location & 0xFF00) >> 8
    ptr_high = ((jump_location - 0xA0000) & 0xFF0000) >> 16
    gau_event.bytestring = bytes_1[:-3] + [ptr_low, ptr_mid, ptr_high] + bytes_2 + bytes_3
    gau_event.write(fout)

    global alt_zone_eater_recruit
    alt_zone_eater_recruit = WoRRecruitInfo(
        label="ZoneEater",
        event_pointers=[gau_event.location + len(bytes_1) + 1, gau_event.location + len(bytes_1) + 3,
                        gau_event.location + len(bytes_1) + len(bytes_2) + 1,
                        gau_event.location + len(bytes_1) + len(bytes_2) + 3,
                        gau_event.location + len(bytes_1) + len(bytes_2) + 6,
                        gau_event.location + len(bytes_1) + len(bytes_2) + 9,],
        recruited_bit_pointers=[gau_event.location + len(bytes_1) + len(bytes_2) + 13],
        location_npcs=[(0x116, 0)],
        dialogue_pointers=[0x286],
        old_char_id=0xB,
        name_pointer=gau_event.location,
        num_name_bytes=7
    )

    next_event = gau_event.location + len(gau_event.bytestring)

    jump_location = gau_event.location
    ptr_low = jump_location & 0xFF
    ptr_mid = (jump_location & 0xFF00) >> 8
    ptr_high = ((jump_location - 0xA0000) & 0xFF0000) >> 16
    gau_event_shim = Substitution()
    gau_event_shim.set_location(0xB4B4B)
    gau_event_shim.bytestring = [
        0xB2, ptr_low, ptr_mid, ptr_high, 0xFE
    ]
    gau_event_shim.write(fout)


def manage_wor_skip(fout, wor_free_char=0xB, airship=False, dragon=False, alternate_gogo=False, esper_replacements=None):
    characters = get_characters()

    espers = [0x0, 0x1, 0x2, 0x3, 0x5, 0x6, 0x7, 0x8, 0x11, 0x13, 0x14, 0x17]
    if esper_replacements:
        espers = [esper_replacements[i].id for i in espers]
    espers = [i + 0x36 for i in espers]

    # jump to FC end cutscene for more space
    startsub0 = Substitution()
    startsub0.bytestring = bytes([0xB2, 0x1E, 0xDD, 0x00, 0xFE])
    startsub0.set_location(0xC9A4F)
    startsub0.write(fout)

    # change code at start of game to warp to wor
    wor_sub = Substitution()
    wor_sub.bytestring = bytes([
        0x6C, 0x01, 0x00, 0x91, 0xD3, 0x02, # make WoR the parent map
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
    ]) + bytes([0x40, 0x0A, 0x0A,] if dragon else [
    ]) + bytes([
        0x40, 0x06, 0x06,  # give Celes properties
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
    ] + [i for e in espers for i in (0x86, e)] + [
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
                if e.content_type == 0x40 and not e.multiple:
                    wor_sub.bytestring += bytes([0x80, e.contents])

    # give the player a basic set of items.  These items are intended to
    # reflect the items a player would probably have by the time they get this
    # far, so that they aren't missing basic supplies they would have in almost any seed.
    for line in open(WOR_ITEMS_TABLE):
        line = line.strip().split(',')
        for i in range(0, int(line[1])):
            wor_sub.bytestring += bytes([0x80, int(line[0], 16)])

    # jump to overwriting the Ramuh cutscene because we need even more space
    wor_sub.bytestring += bytes([
        0xB2, 0x49, 0x97, 0x00,
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
            if wor_free_char is None:
                setbit = 0
            else:
                bit = "2F" + hex(wor_free_char)[2]
        firstbyte = 0xD1 + int(bit[0:1], 16) * 2 - setbit
        lastbyte = int(bit[1:], 16)
        wor_sub2.bytestring += bytearray([firstbyte, lastbyte])
    if alternate_gogo:
        wor_sub2.bytestring += bytearray([0xDA, 0x4B]) # set event bit $54B
    # This is only necessary if the random wor recruitment is on, but it's harmless if not.
    wor_sub2.bytestring += bytearray([
        0x7F, 0x0C, 0x0C, # Set name for GOGO
        0x7F, 0x0D, 0x0D, # Set name for UMARO
        0x7F, 0x0A, 0x0A # Set name for MOG
        ])

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
        set_dialogue(0x9AF, text)

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
