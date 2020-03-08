// Bushido abilities are learned on level up regardless of who's in the party.

architecture wdc65816
include "_defs.asm"


// Handle all characters' script level ups as if they were Cayenne.
// This breaks Blitzes, which we handle with the next patch.
reorg($C0A18A)
	jmp $C0A1DA & $FFFF   // Cayenne handler
	rts  // pointless?
exactpc($C0A18E)

// After processing Tina's natural magic, go back and process Celes's.
// NOTE: This patch has no effect if natmag_learn is in use.
reorg($C0A1B4)
	beq $C0A186
reorg($C0A1B6)

// After processing Celes's natural magic, go back and handle Cayenne's.
// NOTE: This patch has no effect if natmag_learn is in use.
reorg($C0A1D6)
	beq $C0A18A
exactpc($C0A1D8)

// After processing Bushido learning above, process Blitz learning.
reorg($C0A200)
	// Delete the RTS at the end of Cayenne handling to fall through to Mash.
	nop
exactpc($C0A201)


// Lores are learned regardless of having a Lore user in the party.
// I don't know how this actually works.  -- Myria
reorg($C236E4)
	// Disable "bmi $C23708".
	nop
	nop
	// Put zero in the bitmask parameters to C25864 instead of whatever those
	// values (B0C3, 2310) mean in the original.
	pea 0
	pea 0
exactpc($C236EC)


// Dances are learned regardless of whether a Dance user is in the party.
reorg($C25EE8)
	nop
	nop
exactpc($C25EEA)


// On battle level up, handle Bushido learning.
reorg($C261C7)
	// The instructions replaced are:
	//   cmp.b #2        // Cayenne character ID
	//   bne $C261E0
	xba
	pha
	xba
	nop
exactpc($C261CB)
	jsr $C26222 & $FFFF  // original code
exactpc($C261CE)
	// After that Bushido learning, do Blitz learning.
	// Patch a few jumps to go to the Blitz code instead of returning.
	beq C261CE_continue
	tsb.w $7E1CF7        // original code
	bne C261CE_continue
	lda.b #$40           // original code
	tsb.b $F0            // original code
C261CE_continue:
exactpc($C261D9)
	// Restore old value of A and fall through to Blitz processing.
	pla
	xba
	nop
	nop
	nop
	nop
	nop
exactpc($C261E0)
	ldx.w #8             // original code; distance from Bushido level table to Blitz level table
	// Delete this code:
	//   cmp.b #5        // Mash character ID
	//   bne $C26221
	nop
	nop
	nop
	nop
exactpc($C261E7)
