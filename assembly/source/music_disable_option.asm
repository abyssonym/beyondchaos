// Adds music on/off switch to config menu.

architecture wdc65816
include "_defs.asm"

// Use FF6 text mapping instead of ASCII.
map_ff6_menu()


// Hook the reset sequence so that whether the title screen music plays is
// independent of what random state RAM had at boot.
reorg($C00053)
	jsl reset_hook


// Patch a reference to page1_adjust_cursor, because it moved.
reorg($C31C8F)
	jsr navigation_hacks.page1_adjust_cursor


// Scroll to config page 2 when pressing down from the 10th option instead of the 9th.
reorg($C322D0)
	cmp.b #9


// Patch a reference to dpad_page1, because it moved.
reorg($C32303)
	jsr navigation_hacks.dpad_page1


// Redo "click" function pointer table.
reorg($C32347)
function clicktable_hacks {
	// Adjust pointer for page 2 since we're adding an entry to page 1.
	jmp (table_page2,x)

exactpc($C3234A)
table_page1:
	dw $C32341 & $FFFF        // Bat.Mode   (NOP)
	dw $C32341 & $FFFF        // Bat.Speed  (NOP)
	dw $C32341 & $FFFF        // Msg.Speed  (NOP)
	dw cmdset_click           // Cmd.Set
	dw $C32341 & $FFFF        // Gauge      (NOP)
	dw $C32341 & $FFFF        // Sound      (NOP)
	dw $C32341 & $FFFF        // Music      (NOP)  - new option!
	dw $C32341 & $FFFF        // Cursor     (NOP)
	dw $C32341 & $FFFF        // Reequip    (NOP)
	dw $C32379 & $FFFF        // Controller
table_page2:
	dw $C32341 & $FFFF        // Mag.Order  (NOP)
	dw $C32341 & $FFFF        // Window     (NOP)
	dw $C32388 & $FFFF        // Color
	dw $C32388 & $FFFF        // R
	dw $C32388 & $FFFF        // G
	dw $C32388 & $FFFF        // B

// We overwrite 2 bytes into the Cmd.Set click handler.
// Get around this by optimizing 2 bytes out.
exactpc($C3236A)
cmdset_click:
	// The original code did this LDA then BIT #$80 BEQ.
	// We can just BPL after the LDA and there are our two bytes.
	lda.w config_battle
	bpl $C32341
exactpc($C3236F)
}


// Hook when the player reorders party members.
reorg($C32533)
	jmp party_reorder_hook
warnpc($C32536)


// Redo navigation data for config page 1.
reorg($C33858)
function navigation_hacks {
// Load navigation data for Config page 1
start:
	// We need two more bytes to fit the cursor location row for Music.
	// Turn two jmp instructions into bra to save those two bytes.
	ldy.w #navigation_page1
	bra $C33881               // jmp $C305FE
	
// Handle D-Pad for Config page 1
dpad_page1:
	// NOTE: This routine moves, so we need to patch up the reference.
	jsr.w $C3072D             // Handle D-Pad
page1_adjust_cursor:
	// NOTE: This part of the routine has its own references to patch.
	ldy.w #cursor_page1       // Pointer to page1's cursor locations
	bra $C3388A               // jmp $C30640

// Navigation data for Config page 1
navigation_page1:
	db $81                    // Never wraps
	db 0                      // Initial column
	db 0                      // Initial row
	db 1                      // 1 column
	db 10                     // 10 rows - 9 rows originally!

// Cursor positions for Config page 1
cursor_page1:
	db 96, 41 + 0*16          // Bat.Mode
	db 96, 41 + 1*16          // Bat.Speed
	db 96, 41 + 2*16          // Msg.Speed
	db 96, 41 + 3*16          // Cmd.Set
	db 96, 41 + 4*16          // Gauge
	db 96, 41 + 5*16          // Sound
	db 96, 41 + 6*16          // Music         - New option!
	db 96, 41 + 7*16          // Cursor
	db 96, 41 + 8*16          // Reequip
	db 96, 41 + 9*16          // Controller
}
warnpc($C3387E)


// Hook the rendering of the other cyan text to render Music.
reorg($C338D7)
	jsr draw_option_labels_hook


// Hook the drawing of the "Reset" "Memory" text.
reorg($C3390C)
	jsr draw_music_on_off_hook


// Patch a reference to page1_adjust_cursor, because it moved.
reorg($C339FD)
	jmp navigation_hacks.page1_adjust_cursor


// When scrolling up from config page 2 to 1, put cursor on 10th row.
reorg($C33A40)
	lda.b #9
	// We need to patch a jsr here too, for page1_adjust_cursor moving,
	// so just keep going.
	sta.b $4E
	jsr navigation_hacks.page1_adjust_cursor
exactpc($C33A47)


// Redo jump tables for config options.
reorg($C33D3D)
function update_dispatch {
	jmp (page2_table,x)
	jmp (page1_table,x)       // code branches here for page 1
page1_table:
	dw update_battle_mode     // Bat.Mode      - moved a bit to make room for larger table
	dw $C33D7A & $FFFF        // Bat.Speed
	dw $C33DAB & $FFFF        // Msg.Speed
	dw $C33DE8 & $FFFF        // Cmd.Set
	dw $C33E01 & $FFFF        // Gauge
	dw $C33E1A & $FFFF        // Sound
	dw update_music_option    // Music         - New option!
	dw $C33E4E & $FFFF        // Cursor
	dw $C33E6D & $FFFF        // Reequip
	dw $C33E86 & $FFFF        // Controller
page2_table:
	dw $C33E9F & $FFFF        // Mag.Order
	dw $C33ECD & $FFFF        // Window
	dw $C33F01 & $FFFF        // Viewed color
	dw $C33F3C & $FFFF        // R
	dw $C33F5B & $FFFF        // G
	dw $C33F7A & $FFFF        // B

	// We've intruded 2 bytes into the "Bat.Mode" update code.
	// Rather than move it, optimize the routine so it fits in 2 fewer bytes.
exactpc($C33D63)
update_battle_mode:
	jsr.w $C30EA3             // Sound: Cursor
	// Pressing right?
	lda.b $0B                 // Semi-auto keys
	lsr                       // Put low bit into carry for bcs (save 1 byte versus bit + bne)
	lda.b #$08                // Do before branch, because doesn't touch carry (saves 2 bytes)
	bcs pressing_right
	trb.w config_battle       // Clear "Wait" bit
	bra continue              // Save 1 byte by branching to jmp instead of jmp
pressing_right:
	tsb.w config_battle       // Set "Wait" bit
continue:
	jmp.w $C33B8C             // Redraw "Active" and "Wait" strings
}
warnpc($C33D7A)


// Move options two rows down.
reorg($C3490B)
	dw $3D8F + (2 * $40)      // "Controller"
reorg($C34950)
	dw $3CB5 + (2 * $40)      // "Memory"
reorg($C34959)
	dw $3D25 + (2 * $40)      // "Optimum"
reorg($C34963)
	dw $3DB5 + (2 * $40)      // "Multiple"
reorg($C3498A)
	dw $3C8F + (2 * $40)      // "Cursor"
reorg($C349E7)
	dw $3D0F + (2 * $40)      // "Reequip"
reorg($C34A03)
	dw $3CA5 + (2 * $40)      // "Reset"
reorg($C34A0B)
	dw $3D35 + (2 * $40)      // "Empty"
reorg($C34A13)
	dw $3DA5 + (2 * $40)      // "Single"



reorg($C501A4)
	jml music_load_hook

reorg($C505A6)
	jml spc_interrupt_hook


// Room for added code.
reorg($C3FA00)


// Called while drawing the cyan labels.
function draw_option_labels_hook {
	// Draw "Music".
	ldy.w #music_text
	jsr.w $C302F9
	// Replaced code.
	ldx.w #$4993
	rts
	
music_text:
	dw $3C8F
	db "Music",0
}


// Called to update the Music on/off option.
function update_music_option {
	// Play cursor move sound.
	jsr.w $C30EA3
	// Check whether C30EA3 actually played a sound.
	beq done_playing_sound
	// Wait until APU responds because we're about to do a command.
	// This is because C30EA3 doesn't wait for acknowledgement.
	ldx.w #$1024   // timeout
	// NOTE: A is already set to $21 if zero flag was clear.
sound_wait_loop:
	cmp.l $002140
	beq done_playing_sound
	dex
	bne sound_wait_loop
done_playing_sound:

	// Pressing right?
	lda.b $0B
	lsr
	bcs set_to_off
	
	// Setting to "on".
	lda.w config_multiplayer
	bit.b #$10
	beq no_change
	and.b #$EF
	sta.w config_multiplayer
	bra set_volume
	
set_to_off:
	// Setting to "off".
	lda.w config_multiplayer
	bit.b #$10
	bne no_change
	ora.b #$10
	sta.w config_multiplayer
	// fall through

set_volume:
	// Set music volume to what the engine wanted.
	// NOTE: This command itself will overwrite soundvar_unused, so restore after.
	stz.w soundvar_newcmd + 3
	lda.w soundvar_unused
	pha   // save
	sta.w soundvar_newcmd + 2
	lda.b #$01
	sta.w soundvar_newcmd + 1
	lda.b #$81
	sta.w soundvar_newcmd + 0
	jsl do_spc_command
	// Restore soundvar_unused.
	pla
	sta.w soundvar_unused
	
	// Redraw On/Off text and return.
	jmp draw_music_on_off

no_change:
	rts
}


// Hooks the call to initially draw the Reset and Memory options.
function draw_music_on_off_hook {
	// Do our custom drawing.
	jsr draw_music_on_off
	// Go to the drawing routine whose call we overwrote.
	jmp.w $C33CB0
}


// Draw the "On" and "Off" options for Music according to the config.
function draw_music_on_off {
	// Are we muting music?
	lda.w config_multiplayer
	lsr
	// $20=normal, $28=gray.  Mute -> 28, so use the first one for On.
	and.b #$08
	ora.b #$20
	sta.b $29
	pha
	// Draw "On" with this palette.
	ldy.w #on_text
	jsr.w $C302F9
	// Draw "Off" with the opposite palette.
	pla
	eor.b #$08
	sta.b $29
	ldy.w #off_text
	// Tail call (so jmp instead of jsr).
	jmp.w $C302F9
	
on_text:
	dw $3CA5
	db "On",0
off_text:
	dw $3CB5
	db "Off",0
}


// Hooks the music load routine.
function music_load_hook {
	// We take over after the game has decided to actually load the song.
	// Deleted code.
	sep #$20
	// Get volume parameter.
	lda.b dp_soundvar_newcmd + 2
	// Save the volume that the game engine wanted to use.
	sta.b dp_soundvar_unused
	// Decide replacement volume.
	jsr calculate_volume
	sta.b dp_soundvar_newcmd + 2
	// The second instruction we replaced was "lda.b dp_soundvar_newcmd + 2".
	// We already have that in A.
	jml $C501A8
}


// Hooks the generic SPC interrupt routine.
function spc_interrupt_hook {
	// Deleted code.
	sep #$20
	// Get the command being done.
	lda.b dp_soundvar_newcmd + 0
	// 80 = set both the music and SFX volumes.
	cmp.b #$80
	beq command_80
	// 81 = set music volume.
	cmp.b #$81
	bne return
	
	// Command 81: set music volume.
	// Save the volume that the game engine wanted to use.
	lda.b dp_soundvar_newcmd + 2
	sta.b dp_soundvar_unused
	// Replace the volume value.
	jsr calculate_volume
	sta.b dp_soundvar_newcmd + 2
	bra return
	
command_80:
	// Command 80: set both music and sound effect volume.
	// Save the volume that the game engine wanted to use.
	lda.b dp_soundvar_newcmd + 2
	sta.b dp_soundvar_unused
	// HACK: Recurse to do command 82 (set sound effect volume) instead.
	// We ignore 82 in this code, so recursing is fine.
	lda.b #$82
	sta.b dp_soundvar_newcmd + 0
	jsl do_spc_command
	// Now do command 81 (set music volume) with the adjusted volume.
	lda.b #$81
	sta.b dp_soundvar_newcmd + 0
	lda.b dp_soundvar_unused
	jsr calculate_volume
	sta.b dp_soundvar_newcmd + 2
	// fall through
	
return:
	// Deleted code.
	lda.b dp_soundvar_newcmd + 3
	// Resume routine.
	jml $C505AA
}


// A = value 0...255 to scale based on current scale setting.
// Returns scaled A.
function calculate_volume {
	// Is music mute enabled?
	pha
	lda.w config_multiplayer
	bit.b #$10
	bne muted
	pla
	rts
muted:
	pla
	lda.b #0
	rts
}


// Called during reset.
function reset_hook {
	// Clear the multiplayer config, including the new music flag.
	// We need to do this because config_multiplayer doesn't get cleared
	// until the file select screen, which is too late for controlling
	// the music status.
	stz.w config_multiplayer
	// We might as well fix a bug in the original game: config_interface2
	// is being read at C3A436 before it has been initialized.
	stz.w config_interface2
	// For safety, set the last attempted volume to 0.
	stz.w soundvar_unused
	// Resume boot sequence.
	jmp.w $C30006
}


// When the player reorders characters in the menu, the routine at $C324F8
// swaps the corresponding bits of config_multiplayer so that controls remain
// the same per character.  This routine doesn't know that we've added a new
// bit to this byte and blows it away.
function party_reorder_hook {
	// We are JMPed to with A = new intended value of config_multiplayer.
	// Use a stack byte as temporary memory for this calculation.
	pha
	lda.w config_multiplayer
	and.b #$F0
	ora 1,s
	sta.w config_multiplayer
	// Remove value from stack (we don't need to restore A).
	pla
	// Returns from the function that JMPed to us.
	rts
}


warnpc($C3FB00)


// SPC700 patch: Fix volume being maximized when unpausing a song.
// The way the AKAO engine is coded, when resuming a song, the music
// volume will be set to max, ignoring the parameter from the 65816.
// The patch is to modify these instructions:
//
//         MOV   $8B,#$81      ; Interrupt command $81
//         MOV   $8C,#$10      ; Parameter Volume: #$10
// HERE -> MOV   $8D,#$FF      ; Parameter Envelope: #$FF
// HERE -> MOV   $A6,#$20      ; Master Volume high = #$20
//         JMP   L0C6A         ; $81: Set master volume to yy, w/ envelope xx
//
// However, we need 8 bytes, and only have 6.  I optimized the first
// part of TransferPausedSongBack to free up 3 more bytes for the
// patch to the A6 writes.
//
// The comments' above labeling of "volume" and "envelope" are backward.
// 8D already contains the desired volume from the "play music" command.
// The NewSong routine copied 8D to A6 already.
reorg(akao_engine + $1095 - akao_engine_base)
architecture spc700   // We're writing SPC700 code
base $1095
function akao_patch {
	// Save 3 bytes here by optimizing.
	// * A was reloaded with zero before writing to $92, so moving the write
	//   to $92 allows saving an extra loading of A with zero.  2 bytes.
	// * Y gets loaded with zero.  By loading from A instead of an immediate,
	//   we save 1 byte.
	str $C6=#$FF               // MOV   $C6,#$FF      ; Paused Song = #$FF
	lda #$00                   // MOV   A,#$00        ; Zero A
	sta.b $90                  // MOV   $90,A         ; #$00
	sta.b $92                  // MOV   $92,A         ; #$00
	tay                        // MOV   Y,A           ; Zero Y
	lda #$F6                   // MOV   A,#$F6        ; #$F6
	sta.b $91                  // MOV   $91,A         ; Point to $F600, Current Voice Data
	lda #$FA                   // MOV   A,#$FA        ; #$FA
	sta.b $93                  // MOV   $93,A         ; Point to $FA00, Paused Voice Data
	// The rest of the code until the end is the same.
loop1:
	lda ($92),y                // MOV   A,($92)+Y     ; From $FA00+Y, Paused
	sta ($90),y                // MOV   ($90)+Y,A     ; To F600+Y, Current
	iny                        // INC   Y             ; Increment Y
	bne loop1                  // BNE   loop1         ; Loop for $100 bytes
	inc.b $91                  // INC   $91           ; Point to next $100
	inc.b $93                  // INC   $93           ; Point to next $100
	cmp $91=#$FA               // CMP   $91,#$FA      ; Have we reached $FA00
	bne loop1                  // BNE   loop1         ; Loop for $400 bytes
	dew $92                    // DECW  $92           ; Point to $FDFF
	ldy #$80                   // MOV   Y,#$80        ; Y = #$80, dp0 size
loop2:
	lda ($92),y                // MOV   A,($92)+Y     ; From Saved dp 0
	sta $FFFF,y                // MOV   $FFFF+Y,A     ; To dp 0
	bne --y=loop2              // DBNZ  Y,loop2       ; Decrease Y, loop unless zero
	inc.b $93                  // INC   $93           ; Point to $FEFF
	ldy #$A0                   // MOV   Y,#$A0        ; Y = #$A0, dp1 size
loop3:
	lda ($92),y                // MOV   A,($92)+Y     ; From Saved dp 1
	sta $00FF,y                // MOV   $00FF+Y,A     ; To dp 1
	bne --y=loop3              // DBNZ  Y,loop3       ; Decrease Y, loop unless zero
	
	// Now the actual part of the hack that matters.
	// $A6 is set by the caller function to the desired volume level.
	// $8D also has this value, containing the port value from the 65816.
	// $A6 is what the sound engine will use as the current volume.
	//
	// The original code set A6 to $20 for a low volume, but faked a
	// 65816 request to ramp up volume to maximum over time (81 packet).
	// But we don't want the volume to go to maximum necessarily.
	//
	// Instead, if the desired volume is less than $20, set $A6 to the
	// desired volume.  If not, allow the ramp-up as before.  $8D is
	// already the desired volume, so we save 3 bytes there.
	str $8B=#$81               // MOV   $8B,#$81      ; Interrupt command $81
	str $8C=#$10               // MOV   $8C,#$10      ; Parameter Volume: #$10
	// Custom code
	cmp $A6=#$20               // CMP   $A6,#$20      ; Is the desired volume < #$20?
	bcc skip_A6_write          // BCC   skip_A6_write ; If so, skip this.
	str $A6=#$20               // MOV   $A6,#$20      ; Master Volume high = #$20
skip_A6_write:
	jmp $0C6A                  // JMP   L0C6A         ; $81: Set master volume to yy, w/ envelope xx
}
architecture wdc65816
warnpc(akao_engine + $10DF - akao_engine_base)
