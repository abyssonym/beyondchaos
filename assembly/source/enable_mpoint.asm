// Enable recharging of the Morph meter in all cases.

architecture wdc65816
include "_defs.asm"


reorg($C25E38)
	// Delete an undesired "beq" after a check.
	nop
	nop
exactpc($C25E3A)
