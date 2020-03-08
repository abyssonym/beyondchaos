// Provide a convenient way to access the Fanatics' Tower replacement command.

architecture wdc65816
include "_defs.asm"


reorg($C2537E)
	// Same as original code.
replacement_command_load:
	lda.b #$FF
exactpc($C25380)


// Tell the randomizer where the magic table is located.
start_exports()
export("replacement_command", replacement_command_load + 1)
