from chestrandomizer import get_event_items
from character import get_character, get_characters
from locationrandomizer import get_location, get_locations
from utils import (WOB_TREASURE_TABLE, WOR_ITEMS_TABLE, WOB_EVENTS_TABLE,
                   read_multi, Substitution, utilrandom as random, write_multi)


class WoRRecruitInfo(object):
    def __init__(self, event_pointers, recruited_bit_pointers, location_npcs,
                 dialogue_pointers, caseword_pointers=None, prerequisite=None, special=None):
        self.event_pointers = event_pointers
        self.recruited_bit_pointers = recruited_bit_pointers
        self.location_npcs = location_npcs
        self.dialogue_pointers=dialogue_pointers
        self.caseword_pointers=caseword_pointers
        self.prerequisite = prerequisite
        self.special = special

    def write_data(self, fout):
        assert(self.char_id is not None)
        for event_pointer in self.event_pointers:
            fout.seek(event_pointer)
            fout.write(bytes([self.char_id]))
        for recruited_bit_pointer in self.recruited_bit_pointers:
            fout.seek(recruited_bit_pointer)
            fout.write(bytes([0xf0 + self.char_id]))
        for location_id, npc_id in self.location_npcs:
            location = get_location(location_id)
            npc = location.npcs[npc_id]
            npc.graphics = self.char_id
            npc.palette = get_character(self.char_id).palette
        for location in self.dialogue_pointers:
            fout.seek(location)
            fout.write(bytes([self.char_id + 2]))
        if self.caseword_pointers:
            for location in self.caseword_pointers:
                fout.seek(location)
                byte = ord(fout.read(1))
                fout.seek(location)
                fout.write(bytes([byte & 0x0F | (self.char_id << 4)]))
        if self.special:
            self.special(fout, self.char_id)

def gau_recruit(fout, char_id):
    gau_recruit_sub = Substitution()
    gau_recruit_sub.set_location(0xA5324)
    gau_recruit_sub.bytestring = bytes([0xD5, 0xFB])
    gau_recruit_sub.write(fout)

    gau_recruit_sub.set_location(0xA5310 + 2 * char_id - (2 if char_id > 6 else 0))
    gau_recruit_sub.bytestring = bytes([0xD4, 0xF0 + char_id])
    gau_recruit_sub.write(fout)

def manage_wor_recruitment(fout, random_treasure, include_gau):
    candidates = [0x00, 0x01, 0x02, 0x05, 0x07, 0x08]
    locke_event_pointers = [0xc2c48, 0xc2c51, 0xc2c91, 0xc2c9d, 0xc2c9e, 0xc2caf, 0xc2cb8, 0xc2cc5, 0xc2cca, 0xc2cd8, 0xc2ce3, 0xc2ce9, 0xc2cee, 0xc2cf4, 0xc2cfa, 0xc2d0b, 0xc2d33, 0xc2e32, 0xc2e4a, 0xc2e80, 0xc2e86, 0xc2e8b, 0xc2e91, 0xc2ea5, 0xc2eb1, 0xc2ec4, 0xc2f0b, 0xc2fe1, 0xc3102, 0xc3106, 0xc3117, 0xc311d, 0xc3124, 0xc3134, 0xc313d, 0xc3163, 0xc3183, 0xc3185, 0xc3189, 0xc318b, 0xc318e, 0xc3191, 0xc3197, 0xc31c7, 0xc31cb, 0xc31e2, 0xc31e8, 0xc31ed, 0xc31f2, 0xc31f8, 0xc3210, 0xc3215, 0xc321d, 0xc3229, 0xc322f, 0xc3235, 0xc323b]
    locke_event_pointers_2 = [0xc3244, 0xc324a, 0xc324f, 0xc3258, 0xc326a]
    if random_treasure:
        locke_event_pointers_2 = [p + 12 for p in locke_event_pointers_2]
    recruit_info = [
        # Phoenix Cave / Locke
        WoRRecruitInfo(
            event_pointers=locke_event_pointers + locke_event_pointers_2,
            recruited_bit_pointers=[0xc3195],
            location_npcs=[(0x139, 0)],
            dialogue_pointers=[0xe8a06, 0xe8a44, 0xe8ae6, 0xe8b2d, 0xea365, 0xea368, 0xea3ad, 0xea430, 0xea448, 0xea528, 0xea561, 0xea5f1, 0xea617, 0xea668, 0xea674, 0xea6d4, 0xea6e7, 0xea7ac, 0xea7af, 0xea7ba, 0xea7bd, 0xea86c, 0xea886]),
        # Mt. Zozo / Cyan
        WoRRecruitInfo(
            event_pointers=[0xc429c, 0xc429e, 0xc42a2, 0xc42a4, 0xc42a7, 0xc42aa],
            recruited_bit_pointers=[0xc42ae],
            location_npcs=[(0xb4, 8), (0xb5, 2)],
            dialogue_pointers=[0xe9a1e, 0xe9b85, 0xe9bdf, 0xe9c31, 0xe9c34, 0xe9c46, 0xe9c49, 0xe9ca0, 0xe9cc9, 0xe9cde, 0xe9cf4, 0xe9cff, 0xe9d67, 0xe9f53, 0xe9fc5, 0xe9fde]),
        # Collapsing House / Sabin
        WoRRecruitInfo(
            event_pointers=[0xa6c0e, 0xc5aa8, 0xc5aaa, 0xc5aae, 0xc5ab0, 0xc5ab3, 0xc5ab6],
            recruited_bit_pointers=[0xc5aba],
            location_npcs=[(0x131, 1)],
            dialogue_pointers=[0xe6326, 0xe6329, 0xe6341, 0xe6349, 0xe634d, 0xe636e, 0xe63ce, 0xe63f7, 0xe6400, 0xe640c, 0xe6418, 0xe6507, 0xe80b8, 0xe81ad],
            caseword_pointers=[0xa6af1, 0xa6b0c, 0xa6bbd]),
        # Fanatics' Tower / Strago
        WoRRecruitInfo(
            event_pointers=[0xc5418, 0xc541a, 0xc541e, 0xc5420, 0xc5423, 0xc5426],
            recruited_bit_pointers=[0xc542a],
            location_npcs=[(0x16a, 3)],
            prerequisite=[0x08],
            dialogue_pointers=[0xe680d, 0xe6841, 0xe687e, 0xe68be]),
        # Owzer's House / Relm
        WoRRecruitInfo(
            event_pointers=[0xb4e09, 0xb4e0b, 0xb4e0f, 0xb4e11, 0xb4e14, 0xb4e17],
            recruited_bit_pointers=[0xb4e1b],
            location_npcs=[(0x161, 3), (0x15d, 21), (0xd0, 3)],
            dialogue_pointers=[0xea190, 0xeb351, 0xeb572, 0xeb6c1, 0xeb6d2, 0xeb6fc, 0xeb752, 0xeb81b, 0xebd2b, 0xebd7a, 0xebdff, 0xebe31, 0xebe72, 0xebe9c]),
        # Mobliz / Terra
        WoRRecruitInfo(
            event_pointers=[0xc49d1, 0xc49d3, 0xc49da, 0xc49de, 0xc49e2, 0xc4a01, 0xc4a03, 0xc4a0c, 0xc4a0d, 0xc4a2b, 0xc4a37, 0xc4a3a, 0xc4a43, 0xc4a79, 0xc4a7b, 0xc4ccf, 0xc4cd1, 0xc4cd5, 0xc4cd7, 0xc4cdb, 0xc4cde, 0xc4ce1, 0xc4ce5, 0xc4cf4, 0xc4cf6, 0xc5040, 0xc5042, 0xc5048, 0xc504a, 0xc504d, 0xc5050], 
            recruited_bit_pointers=[0xc4cd9, 0xc4cfa, 0xc5046],
            location_npcs=[(0x09A, 1), (0x09A, 2), (0x096, 0), (0x09E, 13)],
            dialogue_pointers=[0xe6ae1, 0xe6af9, 0xe6b1f, 0xe6b48, 0xe6b4d, 0xe6b6b, 0xe6bc5, 0xe6c05, 0xe6c36, 0xe6c5d, 0xe6cb7, 0xe6d26, 0xe6d58, 0xe6d71, 0xe6d9c, 0xe6de0, 0xe6de5, 0xe6ea3, 0xe6f63, 0xe6f70, 0xe702e, 0xe70f7, 0xe70ff, 0xe7103, 0xe7110, 0xe7189, 0xe720f, 0xe7230, 0xe72c0, 0xe72ff, 0xe7347, 0xe73ba, 0xe746d]),
    ]

    if include_gau:
        candidates.append(0x0B)
        recruit_info.append(WoRRecruitInfo([], [], [], [0xe9dd2], special=gau_recruit))
        
    restricted_info = [info for info in recruit_info if info.prerequisite]
    unrestricted_info = [info for info in recruit_info if not info.prerequisite]
    recruit_info = restricted_info + unrestricted_info
    wor_free_char = 0xB  # gau
    for info in recruit_info:
        valid_candidates = candidates
        if info.prerequisite:
            valid_candidates = [c for c in candidates if c not in info.prerequisite]
        candidate = random.choice(valid_candidates)
        candidates.remove(candidate)
        info.char_id = candidate
        if info.special == gau_recruit:
            wor_free_char = candidate
        info.write_data(fout)
        
    return wor_free_char


def manage_wor_skip(fout, wor_free_char=0xB):
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

    wor_sub2.bytestring += bytearray([0x6B, 0x01, 0x00, 0x91, 0xD3, 0x00, # go to WoR
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