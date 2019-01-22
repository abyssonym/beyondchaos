# quick and EXTREMELY messy hack to run nascentorder functions in beyondchaos
# hopefully, this will allow updates on one end to easily copypasta
# to the other.
import ConfigParser, os.path, re
from copy import copy

from utils import (utilrandom as rng, open_mei_fallback as open)
from mml2mfvi import mml_to_akao

try:
    from sys import _MEIPASS
    MEI = True
except ImportError:
    MEI = False
    
HIROM = 0xC00000
MUSIC_PATH = os.path.join('custom','music')
INST_METADATA_OFFSET = 0x310000    #0x600 bytes
CONFIG = ConfigParser.RawConfigParser({
        'free_rom_space': '310600-380000',
        'allow_music_repeats': 'False',
        'preserve_song_data': 'False',
        'battle_music_lookup': 'battle1, boss2, boss3, battle2, battle3, 3B, battle4, boss1',
        'battle_music_ids': '24, new, new, new',
        'boss_music_ids': 'new, 14, 33',
        'pause_current_song': 'battle1, battle2, battle3, battle4, boss1',
        'songcount': '53C5E',
        'brrpointers': '53C5F, 53D1B',
        'brrloops': '53D1C, 53D99',
        'brrpitch': '53D9A, 53E17',
        'brradsr': '53E18, 53E95',
        'songpointers': '53E96, 53F94',
        'instruments': '53F95, 54A34',
        'brrpointerpointer': '50222, 50228, 5022E',
        'brrlooppointer': '5041C',
        'brrpitchpointer': '5049C',
        'brradsrpointer': '504DE',
        'songpointerpointer': '50538',
        'instrumentpointer': '501E3',
        'songdata': '85C7A, 9FDFF',
        'pausesongs': '506F9, 506FD',
        'battlesongs': '2BF3B, 2BF42'
        })
CONFIG.add_section('Music')
CONFIG.add_section('MusicPtr')
CONFIG.add_section('General')

freespace = None
spoiler = {}
f_tellmewhy = False
DEBUG = False
FLAGS = set()

def safepath(vpath):
    if not MEI:
        return vpath
    return [vpath, os.path.join(_MEIPASS, vpath)]

def isfile(fn):
    if not MEI:
        return os.path.isfile(fn)
    
    if os.path.isfile(fn):
        return True
    elif os.path.isfile(os.path.join(_MEIPASS, fn)):
        return True
    else:
        return False
    
#compatibility stubs
def to_default(cfgname): 
    return CONFIG[cfgname]

def despoil(t=""):
    pass

def dprint(t):
    pass

### begin functions shared with nascentorder

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
    if n: dprint("WARNING: tried to insert {} into {} bytes, truncated".format(hex(newdata), length))
    if not reversed: l.reverse()
    return byte_insert(data, position, "".join(l), length)

def bytes_to_int(data, reversed=True):
    n = 0
    for i, d in enumerate(data):
        if reversed:
            n = n + (ord(d) << (8 * i))
        else:
            n = (n << (8 * i)) + ord(d)
    return n
    
def put_somewhere(romdata, newdata, desc, f_silent=False):
    global freespace, spoiler
    if freespace is None:
        init_freespace()
    success = False
    for i, (start, end) in enumerate(freespace):
        room = end-start
        if room < len(newdata):
            continue
        else:
            romdata = byte_insert(romdata, start, newdata)
            freespace[i] = (start+len(newdata), end)
            if 'ROM Map' not in spoiler: spoiler['ROM Map'] = []
            spoiler['ROM Map'].append("  0x{:x} -- {}".format(start, desc))
            success= True
            break
    if not success:
        if not silent: print "ERROR: not enough free space to insert {}\n\n".format(desc)
        assert False
    return (romdata, start, end)
            
def init_freespace():
    global freespace
    fs = CONFIG.get('General', 'free_rom_space').split()
    freespace = []
    while not freespace:
        for t in fs:
            if '-' not in t: continue
            try:
                start, end = [int(n,16) for n in t.split('-')[0:2]]
            except ValueError:
                continue
            if start >= end: continue
            freespace.append((start, end))
        if not freespace:
            to_default('free_rom_space')
            continue
        break

def free_space(start, end):
    global freespace
    if freespace is None:
        init_freespace()
    freespace.append((start, end))
    
    newfs = []
    for i, (start, end) in enumerate(sorted(freespace)):
        if newfs:
            laststart, lastend = newfs[-1][0], newfs[-1][1]
            if start <= lastend + 1:
                newfs[-1] = (laststart, end)
            else:
                newfs.append((start, end))
        else:
            newfs.append((start, end))
    freespace = newfs

def claim_space(startc, endc):
    global freespace
    if freespace is None: return
    if startc > endc: return
    newfs = []
    for i, (start, end) in enumerate(sorted(freespace)):
        if startc <= start and endc >= end:
            pass
        elif startc <= start and endc >= start:
            newstart = endc+1
            if newstart < end:
                newfs.append((newstart, end))
        elif startc <= end and endc >= end:
            newend = startc-1
            if newend > start:
                newfs.append((start, newend))
        elif startc >= start and endc <= end:
            newend = startc-1
            newstart = endc+1
            if newend > start:
                newfs.append((start, newend))
            if newstart > end:
                newfs.append((newstart, end))
        else:
            newfs.append((start, end))
    freespace = newfs
    
def insert_instruments(data_in, metadata_pos= False):
    data = data_in
    samplecfg = ConfigParser.ConfigParser()
    samplecfg.read(safepath(os.path.join('tables', 'samples.txt')))
        
    #pull out instrument infos
    sampleptrs = [int(s.strip(),16) for s in CONFIG.get('MusicPtr', 'brrpointers').split(',')]
    if len(sampleptrs) != 2: sampleptrs = to_default('brrpointers')
    ptrdata = data[sampleptrs[0]:sampleptrs[1]+1]
    
    looplocs = [int(s.strip(),16) for s in CONFIG.get('MusicPtr', 'brrloops').split(',')]
    if len(looplocs) != 2: looplocs = to_default('brrloops')
    loopdata = data[looplocs[0]:looplocs[1]+1]
    
    pitchlocs = [int(s.strip(),16) for s in CONFIG.get('MusicPtr', 'brrpitch').split(',')]
    if len(pitchlocs) != 2: pitchlocs = to_default('brrpitch')
    pitchdata = data[pitchlocs[0]:pitchlocs[1]+1]
    
    adsrlocs = [int(s.strip(),16) for s in CONFIG.get('MusicPtr', 'brradsr').split(',')]
    if len(adsrlocs) != 2: adsrlocs = to_default('brradsr')
    adsrdata = data[adsrlocs[0]:adsrlocs[1]+1]
    
    for id, smp in samplecfg.items('Samples'):
        id = int(id, 16)
        
        inst = [i.strip() for i in smp.split(',')]
        if len(inst) < 4:
            print "WARNING: malformed instrument info '{}'".format(smp)
            continue
        name, loop, pitch, adsr = inst[0:4]
        filename = name + '.brr'
        
        try:
            with open(os.path.join('samples', filename), 'rb') as f:
                sdata = f.read()
        except IOError:
            print "WARNING: couldn't load sample file {}".format(filename)
            continue
        
        try:
            loop = chr(int(loop[0:2], 16)) + chr(int(loop[2:4], 16))
        except (ValueError, IndexError):
            print "WARNING: malformed loop info in '{}', using default".format(smp)
            loop = "\x00\x00"
        try:
            pitch = chr(int(pitch[0:2], 16)) + chr(int(pitch[2:4], 16))
        except (ValueError, IndexError):
            print "WARNING: malformed pitch info in '{}', using default".format(smp)
            pitch = "\x00\x00"
        if adsr:
            try:
                attack, decay, sustain, release = [int(p,16) for p in adsr.split()[0:4]]
                assert attack < 16
                assert decay < 8
                assert sustain < 8
                assert release < 32
                ad = 1 << 7
                ad += decay << 4
                ad += attack
                sr = sustain << 5
                sr += release
                adsr = chr(ad) + chr(sr)
            except (AssertionError, ValueError, IndexError):
                print "WARNING: malformed ADSR info in '{}', disabling envelope".format(smp)
                adsr = "\x00\x00"
        else:
            adsr = "\x00\x00"
            
        data, s, e = put_somewhere(data, sdata, "(sample) [{:02x}] {}".format(id, name))
        ptrdata = int_insert(ptrdata, (id-1)*3, s + HIROM, 3)
        loopdata = byte_insert(loopdata, (id-1)*2, loop, 2)
        pitchdata = byte_insert(pitchdata, (id-1)*2, pitch, 2)
        adsrdata = byte_insert(adsrdata, (id-1)*2, adsr, 2)
        
    data = byte_insert(data, sampleptrs[0], ptrdata)
    CONFIG.set('MusicPtr', 'brrpointers', "{:x}, {:x}".format(sampleptrs[0], sampleptrs[0]+len(data)))
    if metadata_pos:
        p = metadata_pos
        metadata = "\x00"*0x600
        metadata = byte_insert(metadata, 0x0, loopdata)
        metadata = byte_insert(metadata, 0x200, pitchdata)
        metadata = byte_insert(metadata, 0x400, adsrdata)
        
        CONFIG.set('MusicPtr', 'brrloops', "{:x}, {:x}".format(0+p, 0x1FF+p))
        CONFIG.set('MusicPtr', 'brrpitch', "{:x}, {:x}".format(0x200+p, 0x3FF+p))
        CONFIG.set('MusicPtr', 'brradsr', "{:x}, {:x}".format(0x400+p, 0x5FF+p))
        
        loc = int(CONFIG.get('MusicPtr', 'brrlooppointer'),16)
        data = int_insert(data, loc, 0+p+HIROM, 3)
        loc = int(CONFIG.get('MusicPtr', 'brrpitchpointer'),16)
        data = int_insert(data, loc, 0x200+p+HIROM, 3)
        loc = int(CONFIG.get('MusicPtr', 'brradsrpointer'),16)
        data = int_insert(data, loc, 0x400+p+HIROM, 3)
        
        data = byte_insert(data, p, metadata)
    else:
        data, s, e = put_somewhere(data, loopdata, "INSTRUMENT LOOP DATA")
        CONFIG.set('MusicPtr', 'brrloops', "{:x}, {:x}".format(s, e))
        loc = int(CONFIG.get('MusicPtr', 'brrlooppointer'),16)
        data = int_insert(data, loc, s + HIROM, 3)

        data, s, e = put_somewhere(data, pitchdata, "INSTRUMENT PITCH DATA")
        CONFIG.set('MusicPtr', 'brrpitch', "{:x}, {:x}".format(s, e))
        loc = int(CONFIG.get('MusicPtr', 'brrpitchpointer'),16)
        data = int_insert(data, loc, s + HIROM, 3)

        data, s, e = put_somewhere(data, adsrdata, "INSTRUMENT ADSR DATA")
        CONFIG.set('MusicPtr', 'brradsr', "{:x}, {:x}".format(s, e))
        loc = int(CONFIG.get('MusicPtr', 'brradsrpointer'),16)
        data = int_insert(data, loc, s + HIROM, 3)
    
    return data

def process_custom_music(data_in, eventmodes="", f_randomize=True, f_battleprog=True, f_mchaos=False, f_altsonglist=False):
    global freespace
    data = data_in
    freespacebackup = freespace
    f_repeat = CONFIG.getboolean('Music', 'allow_music_repeats')
    f_preserve = CONFIG.getboolean('Music', 'preserve_song_data')
    isetlocs = [int(s.strip(),16) for s in CONFIG.get('MusicPtr', 'instruments').split(',')]
    if len(isetlocs) != 2: isetlocs = to_default('instruments')
    songdatalocs = [int(s.strip(),16) for s in CONFIG.get('MusicPtr', 'songdata').split(',')]
    starts = songdatalocs[::2]
    ends = songdatalocs[1::2]
    if len(ends) < len(starts): ends.append(0x3FFFFF)
    songdatalocs = zip(starts, ends)
    native_prefix = "ff6_"
    isetsize = 0x20
    
    def spoil(txt):
        global spoiler
        if 'Music' not in spoiler: spoiler['Music'] = []
        spoiler['Music'].append(txt)
    
    def spooler(txt):
        global spoiler, f_tellmewhy
        if f_tellmewhy:
            if 'MusicPools' not in spoiler: spoiler['MusicPools'] = []
            spoiler['MusicPools'].append(txt)
    
    def usage_id(name):
        if name.count("_") <= 1:
            return name
        return "_".join(name.split("_")[0:2])
            
    class SongSlot:
        def __init__(self, id, chance=0, is_pointer=True, data="\x00\x00\x00"):
            self.id = id
            self.chance = chance
            self.choices = []
            self.changeto = ""
            self.is_pointer = is_pointer
            self.data = data
            self.inst = ""
            
    # figure out what instruments are available
    sampleptrs = [s.strip() for s in CONFIG.get('MusicPtr', 'brrpointers').split(',')]
    if len(sampleptrs) != 2: sampleptrs = to_default('brrpointers')
    instcount = (int(sampleptrs[1],16) + 1 - int(sampleptrs[0],16)) / 3
    
    ## figure out what music to use
    # build dict of original music from ROM
    try: songcountloc = int(CONFIG.get('MusicPtr', 'songcount'), 16)
    except ValueError: songcountloc = to_default('songcount')
    songptraddrs = [s.strip() for s in CONFIG.get('MusicPtr', 'songpointers').split(',')]
    if len(songptraddrs) != 2: songptraddrs = to_default('songpointers')
    songptraddrs = [int(p, 16) for p in songptraddrs]
    songptrdata = data[songptraddrs[0]:songptraddrs[1]+1]
    songptrs = []
    i = 0
    
    songcount = [ord(data[songcountloc])]
    while i < songcount[0]:
        try: p = songptrdata[i*3:i*3+3]
        except IndexError: p = '\x00\x00\x00'
        songptrs.append(bytes_to_int(p) - HIROM)
        i += 1
        
    # build identifier table
    songconfig = ConfigParser.ConfigParser()
    songconfig.read(safepath(os.path.join('tables','defaultsongs.txt')))
    songconfig.read(safepath(os.path.join('custom', 'songs.txt' if not f_altsonglist else 'songs_alt.txt')))
    songtable = {}
    for ss in songconfig.items('SongSlots'):
        vals = [s.strip() for s in ss[1].split(',')]
        songtable[vals[0]] = SongSlot(int(ss[0],16), chance=int(vals[1]))
    
    tierboss = dict(songconfig.items('TierBoss'))
    
    # determine which songs change
    used_songs = []
    songs_to_change = []
    for ident, s in songtable.items():
        if rng.randint(1, 100) > s.chance:
            if not f_repeat: used_songs.append(native_prefix + ident)
            songtable[ident].changeto = native_prefix + ident
        else:
            songs_to_change.append((ident, s))
            if f_mchaos and len(songconfig.items('Imports')) < len(songtable):
                if not songconfig.has_option('Imports', ident):
                    songconfig.set('Imports', native_prefix + ident, "")
    
    # build choice lists
    intensitytable = {}
    for song in songconfig.items('Imports'):
        canbe = [s.strip() for s in song[1].split(',')]
        intense, epic = 0, 0
        event_mults = {}
        if f_mchaos:
            for ident, s in songtable.items():
                s.choices.append(song[0])
        for c in canbe:
            if not c: continue
            if c[0] in eventmodes and ":" not in c:
                try:
                    event_mults[c[0]] = int(c[1:])
                except ValueError:
                    print "WARNING: in songs.txt: could not interpret '{}'".format(c)
        static_mult = 1
        for k, v in event_mults.items():
            static_mult *= v
        for c in canbe:
            if not c: continue
            if ":" in c and c[0] in eventmodes:
                c = c.split(':', 1)[1]
            if c[0] == "I":
                intense = int(c[1:])
            elif c[0] == "E" or c[0] == "G":
                epic = int(c[1:])
            elif not f_mchaos:
                if "*" in c:
                    ch = c.split('*')
                    mult = int(ch[1])
                    ch = ch[0]
                else:
                    ch = c
                    mult = 1 
                if ch in songtable:
                    songtable[ch].choices.extend([song[0]]*mult*static_mult)
        intense = max(0, min(intense, 99))
        epic = max(0, min(epic, 99))
        if (intense or epic):
            intensitytable[song[0]] = (intense, epic)
    
    for ident, s in songtable.items():
        spooler("{} pool ({}/{}): {}".format(ident, len([i for i in s.choices if i == native_prefix + ident]), len(s.choices), s.choices))
        
    # battle select
    def process_battleprog():
        newsongs = 0
        nextsongid = songcount[0]
        battleids = [s.strip() for s in CONFIG.get('Music', 'battle_music_ids').split(',')]
        bossids = [s.strip() for s in CONFIG.get('Music', 'boss_music_ids').split(',')]
        newidx = 0
        old_method = False if "battlebylevel" not in FLAGS else True
        if not old_method:
            if len(battleids) != 4 or len(bossids) != 3:
                print "WARNING: Improper song ID configuration for default method (by area)"
                print "     Falling back to old method (by level)"
                old_method = True
                FLAGS.append("battlebylevel")
                
        for i, id in enumerate(battleids):
            if str(id).lower() == "new":
                songtable['NaObattle' + str(newidx)] = SongSlot(nextsongid, chance=100)
                battleids[i] = nextsongid
                nextsongid += 1
                newidx += 1
            else:
                battleids[i] = int(id, 16)
        newidx = 0
        for i, id in enumerate(bossids):
            if str(id).lower() == "new":
                songtable['NaOboss' + str(newidx)] = SongSlot(nextsongid, chance=100)
                bossids[i] = nextsongid
                nextsongid += 1
                newidx += 1
            else:
                bossids[i] = int(id, 16)
        claim_space(songptraddrs[0], songptraddrs[0] + 3*len(songtable))
        
        # what this is trying to do is:
        # we judge songs by pure INTENSITY or by combined INTENSITY and GRANDEUR
        # old method: all songs separated by pure intensity into battle and boss
        # within these categories they are set in combined rating order
        # new method: uses subsets of the I/G grid as pools for songs.
        # 1. event-battle (boss0) is chosen from I>33, G<33
        # 2. boss2 is chosen from I>min(boss0,60), G>66
        # 3. boss1 is chosen from I>boss0, boss0<G<boss2
        # 4. battle0 and battle1 chosen from I<boss0, G<max(50,boss1), sorted by G
        # 5. battle2 and battle3 chosen from I<boss2, G>battle1
        def intensity_subset(imin=0, gmin=0, imax=99, gmax=99):
            return {k: v for k, v in intensitytable.items() if v[0] >= imin and v[0] <= imax and v[1] >= gmin and v[1] <= gmax and usage_id(k) not in used_songs}
            
        battlecount = len(battleids) + len(bossids)
        while len(intensitytable) < battlecount:
            dprint("WARNING: not enough battle songs marked, adding random song to pool")
            newsong = rng.choice([k[0] for k in songconfig.items('Imports') if k not in intensitytable])
            intensitytable[newsong] = (rng.randint(0,9), rng.randint(0,9))

        if old_method:
            retry = True
            while retry:
                retry = False
                battlechoices = rng.sample([(k, sum(intensitytable[k]), intensitytable[k][0]) for k in intensitytable.keys()], battlecount)
                for c in battlechoices:
                    if usage_id(battlechoices[0]) in used_songs: retry = True
            battlechoices.sort(key=operator.itemgetter(1))
            battleprog = [None]*len(battleids)
            bossprog = [None]*len(bossids)
            bosschoices = []
            battlechoices.sort(key=operator.itemgetter(2))
            for i in xrange(0, len(bossids)):
                bosschoices.append(battlechoices.pop(-1))
            bosschoices.sort(key=operator.itemgetter(1))
            while None in bossprog:
                bossprog[bossprog.index(None)] = bosschoices.pop(-1)
            bossprog.reverse()
            battlechoices.sort(key=operator.itemgetter(1))
            while None in battleprog:
                battleprog[battleprog.index(None)] = battlechoices.pop(0)
            battleprog = [b[0] for b in battleprog]
            bossprog = [b[0] for b in bossprog]
        else:
            tries=0
            while True:
                try:
                    event, (ei, eg) = rng.choice(intensity_subset(imin=33, gmax=33).items())
                    bt = min(ei,60) 

                    super, (si, sg) = rng.choice(intensity_subset(imin=bt, gmin=66).items())
                    boss, (bi, bg) = rng.choice(intensity_subset(imin=bt, gmin=max(22,eg), gmax=sg).items())
                    wt = min(80,max(bg, 50))
                    balance = rng.sample(intensity_subset(imax=bt, gmax=wt).items(), 2)
                    if balance[0][1][0] + balance[0][1][1] > balance[1][1][0] + balance[1][1][1]:
                        boutside, (boi, bog) = balance[1]
                        binside, (bii, big) = balance[0]
                    else:
                        boutside, (boi, bog) = balance[0]
                        binside, (bii, big) = balance[1]
                    ruin = rng.sample(intensity_subset(imax=min(bi, si), gmin=max(bog,big)).items(), 2)
                    if ruin[0][1][0] + ruin[0][1][1] > ruin[1][1][0] + ruin[1][1][1]:
                        routside, (roi, rog) = ruin[1]
                        rinside, (rii, rig) = ruin[0]
                    else:
                        routside, (roi, rog) = ruin[0]
                        rinside, (rii, rig) = ruin[1]
                    battleprog = [boutside, binside, routside, rinside]
                    bossprog = [event, boss, super]
                    if len(set(battleprog) | set(bossprog)) < 7:
                        tries += 1
                        continue
                except IndexError as e:
                    print "DEBUG: new battle prog mode failed {}rd attempt: {}".format(tries, e)
                    raw_input("press enter to continue>")
                    if tries >= 500:
                        FLAGS.append("battlebylevel")
                        print "WARNING: couldn't find valid configuration of battle songs by area."
                        print "     Falling back to old method (by level)."
                        return process_battleprog()
                    else:
                        tries += 1
                        continue
                break
                    
        fightids = [(id, False) for id in battleids] + [(id, True) for id in bossids]
        for id, is_boss in fightids:
            for ident, s in songtable.items():
                if s.id == id:
                    if is_boss:
                        changeto = bossprog[bossids.index(id)]
                    else:
                        changeto = battleprog[battleids.index(id)]
                    s.changeto = changeto
                    used_songs.append(usage_id(changeto))

        return (battleids, bossids)
    
    def check_ids_fit():
        n_by_isets = (isetlocs[1] - isetlocs[0] + 1) / 0x20
        n_by_sptrs = (songptraddrs[1] - songptraddrs[0] + 1) / 3
        if len(songtable) > n_by_isets or len(songtable) > n_by_sptrs:
            return False
        return True
        
    def process_mml(id, mml, name):
        sfx = ""
        if id == 0x29:
            sfx = "sfx_zozo.mmlappend"
        elif id == 0x4F:
            sfx = "sfx_wor.mmlappend"
        elif id == 0x20:
            sfx = "sfx_train.mmlappend"
            mml = re.sub("\{[^}]*?([0-9]+)[^}]*?\}", "$888\g<1>", mml)
            for i in xrange(1,9):
                if "$888{}".format(i) not in mml:
                    mml = mml + "\n$888{} r;".format(i)
        if sfx:
            try:
                with open(os.path.join(MUSIC_PATH, sfx), 'r') as f:
                    mml += f.read()
            except IOError:
                print "couldn't open {}".format(sfx)
                
        return mml_to_akao(mml, name, True if (id == 0x4F) else False)
    
    def process_tierboss(opts):
        opts = [o.strip() for o in opts.split(',')]
        attempts = 0
        fallback = False
        while True:
            attempts += 1
            if attempts >= 1000:
                print "warning: check your tierboss config in songs.txt"
                fallback = True
                attempts = 0
            retry = False
            tiernames = rng.sample(opts, 3)
            tierfiles = []
            for n in tiernames:
                try:
                    with open(os.path.join(MUSIC_PATH, n + '_dm.mml'), 'r') as f:
                        tierfiles.append(f.read())
                except IOError:
                    print "couldn't open {}".format(n + '_dm.mml')
                    retry = True
            if retry: continue
            
            mml = re.sub('[~!]', '', tierfiles[0])
            mml = re.sub('[?_]', '?', mml)
            mml = re.sub('j([0-9]+),([0-9]+)', 'j\g<1>,555\g<2>', mml)
            mml = re.sub('([;:\$])([0-9]+)(?![,0-9])', '\g<1>555\g<2>', mml)
            mml = re.sub('([;:])555444([0-9])', '\g<1>222\g<2>', mml)
            mml = re.sub('#VARIANT', '#', mml, flags=re.IGNORECASE)
            mml = re.sub('{.*?}', '', mml)
            mml = re.sub('\$555444([0-9])', '{\g<1>}', mml)
            mml = re.sub('#def\s+(\S+)\s*=', '#def 555\g<1>=', mml, flags=re.IGNORECASE)
            mml = re.sub("'(.*)'", "'555\g<1>'", mml)
            tierfiles[0] = mml
            
            mml = re.sub('[?!]', '', tierfiles[1])
            mml = re.sub('[~_]', '?', mml)
            mml = re.sub('j([0-9]+),([0-9]+)', 'j\g<1>,666\g<2>', mml)
            mml = re.sub('([;:\$])([0-9]+)(?![,0-9])', '\g<1>666\g<2>', mml)
            mml = re.sub('([;:])666444([0-9])', '\g<1>333\g<2>', mml)
            mml = re.sub('\$666444([0-9])', '$222\g<1>', mml)
            mml = re.sub('#VARIANT', '#', mml, flags=re.IGNORECASE)
            mml = re.sub('{.*?}', '', mml)
            mml = re.sub('#def\s+(\S+)\s*=', '#def 666\g<1>=', mml, flags=re.IGNORECASE)
            mml = re.sub("'(.*)'", "'666\g<1>'", mml)
            mml = re.sub('"', ')', mml)
            tierfiles[1] = mml
            
            mml = re.sub('[?_]', '', tierfiles[2])
            mml = re.sub('[~!]', '?', mml)
            mml = re.sub('j([0-9]+),([0-9]+)', 'j\g<1>,777\g<2>', mml)
            mml = re.sub('([;:\$])([0-9]+)(?![,0-9])', '\g<1>777\g<2>', mml)
            mml = re.sub('\$777444([0-9])', '$333\g<1>', mml)
            mml = re.sub('#VARIANT', '#', mml, flags=re.IGNORECASE)
            mml = re.sub('{.*?}', '', mml)
            mml = re.sub('#def\s+(\S+)\s*=', '#def 777\g<1>=', mml, flags=re.IGNORECASE)
            mml = re.sub("'(.*)'", "'777\g<1>'", mml)
            mml = re.sub('"', '(', mml)
            tierfiles[2] = mml
            
            mml = "#VARIANT / \n#VARIANT ? ignore \n" + tierfiles[0] + tierfiles[1] + tierfiles[2]
            ## uncomment to debug tierboss MML
            #with open("lbdebug.mml", "w") as f:
            #    f.write(mml)
                
            akao = mml_to_akao(mml, str(tiernames), variant='_default_')
            inst = akao['_default_'][1]
            akao = akao['_default_'][0]
            if len(akao) >= 0x1000:
                continue
            break
        return (akao, inst)
        
    # choose replacement songs
    used_songs_backup = used_songs
    songtable_backup = songtable
    songs_to_change_backup = songs_to_change
    keeptrying = True
    attempts = 0
    songlocations = {} #debug
    while keeptrying and attempts <= 1000:
        attempts += 1
        keeptrying = False
        data = data_in
        freespace = freespacebackup
        used_songs = copy(used_songs_backup)
        songtable = copy(songtable_backup)
        songs_to_change = copy(songs_to_change_backup)
        set_by_battleprog = []
        if f_battleprog:
            battleprog = process_battleprog()
            set_by_battleprog = battleprog[0] + battleprog[1]
        songs_to_change = [s for s in songs_to_change if s[1].id not in set_by_battleprog]
        f_moveinst = False if check_ids_fit() or f_preserve else True
        rng.shuffle(songs_to_change)
        for ident, s in songs_to_change:
            if ident in tierboss:
                songtable[ident].changeto = '!!tierboss'
            else:
                choices = [c for c in songtable[ident].choices if usage_id(c) not in used_songs]
                if not choices: choices.append(native_prefix + ident)
                newsong = rng.choice(choices)
                if (usage_id(newsong) in used_songs) and (not f_repeat):
                    keeptrying = True
                    break
                else:
                    if not f_repeat: used_songs.append(usage_id(newsong))
                    songtable[ident].changeto = newsong if f_randomize else native_prefix + ident
                
        if keeptrying:
            dprint("failed music generation during song selection")
            continue
        
        #get data now, so we can keeptrying if there's not enough space
        for ident, s in songtable.items():
            if s.changeto == '!!tierboss':
                s.data, s.inst = process_tierboss(tierboss[ident])
                s.is_pointer = False
            # case: get song from MML
            elif isfile(os.path.join(MUSIC_PATH, s.changeto + ".mml")) or isfile(os.path.join(MUSIC_PATH, usage_id(s.changeto) + ".mml")):
                mml, variant = "", ""
                akao = {}
                try:
                    with open(os.path.join(MUSIC_PATH, usage_id(s.changeto)) + ".mml", 'r') as mmlf:
                        mml = mmlf.read()
                except IOError:
                    pass
                if mml:
                    akao = process_mml(s.id, mml, usage_id(s.changeto) + ".mml")
                if s.changeto.count("_") >= 2:
                    variant = s.changeto[len(usage_id(s.changeto)):]
                    if variant[0] == "_" and len(variant) > 1: variant = variant[1:]
                    if variant not in akao:
                        variant = ""
                        try:
                            with open(os.path.join(MUSIC_PATH, s.changeto) + ".mml", 'r') as mmlf:
                                mml = mmlf.read()
                        except IOError:
                            mml = ""
                        if mml:
                            akao = process_mml(s.id, mml, s.changeto + ".mml")
                        else:
                            akao = {}
                if not akao:
                    print "couldn't find valid mml for {}".format(s.changeto)
                    keeptrying = True
                    break
                if variant and variant in akao:
                    s.data = akao[variant][0]
                    s.inst = akao[variant][1]
                else:
                    s.data = akao['_default_'][0]
                    s.inst = akao['_default_'][1]
                s.is_pointer = False
                if max(map(ord, s.inst)) > instcount:
                    if 'nopatch' in akao:
                        s.inst = akao['nopatch'][1]
                        s.data = akao['nopatch'][0]
                    elif 'nat' in akao:
                        s.inst = akao['nat'][1]
                        s.data = akao['nat'][0]
                    else:
                        print "WARNING: instrument out of range in {}".format(s.changeto + ".mml")
            # case: get song from source ROM
            elif not isfile(os.path.join(MUSIC_PATH, s.changeto + "_data.bin")):
                target = s.changeto[len(native_prefix):]
                if (s.changeto[:len(native_prefix)] == native_prefix and
                        target in songtable):
                    sid = songtable[target].id
                    loc = songptrs[sid]
                    assert loc >= min([l[0] for l in songdatalocs])
                    if f_preserve:
                        s.is_pointer = True
                        s.data = loc
                    else:
                        s.is_pointer = False
                        slen = bytes_to_int(data[loc:loc+2]) + 2
                        s.data = data[loc:loc+slen]
                    loc = isetlocs[0] + sid * isetsize
                    assert loc + isetsize <= isetlocs[1] + 1
                    s.inst = data[loc:loc+isetsize]
                else:
                    print "target song {} not found for id {} {}".format(s.changeto, s.id, ident)
                    keeptrying = True
                    break
            else:
                s.is_pointer = False
                # check instrument validity
                try:
                    fi = open(os.path.join(MUSIC_PATH, s.changeto + "_inst.bin"), "rb")
                    s.inst = fi.read()
                    fi.close()
                except IOError:
                    print "couldn't open {}_inst.bin".format(s.changeto)
                    keeptrying = True
                    break
                if max(map(ord, s.inst)) > instcount:
                    # case: get nopatch version
                    try:
                        fi = open(os.path.join(MUSIC_PATH, s.changeto + "_inst_nopatch.bin"), "rb")
                        s.inst = fi.read()
                        fi.close()
                    except IOError:
                        dprint("translating inst file for id{} {}".format(s.id, s.changeto))
                        dprint("translation is NYI")
                    try:
                        fi = open(os.path.join(MUSIC_PATH, s.changeto + "_data_nopatch.bin"), "rb")
                        s.data = fi.read()
                        fi.close()
                    except IOError:
                        try:
                            fi = open(os.path.join(MUSIC_PATH, s.changeto + "_data.bin"), "rb")
                            s.data = fi.read()
                            fi.close()
                        except IOError:
                            print "couldn't open {}_data.bin".format(s.changeto)
                            keeptrying = True
                            break
                else:
                    # case: get standard version
                    try:
                        fi = open(os.path.join(MUSIC_PATH, s.changeto + "_data.bin"), "rb")
                        s.data = fi.read()
                        fi.close()
                    except IOError:
                        print "couldn't open {}_data.bin".format(s.changeto)
                        keeptrying = True
                        break
        
        if keeptrying:
            dprint("failed music generation during data read")
            continue
        
        # try to fit it all in!
        if f_preserve:
            freelocs = []
            for b, e in songdatalocs:
                i = b
                lastchar = ''
                streak = 0
                while i <= e:
                    curchar = data[i]
                    if curchar == lastchar:
                        streak += 1
                    else:
                        if streak >= 64:
                            freelocs.append((i-(streak+1), i-1))
                        streak = 0
                    lastchar = curchar
                    i += 1
                if streak >= 64: freelocs.append((i-streak, i))
            songdatalocs = freelocs
        else:
            free_space(songdatalocs[0][0], songdatalocs[0][1])
        if f_moveinst:
            instsize = (len(songtable)+1) * 0x20
            for i, l in enumerate(songdatalocs):
                if l[1] - l[0] > instsize:
                    new_instloc = (songdatalocs[i][0], songdatalocs[i][0] + instsize - 1)
                    songdatalocs[i] = (songdatalocs[i][0] + instsize, songdatalocs[i][1])
                    break
            for i, l in enumerate(songdatalocs):
                if l[0] > l[1]: del songdatalocs[i]
        space = [e - b for b, e in songdatalocs]
        songdata = [""] * len(space)
        songinst = data[isetlocs[0]:isetlocs[1]+1]    
        if f_moveinst: free_space(isetlocs[0], isetlocs[1])
        claim_space(songptraddrs[0], songptraddrs[0] + 3*(len(songtable)+1))
        for ident, s in songtable.items():
            if not s.is_pointer:
                try:
                    data, start, end = put_somewhere(data, s.data, "  (song) [{:02x}] {}".format(s.id, s.changeto), True)
                except AssertionError:
                    data = data_in
                    continue
                songinst = byte_insert(songinst, s.id * isetsize, s.inst, isetsize)
                songptrdata = int_insert(songptrdata, s.id * 3, start + HIROM, 3)
                songlocations[s.id] = start
            else:
                songptrdata = int_insert(songptrdata, s.id * 3, s.data, 3)
                songlocations[s.id] = s.data - HIROM
                    
    if attempts >= 1000:
        print "failed to produce valid music set"
        print "    try increasing available space or adjusting song insert list"
        print "    to use less space"
        print
        return data_in
    
    # build battle music related tables
    if f_battleprog:
        translator = {}
        battletable = [s.strip() for s in CONFIG.get('Music', 'battle_music_lookup').split(',')]
        if len(battletable) != 8: battletable = to_default('battle_music_lookup')
        pausetable = [s.strip() for s in CONFIG.get('Music', 'pause_current_song').split(',')]
        pausetableloc = int([s.strip() for s in CONFIG.get('MusicPtr', 'pausesongs').split(',')][0], 16)
        battlesongsloc = int([s.strip() for s in CONFIG.get('MusicPtr', 'battlesongs').split(',')][0], 16)
        
        for i, s in enumerate(battleprog[0]):
            translator['battle' + str(i + 1)] = s
        for i, s in enumerate(battleprog[1]):
            translator['boss' + str(i + 1)] = s
        
        def translatetbl(table):
            for i, v in enumerate(table):
                if v in translator:
                    table[i] = translator[v]
                else:
                    table[i] = int(v, 16)
        translatetbl(battletable)
        translatetbl(pausetable)
        
        battletable = "".join(map(chr, battletable))
        pausetable = "".join(map(chr, pausetable))
        
        
    # write to rom        
    if f_battleprog:
        data = byte_insert(data, pausetableloc, pausetable, 5)
        data = byte_insert(data, battlesongsloc, battletable, 8)
    data = int_insert(data, songcountloc, len(songtable)+1, 1)
    if not f_moveinst: songptrdata = songptrdata[:songptraddrs[1] + 1]
    data = byte_insert(data, songptraddrs[0], songptrdata)
    if f_moveinst:
        data, s, e = put_somewhere(data, songinst, "INSTRUMENT TABLES FOR SONGS")
        instlocptr = int(CONFIG.get('MusicPtr', 'instrumentpointer'), 16)
        data = int_insert(data, instlocptr, s + HIROM, 3)
    else:
        data = byte_insert(data, isetlocs[0], songinst, end=isetlocs[1])

    # make spoiler
    changed_songs = {}
    for ident, s in songtable.items():
        if s.changeto != native_prefix + ident:
            changed_songs[s.id] = (ident, s.changeto)
    spoiltext = []
    for id, s in sorted(changed_songs.items()):
        spoiltext.append(hex(id)[2:] + " : " + s[0] + " ")
    arrowpos = max(map(len, spoiltext))
    for i, (id, s) in enumerate(sorted(changed_songs.items())):
        while len(spoiltext[i]) < arrowpos:
            spoiltext[i] += " "
        spoiltext[i] += "-> {}".format(s[1])
    for t in spoiltext: spoil(t)
    
    if DEBUG:
        fullsonglist = {}
        for ident, s in songtable.items():
            fullsonglist[s.id] = (ident, s.changeto, songlocations[s.id])
        despoil("song data locations")
        for id, (ident, newsong, loc) in fullsonglist.items():
            despoil("{} ({}) -----> {} at {}".format(hex(id), ident, newsong, hex(loc)))
    return data

### end functions shared with nascentorder

def process_formation_music_by_table(data, form_music_overrides={}):
    
    o_forms = 0xF6200
    o_formaux = 0xF5900
    o_monsters = 0xF0000
    o_epacks = 0xF5000
    
    with open(os.path.join("tables","formationmusic.txt"), "r") as f:
        tbl = f.readlines()
    
    table = []
    for line in tbl:
        line = [s.strip() for s in line.split()]
        if len(line) == 2: line.append(None)
        if len(line) == 3: table.append(line)
    
    event_formations = set()
    for i in xrange(0,256):
        loc = o_epacks + i*4
        event_formations.add(bytes_to_int(data[loc:loc+2]))
        event_formations.add(bytes_to_int(data[loc+2:loc+4]))
    
    for line in table:
        #table format: [formation id] [music bitfield] [force music on/off]
        #value of 'c' forces music on if:
        #   unrunnable enemy in formation
        #   hard to run enemy in formation
        #   "attack first" enemy in formation
        #   formation is present in packs > 255 (event battles)
        try:
            fid = int(line[0])
        except ValueError:
            continue
        
        # account for random music settings in other parts of the randomizer
        # ancient cave bosses can be set to 5, 2, or 4
        # superbosses (formations_hidden) can be set to anything 1-5
        # I don't recommend using random tierboss in this way; it should only be used on the tierboss itself. So we need to adjust these settings
        # 1 (boss) remains 1
        # 2 (superboss) changes to 6 (battle4)
        # 3 (savethem) changes to 5 (battle3)
        # 4 (returners) changes to 7 (event)
        # 5 (dmad1) changes to 2 (superboss)
        force_music = False
        if fid in form_music_overrides:
            mutation_table = [0, 1, 6, 5, 7, 2, 0, 0]
            line[1] = mutation_table[form_music_overrides[fid]]
            force_music = True
            
        try:
            mbf = int(line[1]) << 3
        except ValueError:
            mbf = 0
        pos = o_formaux + fid*4
        dat = list(data[pos:pos+4])
        
        dat[3] = chr((ord(dat[3]) & 0b11000111) | mbf)
        if line[2] == "0":
            dat[1] = chr(ord(dat[1]) | 0b00000010)
            dat[3] = chr(ord(dat[3]) | 0b10000000)
        elif line[2] == "c":
            if fid in event_formations:
                force_music = True
            else:
                for m in xrange(0,6):
                    fpos = o_forms + fid*15
                    if (ord(data[fpos+1]) >> m) & 1:
                        mid = ord(data[fpos+2+m]) + (((ord(data[fpos+14]) >> m) & 1) << 8)
                        mb = ord(data[o_monsters+mid*32+19])
                        if mb & 0b00001011:
                            force_music = True
                            break
        if line[2] == "1" or force_music:
            dat[1] = chr(ord(dat[1]) & 0b11111101)
            dat[3] = chr(ord(dat[3]) & 0b01111111)
        data = byte_insert(data, pos, ''.join(dat))
    
    return data
        
def randomize_music(fout, f_mchaos=False, codes=[], form_music_overrides={}):
    events = ""
    if 'christmas' in codes:
        events += "W"
    if 'halloween' in codes:
        events += "H"
    fout.seek(0)
    data = fout.read()
    data = insert_instruments(data, INST_METADATA_OFFSET)
    data = process_custom_music(data, f_mchaos=f_mchaos, eventmodes=events)
    data = process_formation_music_by_table(data, form_music_overrides=form_music_overrides)
    
    fout.seek(0)
    fout.write(data)
    return "\n".join(spoiler['Music'])
    