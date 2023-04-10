// alphabetize rages in the skill menu (rages are already alphabetized in the battle menu)

architecture wdc65816
include "_defs.asm"

// call C25217 indirectly. sets X = A / 8, A = 2 ^ (A % 8)
reorg($C2FC69)
call_C25217:
jsr $5217
rtl
exactpc($C2FC6D)


reorg($C353C7)

sep #$10
ldx.b $00
loop:
lda.l $F01416,x
tay
phx
clc
jsl call_C25217
bit $1d2c,x
beq store_null
tya
bra store_monster_num
store_null:
lda.b #$FF
store_monster_num:
sta $2180
plx
inx
bne loop
rep #$10
rts
nop
nop
nop
rts
exactpc($C353EE)

reorg($C35433)
nop
nop
jsr $8467
