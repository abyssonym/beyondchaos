from os import path
import random

ENEMY_TABLE = path.join("tables", "enemycodes.txt")
ITEM_TABLE = path.join("tables", "itemcodes.txt")
SPELL_TABLE = path.join("tables", "spellcodes.txt")
SPELLBANS_TABLE = path.join("tables", "spellbans.txt")
ESPER_TABLE = path.join("tables", "espercodes.txt")
CHEST_TABLE = path.join("tables", "chestcodes.txt")
COMMAND_TABLE = path.join("tables", "commandcodes.txt")
CHAR_TABLE = path.join("tables", "charcodes.txt")
TEXT_TABLE = path.join("tables", "text.txt")
ENEMY_NAMES_TABLE = path.join("tables", "enemynames.txt")
MODIFIERS_TABLE = path.join("tables", "moves.txt")
MOVES_TABLE = path.join("tables", "moves.txt")
LOCATION_TABLE = path.join("tables", "locationformations.txt")


texttable = {}
f = open(TEXT_TABLE)
for line in f:
    line = line.strip()
    char, value = tuple(line.split())
    texttable[char] = value
texttable[' '] = 'FE'
f.close()


def hex2int(hexstr):
    return int(hexstr, 16)


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

    return bs[:length]


def read_multi(f, length=2, reverse=True):
    vals = map(ord, f.read(length))
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

    f.write(''.join(map(chr, vals)))


utilrandom = random.Random()


def mutate_index(index, length, continuation=None,
                 basic_range=None, extended_range=None):
    if length == 0:
        return None

    highest = length - 1
    continuation = continuation or [True, False]
    basic_range = basic_range or (-3, 3)
    extended_range = extended_range or (-1, 1)

    index += utilrandom.randint(*basic_range)
    index = max(0, min(index, highest))
    while utilrandom.choice(continuation):
        index += utilrandom.randint(*extended_range)
        index = max(0, min(index, highest))

    return index


def generate_swapfunc(swapcode=None):
    if swapcode is None:
        swapcode = utilrandom.randint(0, 7)

    f = lambda w: w
    g = lambda w: w
    h = lambda w: w
    if swapcode & 1:
        f = lambda (x, y, z): (y, x, z)
    if swapcode & 2:
        g = lambda (x, y, z): (z, y, x)
    if swapcode & 4:
        h = lambda (x, y, z): (x, z, y)
    swapfunc = lambda w: f(g(h(w)))

    return swapfunc


def shift_middle(triple, degree, ungray=False):
    low, medium, high = tuple(sorted(triple))
    triple = list(triple)
    mediumdex = triple.index(medium)
    if ungray:
        lowdex, highdex = triple.index(low), triple.index(high)
        while utilrandom.choice([True, False]):
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


def get_palette_transformer():
    swapfuncs = [generate_swapfunc(swapcode=None) for _ in range(8)]
    degree = utilrandom.randint(-75, 75)

    def palette_transformer(color):
        red, green, blue = color
        a = red >= green
        b = red >= blue
        c = green >= blue
        index = (a << 2) | (b << 1) | c
        swapfunc = swapfuncs[index]
        red, green, blue = swapfunc((red, green, blue))
        red, green, blue = shift_middle((red, green, blue), degree)
        return (red, green, blue)

    return palette_transformer


def mutate_palette_dict(palette_dict):
    colorsets = {}
    for n, (red, green, blue) in palette_dict.items():
        key = (red >= green, red >= blue, green >= blue)
        if key not in colorsets:
            colorsets[key] = []
        colorsets[key].append(n)

    pastswap = []
    for key in colorsets:
        degree = utilrandom.randint(-75, 75)

        while True:
            swapcode = utilrandom.randint(0, 7)
            if swapcode not in pastswap or utilrandom.randint(1, 10) == 10:
                break

        pastswap.append(swapcode)
        swapfunc = generate_swapfunc(swapcode)

        for n in colorsets[key]:
            red, green, blue = palette_dict[n]
            red, green, blue = shift_middle((red, green, blue), degree)
            low, medium, high = tuple(sorted([red, green, blue]))

            assert low <= medium <= high
            palette_dict[n] = swapfunc((low, medium, high))

    return palette_dict
