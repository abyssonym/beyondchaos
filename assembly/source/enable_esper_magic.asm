// Any character can learn natural magic, rather than just Tina and Celes.

architecture wdc65816
include "_defs.asm"


reorg($C34D3D)
	jsr hook
	nop
exactpc($C34D41)


reorg(enable_esper_magic_start)
function hook {
	// Enable Esper menu regardless of Magic command, unless character
	// is Gogo.  (Gogo check is at $C34D6F, overwriting this one.)
	lda.b #$20
	ldx.b $00
	sta.b $79,x
	inx
	lda.b #$24
	rts
}
warnpc(enable_esper_magic_start + enable_esper_magic_size)
