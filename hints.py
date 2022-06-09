from character import get_character
from dialoguemanager import set_dialogue
from itemrandomizer import get_item, get_dragoon_boots_command
from monsterrandomizer import get_collapsing_house_help_skill
from skillrandomizer import get_spell
from utils import Substitution


def setup_hints(fout, options_, commands):
    if options_.replace_commands or options_.shuffle_commands:
        _sabin_hint(commands)

    if options_.sprint:
        _sprint_shoes_hint(fout)

    if options_.random_enemy_stats or options_.random_formations:
        _house_hint()
        
    _school_hints(fout, options_, commands)


def _sprint_shoes_hint(fout):
    sprint_shoes = get_item(0xE6)
    spell_id = sprint_shoes.features['learnspell']
    spellname = get_spell(spell_id).name
    hint = f'Equip relics to gain a variety of abilities!<page>These teach me {spellname}!'

    set_dialogue(0xb8, hint)

    # disable fade to black relics tutorial
    sprint_sub = Substitution()
    sprint_sub.set_location(0xA790E)
    sprint_sub.bytestring = b'\xFE'
    sprint_sub.write(fout)


def _sabin_hint(commands):
    sabin = get_character(0x05)
    command_id = sabin.battle_commands[1]
    if not command_id or command_id == 0xFF:
        command_id = sabin.battle_commands[0]

    command = [c for c in commands.values() if c.id == command_id][0]
    hint = f'My husband, Duncan, is a world-famous martial artist!<page>He is a master of the art of {command.name}.'

    set_dialogue(0xb9, hint)


def _house_hint():
    skill = get_collapsing_house_help_skill()

    hint = f'There are monsters inside! They keep {skill}ing everyone who goes in to help. You using suitable Relics?'.format(skill)
    set_dialogue(0x8A4, hint)


def _school_hints(fout, options_, commands):
    set_dialogue(0x6d4, "At Save Points you can use a “Sleeping Bag” or “Tent”, and also save a game.<page>If you should perish, you'll automatically be able to play from your last save.<page>In Beyond Chaos, your Level and Exp. data will NOT be retained, unlike the original game.<page>You can save a game anywhere on the world map.")

    command_name = get_dragoon_boots_command(fout, commands).capitalize()
    if options_.sprint:
        sprint_shoes = get_item(0xE6)
        spell_id = sprint_shoes.features['learnspell']
        spellname = get_spell(spell_id).name
        shoes_effect = f'teach you {spellname}'
    else:
        shoes_effect = 'double your speed'
     
    set_dialogue(0x6d2, f'Relics give your party members a variety of abilities.<line>For example…<page>“Sprint Shoes” {shoes_effect}.<page>“True Knight” lets you shield others during battle.<page>“Dragoon Boots” add the “{command_name}” command to your battle list.<page>“Gauntlet” allows you to hold a sword with both hands.<line>Use the Main Menu to equip up to 2 relics per person.')

    if options_.random_treasure:
        set_dialogue(0x25c, "Healing items aren't available in every town! Stock up on them wherever you can.")

    if options_.random_items or options_.random_enemy_stats or options_.random_dances:
        if options_.random_items:
            items_text = '<page>Press the B button twice on an item to see its elemental properties and who can equip it.<page>Press B again (or Left) to see its stats and special effects.'
        else:
            item_text = ''
        if options_.random_enemy_stats:
            rage_text = '<page>Press the B button twice on Rages in the Skill menu to see what they do.'
        else:
            rage_text = ''
        if options_.random_dances:
            dance_text = '<page>Select Dances in the Skill menu to see what abilities they can use.'
        else:
            dance_text = ''
        set_dialogue(0x25f, f'Beyond Chaos has improved menu features!<page>You can press the Y button to switch between the Equip and Relics menus{items_text}{rage_text}{dance_text}')

    if options_.replace_commands or options_.random_enemy_stats:
        set_dialogue(0x26d, "It's a good idea to use “Float” as much as possible! You never know when a Quake will show up!")

    set_dialogue(0x26f, 'Some bosses in the original game required certain skills, like Pummel, to defeat them.<page>In Beyond Chaos, those will still work if you happen to have them, but you can also just kill them normally.')

    if options_.replace_commands:
        set_dialogue(0x272, "Got a command you don't recognize?<page>If it looks like two ability names smooshed together, it uses both of them in sequence!<page>“R-” commands use a random ability from a group.<page>“W-” commands use that ability twice.<page>“?-” commands use that ability a random number of times.<page>Some might not be useful…<wait 60 frames><line>Or even safe!")
        

    if options_.shuffle_commands and not options_.is_code_active('suplexwrecks'):
        set_dialogue(0x275, 'You learn Swdtechs and Blitzes based on the level of your highest level party member.<page>You learn new Dances and Lores regardless of who is in your party.<page>You learn new Rages regardless of who is in your party, even off the Veldt and without Leaping.')
