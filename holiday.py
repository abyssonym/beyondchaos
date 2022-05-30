import re
import time
from typing import Dict

from dialoguemanager import get_dialogue, load_patch_file, set_dialogue, set_dialogue_var, set_dialogue_flag, set_battle_dialogue
from options import Options
from skillrandomizer import CommandBlock, get_spell
from utils import get_long_battle_text_pointer, name_to_bytes, Substitution


def activate_holiday(seed: int, options_: Options) -> str:
    tm = time.gmtime(seed)
    if tm.tm_mon == 12 and (tm.tm_mday == 24 or tm.tm_mday == 25):
        options_.activate_code('christmas')
        return "CHRISTMAS MODE ACTIVATED\n"
    elif tm.tm_mon == 10 and tm.tm_mday == 31:
        options_.activate_code('halloween')
        return "ALL HALLOWS' EVE MODE ACTIVATED\n"
    elif tm.tm_mon == 5 and tm.tm_mday == 9:
        options_.activate_code('dragonball')
        return 'DRAGONBALL MODE ACTIVATED\n'
    return ''


def hail_demon_chocobo(fout):
    demon_chocobo_sub = Substitution()
    fout.seek(0x2d0000 + 896 * 7)
    demon_chocobo_sub.bytestring = fout.read(896)
    for i in range(7):
        demon_chocobo_sub.set_location(0x2d0000 + 896 * i)
        demon_chocobo_sub.write(fout)


def activate_holiday_post_random(fout, options_: Options, commands: Dict[str, CommandBlock]):
    if options_.is_code_active('christmas'):
        _santafy()
    elif options_.is_code_active('halloween'):
        _add_spookiness()
    elif options_.is_code_active('dragonball'):
        morph = commands['morph']
        morph.newname('SSJ', fout)
        _kamehameha(fout)
        _dragonballs()
        _piccolo_day()
        _piccolo()


def _santafy():
    for index in [0x72, 0x75, 0x7c, 0x8e, 0x17e, 0x1e1, 0x1e7, 0x1eb, 0x20f, 0x35c, 0x36d, 0x36e, 0x36f, 0x372, 0x3a9, 0x53a, 0x53f, 0x53f, 0x57c, 0x580, 0x5e9, 0x5ec, 0x5ee, 0x67e, 0x684, 0x686, 0x6aa, 0x6b3, 0x6b7, 0x6ba, 0x6ef, 0xa40, 0x717, 0x721, 0x723, 0x726, 0x775, 0x777, 0x813, 0x814, 0x818, 0x823, 0x851, 0x869, 0x86b, 0x86c, 0x89a, 0x89b, 0x89d, 0x8a3, 0x8a5, 0x8b1, 0x8b6, 0x8b8, 0x8c6, 0x8ca, 0x8cb, 0x8d2, 0x8d4, 0x913, 0x934, 0x959, 0x95d, 0x960, 0x979, 0x990, 0x9ae, 0x9e7, 0x9ef, 0xa07, 0xa35, 0xb76, 0xba0, 0xbc2, 0xbc9]:
        text = get_dialogue(index)
        text = re.sub(r'Kefka', "Santa", text)
        set_dialogue(index, text)

    for index in [0x24, 0x72, 0x76, 0x77, 0x78, 0x7a, 0x7c, 0x7d, 0x7f, 0x80, 0x90, 0x90, 0x94, 0x97, 0x9e, 0x9f, 0x1eb, 0x1eb, 0x203, 0x204, 0x205, 0x206, 0x207, 0x207, 0x207, 0x209, 0x20a, 0x20b, 0x20c, 0x20e, 0x210, 0x35b, 0x35c, 0x35c, 0x35d, 0x36b, 0x36c, 0x377, 0x55c, 0x55d, 0x55e, 0x56d, 0x56f, 0x570, 0x573, 0x575, 0x576, 0x585, 0x587, 0x66d, 0x674, 0x6b4, 0x6b5, 0x6b6, 0x80f, 0x813, 0x815, 0x819, 0x81a, 0x81b, 0x81c, 0x81d, 0x81e, 0x81f, 0x820, 0x821, 0x85d, 0x85e, 0x861, 0x862, 0x863, 0x866, 0x867, 0x868, 0x869, 0x86d, 0x86e, 0x871, 0xbab, 0xbac, 0xbad, 0xbaf, 0xbb2, 0xbc0, 0xbc1, 0xbc3, 0xbc4, 0xbc6, 0xbc8, 0xbca, 0xc0b]:
        text = get_dialogue(index)
        text = re.sub(r'KEFKA', "SANTA", text)
        set_dialogue(index, text)

    BattleSantasub = Substitution()
    BattleSantasub.bytestring = bytes([0x92, 0x9A, 0xA7, 0xAD, 0x9A])
    for location in [0xFCB54, 0xFCBF4, 0xFCD34]:
        BattleSantasub.set_location(location)
        BattleSantasub.write(fout)
    for index, offset in [(0x30, 0x4), (0x5F, 0x4), (0x64, 0x1A), (0x66, 0x5), (0x86, 0x14), (0x93, 0xE), (0xCE, 0x59), (0xD9, 0x9), (0xE3, 0xC), (0xE8, 0xD)]:
        BattleSantasub.set_location(get_long_battle_text_pointer(fout, index) + offset)
        BattleSantasub.write(fout)

    BattleSANTAsub = Substitution()
    BattleSANTAsub.bytestring = bytes([0x92, 0x80, 0x8D, 0x93, 0x80])
    for location in [0x479B6, 0x479BC, 0x479C2, 0x479C8, 0x479CE, 0x479D4, 0x479DA]:
        BattleSANTAsub.set_location(location)
        BattleSANTAsub.write(fout)
    for index, offset in [(0x1F, 0x0), (0x2F, 0x0), (0x31, 0x0), (0x57, 0x0), (0x58, 0x0), (0x5A, 0x0), (0x5C, 0x0), (0x5D, 0x0), (0x60, 0x0), (0x62, 0x0), (0x63, 0x0), (0x65, 0x0), (0x85, 0x0), (0x87, 0x0), (0x8d, 0x0), (0x91, 0x0), (0x94, 0x0), (0x95, 0x0), (0xCD, 0x0), (0xCE, 0x0), (0xCF, 0x0), (0xDA, 0x0), (0xE5, 0x0), (0xE7, 0x0), (0xE9, 0x0), (0xEA, 0x0), (0xEB, 0x0), (0xEC, 0x0), (0xED, 0x0), (0xEE, 0x0), (0xEF, 0x0), (0xF5, 0x0)]:
        BattleSANTAsub.set_location(get_long_battle_text_pointer(fout, index) + offset)
        BattleSANTAsub.write(fout)


def _add_spookiness():
    n_o_e_s_c_a_p_e_sub = Substitution()
    n_o_e_s_c_a_p_e_sub.bytestring = bytes([0x4B, 0xAE, 0x42])
    locations = [0xCA1C8, 0xCA296, 0xB198B]
    if not options_.is_code_active('notawaiter'):
        locations.extend([0xA89BF, 0xB1963])
    for location in locations:
        n_o_e_s_c_a_p_e_sub.set_location(location)
        n_o_e_s_c_a_p_e_sub.write(fout)

    n_o_e_s_c_a_p_e_bottom_sub = Substitution()
    n_o_e_s_c_a_p_e_bottom_sub.bytestring = bytes([0x4B, 0xAE, 0xC2])
    for location in [0xA6325]:
        n_o_e_s_c_a_p_e_bottom_sub.set_location(location)
        n_o_e_s_c_a_p_e_bottom_sub.write(fout)

    nowhere_to_run_sub = Substitution()
    nowhere_to_run_sub.bytestring = bytes([0x4B, 0xB3, 0x42])
    locations = [0xCA215, 0xCA270, 0xC8293]
    if not options_.is_code_active('notawaiter'):
        locations.extend([0xB19B5, 0xB19F0])
    for location in locations:
        nowhere_to_run_sub.set_location(location)
        nowhere_to_run_sub.write(fout)

    nowhere_to_run_bottom_sub = Substitution()
    nowhere_to_run_bottom_sub.bytestring = bytes([0x4B, 0xB3, 0xC2])
    locations = [0xCA7EE]
    if not options_.is_code_active('notawaiter'):
        locations.append(0xCA2F0)
    for location in locations:
        nowhere_to_run_bottom_sub.set_location(location)
        nowhere_to_run_bottom_sub.write(fout)

def _dragonballs():
    load_patch_file('magicite')
    set_dialogue_var('magicite_singular', 'Dragonball')
    set_dialogue_var('magicite_piece', 'Dragonball')
    set_dialogue_var('magicite_plural', 'Dragonballs')
    set_dialogue_var('magicite_pieces', 'Dragonballs')

def _piccolo_day():
    set_dialogue(38, 'PICCOLO: Therefore, every May 9th will be celebrated as Piccolo Day.')

def _piccolo():
    load_patch_file('gestahl')
    set_dialogue_var('Gestahl', 'Piccolo')
    set_dialogue_var('Gestahl_title', 'King')
    set_dialogue_flag('Gestahl_title_vowel', False)
    set_battle_dialogue(135, 'KEFKA:<line>K<wait for key>I<wait for key>N<wait for key>G<wait for key> P<wait for key>I<wait for key>C<wait for key>C<wait for key>O<wait for key>L<wait for key>O……<wait for key><line>I need you here……<P>')

def _kamehameha(fout):
    fout.seek(0x26F83B)
    fout.write(name_to_bytes('Kamehameha', 10))
    # Make it bluer
    fout.seek(0x107FB2 + 14*94 + 6)
    fout.write(bytes([173]*3))
    # Make it stronger
    aurabolt = get_spell(0x5e)
    power = min(aurabolt.power * 3 // 2, 255)
    fout.seek(aurabolt.pointer + 6)
    fout.write(bytes([power]))
