from os import path
from collections import defaultdict
import random
import re

try:
    from sys import _MEIPASS
    MEI = True
    tblpath = path.join(_MEIPASS, "tables")
except ImportError:
    # This is new
    # this prepends the absolute file path of the parent/calling script
    #   to the 'tables' directory - GreenKnight5
    bundle_dir = path.dirname(path.abspath(__file__))
    tblpath = path.join(bundle_dir, "tables")

    # tblpath = "tables"
    MEI = False

ENEMY_TABLE = path.join(tblpath, "enemycodes.txt")
ITEM_TABLE = path.join(tblpath, "itemcodes.txt")
SPELL_TABLE = path.join(tblpath, "spellcodes.txt")
SPELLBANS_TABLE = path.join(tblpath, "spellbans.txt")
ESPER_TABLE = path.join(tblpath, "espercodes.txt")
CHEST_TABLE = path.join(tblpath, "chestcodes.txt")
COMMAND_TABLE = path.join(tblpath, "commandcodes.txt")
CHAR_TABLE = path.join(tblpath, "charcodes.txt")
TEXT_TABLE = path.join(tblpath, "text.txt")
SHORT_TEXT_TABLE = path.join(tblpath, "shorttext.txt")
DIALOGUE_TEXT_TABLE = path.join(tblpath, "dialoguetext.txt")
ENEMY_NAMES_TABLE = path.join(tblpath, "enemynames.txt")
MODIFIERS_TABLE = path.join(tblpath, "moves.txt")
MOVES_TABLE = path.join(tblpath, "moves.txt")
LOCATION_TABLE = path.join(tblpath, "locationformations.txt")
LOCATION_PALETTE_TABLE = path.join(tblpath, "locationpaletteswaps.txt")
BATTLE_BG_PALETTE_TABLE = path.join(tblpath, "battlebgpalettes.txt")
CHARACTER_PALETTE_TABLE = path.join(tblpath, "charpaloptions.txt")
EVENT_PALETTE_TABLE = path.join(tblpath, "eventpalettes.txt")
MAP_NAMES_TABLE = path.join(tblpath, "mapnames.txt")
USED_LOCATIONS_TABLE = path.join(tblpath, "usedlocs.txt")
UNUSED_LOCATIONS_TABLE = path.join(tblpath, "unusedlocs.txt")
TOWER_LOCATIONS_TABLE = path.join(tblpath, "finaldungeonmaps.txt")
TOWER_CHECKPOINTS_TABLE = path.join(tblpath, "finaldungeoncheckpoints.txt")
ANCIENT_CHECKPOINTS_TABLE = path.join(tblpath, "ancientcheckpoints.txt")
MAP_BATTLE_BG_TABLE = path.join(tblpath, "mapbattlebgs.txt")
ENTRANCE_REACHABILITY_TABLE = path.join(tblpath, "reachability.txt")
FINAL_BOSS_AI_TABLE = path.join(tblpath, "finalai.txt")
TREASURE_ROOMS_TABLE = path.join(tblpath, "treasurerooms.txt")
NAMEGEN_TABLE = path.join(tblpath, "generator.txt")
CUSTOM_ITEMS_TABLE = path.join(tblpath, "customitems.txt")
SHOP_TABLE = path.join(tblpath, "shopcodes.txt")
LOCATION_MAPS_TABLE = path.join(tblpath, "locationmaps.txt")
WOB_TREASURE_TABLE = path.join(tblpath, "wobonlytreasure.txt")
WOR_ITEMS_TABLE = path.join(tblpath, "worstartingitems.txt")
WOB_EVENTS_TABLE = path.join(tblpath, "wobeventbits.txt")
RIDING_SPRITE_TABLE = path.join(tblpath, "ridingsprites.txt")
SKIP_EVENTS_TABLE = path.join(tblpath, "skipevents.txt")
DIVERGENT_TABLE = path.join(tblpath, "divergentedits.txt")
MAGICITE_TABLE = path.join(tblpath, "magicite.txt")

custom_path = "custom"
MALE_NAMES_TABLE = path.join(custom_path, "malenames.txt")
FEMALE_NAMES_TABLE = path.join(custom_path, "femalenames.txt")
SPRITE_REPLACEMENT_TABLE = path.join(custom_path, "spritereplacements.txt")
MOOGLE_NAMES_TABLE = path.join(custom_path, "mooglenames.txt")
DANCE_NAMES_TABLE = path.join(custom_path, "dancenames.txt")
PASSWORDS_TABLE = path.join(custom_path, "passwords.txt")
POEMS_TABLE = path.join(custom_path, "poems.txt")

def open_mei_fallback(filename, mode='r', encoding=None):
    if not MEI:
        return open(filename, mode, encoding=encoding)

    try:
        f = open(filename, mode, encoding=encoding)
    except IOError:
        f = open(path.join(_MEIPASS, filename), mode, encoding=encoding)
    return f


class Substitution:
    location = None
    bytestring = None

    @property
    def size(self):
        return len(self.bytestring)

    def set_location(self, location):
        self.location = location

    def write(self, fout):
        fout.seek(self.location)
        fout.write(bytes(self.bytestring))


class AutoLearnRageSub(Substitution):
    def __init__(self, require_gau):
        self.require_gau = require_gau

    @property
    def bytestring(self):
        # NOTE: This must be placed at a location called from C2/5EE5
        bs = []
        if self.require_gau:
            bs += [0xAD, 0x0B, 0x30, 0x30, 0x03]
        bs += [0x20, 0x07, 0x4A, 0xAD, 0x0A, 0x30, 0x60]
        return bytes(bs)

    def write(self, fout):
        learn_leap_sub = Substitution()
        learn_leap_sub.bytestring = bytes([0xEA] * 7)
        learn_leap_sub.set_location(0x2543E)
        learn_leap_sub.write(fout)

        gau_cant_appear_sub = Substitution()
        gau_cant_appear_sub.bytestring = bytes([0x80, 0x0C])
        gau_cant_appear_sub.set_location(0x22FB5)
        gau_cant_appear_sub.write(fout)

        vict_sub = Substitution()
        vict_sub.bytestring = bytes([0x20]) + int2bytes(self.location, length=2)
        vict_sub.set_location(0x25EE5)
        vict_sub.write(fout)

        super(AutoLearnRageSub, self).write(fout)


texttable = {}
f = open(TEXT_TABLE)
for line in f:
    line = line.strip()
    char, value = tuple(line.split())
    texttable[char] = value
texttable[' '] = 'FE'
f.close()


def name_to_bytes(name, length):
    name = [hex2int(texttable[c]) for c in name]
    assert len(name) <= length
    while len(name) < length:
        name.append(0xFF)
    return bytes(name)


shorttexttable = {}
f = open(SHORT_TEXT_TABLE)
for line in f:
    line = line.strip()
    char, value = tuple(line.split())
    shorttexttable[char] = value
shorttexttable[' '] = 'FF'
f.close()


dialoguetexttable = {}
f = open(DIALOGUE_TEXT_TABLE, encoding='utf8')
for line in f:
    line = line.strip('\n')
    if not line:
        continue
    value, string = tuple(line.split('=', 1))
    if string not in dialoguetexttable:
        dialoguetexttable[string] = value
f.close()


reverse_dialoguetexttable = {v: k for k, v in dialoguetexttable.items()}
reverse_dialoguetexttable["1104"] = "<wait 60 frames>"


def hex2int(hexstr):
    return int(hexstr, 16)


def shuffle_key_values(d):
    keys = list(d.keys())
    random.shuffle(keys)
    shuffled = dict(zip(keys, d.values()))
    d.update(shuffled)

def dialogue_to_bytes(text, null_terminate=True):
    bs = []
    i = 0
    while i < len(text):
        if text[i] == " ":
            spaces = re.match(" +", text[i:]).group(0)
            count = len(spaces)
            j = i + count
            hexstr = dialoguebytetable.get(text[i:j], "")
            if not hexstr:
                hexstr = dialoguebytetable.get(text[i])
                j = i + 1
            i = j
        elif text[i] == "<":
            j = text.find(">", i) + 1
            hexstr = dialoguetexttable.get(text[i:j], "")
            i = j
        elif i < len(text) - 1 and text[i:i+2] in dialoguetexttable:
            hexstr = dialoguetexttable[text[i:i+2]]
            i += 2
        else:
            hexstr = dialoguetexttable[text[i]]
            i += 1

        if hexstr != "":
            bs.extend(bytes.fromhex(hexstr))

    if null_terminate and bs[-1] != 0x0:
        bs.append(0x0)
    return bytes(bs)


def bytes_to_dialogue(bs):
    text = []
    i = 0
    while i < len(bs):
        c = bs[i]
        if c == b'\x00':
            break
        d = bs[i+1] if i + 1 < len(bs) else None
        if d and f"{c:02X}{d:02X}" in reverse_dialoguetexttable:
            text.append(reverse_dialoguetexttable[f"{c:02X}{d:02X}"])
            i += 2
        elif f"{c:02X}" in reverse_dialoguetexttable:
            text.append(reverse_dialoguetexttable[f"{c:02X}"])
            i += 1
        else:
            print(bs[i], f"{c:02X}{d:02X}" if d else f"{c:02X}")
            raise ValueError

    return "".join(text)


def get_long_battle_text_pointer(f, index):
    base = 0x100000
    ptrs_start = 0x10D000
    f.seek(ptrs_start + index * 2)
    ptr = read_multi(f)
    ptr += base
    return ptr


def get_long_battle_text_index(f, address):
    base = 0x100000
    ptrs_start = 0x10D000
    ptrs_end = 0x10D200
    prev = 0
    for index, ptr_ptr in enumerate(range(ptrs_start, ptrs_end, 2)):
        f.seek(ptr_ptr)
        ptr = read_multi(f) + base
        if ptr > address:
            return index - 1
    return -1


def get_dialogue_pointer(f, index):
    f.seek(0xCE600)
    increment_index = read_multi(f)
    base = 0xD0000 if index <= increment_index else 0xE0000
    ptrs_start = 0xCE602
    f.seek(ptrs_start + index * 2)
    ptr = read_multi(f)
    ptr += base
    return ptr


def get_dialogue_index(f, address):
    f.seek(0xCE600)
    increment_index = read_multi(f)
    ptrs_start = 0xCE602
    ptrs_end = 0xD0000
    prev = 0
    for index, ptr_ptr in enumerate(range(ptrs_start, ptrs_end, 2)):
        base = 0xD0000 if index <= increment_index else 0xE0000
        f.seek(ptr_ptr)
        ptr = read_multi(f) + base
        if ptr > address:
            return index - 1
    return -1


battlebg_palettes = {}
f = open(BATTLE_BG_PALETTE_TABLE)
for line in f:
    line = line.strip()
    bg, palette = tuple(line.split())
    bg, palette = hex2int(bg), hex2int(palette)
    battlebg_palettes[bg] = palette
f.close()


def int2bytes(value, length=2, reverse=True):
    # reverse=True means high-order byte first
    bs = []
    while value:
        bs.append(value & 255)
        value = value >> 8

    while len(bs) < length:
        bs.append(0)

    if not reverse:
        bs = reversed(bs)

    return bytes(bs[:length])


def read_multi(f, length=2, reverse=True):
    vals = list(f.read(length))
    if reverse:
        vals = list(reversed(vals))
    value = 0
    for val in vals:
        value = value << 8
        value = value | val
    return value


def write_multi(f, value, length=2, reverse=True):
    vals = []
    while value:
        vals.append(value & 0xFF)
        value = value >> 8
    if len(vals) > length:
        raise Exception("Value length mismatch.")

    while len(vals) < length:
        vals.append(0x00)

    if not reverse:
        vals = reversed(vals)

    f.write(bytes(vals))


utilrandom = random.Random()
utran = utilrandom
random = utilrandom

RANDOM_MULTIPLIER = 1

def set_randomness_multiplier(multiplier):
    global RANDOM_MULTIPLIER
    RANDOM_MULTIPLIER = multiplier

def clamp(n, lower_bound, upper_bound):
    assert lower_bound <= upper_bound
    return max(lower_bound, min(n, upper_bound))

def mutate_index(index, length, continuation=None, basic_range=None,
                 extended_range=None, disregard_multiplier=False):
    if length == 0:
        return None

    highest = length - 1
    if RANDOM_MULTIPLIER is None and not disregard_multiplier:
        return utran.randint(0, highest)

    continuation = continuation or [True, False]
    basic_range = basic_range or (-3, 3)
    extended_range = extended_range or (-1, 1)
    if not disregard_multiplier:
        basic_range = tuple(int(round(RANDOM_MULTIPLIER*v))
                            for v in basic_range)
        extended_range = tuple(int(round(RANDOM_MULTIPLIER*v))
                               for v in extended_range)

    index = utran.randint(*(clamp(index + b, 0, highest) for b in basic_range))
    while utran.choice(continuation):
        index = utran.randint(*(clamp(index + e, 0, highest) for e in extended_range))

    return index


def generate_swapfunc(swapcode=None):
    if swapcode is None:
        swapcode = utran.randint(0, 7)

    f = lambda w: w
    g = lambda w: w
    h = lambda w: w
    if swapcode & 1:
        f = lambda x_y_z: (x_y_z[1], x_y_z[0], x_y_z[2])
    if swapcode & 2:
        g = lambda x_y_z1: (x_y_z1[2], x_y_z1[1], x_y_z1[0])
    if swapcode & 4:
        h = lambda x_y_z2: (x_y_z2[0], x_y_z2[2], x_y_z2[1])
    swapfunc = lambda w: f(g(h(w)))

    return swapfunc


def shift_middle(triple, degree, ungray=False):
    low, medium, high = tuple(sorted(triple))
    triple = list(triple)
    mediumdex = triple.index(medium)
    if ungray:
        lowdex, highdex = triple.index(low), triple.index(high)
        while utran.choice([True, False]):
            low -= 1
            high += 1

        low = max(0, low)
        high = min(31, high)

        triple[lowdex] = low
        triple[highdex] = high

    if degree < 0:
        value = low
    else:
        value = high
    degree = abs(degree)
    a = (1 - (degree/90.0)) * medium
    b = (degree/90.0) * value
    medium = a + b
    medium = int(round(medium))
    triple[mediumdex] = medium
    return tuple(triple)


def get_palette_transformer(use_luma=False, always=None, middle=True,
                            basepalette=None):
    def get_ratio(a, b):
        if a > 0 and b > 0:
            return max(a, b) / float(min(a, b))
        if abs(a-b) <= 1:
            return 1.0
        return 9999

    def color_to_components(color):
        blue = (color & 0x7c00) >> 10
        green = (color & 0x03e0) >> 5
        red = color & 0x001f
        return (red, green, blue)

    def components_to_color(xxx_todo_changeme):
        (red, green, blue) = xxx_todo_changeme
        return red | (green << 5) | (blue << 10)

    if always is not None and basepalette is not None:
        raise Exception("'always' argument incompatible with 'basepalette'")

    swapmap = {}
    if basepalette is not None and not use_luma:
        threshold = 1.2

        def color_to_index(color):
            red, green, blue = color_to_components(color)
            a = red >= green
            b = red >= blue
            c = green >= blue
            d = get_ratio(red, green) >= threshold
            e = get_ratio(red, blue) >= threshold
            f = get_ratio(green, blue) >= threshold

            index = (d << 2) | (e << 1) | f
            index |= ((a and not d) << 5)
            index |= ((b and not e) << 4)
            index |= ((c and not f) << 3)

            return index

        colordict = defaultdict(set)
        for color in basepalette:
            index = color_to_index(color)
            colordict[index].add(color)

        saturated = dict((k, v) for (k, v) in colordict.items() if k & 0x7)
        satlist = sorted(saturated)
        random.shuffle(satlist)
        grouporder = sorted(satlist, key=lambda k: len(saturated[k]),
                            reverse=True)
        if grouporder:
            dominant = grouporder[0]
            domhue, domsat = dominant >> 3, dominant & 0x7
            for key in grouporder[1:]:
                colhue, colsat = key >> 3, key & 0x7
                if (domhue ^ colhue) & (domsat | colsat) == 0:
                    continue
                secondary = key
                break
            else:
                secondary = dominant
            sechue, secsat = secondary >> 3, secondary & 0x7
        else:
            dominant, domhue, domsat = 0, 0, 0
            secondary, sechue, secsat = 0, 0, 0

        while True:
            domswap = random.randint(0, 7)
            secswap = random.randint(0, 7)
            tertswap = random.randint(0, 7)
            if domswap == secswap:
                continue
            break

        for key in colordict:
            colhue, colsat = key >> 3, key & 0x7
            if ((domhue ^ colhue) & (domsat | colsat)) == 0:
                if ((sechue ^ colhue) & (secsat | colsat)) == 0:
                    swapmap[key] = random.choice([domswap, secswap])
                else:
                    swapmap[key] = domswap
            elif ((sechue ^ colhue) & (secsat | colsat)) == 0:
                swapmap[key] = secswap
            elif ((domhue ^ colhue) & domsat) == 0:
                if ((sechue ^ colhue) & secsat) == 0:
                    swapmap[key] = random.choice([domswap, secswap])
                else:
                    swapmap[key] = domswap
            elif ((sechue ^ colhue) & secsat) == 0:
                swapmap[key] = secswap
            elif ((domhue ^ colhue) & colsat) == 0:
                if ((sechue ^ colhue) & colsat) == 0:
                    swapmap[key] = random.choice([domswap, secswap])
                else:
                    swapmap[key] = domswap
            elif ((sechue ^ colhue) & colsat) == 0:
                swapmap[key] = secswap
            else:
                swapmap[key] = tertswap

    elif basepalette is not None and use_luma:
        def color_to_index(color):
            red, green, blue = color_to_components(color)
            index = red + green + blue
            return index

        values = []
        for color in basepalette:
            index = color_to_index(color)
            values.append(index)
        values = sorted(values)
        low, high = min(values), max(values)
        median = values[len(values)//2]
        clusters = [set([low]), set([high])]
        done = set([low, high])
        if median not in done and random.choice([True, False]):
            clusters.append(set([median]))
            done.add(median)

        to_cluster = sorted(basepalette)
        random.shuffle(to_cluster)
        for color in to_cluster:
            index = color_to_index(color)
            if index in done:
                continue
            done.add(index)

            def cluster_distance(cluster):
                distances = [abs(index-i) for i in cluster]
                return sum(distances) // len(distances)
                nearest = min(cluster, key=lambda x: abs(x-index))
                return abs(nearest-index)

            chosen = min(clusters, key=cluster_distance)
            chosen.add(index)

        swapmap = {}
        for cluster in clusters:
            swapcode = random.randint(0, 7)
            for index in cluster:
                try:
                    assert index not in swapmap
                except:
                    import pdb
                    pdb.set_trace()
                swapmap[index] = swapcode

        remaining = [i for i in range(94) if i not in swapmap.keys()]
        random.shuffle(remaining)

        def get_nearest_swapcode(index):
            nearest = min(swapmap, key=lambda x: abs(x-index))
            return nearest

        for i in remaining:
            nearest = get_nearest_swapcode(i)
            swapmap[i] = swapmap[nearest]

    else:
        def color_to_index(unused_color):
            return 0

        if always:
            swapmap[0] = random.randint(1, 7)
        else:
            swapmap[0] = random.randint(0, 7)

    for key in swapmap:
        swapmap[key] = generate_swapfunc(swapmap[key])

    if middle:
        degree = utran.randint(-75, 75)

    def palette_transformer(raw_palette, single_bytes=False):
        if single_bytes:
            raw_palette = list(zip(raw_palette, raw_palette[1:]))
            raw_palette = [p for (i, p) in enumerate(raw_palette) if not i % 2]
            raw_palette = [(b << 8) | a for (a, b) in raw_palette]
        transformed = []
        for color in raw_palette:
            index = color_to_index(color)
            swapfunc = swapmap[index]
            red, green, blue = color_to_components(color)
            red, green, blue = swapfunc((red, green, blue))
            if middle:
                red, green, blue = shift_middle((red, green, blue), degree)
            color = components_to_color((red, green, blue))
            transformed.append(color)
        if single_bytes:
            major = [p >> 8 for p in transformed]
            minor = [p & 0xFF for p in transformed]
            transformed = []
            for a, b in zip(minor, major):
                transformed.append(a)
                transformed.append(b)
        return transformed

    return palette_transformer

huetranstable = {
    0: [31, 0, 0],
    60: [31, 31, 0],
    120: [0, 31, 0],
    180: [0, 31, 31],
    240: [0, 0, 31],
    300: [31, 0, 31],
    }

def hue_rgb(deg):
    rgbtweentable = {0: 2, 60: -1, 120: 3, 180: -2, 240: 1, 300: -3}
    while deg >= 360:
        deg -= 360
    remainder = deg % 60
    color = deg - remainder
    rgb = list(huetranstable[color])
    tween = rgbtweentable[color]
    descending = False
    if tween < 0:
        descending = True
    tween = abs(tween) - 1
    remainder = int((((remainder + 1) * 32) / 60.0) - 1)
    remainder = min(31, max(0, remainder))
    if descending:
        remainder = 31 - remainder
    rgb[tween] = remainder
    return rgb

def shuffle_char_hues(hues):
    while True:
        tryagain = False
        random.shuffle(hues)
        for c in range(0, 18, 3): #check for too close colors vertically (within one palette)
            chunk = hues[c:c+3]
            chunk += [h+360 for h in chunk]
            for i in range(6):
                for j in range(i+1, 6):
                    if abs(chunk[i]-chunk[j]) <= 16:
                        tryagain = True
                        break
                if tryagain:
                    break
            if tryagain:
                break
        if tryagain:
            continue
        for c in range(0, 3): #check for too close colors horizontally (same element on different palettes)
            chunk = hues[c:len(hues):3]
            chunk += [h+360 for h in chunk]
            for i in range(12):
                for j in range(i+1, 12):
                    if abs(chunk[i]-chunk[j]) <= 16:
                        tryagain = True
                        break
                if tryagain:
                    break
            if tryagain:
                break
        if tryagain:
            continue
        break
    return list(map(hue_rgb, hues))

def generate_character_palette(skintones_unused=None, char_hues_unused=None, trance=False):

    def hue_deg(rgb):
        tweens = [i for i in rgb if i not in [0, 31]]
        assert len(tweens) <= 1
        transtable = {tuple(v): k for k, v in huetranstable.items()}
        if not tweens:
            return transtable[tuple(rgb)]
        shrunk = tuple([(31 if i == 31 else 0) for i in rgb])
        grown = tuple([(0 if i == 0 else 31) for i in rgb])
        bounds = (transtable[shrunk], transtable[grown])
        if 300 in bounds and 0 in bounds:
            prev = 300
            next = 360
        else:
            prev = min(bounds)
            next = max(bounds)
        descending = prev != bounds[0]
        if descending:
            return int(next - (((tweens[0] + 1) * 60) / 32.0) - 1)
        return int((((tweens[0] + 1) * 60) / 32.0) - 1 + prev)

    def guess_hue(rgb):
        assert len(rgb) >= 3
        order = [rgb.index(min(rgb)), rgb.index(max(rgb))]
        order = [order[0], [n for n in [0, 1, 2] if n not in order][0], order[1]]
        color = list(rgb)
        color = [c-color[order[0]] for c in color]
        pct = color[order[1]] / float(color[order[2]])
        pure = [0, 0, 0]
        pure[order[1]] = int(31 * pct)
        pure[order[2]] = 31
        return hue_deg(pure)

    def components_to_color(components):
        (red, green, blue) = components
        return red | (green << 5) | (blue << 10)

    def color_to_components(color):
        blue = (color & 0x7C00) >> 10
        green = (color & 0x03E0) >> 5
        red = color & 0x001F
        return (red, green, blue)

    def scalecolor(color, bot, top):
        red, green, blue = color_to_components(color)
        width = top - bot
        lightest = max(red, green, blue)
        red = int(round(width*(float(red)/float(lightest)))) + bot
        green = int(round(width*(float(green)/float(lightest)))) + bot
        blue = int(round(width*(float(blue)/float(lightest)))) + bot
        return components_to_color((red, green, blue))

    def hsv_approx(hue, sat, val):
        floor = (1 - (float(sat) / 100)) * 31 / 2
        ceil = 31 - floor
        new_color = list(color_to_components(scalecolor(components_to_color(tuple(hue)),
                                                        int(floor), int(ceil))))
        skewtoward = [0, 0, 0] if val <= 50 else [31, 31, 31]
        skewamount = 1 - (float(val) / 50) if val <= 50 else (float(val) / 50) - 1
        for i, c in enumerate(new_color):
            new_color[i] = int(c * (1 - skewamount) + skewtoward[i] * skewamount)
        new_color = [(c if c <= 31 else 31) for c in new_color]
        new_color = [(c if c >= 0 else 0) for c in new_color] # just in case
        return new_color

    def nudge_hue(hue): #designed for 'pure' hue: one 31, one 0, one anything
        new_color = hue[:]
        if len([h for h in hue if h not in [0, 31]]) > 0:
            new_color = [(h if h in [0, 31] else h + random.randint(-2, 2)) for h in hue]
        elif len([h for h in hue if h == 31]) >= 2:
            nudge_idx = random.choice([i for i, h in enumerate(hue) if h == 31])
            new_color[nudge_idx] -= random.randint(0, 3)
        elif 0 in hue:
            nudge_idx = random.choice([i for i, h in enumerate(hue) if h == 0])
            new_color[nudge_idx] += random.randint(0, 3)
        new_color = [(c if c <= 31 else 31) for c in new_color]
        new_color = [(c if c >= 0 else 0) for c in new_color] # just in case
        return new_color

    def nudge_apart(dynamic, static, threshold=10):
        if static - dynamic >= 360-threshold:
            dynamic += 360
        if dynamic - static >= 360-threshold:
            static += 360
        if dynamic in range(static, static+threshold):
            dynamic = static + threshold
        elif dynamic in range(static, static-threshold):
            dynamic = static - threshold
        while dynamic >= 360:
            dynamic -= 360
        return dynamic

    if not trance:
        skintone = skintones_unused.pop(0)
        skin_hue = guess_hue(list(skintone[0]))
        hair_hue = char_hues_unused.pop(0)
        cloth_hue_deg = nudge_apart(hue_deg(char_hues_unused.pop(0)), skin_hue)
        cloth_hue = hue_rgb(cloth_hue_deg)
        acc_hue = hue_rgb(nudge_apart(hue_deg(char_hues_unused.pop(0)), skin_hue))

        new_palette = [[0, 0, 0], [3, 3, 3]] + list(skintone)
        new_palette = list(map(components_to_color, new_palette)) * 3

        hair_sat = random.choice([random.randint(15, 30), random.randint(20, 50), random.randint(20, 75)])
        hair_light = random.choice([random.randint(60, 80), random.randint(55, 90)])
        hair_dark = random.randint(int(hair_light * .5), int(hair_light * .65)) if hair_sat < 40 else \
                    random.randint(int(hair_light * .45), int(hair_light * .52))
        hair_highlight = random.randint(93, 100)
        hair_shadow = random.randint(10, 22)

        cloth_light = random.randint(32, max(42, hair_dark + 10))
        cloth_dark = random.randint(int(cloth_light * .6), int(cloth_light * .72))
        cloth_sat = random.choice([random.randint(10, 50), random.randint(30, 60), random.randint(10, 85)]) if cloth_light < 40 else \
                    random.choice([random.randint(10, 40), random.randint(25, 55)])
        while hair_light >= hair_highlight - 8:
            hair_light -= 1
            if hair_light <= int(hair_dark / .65):
                break
        while hair_dark <= hair_shadow + 5:
            hair_shadow -= 1
            if hair_shadow <= 10:
                break
        while cloth_dark > hair_dark - 3:
            hair_dark += 1
        cycle, done = 0, 0
        if 210 <= cloth_hue_deg <= 270:
            mindelta = 8
        elif 180 <= cloth_hue_deg <= 300:
            mindelta = 6
        else: mindelta = 4
        while cloth_dark < hair_shadow + mindelta:
            if cycle < 1:
                cycle = 1
            if cycle == 1:
                if cloth_dark < int(cloth_light * .72):
                    cloth_dark += 1
                elif done & 0b11:
                    break
                else:
                    cycle = 2
            elif cycle == 2:
                if hair_shadow > 10:
                    hair_shadow -= 1
                else:
                    done |= 0b10
                cycle = 3
            elif cycle == 3:
                if cloth_light < hair_dark + 5:
                    cloth_light += 1
                else:
                    done |= 0b01
                cycle = 1

        new_palette[2] = components_to_color(hsv_approx(nudge_hue(hair_hue), random.randint(80, 97), random.randint(93, 98)))
        new_palette[3] = components_to_color(hsv_approx(nudge_hue(hair_hue), random.randint(10, 100), hair_shadow))
        new_palette[4] = components_to_color(hsv_approx(nudge_hue(hair_hue), hair_sat + random.randint(-7, 8), hair_light))
        new_palette[5] = components_to_color(hsv_approx(nudge_hue(hair_hue), hair_sat + random.randint(-7, 8), hair_dark))
        new_palette[8] = components_to_color(hsv_approx(nudge_hue(cloth_hue), cloth_sat + random.randint(-7, 8), cloth_light))
        new_palette[9] = components_to_color(hsv_approx(nudge_hue(cloth_hue), cloth_sat + random.randint(-7, 8), cloth_dark))

        acc_sat = random.choice([random.randint(10, 25)] + [random.randint(25, 65)]*2 + [random.randint(20, 85)]*2)
        acc_light = random.randint(cloth_light + 10, min(100, max(80, cloth_light + 20)))
        acc_dark = random.randint(int(acc_light * .5), int(acc_light * .68)) #if acc_sat < 50 else \
                   #random.randint(int(acc_light * .4), int(acc_light * .52))
        new_palette[10] = components_to_color(hsv_approx(nudge_hue(acc_hue), acc_sat + random.randint(-7, 8), acc_light))
        new_palette[11] = components_to_color(hsv_approx(nudge_hue(acc_hue), acc_sat + random.randint(-7, 8), acc_dark))
    else:
        sign = random.choice([1, -1])
        hues = [random.randint(0, 360)] # skin
        if hues[0] in range(20, 40): # -- discourage skin-colored skin
            hues[0] = random.randint(0, 360)
        hues.append(hues[0] + random.randint(15, 60) * sign) # hair
        hues.append(hues[1] + random.randint(15, 60) * sign) # clothes
        hues.append(hues[2] + random.randint(15, 60) * sign) # acc

        new_palette = [[0, 0, 0], [3, 3, 3]] * 6

        sats, vals = [], []
        for i, h in enumerate(hues):
            while hues[i] < 0:
                hues[i] += 360
            while hues[i] >= 360:
                hues[i] -= 360
            sats.append(random.randint(80, 100))
            vals.append(random.randint(80, 100))

        new_palette[2] = [31, 31, 31]
        new_palette[3] = hsv_approx(nudge_hue(hue_rgb(hues[1])), sats[1], random.randint(15, 30))
        new_palette[4] = hsv_approx(nudge_hue(hue_rgb(hues[1])), sats[1], vals[1])
        new_palette[5] = hsv_approx(nudge_hue(hue_rgb(hues[1])), sats[1], vals[1] * .66)
        new_palette[6] = hsv_approx(nudge_hue(hue_rgb(hues[0])), sats[0], vals[0])
        new_palette[7] = hsv_approx(nudge_hue(hue_rgb(hues[0])), sats[0], vals[0] * .66)
        new_palette[8] = hsv_approx(nudge_hue(hue_rgb(hues[2])), sats[2], vals[2])
        new_palette[9] = hsv_approx(nudge_hue(hue_rgb(hues[2])), sats[2], vals[2] * .66)
        new_palette[10] = hsv_approx(nudge_hue(hue_rgb(hues[3])), sats[3], vals[3])
        new_palette[11] = hsv_approx(nudge_hue(hue_rgb(hues[3])), sats[3], vals[3] * .66)

        new_palette = list(map(components_to_color, new_palette))

    return new_palette


def line_wrap(things, width=16):
    newthings = []
    while things:
        newthings.append(things[:width])
        things = things[width:]
    return newthings


def get_matrix_reachability(M):
    M2 = list(zip(*M))
    new = [0]*len(M)
    new = [list(new) for _ in range(len(M))]
    for i, row in enumerate(M):
        for j, row2 in enumerate(M2):
            for a, b in zip(row, row2):
                if a & b:
                    new[i][j] = a & b
                    break
            else:
                new[i][j] = 0 | M[i][j]
    return new


def make_table(cols):
    table = ""
    num_rows = max(len(c) for c in cols)
    for i, c in enumerate(cols):
        while len(c) < num_rows:
            c.append("")
        maxwidth = max(len(b) for b in c)
        new_c = []
        for b in c:
            while len(b) < maxwidth:
                b += " "
            new_c.append(b)
        cols[i] = new_c

    while any(cols):
        cols = [c for c in cols if c]
        row = list(zip(*cols))[0]
        row = " | ".join(row)
        row = "| %s |" % row
        table = "\n".join([table, row])
        cols = [col[1:] for col in cols]
    table = table.strip()
    fullwidth = max([len(r.strip()) for r in table.split("\n")])
    horizborder = "-" * (fullwidth - 2)
    horizborder = "/%s\\" % horizborder
    table = "\n".join([horizborder, table, horizborder[::-1]])
    return table

if __name__ == "__main__":
    M = [[1, 0, 0, 1],
         [0, 1, 0, 0],
         [0, 0, 1, 1],
         [1, 0, 0, 1]]
    M = get_matrix_reachability(M)
    for row in M:
        print(row)
