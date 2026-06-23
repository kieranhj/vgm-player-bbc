\ ******************************************************************
\ AI-GENERATED CODE
\ ------------------------------------------------------------------
\ sim.asm - standalone build of the VGC player for byte-exact /
\ cycle measurement in py65. Generated with the assistance of an AI
\ model: Claude Opus 4.8 (claude-opus-4-8).
\
\ -D OPT=0 builds the original lib/vgcplayer.asm.
\ -D OPT=1 builds the optimised lib/vgcplayer_opt.asm.
\ measure.py assembles both, plays a tune through once and asserts the
\ SN76489 write stream (&FE4F) is identical, then reports the speedup.
\ ******************************************************************
.zp_start
ORG &70
GUARD &9f
INCLUDE "../../lib/vgcplayer_config.h.asm"
INCLUDE "../../lib/vgcplayer.h.asm"
.zp_end

ORG &1100
GUARD &7c00
.start
IF OPT
INCLUDE "../../lib/vgcplayer_opt.asm"
ELSE
INCLUDE "../../lib/vgcplayer.asm"
ENDIF

.vgm_buffer_start
ALIGN 256
.vgm_stream_buffers
  SKIP 2048
.vgm_buffer_end
.vgm_data
INCBIN "../../music/vgc/acid_demo.vgc"
.end
SAVE "Vgc", start, end, start
