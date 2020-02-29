// Any character can learn natural magic, rather than just Tina and Celes.

arch snes.cpu
incsrc "_defs.asm"


{reorg $C0A182}
	jsl hook1
	nop
	nop
	nop
	nop
{exactpc $C0A18A}
{reorg $C261B6}
	jsl hook2
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
{exactpc $C261C4}


{reorg {natmag_learn_start}}
hook1:
	cmp.b #12
	bcs .return
	pha
	phx
	phy
	phd
	pea $1500
	pld
	sta.b $08
	xba
	pha
	sta.b $0B
	ldx.w $00F4
	stx.b $09
	tdc
	xba
	lda.b #$80
	sta.b $0C
	jsl main_function
	pla
	xba
	pld
	ply
	plx
	pla
.return:
	rtl

hook2:
	cmp.b #12
	bcs hook1.return
	pha
	phx
	phy
	phd
	pea $1500
	pld
	sta.b $08
	sta.w $4202
	lda.b #$36
	sta.w $4203
	lda $1608, y
	sta.b $0B
	
	rep #$20
	lda.w $4216
	clc
	adc.w #$1A6E
	sta.b $09
	lda.w #0
	sep #$20
	
	lda.b #$FF
	sta.b $0C
	jsl main_function
	pld
	ply
	plx
	pla
	rtl

main_function:
	ldy.b #$10
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

.loop:
	lda.l magic_table + 1, x
	cmp.b $0B
	beq .zero
	bcs .next

.zero:
	phy
	lda.l magic_table + 0, x
	tay
	lda ($09), y
	cmp.b #$FF
	beq .nothing
	lda.b $0C
	sta ($09), y
.nothing:
	ply
	
.next:
	inx
	inx
	dey
	bne .loop
	rtl

// Overwritten by randomizer
magic_table:
	fill 2 * 16 * 12, $FF

{warnpc {natmag_learn_start} + {natmag_learn_size}}


// Tell the randomizer where the magic table is located.
{start_exports}
{export "magic_table", magic_table}
