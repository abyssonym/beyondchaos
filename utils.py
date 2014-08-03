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
