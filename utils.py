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


texttable = {}
f = open(TEXT_TABLE)
for line in f:
    line = line.strip()
    char, value = tuple(line.split())
    texttable[char] = value
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
        vals = reversed(vals)
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

    while len(vals) < length:
        vals.append(0x00)

    if not reverse:
        vals = reversed(vals)

    f.write(''.join(map(chr, vals)))


utilrandom = random.Random()


def mutate_index(index, length, continuation=None,
                 basic_range=None, extended_range=None):
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
