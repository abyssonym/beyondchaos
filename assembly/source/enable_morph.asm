// Enable Morph command before Tina wakes up in Zozo?

architecture wdc65816
include "_defs.asm"


reorg($C25410)
	// Delete an undesired "beq" after a bit check.
	nop
	nop
exactpc($C25412)
