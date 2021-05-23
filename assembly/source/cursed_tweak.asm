// Allow multiple items to be uncursed.
// Originally created by madsiur.

architecture wdc65816
include "_defs.asm"

// SRAM Init (This replace SwTech init)
reorg($C0BDE4)
initRam:
	stz $1E1D,x			// Free SRAM 
	inx
	cpx #$0008			// Init 4 bytes, one for each upgrade battle number
	bne initRam			// If you want 8 items, change #$0004 to #$0008
	bra continueA

reorg($C0BDF1)
continueA:

// Cursed shield check routine hookup
reorg($C25FFA)
	jsl CheckEmptyEquip
	bra continueB

reorg($C2600C)
continueB:

// New code
reorg($EEAF01)		// Free ROM space. I always use the same spot for new code.
					// Make sure to change this if you need to relocate the code.
CheckEmptyEquip:
	sta $1440			// Use of free RAM $1440 as temp storing value 
	pha					// Push A and X for the sake of restoring registers 
	phx					// at the end of routine
	ldx #$0000
equipLoop:
	lda EquipTableA,x	// Get weapon to upgrade
	cmp $1440			// Check if match equipped weapon
	beq itemFound		// Branch if match
	inx					// Increment table index
	cpx #$0008			// Check if done 4 items (change this value for bigger/smaller tables)
	bne equipLoop		// If not check next item in table
	bra exit			// If we reach this point no item match so exit
itemFound:
	inc $1E1D,x			// Item match so increment its counter
	lda FightsTable,x	// Load battle table value
	cmp $1E1D,x			// Check if it equal counter
	beq fightEqual		// branch if so
	bra exit			// if not we need to win more fights!
fightEqual:
	stz $1E1D,x			// Counter equal number of fights needed so reset counter
	lda #$01
	tsb $F0				// Display "uncursed" message at end of fight
	lda EquipTableB,x	// Load upgraded item
	plx			
	sta $161F,x			// Store upgraded weapon in place of the old one
	pla
	rtl
exit:
	plx
	pla
	rtl

// Items to upgrade. Comment out or add lines for more item as well as 
// changing line 36 (Main routine) and 9 (SRAM Init) above if needed.
EquipTableA:
db $66	// Cursed shield
db $00	
db $00
db $00
db $00
db $00
db $00
db $00


// Upgraded items. Number of line must match table above.
EquipTableB:
db $67	// Paladin Shield
db $00	
db $00
db $00
db $00
db $00
db $00
db $00


// Number of battles needed to upgrade item
FightsTable:
db $FF	// 256 battles
db $FF
db $FF
db $FF
db $FF
db $FF
db $FF
db $FF

start_exports()
export("equip_table_a", EquipTableA)
export("equip_table_b", EquipTableB)
export("fights_table", FightsTable)