#!/usr/bin/env python3

# Dialogue manager:
# Stores words defined in other parts of the randomizer,
# then patches and re-inserts dialogue scripts with
# designated words changed to the new, randomized words.

# NOTE: FF3usME indexes are 1 lower than the actual ROM indexes used here

import os
import re
from utils import bytes_to_dialogue, dialogue_to_bytes, dialoguetexttable, reverse_dialoguetexttable, battledialoguetexttable, reverse_battledialoguetexttable, get_long_battle_text_pointer, utilrandom as random, open_mei_fallback as open, read_multi, write_multi

try:
    from sys import _MEIPASS
    MEI = True
except ImportError:
    MEI = False


dialogue_vars = {}
dialogue_flags = set()
dialogue_patches = {}
dialogue_patches_battle = {}
script_ptrs = {}
script = {}
script_bin = bytes()
battle_script_ptrs = {}
battle_script = {}
battle_script_bin = bytes()
script_edited = False

location_name_ptrs = {}
location_names = {}
location_name_bin = bytes()

def safepath(vpath):
    # NEW
    # this prepends the absolute file path of the parent/calling script
    #   to the virtual path passed as a param - GreenKnight5
    vpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), vpath)

    if not MEI:
        return vpath
    return [vpath, os.path.join(_MEIPASS, vpath)]


def set_dialogue_var(k, v):
    dialogue_vars[k.lower()] = v

def set_dialogue_flag(f, v=True):
    if v:
        dialogue_flags.add(f.lower())
    elif f in dialogue_flags:
        dialogue_flags.remove(f)

def set_pronoun(name, gender, force=True):
    gender = gender.lower()
    name = name.lower().capitalize()

    if "random" in gender:
        force = True
        opts = ["male"]*9+["female"]*9+["neutral"]*2 if "truerandom" not in gender else ["male", "female", "neutral"]
        if gender == "orandom":
            opts += ["object"]*20
        gender = random.choice(opts)

    if not force:
        if gender == "neutral":
            gender = random.choice(["male"]*9 + ["female"]*9 + ["neutral"]*2)
        elif gender != "object":
            gender = random.choice([gender]*19 + ["neutral"])

    if gender == "male":
        pset = ("he", "him", "his", "his", "he's")
        set_dialogue_flag(name + "Plu", False)
    elif gender == "female":
        pset = ("she", "her", "her", "hers", "she's")
        set_dialogue_flag(name + "Plu", False)
    elif gender == "object":
        pset = ("it", "it", "its", "its", "it's")
        set_dialogue_flag(name + "Plu", False)
    else:
        pset = ("they", "them", "their", "theirs", "they're")
        set_dialogue_flag(name + "Plu")
        gender = "neutral"

    pmap = ("Ey", "Em", "Eir", "Eirs", "EyIs")
    for i in range(5):
        set_dialogue_var(name + pmap[i], pset[i])

    return gender

def patch_dialogue(id, from_text, to_text, index=None, battle=False):
    patches = dialogue_patches_battle if battle else dialogue_patches
    if id not in patches:
        patches[id] = {}
    patches[id][(from_text.lower(), index)] = to_text
        

def get_dialogue(idx):
    return script[idx]

def set_dialogue(idx, text):
    global script_edited
    script[idx] = text
    script_edited = True

def get_battle_dialogue(idx):
    return battle_script[idx]

def set_battle_dialogue(idx, text):
    global script_edited
    battle_script[idx] = text
    script_edited = True

def set_location_name(idx, text):
    location_names[idx] = text

def load_patch_file(fn):
    filepath = os.path.join('data', 'script', fn + ".txt")

    # NEW
    # this prepends the absolute file path of the parent/calling script
    #   to filepath created above - GreenKnight5
    filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), filepath)

    try:
        with open(filepath, "r") as f:
            lines = f.readlines()
    except IOError:
        print(f"failed to open data/script/{fn}.txt")
        return
    for i, line in enumerate(lines):
        battle = False
        s = line.split(':', 1)
        index = s[0].strip()
        if index[0] == 'b':
            index = index[1:]
            battle = True
        try:
            script_idx = int(index)
        except ValueError:
            print(f"{fn}.txt: line {i} - {s[0].strip()} is not a valid caption index")
            continue
        changes = s[1].rstrip('\n').split('|')
        for c in changes:
            if '->' not in c:
                continue
            chgfrom, chgto = c.split('->', 1)
            if '@' in chgfrom:
                chgfrom, match_idx = chgfrom.split('@', 1)
                try:
                    match_idx = int(match_idx)
                except ValueError:
                    print(f"{fn}.txt: line {i} - {match_idx} is not a valid match index")
                    match_idx = 0
            else:
                match_idx = None
            if chgto == "*":
                chgto = None
            patch_dialogue(script_idx, chgfrom, chgto, index=match_idx, battle=battle)


def read_dialogue(fout):
    #load existing script & pointer table
    fout.seek(0xD0000)
    script_bin = fout.read(0x1F0FF)

    fout.seek(0xCE600)
    bankidx = read_multi(fout, 2)
    for idx in range(0xC0C): #C0D through CFF pointers are repurposed
        script_ptrs[idx] = read_multi(fout, 2) + (0x10000 if idx >= bankidx else 0)

    for idx in range(0xC0C): #C0D through CFF pointers are repurposed
        start = script_ptrs[idx]
        end = script_ptrs.get(idx+1, 0)
        if end == 0:
            end = script_bin.find(b'\x00', start)
        script[idx] = bytes_to_dialogue(script_bin[start:end])

    fout.seek(0x10D200)
    battle_script_bin = fout.read(0x2aff)
    fout.seek(0x10D000)
    for idx in range(256):
        battle_script_ptrs[idx] = read_multi(fout,2) - 0xd200
    
    for idx in range(256):
        start = battle_script_ptrs[idx]
        end = battle_script_ptrs.get(idx+1, 0)
        if end == 0:
            end = battle_script_bin.find(b'\x00', start)
        battle_script[idx] = bytes_to_dialogue(battle_script_bin[start:end], table=reverse_battledialoguetexttable)


def _apply_patches(script, patch_dict):
    for idx, patches in patch_dict.items():
        line = split_line(script[idx])

        #print(f"patching line {idx}")
        #print(f"  original: {script[idx]}")
        token_counter = {}
        for i, token in enumerate(line):
            if token.lower() not in token_counter:
                token_counter[token.lower()] = 1
            else:
                token_counter[token.lower()] += 1
            if (token.lower(), token_counter[token.lower()]) in patches:
                line[i] = patch(patches[token.lower(), token_counter[token.lower()]], token)
            elif (token.lower(), None) in patches:
                line[i] = patch(patches[token.lower(), None], token)
            #handle removing text along with following space
            if line[i] is None:
                line[i] = ""
                try:
                    if line[i+1][0] == " ":
                        line[i+1] = "" if len(line[i+1]) < 2 else line[i+1][1:]
                    elif line[1-1][0] == " ":
                        line[i-1] = "" if len(line[i-1]) < 2 else line[i-1][1:]
                except IndexError:
                    pass
        new_text = "".join(line)
        #print(f"  new: {new_text}")
        script[idx] = new_text


def manage_dialogue_patches(fout):
    global script_bin

    #don't do anything unless we need to
    if not dialogue_patches and not dialogue_patches_battle and not script_edited:
        return

    _apply_patches(script, dialogue_patches)
    _apply_patches(battle_script, dialogue_patches_battle)
    #TODO battle pointers

    #print(f"original script size is ${len(script_bin):X} bytes")

    #apply changes to dialogue
    

    new_script = b""
    new_ptrs = b""
    offset = 0
    first_high_index = None
    for idx, text in script.items():
    ####TODO!!! rewrite to only re-encode dialogue if it is changed?
        lastlength = len(new_script) - offset
        if first_high_index:
            lastlength -= 0x10000
        offset += lastlength
        if offset > 0xFFFF:
            if offset > 0x1FFFF or first_high_index is not None:
                print(f"script addressing overflow at index {idx}")
                raise IndexError
            offset -= 0x10000
            first_high_index = idx
            #print(f"first high index at {first_high_index}")
        new_script += dialogue_to_bytes(text)
        new_ptrs += bytes([offset & 0xFF, (offset >> 8) & 0xFF])
    #print(f"new script: ${len(new_script):X} bytes")

    #write to file
    fout.seek(0xD0000)
    assert len(new_script) <= 0x1F0FF
    fout.write(new_script)

    fout.seek(0xCE600)
    write_multi(fout, first_high_index)
    assert len(new_ptrs) <= 0x19FE
    fout.write(new_ptrs)
    
    new_battle_script = b""
    new_battle_ptrs = b""
    offset = 0
    base = 0xD200  # pointers are relative to 0x100000
    for idx, text in battle_script.items():
        lastlength = len(new_battle_script) - offset
        offset += lastlength
        new_battle_script += dialogue_to_bytes(text, table=battledialoguetexttable)
        ptr = offset + base
        new_battle_ptrs += bytes([ptr & 0xFF, (ptr >> 8) & 0xFF])

    fout.seek(0x10D200)
    assert len(new_battle_script) <= 0x2AFF
    fout.write(new_battle_script)
    
    fout.seek(0x10D000)
    assert len(new_battle_ptrs) <= 0x200
    fout.write(new_battle_ptrs)

def read_script(idx, table=reverse_dialoguetexttable):
    loc = script_ptrs[idx]
    dialogue = []
    while loc < len(script_bin):
        if script_bin[loc] == 0:
            break
        dialogue.append(table[f"{script_bin[loc]:02X}"])
        loc += 1
    return "".join(dialogue)

def split_line(line):
    line = line.replace('’', "'")
    split = re.split("(\$..|(?:[A-Za-z']\.)+[A-Za-z]|[A-Za-z']+|[^$A-Za-z']+)", line)
    return [s for s in split if len(s)]

def patch(text, token):
    if text is None:
        return None
    #print(f"patching {text}", end="")
    while True:
        match = re.search("\{(.+)\}", text)
        if not match:
            break

        # handle conditionals/flags
        if "?" in match[1]:
            flag, opts = match[1].split('?', 1)
            try:
                textiftrue, textiffalse = opts.split(':', 1)
            except ValueError:
                textiftrue = opts
                textiffalse = ""
            var = textiftrue if flag.lower() in dialogue_flags else textiffalse
        # handle variables
        else:
            if match[1].lower() not in dialogue_vars:
                print(f"warning: dialogue variable {match[1]} not defined")
                var = match[1]
            else:
                var = dialogue_vars[match[1].lower()]

            if token.upper() == token:
                var = var.upper()
            elif token[0] in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                try:
                    var = var[0].upper() + var[1:]
                except IndexError:
                    var = var.capitalize()

        text = text[0:match.start()] + var + text[match.end():]

    #print(f" to {text}")
    return text

def read_location_names(f):
    #load existing script & pointer table
    f.seek(0xEF100)
    location_name_bin = f.read(0x4ff)

    f.seek(0x268400)
    for idx in range(0x49):
        location_name_ptrs[idx] = read_multi(f, 2)

    for idx in range(0x49):
        start = location_name_ptrs[idx]
        end = location_name_ptrs.get(idx+1, location_name_bin.find(b'\0', start) + 1)
        location_names[idx] = bytes_to_dialogue(location_name_bin[start:end])

def write_location_names(fout):
    new_location_names = b""
    new_ptrs = b""
    offset = 0
    for idx, text in location_names.items():
        lastlength = len(new_location_names) - offset

        offset += lastlength
        if offset > 0x1FFFF:
            print(f"location name addressing overflow at index {idx}")
            raise IndexError
        new_location_names += dialogue_to_bytes(text)
        new_ptrs += bytes([offset & 0xFF, (offset >> 8) & 0xFF])
    #print(f"new script: ${len(new_script):X} bytes")

    #write to file
    fout.seek(0xEF100)
    assert len(new_location_names) <= 0x4FF
    fout.write(new_location_names)

    fout.seek(0x268400)
    assert len(new_ptrs) <= 0x375
    fout.write(new_ptrs)
