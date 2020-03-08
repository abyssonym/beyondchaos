// Fix the Sketch glitch in FF6 US 1.0.
// The original author of this hack wasn't listed in the source file.

architecture wdc65816
include "_defs.asm"


//(Original code.  Much of this is unchanged by the patch, but I've included it for reference
// so you know where branches go.)
//
//C2/F58D: 20 33 FA     JSR $FA33
//C2/F590: A9 08        LDA #$08
//C2/F592: 85 26        STA $26
//C2/F594: A9 05        LDA #$05
//C2/F596: 20 F8 F4     JSR $F4F8
//C2/F599: A9 06        LDA #$06
//C2/F59B: 4C E6 F6     JMP $F6E6
//
//C2/F59E: 4C 33 FA     JMP $FA33
//
//C2/F5A1: 4C 33 FA     JMP $FA33   (identical to above.  could reuse these 3 bytes if we
//                                   changed the C2/E8D8 table entry that pointed here.)
//
//C2/F5A4: A9 00        LDA #$00
//C2/F5A6: 85 26        STA $26
//C2/F5A8: A9 07        LDA #$07
//C2/F5AA: 20 F8 F4     JSR $F4F8
//C2/F5AD: A9 08        LDA #$08
//C2/F5AF: 20 E6 F6     JSR $F6E6
//C2/F5B2: 20 4F FA     JSR $FA4F
//C2/F5B5: A9 3C        LDA #$3C
//C2/F5B7: 8F 23 21 00  STA $002123
//C2/F5BB: 9C 1B 96     STZ $961B
//C2/F5BE: 4C 27 FA     JMP $FA27
//
//C2/F5C1: EE AC 60     INC $60AC
//C2/F5C4: A9 00        LDA #$00
//C2/F5C6: 85 26        STA $26     (these 5 lines look mighty similar to C2/F592...)
//C2/F5C8: A9 05        LDA #$05
//C2/F5CA: 20 F8 F4     JSR $F4F8
//C2/F5CD: A9 06        LDA #$06
//C2/F5CF: 4C E6 F6     JMP $F6E6   (such waste!  somewhere right now, an elderly Native American
//                                   is looking at this, and a lone tear rolls down his cheek.)
//
//
//****  Below is the block of code that allows the bug of much infamy! ****
//
//C2/F5D2: A0 00 28     LDY #$2800
//C2/F5D5: 22 09 B1 C1  JSL $C1B109
//C2/F5D9: AD 8D 89     LDA $898D
//C2/F5DC: 29 FE        AND #$FE
//C2/F5DE: 8D 8D 89     STA $898D    (turn off Bit 0 of $898D)
//C2/F5E1: A0 03 00     LDY #$0003
//C2/F5E4: B1 76        LDA ($76),Y  (get 0-5 index of enemy within formation ?)
//C2/F5E6: 0A           ASL 
//C2/F5E7: AA           TAX          (If "($76),Y" held a big value like FFh, we shouldn't
//                                    be deriving X from it.  This will let C2/F5EA load
//                                    a value from unrelated territory, and a dangerous
//                                    gibberish X value gets passed to Bank C1...)
//
//C2/F5E8: C2 20        REP #$20     (Set 16-bit Accumulator)
//C2/F5EA: BD 01 20     LDA $2001,X  (get enemy number ranging from 0-383 ?)
//C2/F5ED: AA           TAX 
//C2/F5EE: 7B           TDC 
//C2/F5EF: E2 20        SEP #$20     (Set 8-bit Accumulator)
//C2/F5F1: 22 D1 24 C1  JSL $C124D1
//C2/F5F5: 4C 09 F8     JMP $F809


//===============================================================================================
// (Bugfixed code.  Changes start at C2/F5C6.)


reorg($C2F5C6)
function sketch_fix {
	bra $C2F592                 // (Zap!  there goes 10 bytes of redundant code.)
    nop
    nop
    nop
    nop
    nop
    nop
    nop                         // (7 bytes freed on top of the fix!  Contrast that
                                //  with FF3us 1.1, which ADDS 7 bytes.)

replacement:
	jmp $C2F809 & $FFFF         // (displaced from the C2/F5D2 block below)

exactpc($C2F5D2)
	ldy.w #$2800
	jsl $C1B109
	lda.b #$01
	trb.w $898D                 // (turn off Bit 0 of $898D)
	ldy.w #3
	lda ($76),y                 // (get 0-5 index of enemy within formation ?)
	asl
	tax
	
	rep #$20                    // (Set 16-bit Accumulator)
	lda.w $2001,x               // (get enemy number ranging from 0-383 ?)
	bcc alright                 // (If "($76),Y" held a low value, we're alright, so branch.
                                //  If the top bit was set, meaning it likely held FFh due
                                //  to a Sketch miss, we need to take precautions.)

bad:
	tdc
	dec                         // (X will become a safe FFFFh)

alright:
	tax
	tdc
	sep #$20                    // (Set 8-bit Accumulator)
	jsl $C124D1
	bra replacement             // (The fix was a mere 1 byte short of fitting in this block,
                                //  so branch to a newly renovated block to execute Square's
                                //  final instruction.)
}
exactpc($C2F5F8)
