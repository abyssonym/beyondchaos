// Allows characters with the hardwired X-Magic command to use the Magic menu
// in the menu system.

architecture wdc65816
include "_defs.asm"


// List of commands that unlock each entry of the Skills menu.
// (addresses in comments from Japanese FF6)
//C3/5438:  02      ; Magic (unlocks Espers)
//C3/5439:  02      ; Magic (unlocks Magic)
//C3/543A:  07      ; SwdTech
//C3/543B:  0A      ; Blitz
//C3/543C:  0C      ; Lore
//C3/543D:  10      ; Rage
//C3/543E:  13      ; Dance
reorg($C34D78)
commands_for_skill_unlock:


// Replace "cmp.l commands_for_skill_unlock,x" with a call to our code.
reorg($C34D56)
	jsl hook
exactpc($C34D5A)


reorg(enable_xmagic_menu_start)
function hook {
	// A = command in character's battle menu.
	// X = index of option in Skills menu.
	// Replaced instruction: Does this character have the requisite command?
	cmp.l commands_for_skill_unlock,x
	// If yes, return with zero flag set so it's allowed.
	beq return
	// Are we checking whether to allow the Magic option?
	cpx.w #1
	// If no, return with zero flag clear so it's grayed and blocked.
	bne return
	// Does this character have the X-Magic command?  If so, return zero flag.
	cmp.b #$17
return:
	rtl
}

warnpc(enable_xmagic_menu_start + enable_xmagic_menu_size)
