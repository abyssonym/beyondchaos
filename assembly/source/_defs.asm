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

// --- USEFUL RAM ADDRESSES ---
constant frame_counter                                      = $7E021E
constant rngseed_encounter                                  = $7E1FA3
constant rngseed_event                                      = $7E1F6D

// --- USEFUL ROM ADDRESSES ---
constant rng_table                                          = $C0FD00
constant rom_item_data                                      = $D85000


// --- MEMORY MAP - BANK FF ---
constant bank_FF_start                                      = $FF0000

// Allocations of free space to various hacks.
// Hacks that only modify existing code don't need entries here.
constant enable_esper_magic_start                           = $C3F091
constant enable_esper_magic_size                            = $000A
constant enable_xmagic_menu_start                           = $C3F09B
constant enable_xmagic_menu_size                            = $0020
constant auto_equip_start                                   = $C3F1A0
constant auto_equip_size                                    = $1000
constant natmag_learn_start                                 = $F0084B
constant natmag_learn_size                                  = $00A0 + (2 * 16 * 12)

// For future use
//constant enable_xmagic_menu_start                           = bank_FF_start
//constant enable_xmagic_menu_size                            = $0020
//constant natmag_learn_start                                 = enable_xmagic_menu_start + enable_xmagic_menu_size
//constant natmag_learn_size                                  = $00A0 + (2 * 16 * 12)
