#!/usr/bin/env python3

# Dialogue manager:
# Stores words defined in other parts of the randomizer,
# then patches and re-inserts dialogue scripts with
# designated words changed to the new, randomized words.

# NOTE: FF3usME indexes are 1 lower than the actual ROM indexes used here

import re, os
from utils import dialoguetexttable, utilrandom as random, open_mei_fallback as open, read_multi, write_multi

try:
    from sys import _MEIPASS
    MEI = True
except ImportError:
    MEI = False
    
textdialoguetable = {v:k for k,v in dialoguetexttable.items()}
for i in range(0xFF):
    if f"{i:2X}" not in textdialoguetable:
        textdialoguetable[f"{i:02X}"] = f"${i:02X}"
textdialoguetable["63"] = "'"

dialoguebytetable = {}
for k, v in dialoguetexttable.items():
    dialoguebytetable[k] = v
for i in range(0xFF):
    dialoguebytetable[f"${i:02X}"] = f"{i:02X}"
dialoguebytetable["'"] = dialoguebytetable["’"]
    
dialogue_vars = {}
dialogue_patches = {}
dialogue_patches_battle = {}
script_ptrs = {}
script_bin = None

def safepath(vpath):
    if not MEI:
        return vpath
    return [vpath, os.path.join(_MEIPASS, vpath)]
    
#need to use a different table here, so redefined
def dialogue_to_bytes(text, null_terminate=True):
    bs = []
    i = 0
    while i < len(text):
        if text[i] == "<":
            j = text.find(">", i) + 1
            hex = dialoguebytetable.get(text[i:j], "")
            i = j
        elif text[i] == "$":
            hex = text[i+1:i+3]
            i += 3
        elif i < len(text) - 1 and text[i:i+2] in dialoguebytetable:
            hex = dialoguebytetable[text[i:i+2]]
            i += 2
        else:
            hex = dialoguebytetable[text[i]]
            i += 1

        if hex != "":
            bs.append(int(hex, 16))

    if null_terminate:
        bs.append(0x0)
    return bytes(bs)
    
    
def set_dialogue_var(k, v):
    dialogue_vars[k.lower()] = v
    
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
            gender = random.choice( ["male"]*9+["female"]*9+["neutral"]*2 )
        elif gender != "object":
            gender = random.choice( [gender]*19+["neutral"] )
            
    if gender == "male":
        pset = ("he", "him", "his", "his", "he's")
    elif gender == "female":
        pset = ("she", "her", "her", "hers", "she's")
    elif gender == "object":
        pset = ("it", "it", "its", "its", "it's")
    else:
        pset = ("they", "them", "their", "theirs", "they're")
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
    
def load_patch_file(fn):
    filepath = safepath(os.path.join('data', 'script', fn + ".txt"))
    try:
        with open(filepath, "r") as f:
            lines = f.readlines()
    except IOError:
        print(f"failed to open data/script/{fn}.txt")
        return
    for i, line in enumerate(lines):
        s = line.split(':',1)
        try:
            script_idx = int(s[0].strip())
        except ValueError:
            print(f"{fn}.txt: line {i} - {s[0]} is not a valid caption index")
            continue
        changes = s[1].rstrip('\n').split('|')
        for c in changes:
            if '->' not in c: continue
            chgfrom, chgto = c.split('->',1)
            if '@' in chgfrom:
                chgfrom, match_idx = chgfrom.split('@',1)
                try:
                    match_idx = int(match_idx)
                except ValueError:
                    print(f"{fn}.txt: line {i} - {match_idx} is not a valid match index")
                    match_idx = 0
            else:
                match_idx = None
            if chgto == "*": chgto = None
            patch_dialogue(script_idx, chgfrom, chgto, index=match_idx)
            
def manage_dialogue_patches(fout):
    global script_bin
    
    #don't do anything unless we need to
    if not dialogue_patches and not dialogue_patches_battle:
        return
        
    #load existing script & pointer table
    fout.seek(0xD0000)
    script_bin = fout.read(0x1F0FF)
    script = {}
    #TODO battle script
    
    fout.seek(0xCE600)
    bankidx = read_multi(fout, 2)
    for idx in range(0xC14): #C15 through CFF pointers are repurposed
        script_ptrs[idx] = read_multi(fout,2) + (0x10000 if idx > bankidx else 0)
        script[idx] = read_script(idx)
        
    #TODO battle pointers
            
    print(f"original script size is ${len(script_bin):X} bytes")
    
    #apply changes to dialogue
    for idx, patches in dialogue_patches.items():
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
                line[i] = patch(patches[token.lower(), token_counter[token.lower()]])
            elif (token.lower(), None) in patches:
                line[i] = patch(patches[token.lower(), None])
            #handle removing text along with following space
            if line[i] is None:
                line[i] = ""
                try:
                    if line[i+1][0] == " ":
                        line[i+1] = "" if len(line[i+1]) < 2 else line[i+1][1:]
                except IndexError:
                    pass
        new_text = "".join(line)
        #print(f"  new: {new_text}")
        script[idx] = new_text
        
    new_script = b""
    new_ptrs = b""
    offset = 0
    first_high_index = None
    for idx, text in script.items():
    ####TODO!!! rewrite to only re-encode dialogue if it is changed?
        lastlength = len(new_script) - offset
        if first_high_index: lastlength -= 0x10000
        offset += lastlength
        if offset > 0xFFFF:
            if offset > 0x1FFFF or first_high_index is not None:
                print(f"script addressing overflow at index {idx}")
                raise IndexError
            offset -= 0x10000
            first_high_index = idx
            print(f"first high index at {first_high_index}")
        new_script += dialogue_to_bytes(text)
        new_ptrs += bytes([offset & 0xFF, (offset >> 8) & 0xFF])
    print(f"new script: ${len(new_script):X} bytes")
    
    #write to file
    fout.seek(0xD0000)
    assert len(new_script) <= 0x1F0FF
    fout.write(new_script)
    
    fout.seek(0xCE600)
    write_multi(fout, first_high_index)
    assert len(new_ptrs) <= 0x19FE
    fout.write(new_ptrs)
    
def read_script(idx, battle=False):
    loc = script_ptrs[idx]
    dialogue = []
    while loc < len(script_bin):
        if script_bin[loc] == 0:
            break
        dialogue.append(textdialoguetable[f"{script_bin[loc]:02X}"])
        loc += 1
    return "".join(dialogue)
    
def split_line(line):
    line = line.replace('’',"'")
    split = re.split("(\$..|[A-Za-z']+|[^$A-Za-z']+)", line)
    return [s for s in split if len(s)]
        
def patch(text):
    if text is None:
        return None
    print(f"patching {text}", end="")
    while True:
        match = re.search("\{(.+)\}", text)
        if not match: break
        
        if match[1].lower() not in dialogue_vars:
            print(f"warning: dialogue variable {match[1]} not defined")
            var = match[1]
        else:
            var = dialogue_vars[match[1].lower()]
        
        if match[1].upper() == match[1]:
            var = var.upper()
        elif match[1][0] in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            try:
                var = var[0].upper() + var[1:]
            except IndexError:
                var = var.capitalize()
            
        text = text[0:match.start()] + var + text[match.end():]
            
    print(f" to {text}")
    return text