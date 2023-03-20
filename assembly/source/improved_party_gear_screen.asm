

architecture wdc65816
include "_defs.asm"


constant slot_name_table = $F007DB


reorg($C38F04)
function party_gear_hack {
	// Start at first slot.
	stz.b $28
	
	// Initialize extra palette color.
	jsl yellow_palette

member_loop:
	// Clear high part of A.
	lda.b #0
	xba
	// Is anyone in this slot?
	lda.b $28
	tax
	lda.b $69,x
	bmi nobody
	// Save the character ID.
	pha
	
	// While we have the slot in A, let's do some things.
	// Double slot and give to Y.  Clears carry because slot < 128.
	txa
	asl
	tay
	// Calculate high byte of text position for this slot:
	// $390D + (slot * $200).
	adc.b #$39
	xba
	lda.b #$0D
	// Copy actor's address.  They're words at 69, 6B, 6D, 6F.
	ldx.b $6D,y
	stx.b $67
	
	// Set palette to cyan and draw actor's name.
	// Y = text address (the 390D calculation above).
	tay
	phy
	lda.b #$24
	sta.b $29
	jsr $C334CF & $FFFF
	ply

	// Palette for slot name.
	lda.b #$28
	sta.b $29
	
	// Compute tile address for slot's name.
	rep #$21   // clear carry too
	tya
	adc.w #8 * 2
	sta.l $7E9E89
	// Set up parameters for fixed-size table.
	lda.w #8
	sta.b $EB
	lda.w #slot_name_table & $FFFF
	sta.b $EF
	sep #$20
	lda.b #slot_name_table >> 16
	sta.b $F1

	// Get back the character ID.
	pla
	// Don't draw slot's name if not a usual character.
	cmp.b #14
	bcs special_character

	// Copy fixed-size string to write buffer.
	// A = index of fixed-size string, just set.
	phy
	jsr $C38467 & $FFFF
	// Draw write buffer to tilemap.
	jsr $C37FD9 & $FFFF
	ply
	
special_character:	
	// Use special yellow palette.
	lda.b #$34
	sta.b $29
	
	// Draw esper's name.
	// Get tilemap address and move over 18 tiles.
	rep #$21   // clear carry too
	tya
	adc.w #16 * 2
	tay
	sep #$20
	// This routine wants the actor address in D+$67 and tilemap in Y.
	jsr $C334E6 & $FFFF
	
no_esper:
	// Reset palette to normal.
	lda.b #$20
	sta.b $29
	
	// Draw gear for this party member.
	// Row = 4 + (slot * 8).
	lda.b $28
	asl
	asl
	asl
	adc.b #$04
	jsr $C38F8A & $FFFF
	
	// Next party member.
nobody:
	lda.b $28
	inc
	sta.b $28
	cmp.b #4
	bne member_loop

	// Do stuff from the original code after the menu draws.
	jsr $C30E28 & $FFFF
	jsr $C30E36 & $FFFF
	jsr $C36A3C & $FFFF
	jmp $C30E6E & $FFFF
}

warnpc($C38F8A)


reorg($FF0000)
yellow_palette:
	rep #$20
	lda.w #$0000
	sta.l $7E3049 + (((5 * 16) + 0) * 2)
	sta.l $7E3049 + (((5 * 16) + 1) * 2)
	lda.w #$39CE
	sta.l $7E3049 + (((5 * 16) + 2) * 2)
	lda.w #$03BF
	sta.l $7E3049 + (((5 * 16) + 3) * 2)
	sep #$20
	rtl
