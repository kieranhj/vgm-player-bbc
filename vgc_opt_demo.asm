;******************************************************************
; AI-GENERATED CODE
;------------------------------------------------------------------
; vgc_opt_demo.asm - demo for the optimised VGC player
; (lib/vgcplayer_opt.asm). Generated with the assistance of an AI
; model: Claude Opus 4.8 (claude-opus-4-8).
;
; This is the standard vgc_demo.asm wired to the optimised player.
; The only differences from vgc_demo.asm are this banner, the player
; INCLUDE below, and the tune. Each frame raises the screen colour
; (palette reg &FE21) just before vgm_update and drops it just after,
; so the on-screen band height = the player's per-frame CPU cost - the
; same raster-timing trick used to compare players visually.
;******************************************************************


; Allocate vars in ZP
.zp_start
ORG &70
GUARD &8f


;----------------------------------------------------------------------------------------------------------
; Common code headers
;----------------------------------------------------------------------------------------------------------
; Include common code headers here - these can declare ZP vars from the pool using SKIP...

INCLUDE "lib/vgcplayer_config.h.asm"
INCLUDE "lib/vgcplayer.h.asm"


.zp_end


\ ******************************************************************
\ *	Utility code - always memory resident
\ ******************************************************************

ORG &3000
GUARD &7c00

.start

;----------------------------


;-------------------------------------------
; main
;-------------------------------------------




; code routines

; NOTE: this is the only functional change from vgc_demo.asm - it pulls in the
; optimised player (resident LZ context) instead of lib/vgcplayer.asm.
INCLUDE "lib/vgcplayer_opt.asm"


ALIGN 256
.main
{
    ; initialize the vgm player with a vgc data stream
    lda #hi(vgm_stream_buffers)
    ldx #lo(vgm_data)
    ldy #hi(vgm_data)
    sec ; set carry to enable looping
    jsr vgm_init

    ; loop & update
    sei
.loop

; set to false to playback at full speed for performance testing
IF TRUE
    ; vsync
    lda #2
    .vsync1
    bit &FE4D
    beq vsync1
    sta &FE4D
ENDIF


    ;ldy#10:.loop0 ldx#0:.loop1 nop:nop:dex:bne loop1:dey:bne loop0

    ; raster-timing band: colour up before vgm_update, back to black after.
    ; The visible band height is the optimised player's per-frame CPU cost.
    lda #&03:sta&fe21
    jsr vgm_update
    pha
    lda #&07:sta&fe21
    pla
    beq loop
    cli
    rts
}




.vgm_buffer_start

; reserve space for the vgm decode buffers (8x256 = 2Kb)
ALIGN 256
.vgm_stream_buffers
    skip 256
    skip 256
    skip 256
    skip 256
    skip 256
    skip 256
    skip 256
    skip 256


.vgm_buffer_end

; include your tune of choice here, some samples provided....
.vgm_data
;INCBIN "music/vgc/song_091.vgc"
;INCBIN "music/vgc/ym_009.vgc"
INCBIN "music/vgc/acid_demo.vgc"



.end

PRINT ~vgm_data


SAVE "Main", start, end, main
