

# quick and EXTREMELY messy hack to run nascentorder functions in beyondchaos
# hopefully, this will allow updates on one end to easily copypasta
# to the other.
import configparser, os.path, re
from copy import copy

from locationrandomizer import get_locations, get_location
from dialoguemanager import set_dialogue_var, set_pronoun, patch_dialogue, load_patch_file
from utils import (utilrandom as random, open_mei_fallback as open)
from mml2mfvi import mml_to_akao


try:
    from sys import _MEIPASS
    MEI = True
except ImportError:
    MEI = False
    
HIROM = 0xC00000
MUSIC_PATH = os.path.join('custom','music')
INST_METADATA_OFFSET = 0x310000    #0x600 bytes
CONFIG = configparser.RawConfigParser({
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

# define native song information
class TrackMetadata:
    def __init__(self, title="", album="", composer="", arranged=""):
        self.title, self.album, self.composer, self.arranged = title, album, composer, arranged
        
metadata = {
    "ff6_prelude": "The Prelude",
    "ff6_omen1": "Omen, part 1",
    "ff6_omen2": "Omen, part 2",
    "ff6_omen3": "Omen, part 3",
    "ff6_awakening": "Awakening",
    "ff6_balance": "Terra's Theme",
    "ff6_shadow": "Shadow's Theme",
    "ff6_strago": "Strago's Theme",
    "ff6_gau": "Gau's Theme",
    "ff6_figaro": "Edgar & Sabin's Theme",
    "ff6_coin": "Coin of Fate",
    "ff6_cyan": "Cyan's Theme",
    "ff6_locke": "Locke's Theme",
    "ff6_rachel": "Forever Rachel",
    "ff6_relm": "Relm's Theme",
    "ff6_setzer": "Setzer's Theme",
    "ff6_daryl": "Epitaph",
    "ff6_celes": "Celes's Theme",
    "ff6_chocobo": "Techno de Chocobo",
    "ff6_boss": "The Decisive Battle",
    "ff6_johnny": "Johnny C. Bad",
    "ff6_kefka": "Kefka",
    "ff6_narshe": "The Mines of Narshe",
    "ff6_forest": "Phantom Forest",
    "ff6_veldt": "The Veldt",
    "ff6_savethem": "Protect the Espers! // Save Them!",
    "ff6_gestahl": "The Gestahl Empire",
    "ff6_troops": "Troops March On",
    "ff6_martiallaw": "Under Martial Law",
    "ff6_metamorphosis": "Metamorphosis",
    "ff6_train": "Phantom Train",
    "ff6_espers": "Esper World",
    "ff6_grandfinale": "Grand Finale?",
    "ff6_mountain": "Mt. Koltz",
    "ff6_battle": "Battle",
    "ff6_fanfareslow": "Unused Fanfare",
    "ff6_wed_dance": "Wedding Waltz - Dance",
    "ff6_aria": "Aria di Mezzo Carattere",
    "ff6_serpent": "The Serpent Trench",
    "ff6_zozo": "Slam Shuffle",
    "ff6_town": "Kids Run Through the City",
    "ff6_what": "What?",
    "ff6_gogo": "Gogo's Theme",
    "ff6_returners": "The Returners",
    "ff6_fanfare": "Victory Fanfare",
    "ff6_umaro": "Umaro's Theme",
    "ff6_moogles": "Mog's Theme",
    "ff6_unforgiven": "The Unforgiven",
    "ff6_atma": "Battle to the Death",
    "ff6_town_ruin": "From That Day On... // The Day After",
    "ff6_blackjack": "The Airship Blackjack",
    "ff6_catastrophe": "Catastrophe",
    "ff6_owzer": "The Magic House",
    "ff6_dmad123": "Dancing Mad (part 1)",
    "ff6_spinachrag": "Spinach Rag",
    "ff6_death": "Rest in Peace",
    "ff6_opera_intro": "Overture - Intro",
    "ff6_opera_draco": "Overture - Draco",
    "ff6_opera_overture": "Overture - Intermission",
    "ff6_wed_attack": "Wedding Waltz - Attack",
    "ff6_wed_duel": "Wedding Waltz - Duel",
    "ff6_wed_rafters": "Wedding Waltz - In the Rafters",
    "ff6_magitek": "Devil's Lab // Magitek Research Facility",
    "ff6_floatingcont": "Floating Continent",
    "ff6_fanatics": "The Fanatics",
    "ff6_kefkastower": "Kefka's Tower",
    "ff6_ruin": "Dark World",
    "ff6_dmad5": "Dancing Mad (part 5)",
    "ff6_dmad4": "Dancing Mad (part 4)",
    "ff6_ending1": "Balance is Restored (part 1)",
    "ff6_ending2": "Balance is Restored (part 2)"
    }
for k, v in metadata.items():
    metadata[k] = TrackMetadata(v, "Final Fantasy VI", "Nobuo Uematsu", "Nobuo Uematsu")
    
### begin functions shared with nascentorder

def byte_insert(data, position, newdata, maxlength=0, end=0):
    while position > len(data):
        data = data + b"\x00"
    if end:
        maxlength = end - position + 1
    if maxlength and len(data) > maxlength:
        newdata = newdata[:maxlength]
    return data[:position] + newdata + data[position+len(newdata):]

    
def int_insert(data, position, newdata, length, reversed=True):
    n = int(newdata)
    l = []
    while len(l) < length:
        l.append(n & 0xFF)
        n = n >> 8
    if n: dprint("WARNING: tried to insert {} into {} bytes, truncated".format(hex(newdata), length))
    if not reversed: l.reverse()
    return byte_insert(data, position, bytes(l), length)

def bytes_to_int(data, reversed=True):
    n = 0
    for i, d in enumerate(data):
        if reversed:
            n = n + (d << (8 * i))
        else:
            n = (n << (8 * i)) + d
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
        if not silent: print("ERROR: not enough free space to insert {}\n\n".format(desc))
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
    
def insert_instruments(fout, metadata_pos= False):
    fout.seek(0)
    data = fout.read()
    samplecfg = configparser.ConfigParser()
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
            print("WARNING: malformed instrument info '{}'".format(smp))
            continue
        name, loop, pitch, adsr = inst[0:4]
        filename = name + '.brr'
        
        try:
            with open(os.path.join('data', 'samples', filename), 'rb') as f:
                sdata = f.read()
        except IOError:
            print("WARNING: couldn't load sample file {}".format(filename))
            continue
        
        try:
            loop = bytes([int(loop[0:2], 16), int(loop[2:4], 16)])
        except (ValueError, IndexError):
            print("WARNING: malformed loop info in '{}', using default".format(smp))
            loop = b"\x00\x00"
        try:
            pitch = bytes([int(pitch[0:2], 16), int(pitch[2:4], 16)])
        except (ValueError, IndexError):
            print("WARNING: malformed pitch info in '{}', using default".format(smp))
            pitch = b"\x00\x00"
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
                adsr = bytes([ad, sr])
            except (AssertionError, ValueError, IndexError):
                print("WARNING: malformed ADSR info in '{}', disabling envelope".format(smp))
                adsr = b"\x00\x00"
        else:
            adsr = b"\x00\x00"
            
        data, s, e = put_somewhere(data, sdata, "(sample) [{:02x}] {}".format(id, name))
        ptrdata = int_insert(ptrdata, (id-1)*3, s + HIROM, 3)
        loopdata = byte_insert(loopdata, (id-1)*2, loop, 2)
        pitchdata = byte_insert(pitchdata, (id-1)*2, pitch, 2)
        adsrdata = byte_insert(adsrdata, (id-1)*2, adsr, 2)
        
    data = byte_insert(data, sampleptrs[0], ptrdata)
    CONFIG.set('MusicPtr', 'brrpointers', "{:x}, {:x}".format(sampleptrs[0], sampleptrs[0]+len(data)))
    if metadata_pos:
        p = metadata_pos
        
        imetadata = b"\x00"*0x600
        imetadata = byte_insert(imetadata, 0x0, loopdata)
        imetadata = byte_insert(imetadata, 0x200, pitchdata)
        imetadata = byte_insert(imetadata, 0x400, adsrdata)
        
        CONFIG.set('MusicPtr', 'brrloops', "{:x}, {:x}".format(0+p, 0x1FF+p))
        CONFIG.set('MusicPtr', 'brrpitch', "{:x}, {:x}".format(0x200+p, 0x3FF+p))
        CONFIG.set('MusicPtr', 'brradsr', "{:x}, {:x}".format(0x400+p, 0x5FF+p))
        
        loc = int(CONFIG.get('MusicPtr', 'brrlooppointer'),16)
        data = int_insert(data, loc, 0+p+HIROM, 3)
        loc = int(CONFIG.get('MusicPtr', 'brrpitchpointer'),16)
        data = int_insert(data, loc, 0x200+p+HIROM, 3)
        loc = int(CONFIG.get('MusicPtr', 'brradsrpointer'),16)
        data = int_insert(data, loc, 0x400+p+HIROM, 3)
        
        data = byte_insert(data, p, imetadata)
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
    
    fout.seek(0)
    fout.write(data)

def process_custom_music(data_in, eventmodes="", opera=None, f_randomize=True, f_battleprog=True, f_mchaos=False, f_altsonglist=False):
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
    songdatalocs = list(zip(starts, ends))
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
        def __init__(self, id, chance=0, is_pointer=True, data=b"\x00\x00\x00"):
            self.id = id
            self.chance = chance
            self.choices = []
            self.changeto = ""
            self.is_pointer = is_pointer
            self.data = data
            self.inst = b""
            
    # figure out what instruments are available
    sampleptrs = [s.strip() for s in CONFIG.get('MusicPtr', 'brrpointers').split(',')]
    if len(sampleptrs) != 2: sampleptrs = to_default('brrpointers')
    instcount = (int(sampleptrs[1],16) + 1 - int(sampleptrs[0],16)) // 3
    
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
    
    songcount = [data[songcountloc]]
    while i < songcount[0]:
        try: p = songptrdata[i*3:i*3+3]
        except IndexError: p = b'\x00\x00\x00'
        songptrs.append(bytes_to_int(p) - HIROM)
        i += 1
        
    # build identifier table
    songconfig = configparser.ConfigParser()
    songconfig.read(safepath(os.path.join('tables','defaultsongs.txt')))
    songconfig.read(safepath(os.path.join('custom', 'songs.txt' if not f_altsonglist else 'songs_alt.txt')))
    songtable = {}
    for ss in songconfig.items('SongSlots'):
        vals = [s.strip() for s in ss[1].split(',')]
        songtable[vals[0]] = SongSlot(int(ss[0],16), chance=int(vals[1]))
    
    tierboss = dict(songconfig.items('TierBoss'))
    
    if len(songtable) > songcount[0]:
        songcount[0] = len(songtable)
        
    # determine which songs change
    used_songs = []
    songs_to_change = []
    for ident, s in songtable.items():
        if random.randint(1, 100) > s.chance:
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
                if ident.endswith("_tr"): continue
                if ident.endswith("_dm"): continue
                if ident.endswith("_vic"): continue
                s.choices.append(song[0])
        for c in canbe:
            if not c: continue
            if c[0] in eventmodes and ":" not in c:
                try:
                    event_mults[c[0]] = int(c[1:])
                except ValueError:
                    print("WARNING: in songs.txt: could not interpret '{}'".format(c))
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
                print("WARNING: Improper song ID configuration for default method (by area)")
                print("     Falling back to old method (by level)")
                old_method = True
                FLAGS.append("battlebylevel")
                
        for i, id in enumerate(battleids):
            if str(id).lower() == "new":
                songtable['battle' + str(newidx+2)] = SongSlot(nextsongid, chance=100)
                battleids[i] = nextsongid
                nextsongid += 1
                newidx += 1
            else:
                battleids[i] = int(id, 16)
        newidx = 0
        for i, id in enumerate(bossids):
            if str(id).lower() == "new":
                songtable['EventBattle' + str(newidx)] = SongSlot(nextsongid, chance=100)
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
            newsong = random.choice([k[0] for k in songconfig.items('Imports') if k not in intensitytable])
            intensitytable[newsong] = (random.randint(0,9), random.randint(0,9))

        if old_method:
            retry = True
            while retry:
                retry = False
                battlechoices = random.sample([(k, sum(intensitytable[k]), intensitytable[k][0]) for k in intensitytable.keys()], battlecount)
                for c in battlechoices:
                    if usage_id(battlechoices[0]) in used_songs: retry = True
            battlechoices.sort(key=operator.itemgetter(1))
            battleprog = [None]*len(battleids)
            bossprog = [None]*len(bossids)
            bosschoices = []
            battlechoices.sort(key=operator.itemgetter(2))
            for i in range(0, len(bossids)):
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
                    event, (ei, eg) = random.choice(list(intensity_subset(imin=33, gmax=33).items()))
                    bt = min(ei,60) 

                    super, (si, sg) = random.choice(list(intensity_subset(imin=bt, gmin=66).items()))
                    boss, (bi, bg) = random.choice(list(intensity_subset(imin=bt, gmin=max(22,eg), gmax=sg).items()))
                    wt = min(80,max(bg, 50))
                    balance = random.sample(list(intensity_subset(imax=bt, gmax=wt).items()), 2)
                    if balance[0][1][0] + balance[0][1][1] > balance[1][1][0] + balance[1][1][1]:
                        boutside, (boi, bog) = balance[1]
                        binside, (bii, big) = balance[0]
                    else:
                        boutside, (boi, bog) = balance[0]
                        binside, (bii, big) = balance[1]
                    ruin = random.sample(list(intensity_subset(imax=min(bi, si), gmin=max(bog,big)).items()), 2)
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
                    print("DEBUG: new battle prog mode failed {}rd attempt: {}".format(tries, e))
                    input("press enter to continue>")
                    if tries >= 500:
                        FLAGS.append("battlebylevel")
                        print("WARNING: couldn't find valid configuration of battle songs by area.")
                        print("     Falling back to old method (by level).")
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
        n_by_isets = (isetlocs[1] - isetlocs[0] + 1) // 0x20
        n_by_sptrs = (songptraddrs[1] - songptraddrs[0] + 1) // 3
        if len(songtable) > n_by_isets or len(songtable) > n_by_sptrs:
            return False
        return True
        
    def process_mml(id, orig_mml, name):
        def ruin_increment(m):
            val = int(m.group(1))
            if val in [3, 4, 5, 6, 11, 12, 13, 14]:
                val += 2
            elif val in [7, 8, 15, 16]: 
                val -= 4
            return "{{{}}}".format(val)
            return m.group(0)
            
        sfx = ""
        is_sfxv = False
        mml = orig_mml
        if id == 0x29:
            sfx = "sfx_zozo.mmlappend"
            is_sfxv = True
        elif id == 0x4F or (id == 0x5D and random.choice([True, False, False])):
            sfx = "sfx_wor.mmlappend"
            is_sfxv = True
            try:
                mml = re.sub("\{[^}]*?([0-9]+)[^}]*?\}", ruin_increment, mml)
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
    
    def process_tierboss(opts, used_songs=[]):
        opts_full = [o.strip() for o in opts.split(',')]
        opts = [o for o in opts_full if usage_id(o) not in used_songs]
        attempts = 0
        fallback = False
        while True:
            attempts += 1
            if attempts >= 1000:
                print("warning: check your tierboss config in songs.txt")
                fallback = True
                opts = copy(opts_full)
                attempts = 0
            retry = False
            tiernames = random.sample(opts, 3)
            tierfiles = []
            for n in tiernames:
                try:
                    with open(os.path.join(MUSIC_PATH, n + '_dm.mml'), 'r') as f:
                        tierfiles.append(f.read())
                except IOError:
                    print("couldn't open {}".format(n + '_dm.mml'))
                    retry = True
            if retry: continue
            
            mml = re.sub('[~*]', '', tierfiles[0])
            mml = re.sub('[?_]', '?', mml)
            mml = re.sub('j([0-9]+),([0-9]+)', 'j\g<1>,555\g<2>', mml)
            mml = re.sub('([;:\$])([0-9]+)(?![,0-9])', '\g<1>555\g<2>', mml)
            mml = re.sub('([;:])555444([0-9])', '\g<1>222\g<2>', mml)
            mml = re.sub('#VARIANT', '#', mml, flags=re.IGNORECASE)
            mml = re.sub('{.*?}', '', mml)
            mml = re.sub('\$555444([0-9])', '{\g<1>}', mml)
            mml = re.sub('#def\s+(\S+)\s*=', '#def 555\g<1>=', mml, flags=re.IGNORECASE)
            mml = re.sub("'(.*?)'", "'555\g<1>'", mml)
            tierfiles[0] = mml
            
            mml = re.sub('[?*]', '', tierfiles[1])
            mml = re.sub('[~_]', '?', mml)
            mml = re.sub('j([0-9]+),([0-9]+)', 'j\g<1>,666\g<2>', mml)
            mml = re.sub('([;:\$])([0-9]+)(?![,0-9])', '\g<1>666\g<2>', mml)
            mml = re.sub('([;:])666444([0-9])', '\g<1>333\g<2>', mml)
            mml = re.sub('\$666444([0-9])', '$222\g<1>', mml)
            mml = re.sub('#VARIANT', '#', mml, flags=re.IGNORECASE)
            mml = re.sub('{.*?}', '', mml)
            mml = re.sub('#def\s+(\S+)\s*=', '#def 666\g<1>=', mml, flags=re.IGNORECASE)
            mml = re.sub("'(.*?)'", "'666\g<1>'", mml)
            mml = re.sub('"', ')', mml)
            tierfiles[1] = mml
            
            mml = re.sub('[?_]', '', tierfiles[2])
            mml = re.sub('[~*]', '?', mml)
            mml = re.sub('j([0-9]+),([0-9]+)', 'j\g<1>,777\g<2>', mml)
            mml = re.sub('([;:\$])([0-9]+)(?![,0-9])', '\g<1>777\g<2>', mml)
            mml = re.sub('\$777444([0-9])', '$333\g<1>', mml)
            mml = re.sub('#VARIANT', '#', mml, flags=re.IGNORECASE)
            mml = re.sub('{.*?}', '', mml)
            mml = re.sub('#def\s+(\S+)\s*=', '#def 777\g<1>=', mml, flags=re.IGNORECASE)
            mml = re.sub("'(.*?)'", "'777\g<1>'", mml)
            mml = re.sub('"', '(', mml)
            tierfiles[2] = mml
            
            mml = "#VARIANT / \n#VARIANT ? ignore \n" + tierfiles[0] + tierfiles[1] + tierfiles[2]
            
            akao = mml_to_akao(mml, str(tiernames), variant='_default_')
            inst = bytes(akao['_default_'][1], encoding='latin-1')
            akao = bytes(akao['_default_'][0], encoding='latin-1')

            ## uncomment to debug tierboss MML
            #with open("lbdebug.mml", "w") as f:
            #    f.write(mml)
            #print("{}: {}".format(len(akao), tiernames))
            #if "name_of_segment_to_test" not in tiernames: continue
            
            if len(akao) > 0x1002:
                continue
            break
        for n in tiernames: used_songs.append(usage_id(n))
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
        random.shuffle(songs_to_change)
        for ident, s in songs_to_change:
            if ident in tierboss:
                songtable[ident].changeto = '!!tierboss'
            else:
                choices = [c for c in songtable[ident].choices if usage_id(c) not in used_songs]
                if not choices: choices.append(native_prefix + ident)
                newsong = random.choice(choices)
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
                s.data, s.inst = process_tierboss(tierboss[ident], used_songs=used_songs)
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
                title = re.search("(?<=#TITLE )([^;\n]*)", mml, re.IGNORECASE)
                album = re.search("(?<=#ALBUM )([^;\n]*)", mml, re.IGNORECASE)
                composer = re.search("(?<=#COMPOSER )([^;\n]*)", mml, re.IGNORECASE)
                arranged = re.search("(?<=#ARRANGED )([^;\n]*)", mml, re.IGNORECASE)
                title = title.group(0) if title else "??"
                album = album.group(0) if album else "??"
                composer = composer.group(0) if composer else "??"
                arranged = arranged.group(0) if arranged else "??"
                metadata[s.changeto] = TrackMetadata(title, album, composer, arranged)
                if not akao:
                    print("couldn't find valid mml for {}".format(s.changeto))
                    keeptrying = True
                    break
                if variant and variant in akao:
                    s.data = bytes(akao[variant][0], encoding='latin-1')
                    s.inst = bytes(akao[variant][1], encoding='latin-1')
                else:
                    s.data = bytes(akao['_default_'][0], encoding='latin-1')
                    s.inst = bytes(akao['_default_'][1], encoding='latin-1')
                s.is_pointer = False
                if max(list(s.inst)) > instcount:
                    if 'nopatch' in akao:
                        s.inst = bytes(akao['nopatch'][1], encoding='latin-1')
                        s.data = bytes(akao['nopatch'][0], encoding='latin-1')
                    elif 'nat' in akao:
                        s.inst = bytes(akao['nat'][1], encoding='latin-1')
                        s.data = bytes(akao['nat'][0], encoding='latin-1')
                    else:
                        print("WARNING: instrument out of range in {}".format(s.changeto + ".mml"))
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
                        s.data = bytes([loc])
                    else:
                        s.is_pointer = False
                        slen = bytes_to_int(data[loc:loc+2]) + 2
                        s.data = data[loc:loc+slen]
                    loc = isetlocs[0] + sid * isetsize
                    assert loc + isetsize <= isetlocs[1] + 1
                    s.inst = data[loc:loc+isetsize]
                else:
                    print("target song {} not found for id {} {}".format(s.changeto, s.id, ident))
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
                    print("couldn't open {}_inst.bin".format(s.changeto))
                    keeptrying = True
                    break
                if max(list(map(ord, s.inst))) > instcount:
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
                            print("couldn't open {}_data.bin".format(s.changeto))
                            keeptrying = True
                            break
                else:
                    # case: get standard version
                    try:
                        fi = open(os.path.join(MUSIC_PATH, s.changeto + "_data.bin"), "rb")
                        s.data = fi.read()
                        fi.close()
                    except IOError:
                        print("couldn't open {}_data.bin".format(s.changeto))
                        keeptrying = True
                        break
            
            if len(s.data) > 0x1002 and "ending" not in ident:
                print("WARNING: song data too large for {} (as {}), sfx glitches may occur".format(s.changeto, ident))
                
        if keeptrying:
            dprint("failed music generation during data read")
            continue
        
        # force opera music if opera is randomized
        if opera:
            songtable['aria'].is_pointer = False
            songtable['aria'].data = bytes(opera['aria'][0], encoding='latin-1')
            songtable['aria'].inst = bytes(opera['aria'][1], encoding='latin-1')
            songtable['opera_draco'].is_pointer = False
            songtable['opera_draco'].data = bytes(opera['overture'][0], encoding='latin-1')
            songtable['opera_draco'].inst = bytes(opera['overture'][1], encoding='latin-1')
            songtable['wed_duel'].is_pointer = False
            songtable['wed_duel'].data = bytes(opera['duel'][0], encoding='latin-1')
            songtable['wed_duel'].inst = bytes(opera['duel'][1], encoding='latin-1')
            
        # try to fit it all in!
        if f_preserve:
            freelocs = []
            for b, e in songdatalocs:
                i = b
                lastchar = b''
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
        songdata = b"" * len(space)
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
        print("failed to produce valid music set")
        print("    try increasing available space or adjusting song insert list")
        print("    to use less space")
        print()
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
        
        battletable = bytes(battletable)
        pausetable = bytes(pausetable)
        
        
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
    arrowpos = max(list(map(len, spoiltext)))
    for i, (id, s) in enumerate(sorted(changed_songs.items())):
        while len(spoiltext[i]) < arrowpos:
            spoiltext[i] += " "
        spoiltext[i] += "-> {}".format(s[1])
        if s[1] in metadata:
            spoiltext[i] += "\n" + " " * 8 + "{} -- {}".format(metadata[s[1]].album, metadata[s[1]].title)
            spoiltext[i] += "\n" + " " * 8 + "Composed by {} -- Arranged by {}".format(metadata[s[1]].composer, metadata[s[1]].arranged)
    for t in spoiltext: spoil(t + "\n")
    
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
    for i in range(0,256):
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
        dat = bytearray(data[pos:pos+4])
        
        dat[3] = (dat[3] & 0b11000111) | mbf
        if line[2] == "0":
            dat[1] = dat[1] | 0b00000010
            dat[3] = dat[3] | 0b10000000
        elif line[2] == "c":
            if fid in event_formations:
                force_music = True
            else:
                for m in range(0,6):
                    fpos = o_forms + fid*15
                    if (data[fpos+1] >> m) & 1:
                        mid = data[fpos+2+m] + (((data[fpos+14] >> m) & 1) << 8)
                        mb = data[o_monsters+mid*32+19]
                        if mb & 0b00001011:
                            force_music = True
                            break
        if line[2] == "1" or force_music:
            dat[1] = dat[1] & 0b11111101
            dat[3] = dat[3] & 0b01111111
        data = byte_insert(data, pos, dat)
    
    return data
        
def process_map_music(data):
    #find range of valid track #s
    songcount_byte = 0x53C5E
    max_bgmid = data[songcount_byte]
    max_bgmid -= 4 #extra battles always go last
    
    map_offset = 0x2D8F00
    map_block_size = 0x21
    map_music_byte = 0x1C
    
    #replace track ids in map data
    replacements = {}
    replacements[0x51] = [ #Phantom Forest (forest)
        0x84, 0x85, 0x86, 0x87
        ]
    replacements[0x55] = [ #Daryl's Tomb (tomb)
        0x129, 0x12A, 0x12B, 0x12C
        ]
    replacements[0x56] = [ #Cyan's Dream (dream)
        0x13D, #stoogeland
        0x13F, 0x140 #dream of a mine
        ]
    replacements[0x57] = [ #Ancient Castle (ancient)
        0x191, 0x192, #cave
        0x196, 0x197, 0x198 #ruins
        ]
    replacements[0x58] = [ #Phoenix Cave (phoenix)
        0x139, 0x13B
        ]
    replacements[0x59] = [ #Sealed Gate Cave (gate)
        0x17E, 0x17F, 0x180, 0x181, 0x182
        ]
    replacements[0x5A] = [ #Mt. Zozo (mount2)
        0xB0, 0xB1, 0xB2, 0xB3, 0xB4, 0xB5
        ]
    replacements[0x5B] = [ #Figaro Engine Room (engine)
        0x3E, 0x3F, 0x40, 0x41, 0x42
        ]
    replacements[0x5C] = [ #Village (village)
        0x0E, 0x0F, 0x10, #chocobo stable
        0x5D, 0x5E, #Sabin's house
        0x9D, 0xA0, 0xA1, 0xA4, #Mobliz (WoB)
        0xBC #Kohlingen (WoB)
        ]
    replacements[0x5D] = [ #Opening magitek sequence (assault)
        0x13, #outside south
        0x27, #outside north
        0x2A #Tritoch mine room
        ]
    replacements[0x00] = [ #Change maps to "continue current music"
        0x29 #Narshe mines 1
        ]
        
    for bgm_id, maps in replacements.items():
        if bgm_id > max_bgmid: continue
        for map_id in maps:
            offset = map_offset + (map_id * map_block_size) + map_music_byte
            data = byte_insert(data, offset, bytes([bgm_id]))
            
    #also replace relevant play song events
    def adjust_event(dat, offset, oldid, newid):
        op_lengths = {}
        for o in [0x38, 0x39, 0x3A, 0x3B, 0x45, 0x47, 0x49, 0x4A, 0x4E, 0x4F, 0x54, 0x5B, 0x5C, 0x7B, 0x82, 0x8E, 0x8F, 0x90, 0x91, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x9A, 0x9D, 0xA2, 0xA6, 0xA8, 0xA9, 0xAA, 0xAB, 0xAC, 0xAD, 0xAE, 0xAF, 0xB1, 0xBB, 0xBF, 0xDE, 0xDF, 0xE0, 0xE1, 0xE2, 0xE3, 0xE4, 0xF7, 0xF8, 0xFA, 0xFD, 0xFE]:
            op_lengths[o] = 1
        for o in [0x35, 0x36, 0x37, 0x3D, 0x3E, 0x41, 0x42, 0x46, 0x50, 0x52, 0x55, 0x56, 0x57, 0x58, 0x59, 0x5A, 0x62, 0x63, 0x77, 0x78, 0x6C, 0x7D, 0x80, 0x81, 0x86, 0x87, 0x8D, 0x98, 0x9B, 0x9C, 0xA1, 0xA7, 0xB0, 0xB4, 0xB5, 0xB8, 0xB9, 0xBA, 0xD0, 0xD1, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xDB, 0xDC, 0xDD, 0xE7, 0xF0, 0xF2, 0xF3, 0xF4, 0xF9]:
            op_lengths[o] = 2
        for o in [0x37, 0x3F, 0x40, 0x43, 0x44, 0x48, 0x4B, 0x4C, 0x4D, 0x5D, 0x5E, 0x5F, 0x60, 0x64, 0x65, 0x70, 0x71, 0x72, 0x7E, 0x7F, 0x84, 0x85, 0x8B, 0x8C, 0xBC, 0xEF, 0xF1]:
            op_lengths[o] = 3
        for o in [0x51, 0x53, 0x61, 0x79, 0x88, 0x89, 0x8A, 0x99, 0xB2, 0xBD, 0xE8, 0xE9, 0xEA, 0xEB, 0xF5, 0xF6]:
            op_lengths[o] = 4
        for o in [0x3C, 0x7A, 0xB3, 0xB7]:
            op_lengths[o] = 5
        for o in [0x6A, 0x6B, 0x6C, 0xA0, 0xC0, 0xC8]:
            op_lengths[o] = 6
        for o in [0xC1, 0xC9]:
            op_lengths[o] = 8
        for o in [0xC2, 0xCA]:
            op_lengths[o] = 10
        for o in [0xC3, 0xCB]:
            op_lengths[o] = 12
        for o in [0xC4, 0xCC]:
            op_lengths[o] = 14
        for o in [0xC5, 0xCD]:
            op_lengths[o] = 16
        for o in [0xC6, 0xCE]:
            op_lengths[o] = 17
        for o in [0xC7, 0xCF]:
            op_lengths[o] = 18
        
        changes = []
        loc = offset
        while True:
            op = dat[loc]
            #print(f"${loc:06X}: {op:02X}")
            if op == 0xFE:
                break
            elif op in range(0, 0x34): #action queue
                loc += 2 + (dat[loc+1] & 0x7F)
            elif op in [0x73, 0x74]: #bitmap
                loc += 3 + dat[loc+2] * dat[loc+3]
            elif op == 0xB6: #variable length dialogue choice
                loc += 1
                while dat[loc] != 0xFE and edat[loc+2] <= 2:
                    loc += 3
            elif op == 0xBE: #variable length switch/case
                loc += 1 + dat[loc+1]*3
            elif op == 0xF0: #play song
                if dat[loc+1] == oldid:
                    changes.append((loc+1, newid))
                loc += 2
            elif op == 0xF1: #play song with fade
                if dat[loc+1] == oldid:
                    changes.append((loc+1, newid))
                loc += 3
            elif op in op_lengths:
                loc += op_lengths[op]
            else:
                print("unexpected event op ${:02X} at ${:06X}".format(op, loc))
                break
                
        #print("full event at ${:06X}:".format(offset))
        #for b in range(offset, loc):
        #    print("{:02X} ".format(dat[b]), end="")
        #print()
        
        for ch in changes:
            #print("at ${:06X}: {:02X} {:02X} -> {:02X}".format(ch[0]-1, dat[ch[0]-1], dat[ch[0]], ch[1]))
            dat = byte_insert(dat, ch[0], bytes([ch[1]]))
       
        return dat
        
    def adjust_entrance_event(dat, mapid, oldid, newid):
        event_offset = 0x0A0000
        entrance_table = 0x11FA00
        table_offset = entrance_table + mapid*3
        event_offset += dat[table_offset]
        event_offset += (dat[table_offset+1] << 8)
        event_offset += (dat[table_offset+2] << 16)
        dat = adjust_event(dat, event_offset, oldid, newid)
        return dat
        
    data = adjust_entrance_event(data, 0xA2, 0x2A, 0x5C) #mobliz
    data = adjust_entrance_event(data, 0xC0, 0x2A, 0x5C) #kohlingen
    data = adjust_event(data, 0xC3B0E, 0x2A, 0x5C) #kohlingen, WoR, locke recruited
    
    data = adjust_event(data, 0xC9A4F, 0x39, 0x5D) #opening mission
    
    # add music conditional event for Narshe Mines 1 map
    event = b"\xC0\x01\x80\x5A\x39\x02" #if you've met arvis, jump to "play Narshe music"
    event += b"\xB2\x01\x9B\x02" #subroutine: put terra, biggs, wedge on magitek armor
    event += b"\xF0\x5D\xFE" #play opening mission track & return
    data = byte_insert(data, 0xC9F1A, event)
    # 3 bytes unused, C9F27 - C9F29
    
    #code from Mines 1 entrance event moved to subroutine
    #Replaces Save Point tutorial event (already dummied out by BC)
    event = b"\x44\x00\xC0\x44\x0E\xC0\x44\x0F\xC0\xFE" #Put terra, biggs, wedge on magitek armor
    data = byte_insert(data, 0xC9B01, event)
    # $12 bytes unused, C9B0B - C9B1C
    
    data = byte_insert(data, 0xC9F1D, b"\x5A\x39\x02")
    
    return data
    
def randomize_music(fout, opera=None, codes=[], form_music_overrides={}):
    events = ""
    if 'christmas' in codes:
        events += "W"
    if 'halloween' in codes:
        events += "H"
    f_mchaos = 'johnnyachaotic' in codes
    
    fout.seek(0)
    data = fout.read()
    data = process_custom_music(data, opera=opera, f_mchaos=f_mchaos, eventmodes=events)
    if 'ancientcave' not in codes and 'speedcave' not in codes and 'racecave' not in codes:
        data = process_map_music(data)
    data = process_formation_music_by_table(data, form_music_overrides=form_music_overrides)
    
    fout.seek(0)
    fout.write(data)
    
    return "\n".join(spoiler['Music'])
    
#######################################
## End of core music randomizer code ##
#######################################

def manage_opera(fout, affect_music):
    fout.seek(0)
    data = fout.read()
    
    #2088 blocks available for all 3 voices in Waltz 3
    SAMPLE_MAX_SIZE = 0x4968 
    
    #Determine opera cast
    
    class OperaSinger:
        def __init__(self, name, title, sprite, gender, file, sample, octave, volume, init):
            self.name = name
            self.title = title
            self.sprite = sprite
            self.gender = gender
            self.file = file
            self.sample = int(sample,16)
            self.octave = octave
            self.volume = volume
            self.init = init
    
    #voice range notes
    # Overture (Draco) ranges from B(o-1) to B(o)
    # Aria (Maria) ranges from D(o) to D(o+1)
    # Duel 1 (Draco) ranges from B(o-1) to E(o)
    # Duel 2 (Maria) ranges from A(o) to F(o+1)
    # Duel 3 (Ralse) ranges from E(o) to C(o+1)
    # Duel 4 (Draco) ranges from B(o-1) to F(o)
    # Duel 5 (Ralse) ranges from E(o) to B(o)
    
    singer_options = []
    try:
        with open(safepath(os.path.join('custom','opera.txt'))) as f:
            for line in f.readlines():
                singer_options.append([l.strip() for l in line.split('|')])
    except IOError:
        print("WARNING: failed to load opera config")
        return
        
    singer_options = [OperaSinger(*s) for s in singer_options]
    
    #categorize by voice sample
    voices = {}
    for s in singer_options:
        if s.sample in voices:
            voices[s.sample].append(s)
        else:
            voices[s.sample] = [s]
    
    #find a set of voices that doesn't overflow SPC RAM
    sample_sizes = {}
    while True:
        vchoices = random.sample(list(voices.values()), 3)
        for c in vchoices:
            smp = c[0].sample
            if smp not in sample_sizes:
                sample_sizes[smp] = find_sample_size(data, smp)
        sample_total_size = sum([sample_sizes[c[0].sample] for c in vchoices])
        if sample_total_size <= SAMPLE_MAX_SIZE:
            break

    #select characters
    charpool = []
    char = {}
    #by voice, for singers
    for v in vchoices:
        charpool.append(random.choice(v))
    random.shuffle(charpool)
    for c in ["Maria", "Draco", "Ralse"]:
        char[c] = charpool.pop()
    #by sprite/name, for impresario
    charpool = [c for c in singer_options if c not in char.values()]
    char["Impresario"] = random.choice(charpool)
    
    #reassign sprites in npc data
    locations = get_locations()
    #first, free up space for a unique Ralse
    #choose which other NPCs get merged:
    # 0. id for new scholar, 1. offset for new scholar, 2. id for merged sprite, 3. offset for merged sprite, 4. spritesheet filename, 5. extra pose type
    merge_options = [
        (32, 0x172C00, 33, 0x1731C0, "dancer.bin", "flirt"), #fancy gau -> dancer
        (32, 0x172C00, 35, 0x173D40, "gausuit.bin", "sideeye"), #clyde -> fancy gau
        (60, 0x17C4C0, 35, 0x173D40, "daryl.bin", "sideeye"), #clyde -> daryl
        (42, 0x176580, 35, 0x173D40, "katarin.bin", "sideeye"), #clyde -> katarin
        (60, 0x17C4C0, 42, 0x176580, "daryl.bin", "sideeye"), #katarin -> daryl
        (60, 0x17C4C0, 42, 0x176580, "katarin.bin", "sideeye"), #daryl -> katarin
        (60, 0x17C4C0, 41, 0x175FC0, "daryl.bin", "sleeping"), #rachel -> daryl
        (60, 0x17C4C0, 41, 0x175FC0, "rachel.bin", "sleeping"), #daryl -> rachel
        (60, 0x17C4C0, 30, 0x172080, "returner.bin", "prone"), #daryl -> returner
        (53, 0x17A1C0, 59, 0x17BFC0, "figaroguard.bin", None), #conductor -> figaro guard
        (45, 0x1776C0, 48, 0x178800, "maduin.bin", "prone"), #yura -> maduin
        ]
    merge = random.choice(merge_options)
    
    #merge sacrifice into new slot
    replace_npc(locations, (merge[0], None), merge[2])
    #move scholar into sacrifice slot
    for i in [0,1,3,4,5]:
        replace_npc(locations, (27, i), (merge[0], i))
    
    #randomize palettes of shuffled characters
    for i in [0x1A, 0x1B, 0x1C, 0x2B]:
        palette = random.randint(0,5)
        for l in locations:
            for npc in l.npcs:
                if npc.graphics == i:
                    #npc.palette = palette
                    pass
    
    #debug info
    # for l in locations:
        # for npc in l.npcs:
            # if npc.graphics in [118,138]:
                # print()
                # print(f"graphics {npc.graphics} found at ${npc.pointer:X}, in location 0x{l.locid:X}")
                # print(f"palette {npc.palette}, facing byte {npc.facing:X}")
                # print(f"facing {npc.facing & 3:X}, change {npc.facing>>2 & 1:X}")
                # print(f"bglayer {npc.facing>>3 & 3:X}, unknown1 {npc.facing>>5 & 1:X}")
                # print(f"mirror {npc.facing>>6 & 2:X}, unknown2 {npc.facing>>7 & 1:X}")
                
    #randomize item thrown off balcony
    balcony = get_location(0xEC)
    for npc in balcony.npcs:
        if npc.graphics == 88:
            item = random.choice([
                #(84, 0x24, "chest"), #treasure box (palette broken)
                (87, 0x44, "statue"),
                (88, 0x54, "flowers"), #bouquet
                (89, 0x54, "letter"), #letter
                (91, 0x54, "magicite"), #magicite
                (92, 0x44, "book"), #book
                ##DO NOT THROW THE BABY
                (96, 0x44, "crown"), #slave crown
                (97, 0x54, "weight"), #4ton weight
                (100, 0x54, "bandana"), #locke's bandana
                ##(124, 0x02, "helmet") #a shiny thing (didn't work)
                ])
            npc.graphics = item[0]
            npc.palette = random.choice(range(6))
            npc.facing = item[1]
            set_dialogue_var("OperaItem", item[2])
            print(f"opera item is {npc.graphics}, palette {npc.palette} ({item[2]})")
            print(f"at address {npc.pointer:X}")
    #4 ton weight
    for npc in get_location(0xEB).npcs:
        if npc.graphics == 97:
            item = random.choice([
                (58, 0x11), #fish (????)
                (87, 0x44), #mini statue
                (93, 0x54), #ultros is allowed to try to throw the baby (STOP HIM)
                (97, 0x54), #4ton weight
                (112, 0x43), #fire
                ###(118, 0x10), #rock (didn't work)
                ###(138, 0x12) #leo's sword (didn't work)
                ])
            npc.graphics = item[0]
            npc.palette = random.choice(range(6))
            npc.facing = item[1]
            print(f"ultros item is {npc.graphics}, palette {npc.palette}")
            print(f"at address {npc.pointer:X}")

    #set up some spritesheet locations
    pose = {
        'singing': [0x66, 0x67, 0x68, 0x69, 0x64, 0x65, 0x60, 0x61, 0x62, 0x63],
        'ready': list(range(0x3E, 0x44)),
        'prone': list(range(0x51, 0x57)),
        'angry': list(range(0x76, 0x7C)),
        'flirt': [0xA3, 0xA4, 0x9C, 0x99, 0x9A, 0x9B],
        'sideeye': [0x92, 0x93, 0x94, 0x95, 0x08, 0x09],
        'sleeping': [0x86, 0x87, 0x88, 0x89, 0x08, 0x09]
            }
    
    opath = os.path.join("custom","opera")
    #load scholar graphics
    try:
        with open(safepath(os.path.join(opath, "ralse.bin")),"rb") as f:
            sprite = f.read()
    except IOError:
        print(f"failed to open custom/opera/ralse.bin")
        sprite = None
    if sprite:
        new_sprite = create_sprite(sprite)
        data = byte_insert(data, merge[1], new_sprite)
        
    #load new graphics into merged slot
    try:
        with open(safepath(os.path.join(opath, f"{merge[4]}")),"rb") as f:
            sprite = f.read()
    except IOError:
        try:
            with open(safepath(os.path.join("custom","sprites", f"{merge[4]}")),"rb") as f:
                sprite = f.read()
        except:
            print(f"failed to open custom/opera/{merge[4]} or custom/sprites/{merge[4]}")
            sprite = None
    if sprite:
        print(f"merge {merge}, pose {pose}")
        new_sprite = create_sprite(sprite, pose[merge[5]] if merge[5] is not None else [])
        data = byte_insert(data, merge[3], new_sprite)
    
    
    #load new graphics into opera characters
    char_offsets = {
        "Maria": (0x1705C0, pose['ready'] + pose['singing']),
        "Draco": (0x1713C0, pose['prone'] + pose['singing']),
        "Ralse": (0x170CC0, pose['prone'] + pose['singing']),
        "Impresario": (0x176B40, pose['angry'])}
    for cname, c in char.items():
        print(f"{cname} -> {c.name}")
        try:
            with open(safepath(os.path.join(opath, f"{c.sprite}.bin")),"rb") as f:
                sprite = f.read()
        except IOError:
            try:
                with open(safepath(os.path.join("custom","sprites", f"{c.sprite}.bin")),"rb") as f:
                    sprite = f.read()
            except:
                print(f"failed to open custom/opera/{c.sprite}.bin or custom/sprites/{c.sprite}.bin")
                continue
        offset, extra_tiles = char_offsets[cname]
        #tiles = list(range(0x28)) + extra_tiles
        #new_sprite = bytearray()
        #for t in tiles:
        #    loc = t*32
        #    new_sprite.extend(sprite[loc:loc+32])
        #data = byte_insert(data, offset, new_sprite)
        new_sprite = create_sprite(sprite, extra_tiles)
        data = byte_insert(data, offset, new_sprite)
        
    ### adjust script
    
    load_patch_file("opera")
    factions = [
        ("the East", "the West"),
        ("the North", "the South"),
        ("the Rebels", "the Empire"),
        ("the Alliance", "the Horde"),
        ("the Sharks", "the Jets"),
        ("the Fire Nation", "the Air Nation"),
        ("the Sith", "the Jedi"),
        ("the X-Men", "the Sentinels"),
        ("the X-Men", "the Inhumans"),
        ("the Kree", "the Skrulls"),
        ("the jocks", "the nerds"),
        ("Palamecia", "the Wild Rose"),
        ("Baron", "Mysidia"),
        ("Baron", "Damcyan"),
        ("Baron", "Fabul"),
        ("AVALANCHE", "Shinra"),
        ("Shinra", "Wutai"),
        ("Balamb", "Galbadia"),
        ("Galbadia", "Esthar"),
        ("Alexandria", "Burmecia"),
        ("Alexandria", "Lindblum"),
        ("Zanarkand", "Bevelle"),
        ("the Aurochs", "the Goers"),
        ("Yevon", "the Al Bhed"),
        ("the Gullwings", "the Syndicate"),
        ("New Yevon", "the Youth League"),
        ("Dalmasca", "Archadia"),
        ("Dalmasca", "Rozarria"),
        ("Cocoon", "Pulse"),
        ("Lucis", "Niflheim"),
        ("Altena", "Forcena"),
        ("Nevarre", "Rolante"),
        ("Wendel", "Ferolia"),
        ("the Lannisters", "the Starks"),
        ("the Hatfields", "the McCoys"),
        ("the Aliens", "the Predators"),
        ("cats", "dogs"),
        ("YoRHa", "the machines"),
        ("Shevat", "Solaris"),
        ("U-TIC", "Kukai"),
        ("the Bionis", "the Mechonis"),
        ("Samaar", "the Ghosts"),
        ("Mor Ardain", "Uraya"),
        ("Marvel", "Capcom"),
        ("Nintendo", "Sega"),
        ("Subs", "Dubs"),
        ("vampires", "werewolves"),
        ("Guardia", "the Mystics")
        ]
    factions = random.choice(factions)
    if random.choice([False, True]):
        factions = (factions[1], factions[0])
    set_dialogue_var("OperaEast", factions[0])
    set_dialogue_var("OperaWest", factions[1])
        
    set_dialogue_var("maria", char['Maria'].name)
    set_dialogue_var("draco", char['Draco'].name)
    set_dialogue_var("ralse", char['Ralse'].name)
    set_dialogue_var("impresario", char['Impresario'].name)
    set_dialogue_var("mariatitle", char['Maria'].title)
    set_dialogue_var("dracotitle", char['Draco'].title)
    set_dialogue_var("ralsetitle", char['Ralse'].title)
    set_dialogue_var("impresariotitle", char['Impresario'].title)
    char['Maria'].gender = set_pronoun('Maria', char['Maria'].gender)
    char['Draco'].gender = set_pronoun('Draco', char['Draco'].gender)
    char['Ralse'].gender = set_pronoun('Ralse', char['Ralse'].gender)
    char['Impresario'].gender = set_pronoun('Impresario', char['Impresario'].gender)
    
    #due to the variance in power relations connoted by "make X my queen" and "make X my king", this line will be altered in all variations so that it means roughly the same thing no matter the Maria replacement's gender
    
    if char['Maria'].gender == "female":
        set_dialogue_var("MariaTheGirl", "the girl")
        set_dialogue_var("MariaQueenBad", "mine")
        set_dialogue_var("MariaQueen", "queen")
        set_dialogue_var("MariaWife", "wife")
    elif char['Maria'].gender == "male":
        set_dialogue_var("MariaTheGirl", "the guy")
        set_dialogue_var("MariaQueenBad", "mine")
        set_dialogue_var("MariaQueen", "king")
        set_dialogue_var("MariaWife", "husband")
    elif char['Maria'].gender == "object":
        set_dialogue_var("MariaTheGirl", char['Maria'].title + char['Maria'].name)
        set_dialogue_var("MariaQueenBad", "mine")
        set_dialogue_var("MariaQueen", "prize")
        set_dialogue_var("MariaWife", "collection")
    else:
        set_dialogue_var("MariaTheGirl", "the girl")
        set_dialogue_var("MariaQueenBad", "mine")
        set_dialogue_var("MariaQueen", "consort")
        set_dialogue_var("MariaWife", "partner")
    
    if char['Impresario'].gender == "male":
        set_dialogue_var("ImpresarioMan", "man") # from "music man"
    elif char['Impresario'].gender == "female":
        set_dialogue_var("ImpresarioMan", "madam")
    elif char['Impresario'].gender == "object":
        set_dialogue_var("ImpresarioMan", "machine")
    else:
        set_dialogue_var("ImpresarioMan", "maker")
        
    ### adjust music
    opera = {}
    try:
        overture = read_opera_mml('overture')
        overture += f"\n#WAVE 0x2B 0x{char['Draco'].sample:02X}\n"
        overture += f"\n#def draco= |B o{char['Draco'].octave[0]} v{char['Draco'].volume} {char['Draco'].init}\n"
        seg = read_opera_mml(f"{char['Draco'].file}_overture")
        overture += seg
        
        aria = read_opera_mml('aria')
        aria += f"\n#WAVE 0x2A 0x{char['Maria'].sample:02X}\n"
        aria += f"\n#def maria= |A o{char['Maria'].octave[1]} v{char['Maria'].volume} {char['Maria'].init}\n"
        seg = read_opera_mml(f"{char['Maria'].file}_aria")
        aria += seg
        
        duel = read_opera_mml('duel')
        duel += f"\n#WAVE 0x2A 0x{char['Maria'].sample:02X}\n"
        duel += f"\n#def maria= |A o{char['Maria'].octave[3]} v{char['Maria'].volume} {char['Maria'].init}\n"
        duel += f"\n#WAVE 0x2B 0x{char['Draco'].sample:02X}\n"
        duel += f"\n#def draco= |B o{char['Draco'].octave[2]} v{char['Draco'].volume} {char['Draco'].init}\n"
        duel += f"\n#def draco2= |B o{char['Draco'].octave[5]} v{char['Draco'].volume} {char['Draco'].init}\n"
        duel += f"\n#WAVE 0x2C 0x{char['Ralse'].sample:02X}\n"
        duel += f"\n#def ralse= |C o{char['Ralse'].octave[4]} v{char['Ralse'].volume} {char['Ralse'].init}\n"
        duel += f"\n#def ralse2= |C o{char['Ralse'].octave[6]} v{char['Ralse'].volume} {char['Ralse'].init}\n"
        duelists = ["Draco", "Maria", "Ralse", "Draco", "Ralse"]
        for i in range(5):
            seg = read_opera_mml(f"{char[duelists[i]].file}_duel{i+1}")
            duel += seg
        
        #print(overture)
        #print("########")
        #print(duel)
        #print("########")
        #print(aria)
        
        opera['overture'] = mml_to_akao(overture)['_default_']
        opera['duel'] = mml_to_akao(duel)['_default_']
        opera['aria'] = mml_to_akao(aria)['_default_']
        
    except IOError:
        print("opera music generation failed, reverting to default")
        affect_music = False
    
    fout.seek(0)
    fout.write(data)
    
    return opera if affect_music else None
    
def find_sample_size(data, sidx):
    table = 0x53C5F
    offset = bytes_to_int(data[table+sidx*3:table+sidx*3+3]) - 0xC00000
    loc = 0
    
    #scan BRR block headers until one has END bit set
    while not (data[offset+loc*9] & 1):
        loc += 1
    
    return (loc+1)*9
    
def replace_npc(locations, old, new):
    if old[1] is not None: #if a palette is specified,
        for l in locations:
            for n in l.npcs:
                if n.graphics == old[0] and n.palette == old[1]:
                    n.graphics = new[0]
                    n.palette = new[1]
    else:
        for l in locations:
            for n in l.npcs:
                if n.graphics == old[0]:
                    try:
                        n.graphics = new[0]
                    except TypeError:
                        n.graphics = new
    
def create_sprite(sprite, extra_tiles=None):
    tiles = list(range(0x28)) + (extra_tiles if extra_tiles else [])
    new_sprite = bytearray()
    for t in tiles:
        loc = t*32
        new_sprite.extend(sprite[loc:loc+32])
    return new_sprite
    
def read_opera_mml(file):
    try:
        file = safepath(os.path.join('custom','opera',f'{file}.mml'))
        with open(file, "r") as f:
            mml = f.read()
        return mml
    except IOError:
        print(f"Failed to read {file}")
        raise
    