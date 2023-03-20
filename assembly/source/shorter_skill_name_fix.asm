// Fix display of skill names in menu.

architecture wdc65816
include "_defs.asm"

reorg($C352E8)
ldy #swtech    // Text pointer

reorg($C3539B)
ldy #rage      // Text pointer

reorg($C35460)
ldy #espers    // Text pointer

reorg($C355DE)
ldy #blitz     // Text pointer

reorg($C3577E)
ldy #dance     // Text pointer


reorg($C35C91)
db $B7,$81,$8B,$A8,$AB,$9E,$FE,$FE,$FE,$00      // Lore
rage:
db $B7,$81,$91,$9A,$A0,$9E,$FE,$FE,$FE,$00      // Rage
dance:
db $B7,$81,$83,$9A,$A7,$9C,$9E,$FE,$FE,$00      // Dance
espers:
db $B7,$81,$84,$AC,$A9,$9E,$AB,$AC,$FE,$00      // Espers

reorg($C3FF7A)
blitz:
db $B7,$81,$81,$A5,$A2,$AD,$B3,$FE,$FE,$00      // Blitz
swtech:
db $B7,$81,$92,$B0,$9D,$93,$9E,$9C,$A1,$00      // SwdTech


