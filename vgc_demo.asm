;******************************************************************
; 6502 BBC Micro Compressed VGM (VGC) Music Player
; By Simon Morris
; https://github.com/simondotm/vgm-player-bbc
; https://github.com/simondotm/vgm-packer
;******************************************************************

; Exact time for a 50Hz frame less latch load time
FramePeriod = 312*64-2
; Exact time so that the FX draw function call starts at VCC=0,HCC=0.
TimerValue = FramePeriod - 2*64;32*64 - 2*64


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

INCLUDE "lib/vgcplayer.asm"


ALIGN 256
.main
{
    ; initialize the vgm player with a vgc data stream
    lda #hi(vgm_stream_buffers)
    ldx #lo(vgm_data)
    ldy #hi(vgm_data)
    sec ; set carry to enable looping
    jsr vgm_init

    sei
	\\ Wait for vsync
	{
		lda #2
        sta &fe4d
		.vsync1
		bit &FE4D
		beq vsync1
	}
	; Roughly synced to VSync

    ; Now fine tune by waiting just less than one frame
    ; and check if VSync has fired. Repeat until it hasn't.
    ; One frame = 312*128 = 39936 cycles
	{
		.syncloop
		STA &FE4D       ; 6
		LDX #209        ; 2
		.outerloop
		LDY #37         ; 2
		.innerloop
		DEY             ; 2
		BNE innerloop   ; 3/2 (innerloop = 5*37+2-1 = 186)
		DEX             ; 2
		BNE outerloop   ; 3/2 (outerloop = (186+2+3)*209+2-1 = 39920)
		BIT &FE4D       ; 6
		BNE syncloop    ; 3 (total = 39920+6+6+3 = 39935, one cycle less than a frame!)
		IF HI(syncloop) <> HI(P%)
		ERROR "This loop must execute within the same page"
		ENDIF
	}
    ; We are synced precisely with VSync!

	\\ Set up Timer1 to start at the first scanline
    LDA #LO(TimerValue):STA &FE44		; 8c
    LDA #HI(TimerValue):STA &FE45		; 8c

  	; Latch T1 to interupt exactly every 50Hz frame
	LDA #LO(FramePeriod):STA &FE46		; 8c
	LDA #HI(FramePeriod):STA &FE47		; 8c

    ; loop & update
.loop

; set to false to playback at full speed for performance testing
IF TRUE 
    ; vsync
    lda #&40
    .vsync1
    bit &FE4D
    beq vsync1
    sta &FE4D
ENDIF

    ;ldy#10:.loop0 ldx#0:.loop1 nop:nop:dex:bne loop1:dey:bne loop0

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
;INCBIN "music/vgc/axelf.vgc"
;INCBIN "music/vgc/bbcapple.vgc"
;INCBIN "music/vgc/nd-ui.vgc"
;INCBIN "music/vgc/outruneu.vgc"
;INCBIN "music/vgc/ym_009.vgc"
;INCBIN "music/vgc/test_bbc.vgc"
;INCBIN "music/vgc/acid_demo.vgc"
INCBIN "music/vgc/beeb-demo.bbc.vgc"



.end

PRINT ~vgm_data


SAVE "Main", start, end, main

