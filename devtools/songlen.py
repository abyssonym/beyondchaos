## Dev tool for checking song data lengths
## (to find and address overflow glitches)

# sort options:

#sort_by = 'filename'
#sort_by = 'max_normal_datasize'
sort_by = 'max_sfx_datasize'

## Notes:
## sfx_train displaying warnings is fine & expected
## Looks at files only, does not check whether something is in songs.txt
##  (so if a _vic file overflows in rain/wind/train mode there's no problem
##   as long as it's not explicitly defined in songs.txt)

## Add a command line parameter to check only songs with that string in filename
## (much faster, if you only need one / a few)

###
import glob, os, sys, traceback, re
from pathlib import Path

tool_path = Path().absolute().parent
in_path = tool_path / 'custom' / 'music'

sys.path.insert(0, str(tool_path) + "/" )
from mml2mfvi import mml_to_akao

outfile = ""

MUSIC_PATH = in_path
#copypasta from musicrandomizer.py
def process_mml(id, orig_mml, name):
    def wind_increment(m):
        val = int(m.group(1))
        if val in [1, 2, 3, 4, 5, 6, 9, 10, 11, 12, 13, 14]:
            val += 2
        elif val in [7, 8, 15, 16]: 
            val -= 6
        return "{{{}}}".format(val)
        return m.group(0)
        
    sfx = ""
    is_sfxv = False
    mml = orig_mml
    if id == 0x29:
        sfx = "sfx_zozo.mmlappend"
        is_sfxv = True
    elif id == 0x4F or (id == 0x5D and windy_intro):
        sfx = "sfx_wor.mmlappend"
        is_sfxv = True
        try:
            mml = re.sub("\{[^}']*?([0-9]+)[^}]*?\}", wind_increment, mml)
        except ValueError:
            print("WARNING: failed to add wind sounds ({})".format(name))
    elif id == 0x20:
        sfx = "sfx_train.mmlappend"
        mml = re.sub("\{[^}]*?([0-9]+)[^}]*?\}", "$888\g<1>", mml)
        for i in range(1,9):
            if "$888{}".format(i) not in mml:
                mml = mml + "\n$888{} r;".format(i)
    if sfx:
        try:
            with open(os.path.join(MUSIC_PATH, sfx), 'r') as f:
                mml += f.read()
        except IOError:
            print("couldn't open {}".format(sfx))
            
    akaov = mml_to_akao(mml, name, is_sfxv)
    if id == 0x5D and len(bytes(akaov["_default_"][0], encoding="latin-1")) > 0x1002:
        akaov = mml_to_akao(orig_mml, name, False)
    return akaov
#end copypasta

sfxes = [ ("rain", 0x29, "sfx"), ("wind", 0x4F, "sfx"), ("train", 0x20, "tr") ]

try:
    filter = ""
    if len(sys.argv) >= 2:
        filter = sys.argv[1]
    
    files = glob.glob(os.path.join(in_path, "*.mml*"))
    if filter:
        files = [fn for fn in files if filter in fn]
        
    db = {}
    for file in files:
        with open(file, 'r') as f:
            fn = os.path.split(file)[1]
            mml = f.read()
            print(fn, end="", flush=True)
            akao = mml_to_akao(mml, fn, False)
        
        for ignored_variant in ["enh", "nat", "nopatch"]:
            if ignored_variant in akao:
                del akao[ignored_variant]
        
        for vari, data in akao.items():
            akao[vari] = ( bytes(akao[vari][0], encoding="latin-1"),
                           bytes(akao[vari][1], encoding="latin-1") )
                           
        sfx = {}
        if ".mmlappend" not in fn and "_dm.mml" not in fn:
            for effect, sfxid, sfxv in sfxes:
                variant = sfxv if sfxv in akao else "_default_"
                with_effects = process_mml(sfxid, mml, fn)
                sfx[effect] = len(with_effects[variant][0])
                print(".", end="", flush=True)
        print()
        
        most = 0
        for vari, data in akao.items():
            if len(data[0]) > most:
                most = len(data[0])
        sfxmost = most
        for k, v in sfx.items():
            if v > sfxmost:
                sfxmost = v
        db[fn] = (most, sfxmost, [(k, len(v[0])) for k, v in akao.items()], sfx)
        #print(".", end="", flush=True)
    print()
    
    if sort_by == 'filename':
        dbs = sorted(db.items(), key=lambda x:x[0])
    elif sort_by == 'max_normal_datasize':
        dbs = sorted(db.items(), key=lambda x:x[1][0])
    else: #sort by max_sfx_datasize (default)
        dbs = sorted(db.items(), key=lambda x:x[1][1])
    
    for k, v in dbs:
        output = f"{k:22}: {v[0]:4X} {v[1]:4X}     ( "
        varis = sorted(v[2], key=lambda x:x[1])
        for vari in varis:
            output += "{} {:X}, ".format(vari[0], vari[1])
        output = output[:-2]
        output += ") ["
        for effect, sfxid, sfxv in sfxes:
            try:
                output += f"{effect} {v[3][effect]:X}, "
            except KeyError:
                pass
        output = output[:-2]
        output += "]\n"
        print (output, end="")
        outfile += output
        
    with open ("songlen.txt", 'w+') as f:
        f.write(outfile)
    input()
    
except Exception as e:
    traceback.print_exc()
    input()
