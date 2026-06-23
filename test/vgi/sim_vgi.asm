\ ******************************************************************
\ AI-GENERATED CODE
\ ------------------------------------------------------------------
\ sim_vgi.asm - standalone build of the VGI player for byte-exact /
\ cycle measurement in py65. Generated with the assistance of an AI
\ model: Claude Opus 4.8 (claude-opus-4-8).
\
\ Build with -D VGI_UNROLL=0 (looped) or 1 (unrolled). measure.py
\ builds this and sim_vgc.asm, plays the SAME tune through both in a 6502
\ simulator, reconstructs the SN76489 register state each frame and asserts
\ the two players drive the chip identically, then reports the per-frame cost.
\ ******************************************************************
.zp_start
ORG &70
GUARD &9f
INCLUDE "../../lib/vgiplayer.h.asm"
.zp_end

ORG &1100
GUARD &7c00
.start
INCLUDE "../../lib/vgiplayer.asm"

.vgm_buffer_start
ALIGN 256
.vgm_stream_buffers
  SKIP 11*256          ; 11 x 256-byte ring windows (2.75 KB)
.vgm_buffer_end
.vgm_data
INCBIN "../../music/vgi/acid_demo.vgi"
.end
SAVE "Vgi", start, end, start
