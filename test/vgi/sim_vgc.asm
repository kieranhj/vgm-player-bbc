\ ******************************************************************
\ AI-GENERATED CODE
\ ------------------------------------------------------------------
\ sim_vgc.asm - standalone build of the stock VGC player over the SAME
\ tune as sim_vgi.asm, for the byte-exact comparison in measure.py.
\ Generated with the assistance of an AI model: Claude Opus 4.8
\ (claude-opus-4-8).
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
INCLUDE "../../lib/vgcplayer.asm"

.vgm_buffer_start
ALIGN 256
.vgm_stream_buffers
  SKIP 2048            ; 8 x 256-byte LZ4 windows
.vgm_buffer_end
.vgm_data
INCBIN "../../music/vgc/acid_demo.vgc"
.end
SAVE "Vgc", start, end, start
