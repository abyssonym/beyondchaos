// Allows characters with the hardwired X-Magic command to use the Magic menu
// in the menu system.

arch snes.cpu
incsrc "_defs.asm"


{reorg $C34D56}
	jsl hook
{exactpc $C34D5A}

{reorg {enable_xmagic_menu_start}}
hook:
	// Replaced instruction.
	cmp.l $C34D78, x
	beq .return
	// Check whether it's index 1 and has 17 (X-Magic)
	cpx.w #1
	bne .return
	cmp.b #$17
.return:
	rtl

{warnpc {enable_xmagic_menu_start} + {enable_xmagic_menu_size}}
