<!--
AI-GENERATED DOCUMENT
This document was written with the assistance of an AI model:
Claude Opus 4.8 (claude-opus-4-8). It describes lib/vgcplayer_opt.asm,
which was produced with the same assistance.
-->

# Optimised VGC player (`lib/vgcplayer_opt.asm`)

`lib/vgcplayer_opt.asm` is a drop-in faster variant of the standard VGC player
(`lib/vgcplayer.asm`). It plays exactly the same `.vgc` files, produces
**byte-identical** SN76489 output, uses the **same 8 zero-page vars and the same
2 KB workspace** — and is **~1.3× faster per frame** for *less* code.

It is a line-for-line derivative of Simon Morris's `vgcplayer.asm`; every routine
is unchanged except the LZ decode path. Huffman is **not** supported by this
variant (assemble with `ENABLE_HUFFMAN = FALSE`).

## The problem it fixes: the per-byte context swap

The standard player shares one compact ~200-byte LZ decoder across all 8 register
streams. Because the decoder uses fixed zero-page locations and self-modified
window pointers, switching to a stream means **copying that stream's whole 8-byte
LZ context into zero page and copying it back** — *on every decoded byte*:

- load 8 bytes from `vgm_streams[x]` into `zp_stream_src`, `zp_literal_cnt`,
  `zp_match_cnt` and the two window SMC operands; then
- decode one byte; then
- store those 8 bytes back to `vgm_streams[x]`.

Measured in a 6502 simulator, that bookkeeping is the single biggest cost in the
frame (~38% of cycles on the original) — far more than the actual decompression.
On busy frames (many decoded bytes) it is also the main driver of the worst-case
spikes.

## What the optimised player does instead

Keep each stream's LZ context **resident** in `vgm_streams[x]` and decode it in
place — no per-byte swap:

- **X holds the stream index for the whole decode** and is never clobbered by the
  decoder. `vgm_get_register_data` stashes it once in `vgm_temp` so
  `vgm_update_register1` can restore it after `sn_write` (which does clobber X).
- **Literal/match counts** are read and written `abs,X` directly in
  `vgm_streams[x]` (no copy to/from zero page).
- **The window buffer** is addressed `abs,Y`; its page (`hi`) byte is
  self-modified **once per decode** in `vgm_get_register_data`, and the
  read/write indices are held `abs,X` and `inc`-ed in place. The window
  fetch/store are **inlined** (no `jsr`/`rts` per byte).
- **Only the stream read pointer** is paged into `zp_stream_src` for the indirect
  byte fetch, and written back once at the end of the call.
- `lz_fetch_count` was adjusted to **preserve X** (it returns its high byte in
  `zp_temp+1` rather than in X, since X now holds the live stream index).

The per-stream context shrinks from 10 bytes to 8 (the two Huffman bytes are
gone), so the resident `vgm_streams` table is still 8×8 = 64 bytes.

## Measured result

Simulated in py65 over `music/vgc/acid_demo.vgc` (9603 frames; see
`test/vgc_opt/`), per-frame cycle cost @ 2 MHz:

| | mean | p99 | max | total |
|---|--:|--:|--:|--:|
| original  | 1788 | 4022 | 5321 | 17166292 |
| optimised | **1353** | **2964** | **4507** | 12997284 |
| speedup   | **1.32×** | 1.36× | 1.18× | 1.32× |

Code size (BeebAsm, `ENABLE_HUFFMAN = FALSE`, `ENABLE_VGM_FX = TRUE`): total VGC
player **757 → 691 bytes**. So it is faster, smaller, and uses **+0 RAM**.

The biggest remaining cost is the ~per-decode window-page self-mod plus the
pointer load/save; removing it entirely would require unrolling the decoder per
stream (8 hard-wired copies, ~1.5 KB of code) — a separate, larger trade.

## Using it

Identical to the standard player — just include the optimised file:

```
INCLUDE "lib/vgcplayer_config.h.asm"   ; must have ENABLE_HUFFMAN = FALSE
INCLUDE "lib/vgcplayer.h.asm"          ; the SAME shared header as vgcplayer.asm
...
INCLUDE "lib/vgcplayer_opt.asm"        ; instead of lib/vgcplayer.asm
```

The user API is unchanged: `vgm_init()`, `vgm_update()`, `sn_reset()`,
`sn_write()`. See `vgc_opt_demo.asm` for a complete example (it adds a
raster-timing band around `vgm_update` so the per-frame cost is visible).

## Verifying correctness

`test/vgc_opt/` builds both players, plays a tune through once in a 6502
simulator, and asserts the SN76489 write stream is identical, then reports the
speedup:

```
cd test/vgc_opt
pip install py65 numpy        # one-off
python measure.py             # set $BEEBASM if beebasm is not auto-found
```

A run prints `SN76489 output: IDENTICAL` and `RESULT: PASS` when the optimised
player matches the original byte-for-byte.
