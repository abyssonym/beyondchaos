from os import path
from collections import defaultdict
import random

try:
    from sys import _MEIPASS
    MEI = True
    tblpath = path.join(_MEIPASS, "tables")
except ImportError:
    tblpath = "tables"
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

custom_path = "custom"
MALE_NAMES_TABLE = path.join(custom_path, "malenames.txt")
FEMALE_NAMES_TABLE = path.join(custom_path, "femalenames.txt")
SPRITE_REPLACEMENT_TABLE = path.join(custom_path, "spritereplacements.txt")
MOOGLE_NAMES_TABLE = path.join(custom_path, "mooglenames.txt")
DANCE_NAMES_TABLE = path.join(custom_path, "dancenames.txt")

def open_mei_fallback(filename, mode='r'):
    if not MEI:
        return open(filename, mode)

    try:
        f = open(filename, mode)
    except IOError:
        f = open(path.join(_MEIPASS, filename), mode)
    return f


class Substitution(object):
    location = None

    @property
    def size(self):
        return len(self.bytestring)

    def set_location(self, location):
        self.location = location

    def write(self, fout):
        fout.seek(self.location)
        fout.write(bytes(self.bytestring))


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
    value, string = tuple(line.split('=', 1))
    dialoguetexttable[string] = value
f.close()


def hex2int(hexstr):
    return int(hexstr, 16)


def dialogue_to_bytes(text):
    bs = []
    i = 0
    while i < len(text):
        if text[i] == "<":
            j = text.find(">", i) + 1
            hex = dialoguetexttable.get(text[i:j], "")
            i = j
        elif i < len(text) - 1 and text[i:i+2] in dialoguetexttable:
            hex = dialoguetexttable[text[i:i+2]]
            i += 2
        else:
            hex = dialoguetexttable[text[i]]
            i += 1

        if hex != "":
            bs.append(hex2int(hex))

    bs.append(0x0)
    return bytes(bs)

    
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

    index += utran.randint(*basic_range)
    index = max(0, min(index, highest))
    while utran.choice(continuation):
        index += utran.randint(*extended_range)
        index = max(0, min(index, highest))

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
        elif abs(a-b) <= 1:
            return 1.0
        else:
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
                    import pdb; pdb.set_trace()
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
        def color_to_index(color):
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


def decompress(bytestring, simple=False, complicated=False, debug=False):
    result = ""
    buff = [chr(0)] * 2048
    buffaddr = 0x7DE
    while bytestring:
        flags, bytestring = ord(bytestring[0]), bytestring[1:]
        for i in range(8):
            if not bytestring:
                break

            if flags & (1 << i):
                byte, bytestring = bytestring[0], bytestring[1:]
                result += byte
                buff[buffaddr] = byte
                buffaddr += 1
                if buffaddr == 0x800:
                    buffaddr = 0
                if debug:
                    print("%x" % ord(byte), end=' ')
            else:
                low, high, bytestring = (
                    ord(bytestring[0]), ord(bytestring[1]), bytestring[2:])
                seekaddr = low | ((high & 0x07) << 8)
                length = ((high & 0xF8) >> 3) + 3
                if simple:
                    copied = "".join([buff[seekaddr]] * length)
                elif complicated:
                    cycle = buffaddr - seekaddr
                    if cycle < 0:
                        cycle += 0x800
                    subbuff = "".join((buff+buff)[seekaddr:seekaddr+cycle])
                    while len(subbuff) < length:
                        subbuff = subbuff + subbuff
                    copied = "".join(subbuff[:length])
                else:
                    copied = "".join((buff+buff)[seekaddr:seekaddr+length])
                assert len(copied) == length
                result += copied
                if debug:
                    print("%x" % seekaddr, length, end=' ')
                while copied:
                    byte, copied = copied[0], copied[1:]
                    buff[buffaddr] = byte
                    buffaddr += 1
                    if buffaddr == 0x800:
                        buffaddr = 0
                    if debug:
                        print("%x" % ord(byte), end=' ')
            if debug:
                print()
                import pdb; pdb.set_trace()
    return result


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
    M = [[1,0,0,1],
         [0,1,0,0],
         [0,0,1,1],
         [1,0,0,1]]
    M = get_matrix_reachability(M)
    for row in M:
        print(row)
