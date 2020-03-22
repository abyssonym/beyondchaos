// HiROM org macro
macro reorg(n) {
	origin {n} & $3FFFFF
	base {n}
}

// Warn if the current address is greater than the specified value.
macro warnpc(n) {
	{#}:
	if {#} > ({n}) {
		warning "warnpc assertion failure"
	}
}

// Warn if the current address is not the specified value.
macro exactpc(n) {
	{#}:
	if {#} != ({n}) {
		warning "exactpc assertion failure"
	}
}

// Allows saving the current location and seeking somewhere else.
macro savepc() {
	push origin, base
}
macro loadpc() {
	pull base, origin
}

// Warn if the expression is false.
macro static_assert(n) {
	if ({n}) == 0 {
		error "static assertion failure"
	}
}

// Switch to FF6 menu font character mapping.
macro map_ff6_menu() {
	map 'A', $80, 26
	map 'a', $9A, 26
	map '0', $B4, 10
	map '!', $BE
	map '?', $BF
	map '/', $C0
	map ':', $C1
	map '-', $C4
	map '.', $C5
	map ',', $C6
	map $3B, $C8  // ;
	map '#', $C9
	map '+', $CA
	map '(', $CB
	map ')', $CC
	map '%', $CD
	map '~', $CE
	map ' ', $FF
}

// Revert to UTF-8 (pass-through) mapping.
macro map_utf8() {
	map 0, 0, 256
}


// Start with the requested blank file.
reorg($C00000)
fill $400000, {filler}

// Where to write export table.
macro start_exports() {
	origin $400000
	base 0
	map_utf8()
}

// Write an export.
macro export(name, value) {
	db {name}
	db 0
	dd {value}
}


// --- HARDWARE REGISTERS ---
constant reg_mpyl                                           = $002134
constant reg_mpym                                           = $002135
constant reg_mpyh                                           = $002136
constant reg_wmaddl                                         = $002181
constant reg_wmaddm                                         = $002182
constant reg_wmaddh                                         = $002183
constant reg_joyser0                                        = $004016
constant reg_joyser1                                        = $004017
constant reg_nmitimen                                       = $004200
constant reg_wrio                                           = $004201
constant reg_wrmpya                                         = $004202
constant reg_wrmpyb                                         = $004203
constant reg_wrdivl                                         = $004204
constant reg_wrdivh                                         = $004205
constant reg_wrdivb                                         = $004206
constant reg_htimel                                         = $004207
constant reg_htimeh                                         = $004208
constant reg_vtimel                                         = $004209
constant reg_vtimeh                                         = $00420A
constant reg_mdmaen                                         = $00420B
constant reg_hdmaen                                         = $00420C
constant reg_memsel                                         = $00420D
constant reg_rdnmi                                          = $004210
constant reg_timeup                                         = $004211
constant reg_hvbjoy                                         = $004212
constant reg_rdio                                           = $004213
constant reg_rddivl                                         = $004214
constant reg_rddivh                                         = $004215
constant reg_rdmpyl                                         = $004216
constant reg_rdmpyh                                         = $004217
constant reg_joy1l                                          = $004218
constant reg_joy1h                                          = $004219
constant reg_joy2l                                          = $00421A
constant reg_joy2h                                          = $00421B
constant reg_joy3l                                          = $00421C
constant reg_joy3h                                          = $00421D
constant reg_joy4l                                          = $00421E
constant reg_joy4h                                          = $00421F

// --- USEFUL RAM ADDRESSES ---
constant frame_counter                                      = $7E021E
constant direct_soundvar                                    = $7E1300
constant soundvar_newcmd                                    = $7E1300
constant soundvar_currentcmd                                = $7E1304
constant soundvar_previouscmd                               = $7E1308
constant soundvar_unused                                    = $7E130C
constant config_battle                                      = $7E1D4D
constant config_interface                                   = $7E1D4E
constant config_multiplayer                                 = $7E1D4F
constant config_buttons                                     = $7E1D50
constant config_interface2                                  = $7E1D54
constant rngseed_encounter                                  = $7E1FA3
constant rngseed_event                                      = $7E1F6D

// --- DIRECT PAGE OFFSETS ---
constant dp_soundvar_newcmd                                 = soundvar_newcmd - direct_soundvar
constant dp_soundvar_currentcmd                             = soundvar_currentcmd - direct_soundvar
constant dp_soundvar_previouscmd                            = soundvar_previouscmd - direct_soundvar
constant dp_soundvar_unused                                 = soundvar_unused - direct_soundvar

// --- USEFUL ROM ADDRESSES ---
constant rng_table                                          = $C0FD00
constant do_spc_command                                     = $C50004
constant rom_item_data                                      = $D85000

// --- MEMORY MAP - BANK C3 (unused space from original) ---
constant bank_C3_start                                      = $C3F091
constant enable_esper_magic_start                           = $C3F091
constant enable_esper_magic_size                            = $000A
constant enable_xmagic_menu_start                           = $C3F09B
constant enable_xmagic_menu_size                            = $0020
constant auto_equip_start                                   = $C3F1A0
constant auto_equip_size                                    = $1000

// --- MEMORY MAP - BANK F0 ---
constant bank_F0_start                                      = $F00000
constant natmag_learn_start                                 = $F0084B
constant natmag_learn_size                                  = $00A0 + (2 * 16 * 12)

