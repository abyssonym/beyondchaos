import sys, os, re, traceback, copy
from string import maketrans
from mmltbl import *

mml_log = "\n" if __name__ == "__main__" else None

def byte_insert(data, position, newdata, maxlength=0, end=0):
    while position > len(data):
        data = data + "\x00"
    if end:
        maxlength = end - position + 1
    if maxlength and len(data) > maxlength:
        newdata = newdata[:maxlength]
    return data[:position] + newdata + data[position+len(newdata):]

    
def int_insert(data, position, newdata, length, reversed=True):
    n = int(newdata)
    l = []
    while len(l) < length:
        l.append(chr(n & 0xFF))
        n = n >> 8
    if not reversed: l.reverse()
    return byte_insert(data, position, "".join(l), length)

def warn(fileid, cmd, msg):
    global mml_log
    m = "{}: WARNING: in {:<10}: {}".format(fileid, cmd, msg)
    print m
    if __name__ == "__main__": mml_log += m + '\n'

def mlog(msg):
    global mml_log
    if __name__ == "__main__": mml_log += msg + '\n'
    
class Drum:
    def __init__(self, st):
        s = re.findall('(.)(.[+-]?)\\1=\s*([0-9]?)([a-gr^])([+-]?)\s*(.*)', st)
        if s: s = s[0]
        mlog("{} -> {}".format(st, s))
        if len(s) >= 6:
            self.delim = s[0]
            self.key = s[1]
            self.octave = int(s[2]) if s[2] else 5
            self.note = s[3] + s[4]
            s5 = re.sub('\s*', '', s[5]).lower()
            params = re.findall("\|[0-9a-f]|@0x[0-9a-f][0-9a-f]|%?[^|0-9][0-9,]*", s5)
            par = {}
            for p in params:
                if p[0] == "@" and len(p) >= 5:
                    if p[0:3] == "@0x":
                        par['@0'] = str(int(p[3:5], 16))
                        continue
                if p[0] == '|' and len(p) >= 2:
                    par['@0'] = str(int(p[1], 16) + 32)
                else:
                    pre = re.sub('[0-9]+', '0', p)
                    suf = re.sub('%?[^0-9]', '', p, 1)
                    if pre in equiv_tbl:
                        pre = equiv_tbl[pre]
                    par[pre] = suf
            self.params = par
        else:
            self.delim, self.key, self.octave, self.note, self.params = None, None, None, None, None
        mlog("DRUM: [{}] {} -- o{} {} {}".format(self.delim, self.key, self.octave, self.note, self.params))
        
def mml_to_akao(mml, fileid='mml', sfxmode=False, variant=None):
    #preprocessor
    #returns dict of (data, inst) tuples (4096, 32 bytes max)
    #one generated for each #VARIANT directive

    if isinstance(mml, str):
        mml = mml.splitlines()
    #one-to-one character replacement
    transes = []
    for line in mml:
        if line.startswith("#REPLACE") and len(line) > 7:
            tokens = line[7:].split()
            if len(tokens) < 3: continue
            if len(tokens[1]) != len(tokens[2]):
                warn(fileid, line, "token size mismatch, ignoring excess")
                if len(tokens[1]) > len(tokens[2]):
                    tokens[1] = tokens[1][0:len(tokens[2])]
                else:
                    tokens[2] = tokens[2][0:len(tokens[1])]
            transes.append(maketrans(tokens[1], tokens[2]))
    for trans in transes:
        newmml = []
        for line in mml:
            newmml.append(line.translate(trans))
        mml = newmml
    
    #sfxvariant
    all_delims = set()
    for line in mml:
        if line.startswith("#SFXV") and len(line) > 5:
            tokens = line[5:].split()
            if len(tokens) < 1: continue
            if len(tokens) >= 2 and sfxmode:
                all_delims.update(tokens[1])
            elif not sfxmode:
                all_delims.update(tokens[0])
    #variants
    variants = {}
    for line in mml:
        if line.startswith("#VARIANT") and len(line) > 8:
            makedefault = True if not variants else False
            tokens = line[8:].split()
            if len(tokens) < 1: continue
            if len(tokens) == 1:
                tokens.append('_default_')
            all_delims.update(tokens[0])
            variants[tokens[1]] = tokens[0]
            if makedefault: variants["_default_"] = tokens[0]
    for k, v in variants.items():
        variants[k] = "".join([c for c in all_delims if c not in variants[k]])
    if not variants:
        variants['_default_'] = ''.join([c for c in all_delims])
    if variant:
        if variant not in variants:
            print "mml error: requested unknown variant '{}'\n".format(variant)
        variants = {variant: variants[variant]}
        
    #generate instruments
    isets = {}
    for k, v in variants.items():
        iset = {}
        for line in mml:
            skip = False
            if line.startswith("#WAVE") and len(line) > 5:
                for c in v:
                    if c in line:
                        line = re.sub(c+'.*?'+c, '', line)
                line = re.sub('[^x\da-fA-F]', ' ', line[5:])
                tokens = line.split()
                if len(tokens) < 2: continue
                numbers = []
                for t in tokens[0:2]:
                    t = t.lower()
                    base = 16 if 'x' in t else 10
                    t = t.replace('x' if base == 16 else 'xabcdef', '')
                    try:
                        numbers.append(int(t, base))
                    except:
                        warn(fileid, "#WAVE {}, {}".format(tokens[0], tokens[1]), "Couldn't parse token {}".format(t))
                        continue
                if numbers[0] not in range(0x20,0x30):
                    warn(fileid, "#WAVE {}, {}".format(hex(numbers[0]), hex(numbers[1])), "Program ID out of range (expected 0x20 - 0x2F / 32 - 47)")
                    continue
                if numbers[1] not in range(0, 256):
                    warn(fileid, "#WAVE {}, {}".format(hex(numbers[0]), hex(numbers[1])), "Sample ID out of range (expected 0x00 - 0xFF / 0 - 255)")
                    continue
                iset[numbers[0]] = numbers[1]
        raw_iset = "\x00" * 0x20
        for slot, inst in iset.items():
            raw_iset = byte_insert(raw_iset, (slot - 0x20)*2, chr(inst))
        isets[k] = raw_iset
                
            
    #generate data
    datas = {}
    for k, v in variants.items():
        datas[k] = mml_to_akao_main(mml, v, fileid)
        
    output = {}
    for k, v in variants.items():
        output[k] = (datas[k], isets[k])
    
    return output
        
        
def mml_to_akao_main(mml, ignore='', fileid='mml'):
    mml = copy.copy(mml)
    #final bit of preprocessing
    macros = {}
    for line in mml:
        if line.lower().startswith("#def"):
            line = line[4:]
            line = line.split('#')[0].lower()
            if not line: continue
            pre, sep, post = line.partition('=')
            if post:
                pre = pre.replace("'", "").strip()
                for c in ignore:
                    try:
                        post = re.sub(c+".*?"+c, "", post)
                    except Exception:
                        c = "\\" + c
                        post = re.sub(c+".*?"+c, "", post)
                    post = "".join(post.split())
                macros[pre] = post.lower()
    
    #stillmacros = True
    #while stillmacros:
    #    stillmacros = False
    #    for i, line in enumerate(mml):
    #        for k, v in macros.items():
    #            if "'{}'".format(k) in line:
    #                stillmacros = True
    #                line = line.replace("'{}'".format(k), v)
    #        mml[i] = line
    for i, line in enumerate(mml):
        while True:
            r = re.search("'(.*?)'", line)
            if not r: break
            m = r.group(1)
            s = macros[m] if m in macros else ""
            line = line.replace(r.group(0), s, 1)
        mml[i] = line
            
    #drums
    drums = {}
    for line in mml:
        if line.lower().startswith("#drum"):
            s = line[5:].strip()
            s = s.split('#')[0].lower()
            for c in ignore:
                try:
                    s = re.sub(c+".*?"+c, "", s)
                except Exception:
                    c = "\\" + c
                    s = re.sub(c+".*?"+c, "", s)
            for c in ["~", "/", "`", "\?", "_"]:
                s = re.sub(c, '', s)
            d = Drum(s.strip())
            if d.delim:
                if d.delim not in drums: drums[d.delim] = {}
                drums[d.delim][d.key] = d
    
    for i, line in enumerate(mml):
        mml[i] = line.split('#')[0].lower()
            
    m = list(" ".join(mml))
    targets, channels, pendingjumps = {}, {}, {}
    data = "\x00" * 0x26
    defaultlength = 8
    thissegment = 1
    next_jumpid = 1
    state = {}
    jumpout = []
    
    while len(m):
        command = m.pop(0)

        #conditionally executed statements
        if command in ignore:
            while len(m):
                next = m.pop(0)
                if next == command:
                    break
            continue
        #inline comment // channel marker
        elif command == "{":
            thisnumber = ""    
            numbers = []
            while len(m):
                command += m.pop(0)
                if command[-1] in "1234567890":
                    thisnumber += command[-1]
                elif thisnumber:
                    numbers.append(int(thisnumber))
                    thisnumber = ""
                if command[-1] == "}": break
            for n in numbers:
                if n <= 16 and n >= 1:
                    channels[n] = len(data)
            continue
        #drum mode
        elif command in drums:
            mls, dms = [], []
            drumset = drums[command]
            while len(m):
                if m[0] != command:
                    dms.append(m.pop(0))
                else:
                    m.pop(0)
                    break
            dbgdms = "".join(dms)
            lockstate = False
            silent = False
            if len(dms):
                if dms[0] in "1234567890":
                    state["o0"] = dms.pop(0)
                elif dms[0] == ">":
                    co = dms.pop(0)
                    while dms[0] == ">":
                        co += dms.pop(0)
                    state["o0"] += len(co)
                elif dms[0] == "<":
                    co = dms.pop(0)
                    while dms[0] == "<":
                        co += dms.pop(0)
                    state["o0"] -= len(co)
            while len(dms):
                dcom = dms.pop(0)
                if len(dms):
                    if dms[0] in "+-":
                        dcom += dms.pop(0)
                if dcom == "\\":
                    lockstate = True if not lockstate else False
                elif dcom == ":":
                    silent = True if not silent else False
                elif dcom == "!":
                    rcom = dms.pop(0)
                    if rcom == "!":
                        if "o0" in state:
                            state = {"o0": state["o0"]}
                        else:
                            state = {}
                        continue
                    if rcom == "%": rcom += dms.pop(0)
                    while len(dms):
                        if dms[0] in "0,":
                            rcom += dms.pop(0)
                        else: break
                    if rcom in equiv_tbl:
                        rcom = equiv_tbl[rcom]
                    state.pop(rcom, None)
                elif dcom in "0123456789^.":
                    mls.extend(dcom)
                elif dcom in drumset:
                    params = {}
                    for k, v in drumset[dcom].params.items():
                        if lockstate and k != "@0": continue
                        if k in state:
                            if state[k] != v:
                                params[k] = v
                        elif k == "%y" and not ( "%a0" in state or "%y0" in state or 
                                                 "%s0" in state or "%r0" in state):
                             pass
                        else:
                            params[k] = v
                    s = ""
                    for k, v in params.items():
                        t = (re.sub('[0-9,]', '', k) + v).strip()
                        s = t + s if k == "@0" else s + t
                        if k == "%y" or k == "@0":
                            state.pop("%a0", None)
                            state.pop("%y0", None)
                            state.pop("%s0", None)
                            state.pop("%r0", None)
                        if k != "%y": state[k] = v
                    if 'o0' in state:
                        if isinstance(state['o0'], str): state['o0'] = int(state['o0'])
                        ochg = drumset[dcom].octave - int(state['o0'])
                        if ochg < 0:
                            s += ">" * abs(ochg)
                        else: s += "<" * ochg
                        state['o0'] += ochg
                    else:
                        s += "o{}".format(drumset[dcom].octave)
                        state['o0'] = drumset[dcom].octave
                    s += drumset[dcom].note
                    if not silent: mls.extend(list(s))
            mlog("drum: processed {} -> {}".format(dbgdms, "".join(mls)))
            mls.extend(m)
            m = mls
            continue
            
        #populate command variables
        if command == "%": command += m.pop(0)
        prefix = command
        if len(m):
            while m[0] in "1234567890,.+-x":
                command += m.pop(0)
                if not len(m): break
        
        #catch @0x before parsing params
        if "|" in command:
            command = "@0x2" + command[1:]
        if "@0x" in command:
            while len(command) < 5:
                command += m.pop(0)
            number = command[-2:]
            try:
                number = int(number, 16)
            except ValueError:
                warn(fileid, command, "Invalid instrument {}, falling back to 0x20".format(number))
                number = 0x20
            command = "@" + str(number)
                    
        modifier = ""
        params = []
        for c in command:
            if c in "+-":
                modifier = c
        thisnumber = ""
        is_negative = False
        for c in command[len(prefix):] + " ":
            if c in "1234567890":
                thisnumber += c
            elif c == "-" and prefix not in "abcdefg^r":
                is_negative = True
            elif thisnumber:
                params.append(0x100-int(thisnumber) if is_negative else int(thisnumber))
                thisnumber = ""
                is_negative = False
        dots = len([c for c in command if c == "."])
        
        if (prefix, len(params)) not in command_tbl and len(params):
            if (prefix + str(params[0]), len(params) - 1) in command_tbl:
                prefix += str(params.pop(0))
        
        #print "processing command {} -> {} {} mod {} dots {}".format(command, prefix, params, modifier, dots)
        #case: notes
        if prefix in "abcdefg^r":
            pitch = note_tbl[prefix]
            if prefix not in "^r":
                pitch += 1 if "+" in modifier else 0
                pitch -= 1 if "-" in modifier else 0
                while pitch < 0: pitch += 0xC
                while pitch > 0xB: pitch -= 0xC
            if not params:
                length = defaultlength
            else:
                length = params[0]
            if dots and str(length)+"." in length_tbl:
                akao = chr(pitch * 14 + length_tbl[str(length)+"."][0])
                dots -= 1
                length *= 2
            elif length in length_tbl:
                akao = chr(pitch * 14 + length_tbl[length][0])
            else:
                warn(fileid, command, "Unrecognized note length {}".format(length))
                continue
            while dots:
                if length*2 not in length_tbl:
                    warn(fileid, command, "Cannot extend note/tie of length {}".format(length))
                    break
                dots -= 1
                length *= 2
                if dots and str(length)+"." in length_tbl:
                    akao += chr(note_tbl["^"]*14 + length_tbl[str(length)+"."][0])
                    dots -= 1
                    length *= 2
                else:
                    akao += chr(note_tbl["^"]*14 + length_tbl[length][0])
            data += akao
        #case: simple commands
        elif (prefix, len(params)) in command_tbl:
            #special case: loops
            if prefix == "[":
                if len(params):
                    params[0] -= 1
                else:
                    params.append(1)
            #special case: end loop adds jump target if j,1 is used
            if prefix == "]":
                while len(jumpout):
                    pendingjumps[jumpout.pop()] = "jo%d"%next_jumpid
                targets["jo%d"%next_jumpid] = len(data) + 1
                next_jumpid += 1    
            #general case
            akao = chr(command_tbl[prefix, len(params)])
            #special case: pansweep
            if prefix == "p" and len(params) == 3:
                params = params[1:]
            #general case
            while len(params):
                if params[0] >= 256:
                    warn(fileid, command, "Parameter {} out of range, substituting 0".format(params[0]))
                    params[0] = 0
                akao += chr(params.pop(0))
            data += akao
        #case: default length
        elif prefix == "l" and len(params) == 1:
            if params[0] in length_tbl:
                defaultlength = params[0]
            else:
                warn(fileid, command, "Unrecognized note length {}".format(length))
        #case: jump point
        elif prefix == "$":
            if params:
                targets[params[0]] = len(data)
            else:
                targets["seg%d"%thissegment] = len(data)
        #case: end of segment
        elif prefix == ";":
            defaultlength = 8
            state = {}
            if params:
                if params[0] in targets:
                    target = targets[params[0]]
                else:
                    target = len(data)
                    pendingjumps[len(data)+1] = params[0]
            else:
                if "seg%d"%thissegment in targets:
                    target = targets["seg%d"%thissegment]
                else:
                    data += "\xEB"
                    thissegment += 1
                    continue
            data += "\xF6" + int_insert("  ",0,target,2)
            thissegment += 1
        #case: jump out of loop
        elif prefix == "j":
            if len(params) == 1:
                jumpout.append(len(data)+2)
                target = len(data)
            elif len(params) == 2:
                if params[1] in targets:
                    target = targets[params[1]]
                else:
                    target = len(data)
                    pendingjumps[len(data)+2] = params[1]
            else: continue
            if params[0] >= 256:
                warn(fileid, command, "Parameter {} out of range, substituting 1".format(params[0]))
                params[0] = 1
            data += "\xF5" + chr(params[0]) + int_insert("  ",0,target,2)
        #case: hard jump without ending segment
        elif prefix == "%j":
            if len(params)==1:
                if params[0] in targets:
                    target = targets[params[0]]
                else:
                    target = len(data)
                    pendingjumps[len(data)+1] = params[0]
            else: continue
            data += "\xF6" + int_insert("  ",0,target,2)
        #case: conditional jump
        elif prefix == ":" and len(params) == 1:
            if params[0] in targets:
                target = targets[params[0]]
            else:
                target = len(data)
                pendingjumps[len(data)+1] = params[0]
            data += "\xFC" + int_insert("  ",0,target,2)
    
    #insert pending jumps
    for k, v in pendingjumps.items():
        if v in targets:
            data = int_insert(data, k, targets[v], 2)
        else:
            warn(fileid, command, "Jump destination {} not found in file".format(v))
    #set up header
    header = int_insert("\x00"*0x26, 0, len(data)-2, 2)
    header = int_insert(header, 2, 0x26, 2)
    header = int_insert(header, 4, len(data), 2)
    for i in xrange(0,8):
        if i not in channels:
            channels[i] = len(data)
    for k, v in channels.items():
        header = int_insert(header, 4 + k*2, v, 2)
        if k <= 8 and k+8 not in channels:
            header = int_insert(header, 4 + (k+8)*2, v, 2)
    data = byte_insert(data, 0, header, 0x26)
    
    return data
    
def clean_end():
    print "Processing ended."
    raw_input("Press enter to close.")
    quit()
    
if __name__ == "__main__":
    mml_log = "\n"

    print "mfvitools MML to AKAO SNESv4 converter"
    print
    
    if len(sys.argv) >= 2:
        fn = sys.argv[1]
    else:
        print "Enter MML filename.."
        fn = raw_input(" > ").replace('"','').strip()
    
    try:
        with open(fn, 'r') as f:
            mml = f.readlines()
    except IOError:
        print "Error reading file {}".format(fn)
        clean_end()

    try:
        variants = mml_to_akao(mml)
    except Exception:
        traceback.print_exc()
        clean_end()
    
    fn = os.path.splitext(fn)[0]
    for k, v in variants.items():
        vfn = ".bin" if k in ("_default_", "") else "_{}.bin".format(k)
        
        thisfn = fn + "_data" + vfn
        try:
            with open(thisfn, 'wb') as f:
                f.write(v[0])
        except IOError:
            print "Error writing file {}".format(thisfn)
            clean_end()
        print "Wrote {} - {} bytes".format(thisfn, hex(len(v[0])))
        
        thisfn = fn + "_inst" + vfn
        try:
            with open(thisfn, 'wb') as f:
                f.write(v[1])
        except IOError:
            print "Error writing file {}".format(thisfn)
            clean_end()
        print "Wrote {}".format(thisfn)
        
    try:
        with open(os.path.join(os.path.split(sys.argv[0])[0],"mml_log.txt"), 'w') as f:
            f.write(mml_log)
    except IOError:
        print "Couldn't write log file, displaying..."
        print mml_log
            
    print "Conversion successful."
    print
    
    clean_end()
