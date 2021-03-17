// Any character can learn natural magic, rather than just Tina and Celes.

architecture wdc65816
include "_defs.asm"


// 12 * $36 byte table of learned magic for each character slot.
constant num_magical_characters = 12
constant num_spells = $36
constant learned_magic = $7E1A6E


// The routine at C0A17F is executed on level-up to handle character-
// specific logic for leveling up.  Four characters are handled
// specially: Tina, Celes, Cayenne and Mash.
reorg($C0A182)
	// C0A182 says:
	//   cmp.b #0     // Tina
	//   beq $C0A196
	//   cmp.b #6     // Celes
	//   beq $C0A1B8
	// Delete those checks, which are used for their natural magic, and
	// call our code instead.
	jsl hook2
	nop
	nop
	nop
	nop
	// At C0A18A are the special handling checks for Cayenne then Mash.
exactpc($C0A18A)
// In-battle level-ups, same idea.
// FIXME: Why not just replace this routine entirely for both this and
// learn_hacks.asm?
reorg($C261B6)
	jsl hook1
	nop
	nop
	nop
	nop
	nop
	nop
	nop
	nop
	nop
	nop
exactpc($C261C4)


reorg(natmag_learn_start)
function hook1 {
	// If a temporary character or Umaro/Gogo, do nothing.
	cmp.b #num_magical_characters
	bcs return
	pha
	phx
	phy
	phd
	pea $1500
	pld
	// Store character ID.
	sta.b $08
	xba
	pha
	// Level just earned.
	sta.b $0B
	// Copy offset to magic table for this character to D+$09.
	ldx.w $00F4
	stx.b $09
	tdc
	xba
	// Mark learned spells as newly learned so that "X learned Meow!" shows.
	lda.b #$80
	sta.b $0C
	jsl main_function
	pla
	xba
	pld
	ply
	plx
	pla
return:
	rtl
}

function hook2 {
	// If a temporary character or Umaro/Gogo, do nothing.
	cmp.b #num_magical_characters
	bcs hook1.return
	pha
	phx
	phy
	phd
	pea $1500
	pld
	// Store character ID.
	sta.b $08
	// Compute the offset of this character's magic table by multiplying the
	// character ID by num_spells.
	sta.w $4202
	lda.b #num_spells
	sta.w $4203
	// During the multiplier's latency, save the level just earned.
	lda $1608,y
	sta.b $0B
	
	rep #$20
	lda.w $4216
	clc
	adc.w #learned_magic & $FFFF
	sta.b $09
	lda.w #0
	sep #$20
	
	// Mark learned spells as completely learned.
	lda.b #$FF
	sta.b $0C
	jsl main_function
	pld
	ply
	plx
	pla
	rtl
}

function main_function {
	ldy.w #$0010
	lda.b $08
	rep #$20
	and.w #$00FF
	xba
	lsr
	lsr
	lsr
	tax
	lda.w #0
	sep #$20

loop:
	// Has this character achieved this entry's level?
	lda.l magic_table + 1,x
	cmp.b $0B
	beq achieved
	bcs next

achieved:
	// Which spell should be learned?
	phy
	lda.l magic_table + 0,x
	tay
	// Does this character already know the spell?
	lda ($09),y
	cmp.b #$FF
	beq already_learned
	// Mark the spell as learned (or about to be learned at end of battle).
	lda.b $0C
	sta ($09),y
already_learned:
	ply
	
next:
	inx
	inx
	dey
	bne loop
	rtl
}

// Overwritten by randomizer
magic_table:
	fill 2 * 16 * 12, $FF

warnpc(natmag_learn_start + natmag_learn_size)


// Tell the randomizer where the magic table is located.
start_exports()
export("magic_table", magic_table)
