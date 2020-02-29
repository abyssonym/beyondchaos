// HiROM org macro
macro reorg n
	org {n} & $3FFFFF
	base {n}
endmacro

// Warn if the current address is greater than the specified value.
macro warnpc n
	{#}:
	if {#} > ({n})
		warning "warnpc assertion failure"
	endif
endmacro

// Warn if the current address is not the specified value.
macro exactpc n
	{#}:
	if {#} != ({n})
		warning "exactpc assertion failure"
	endif
endmacro

// Allows saving the current location and seeking somewhere else.
define savepc push origin, base
define loadpc pull base, origin

// Warn if the expression is false.
macro static_assert n
	if ({n}) == 0
		warning "static assertion failure"
	endif
endmacro


// Start with the requested blank file.
{reorg $C00000}
fill $400000, {filler}

// Where to write export table.
macro start_exports
	org $400000
	base 0
endmacro

// Write an export.
macro export name, value
	db {name}
	db 0
	dd {value}
endmacro


// --- MEMORY MAP - BANK FF ---
eval bank_FF_start                                          $FF0000

eval enable_xmagic_menu_start                               {bank_FF_start}
eval enable_xmagic_menu_size                                $0020
eval natmag_learn_start                                     {enable_xmagic_menu_start} + {enable_xmagic_menu_size}
eval natmag_learn_size                                      $00A0 + (2 * 16 * 12)
