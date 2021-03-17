// Stops the Status screen from conditionally graying or hiding commands.
// Beyond Chaos players know how the commands work.

architecture wdc65816
include "_defs.asm"


reorg($C35EE1)
	// Skip most of the "Handle battle command modifiers" routine.
	// This skips the special checks for the Magic, Morph, Leap and Dance
	// commands, preventing them from being disabled.
	jsr $C3616F & $FFFF
	// Original code
	bmi $C35F0C
	// Skip the "Select a palette for battle command" routine entirely.
	nop
	nop
	nop
exactpc($C35EE9)
