// Decide whether changing relics forces reequip based on the relics'
// properties, rather than whether they are Gauntlet/Genji Glove/Merit Award.
// The original author of this patch wasn't listed in the source file.

architecture wdc65816
include "_defs.asm"


// Gauntlet, Genji Glove, Merit Award bits
constant relevant_bits = $38


reorg($C39EF8)
	jsr auto_equip

reorg(auto_equip_start)
function auto_equip {
	jsr $C393F2 & $FFFF                 // set Y=character data
	lda.w $0023,y                       // relic 1
	cmp.b $B0                           // unchanged?
	bne compare_new_vs_old              // branch if not
	lda.w $0024,y                       // relic 2
	cmp.b $B1                           // unchanged?
	bne compare_new_vs_old              // branch if not
	bra exit                            // reequip: no

// fork: compare old and new relics
compare_new_vs_old:
	stz.b $99                           // reequip: no
	
	lda.b $B0                           // old relic 1
	jsr $C38321 & $FFFF                 // item index
	ldx.w reg_mpyl                      // multiply result has item pointer from C38321
	lda.l rom_item_data + 12,x          // item properties
	and.b #relevant_bits
	sta.b $FE

	lda.b $B1                           // old relic 2
	jsr $C38321 & $FFFF                 // item index
	ldx.w reg_mpyl                      // multiply result has item pointer from C38321
	lda.l rom_item_data + 12,x          // item properties
	and.b #relevant_bits
	tsb.b $FE

	lda.w $0023,y                       // new relic 1
	jsr $C38321 & $FFFF                 // item index
	ldx.w reg_mpyl                      // multiply result has item pointer from C38321
	lda.l rom_item_data + 12,x          // item properties
	and.b #relevant_bits
	sta.b $FF

	lda.w $0024,y                       // new relic 2
	jsr $C38321 & $FFFF                 // item index
	ldx.w reg_mpyl                      // multiply result has item pointer from C38321
	lda.l rom_item_data + 12,x          // item properties
	and.b #relevant_bits
	tsb.b $FF
	
	lda.b $FE                           // Old effects
	cmp.b $FF                           // New effects
	beq exit                            // Abort if same
	inc.b $99                           // Reequip: yes

exit:
	rts
}

warnpc(auto_equip_start + auto_equip_size)
