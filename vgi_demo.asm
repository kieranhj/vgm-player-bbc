;******************************************************************
; AI-GENERATED CODE
;------------------------------------------------------------------
; vgi_demo.asm - demo for the incremental VGI player (lib/vgiplayer.asm).
; Generated with the assistance of an AI model: Claude Opus 4.8
; (claude-opus-4-8).
;
; This is the standard vgc_demo.asm wired to the VGI player. The only
; differences from vgc_demo.asm are this banner, the player INCLUDE, the
; 11x256 (2.75 KB) decode buffer, and the tune. Each frame raises the screen
; colour (palette reg &FE21) just before vgm_update and drops it just after,
; so the on-screen band height = the player's per-frame CPU cost. Because the
; VGI decoder is bounded, that band sits nearly still frame-to-frame - unlike
; the VGC player, whose band jitters as its RLE/LZ4 cost spikes.
;
; Build (the player needs the VGI_UNROLL flag on every build):
;   beebasm -i vgi_demo.asm -D VGI_UNROLL=0 -do vgi_demo.ssd -boot Main -title VGIPLAY
;   (use -D VGI_UNROLL=1 for the faster unrolled decoder)
;******************************************************************


; Allocate vars in ZP
.zp_start
ORG &70
GUARD &8f


;----------------------------------------------------------------------------------------------------------
; Common code headers
;----------------------------------------------------------------------------------------------------------
; Include common code headers here - these can declare ZP vars from the pool using SKIP...

INCLUDE "lib/vgiplayer.h.asm"


.zp_end


\ ******************************************************************
\ *	Utility code - always memory resident
\ ******************************************************************

ORG &3000
GUARD &7c00

.start

;-------------------------------------------
; main
;-------------------------------------------

; code routines

; NOTE: this is the only functional change from vgc_demo.asm - it pulls in the
; incremental VGI player (bounded per-frame cost) instead of lib/vgcplayer.asm.
INCLUDE "lib/vgiplayer.asm"


ALIGN 256
.main
{
    ; initialize the vgm player with a vgi data stream
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

    ; raster-timing band: colour up before vgm_update, back to black after.
    ; The visible band height is the VGI player's per-frame CPU cost.
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

; reserve space for the vgi decode buffers (11x256 = 2.75Kb)
ALIGN 256
.vgm_stream_buffers
    skip 11*256


.vgm_buffer_end

; include your tune of choice here, some samples provided....
.vgm_data
INCBIN "music/vgi/acid_demo.vgi"



.end

PRINT ~vgm_data


SAVE "Main", start, end, main
