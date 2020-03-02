// Randomizes the order in which characters are sent to fight the final battle
// instead of letting the player decide.

architecture wdc65816
include "_defs.asm"


// Selected character slots, corresponding to the right side of the screen in
// the original code.
constant selected_slots = $7E0205


// handle_end is the part of the original sustain_final_battle_lineup that
// triggers the closing of the final lineup selection dialog.
reorg($C3AA99)
handle_end:


// Overwrite the function "74: Sustain final battle lineup" from the commented
// FF6j disassembly.  This function is called once per frame while the
// character selection dialog is shown.  We just make it immediately end and
// choose a random party.
reorg($C3AA25)
function sustain_final_battle_lineup {
	// Trigger the close of the window.
	// Because the player "hasn't selected" any character, this will cause the
	// list at 0205 to be filled in order with the 12 eligible characters.
	jsr handle_end
	
	// Main code.
	lda.b #0
	tay
	// Use the encounter seed and frame counter to initialize the RNG seed.
	// BUG: Doesn't clear carry.  Not that we really care with RNG.
	lda.w frame_counter
	adc.w rngseed_encounter
	sta.w rngseed_event
	
	// Shuffle the entries of 
loop:
	// Use next seed.
	inc.w rngseed_event
	lda.w rngseed_event
	// BUG: Doesn't clear carry.
	adc.w rngseed_encounter
	// Whiten the raw value using the S-box.
	tax
	lda.l rng_table,x
	
	// Loop until we get a lower nibble in the range [0-11].
	and.b #$0F
	cmp.b #12 - 1
	bcs loop
	
	// Swap the current considered slot with the selected random one.
	tax
	lda.w selected_slots,y
	pha
	lda.w selected_slots,x
	sta.w selected_slots,y
	pla
	sta.w selected_slots,x
	
	// Next.
	iny
	tya
	cmp.b #12
	bcc loop
	
	rts
}

// handle_end is part of the original sustain_final_battle_lineup.  Because we
// call it, that is the point we can't cross.
warnpc(handle_end)
