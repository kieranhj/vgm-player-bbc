<!--
AI-GENERATED DOCUMENT
This document was written with the assistance of an AI model:
Claude Opus 4.8 (claude-opus-4-8). It describes lib/vgiplayer.asm,
which was produced with the same assistance.
-->

# Incremental VGI player (`lib/vgiplayer.asm`)

`lib/vgiplayer.asm` is a second VGM player that trades file size for a **low,
flat, bounded per-frame CPU cost**. It plays `.vgi` files (produced by
`vgipacker.py` in the [vgm-packer](https://github.com/simondotm/vgm-packer)
repo) and exposes the **same user API** as the VGC player —
`vgm_init` / `vgm_update` / `sn_reset` / `sn_write` — so it is a drop-in
alternative for code that already drives `lib/vgcplayer.asm`.

It builds for either of two file versions, and **v3 is the one to use**:

- `-D VGI_V3=0` plays `.vgi` **v2**: 11 register columns, an 11×256 workspace,
  files ~1.4× `.vgc`. Chosen over `.vgc` when the *worst-case* per-frame time
  matters more than size — a raster-budgeted demo that must never overrun.
- `-D VGI_V3=1` plays `.vgi` **v3**: 8 columns, because each channel's tone
  period is a byte index into a table the packer builds. Files are 21-29%
  smaller (roughly `.vgc`'s size), the workspace drops to 8×256 = 2 KB, and
  there are three fewer streams to decode — so it is **cheaper per frame than
  v2 and cheaper than `.vgc` too**, at both the mean and the worst frame. The
  format is documented in the packer repo (`docs/vgi-format.md`).

A build plays one version, not both: `vgm_init` checks the file's version byte
and refuses a mismatch (the player reports finished rather than decoding
noise).

## The problem it addresses: VGC's per-frame cost spikes

The VGC player runs **RLE then LZ4** per stream. That makes `.vgc` small, but
it makes the decode cost **bimodal**:

- most frames just decrement an RLE run counter — nearly free; while
- occasional frames have to refill several LZ4 tokens at once — expensive.

So the per-frame cost has a **long worst-case tail**: cheap most of the time,
with sharp spikes whenever several streams refill together. For a 50 Hz player
you must budget for the *spike*, not the average.

## What the VGI player does instead

`.vgi` drops the RLE layer entirely. Each of the **11 register columns** (one
per SN76489 register) is its own tiny byte-aligned LZSS over a 256-byte ring
window, and the player decodes **exactly one byte from each stream per frame**.
A long match or run is emitted **one byte at a time across successive frames**,
so a single frame never decodes more than the *start* of one token per stream.
The per-frame cost is therefore **bounded independently of match/run length** —
there is no operation whose cost scales with the data. (The format itself,
including the v2 RUN token and the 3-byte token-start bound, is documented in
the packer repo: `docs/vgi-format.md`.)

The noise column keeps the `0x0f` "skip" marker so the player only rewrites the
noise register when it actually changes (writing it restarts the chip's LFSR) —
the one place VGI, like VGC, deliberately skips a write.

## Byte-exact with the VGC player

`test/vgi/measure.py` builds the VGC player and **all four** VGI builds
(looped/unrolled × v2/v3), runs each through a py65 6502 simulator over the same
tune (`acid_demo`), reconstructs the SN76489 register state from the `&FE4F`
writes each frame, and asserts every player drives the chip **identically**.
Over all **9602 frames** of `acid_demo`:

```
VGI v2 looped    SN76489 state IDENTICAL over all 9602 frames
VGI v2 unrolled  SN76489 state IDENTICAL over all 9602 frames
VGI v3 looped    SN76489 state IDENTICAL over all 9602 frames
VGI v3 unrolled  SN76489 state IDENTICAL over all 9602 frames
```

The v3 rows are the ones that matter for the format change: those builds read a
**different file** — 8 indexed columns and a period table instead of 11 raw
columns — and still put the same bytes into the chip.

(The raw write *streams* differ in length — VGC writes only the registers its
RLE says changed, VGI writes all 11 registers every frame — so the test compares
reconstructed chip *state*, which is the playback-equivalence that matters.)

## Measured per-frame cost

Same harness, per-frame cost **including the SN76489 writes**, `acid_demo`
(9602 frames, cycles @ 2 MHz):

| player | min | mean | p99 | max |
|---|--:|--:|--:|--:|
| VGC (stock) | 294 | 1788 | 4022 | **5321** |
| VGI v2 looped | 1483 | 1572 | 2219 | **2677** |
| VGI v2 unrolled | 1052 | 1149 | 1863 | **2377** |
| VGI v3 looped | 1214 | 1277 | 1762 | **2125** |
| VGI v3 unrolled | 917 | **985** | 1511 | **1894** |

The shape is the whole point. VGC is cheap on average but spikes to **5321**
cycles (13% of a 50 Hz frame). Every VGI build sits in a tight band, even though
VGI re-writes all 11 registers every frame (which lifts its *floor* — that is
why VGI's minimum is higher). The unrolled build is faster across the board for
more code.

**v3 costs less than v2 everywhere**: −295 cycles at the mean and −552 at the
worst frame for the looped build, −164 and −483 for the unrolled one. Three
fewer per-stream state machines is the whole of it; the two table lookups that
replace them are an `absolute,Y` load each (`sn_write` clobbers X but never Y,
so the index survives the pair of writes it feeds).

And **VGI v3 unrolled beats the stock VGC player at both ends** — mean 985
against 1788, worst frame 1894 against 5321 — on a file about the same size.
That was not true of v2, which bought its bounded worst case with a higher
mean.

> Prior findings (the motivation). A wider study in the vgm-packer repo
> (`beeb/`, decode cost only, SN writes stubbed, 11-tune / 74052-frame corpus)
> shows the same story at corpus scale: the VGI players occupy a narrow band
> (looped median ~1158, max ~2770; unrolled median ~673, max ~2404) while the
> VGC players are spiky (original median ~1557 spiking to ~5396; the
> resident-context "VGC-opt" median ~1143 spiking to ~4624). VGI's worst case is
> ~1.7–1.9× lower than VGC's there too. Those numbers are decode-only on a
> standalone prototype, so they are not directly comparable to the
> incl.-sound table above — they are cited as the design rationale, not as this
> player's spec.

## Code & RAM footprint

Measured from these builds (`vgm_start`..`vgm_end`, i.e. code + resident state;
`ENABLE_HUFFMAN = FALSE`):

| player | code + state | decode buffer | zero page |
|---|--:|--:|--:|
| VGC (stock) | 555 | 2048 (8×256) | 8 |
| VGI v2 looped | 559 | 2816 (11×256) | 4 |
| VGI v2 unrolled | 1064 | 2816 (11×256) | 4 |
| VGI v3 looped | 663 | **2048 (8×256)** | 4 |
| VGI v3 unrolled | **1018** | **2048 (8×256)** | 4 |

So the looped VGI player is about the same code size as the stock VGC player and
uses *fewer* zero-page bytes. v3 removes three ring pages, 768 bytes, and the
tune it plays is ~25% smaller as well; the period table it adds lives in the
file, not in the player. The looped v3 build costs 104 bytes more code for the
table expansion, while the **unrolled v3 build is 46 bytes SMALLER** than
unrolled v2 — three fewer streams to inline more than pays for the lookups.

## Build flags

`lib/vgiplayer.asm` needs **two** `-D` defines on **every** build, exactly like
`OPT` in `test/vgc_opt`. `VGI_V3` picks the file version (see the top of this
document); `VGI_UNROLL` picks the decoder shape:

- `-D VGI_UNROLL=0` — compact looped decoder (**default**). One decode
  subroutine driven by an X stream index.
- `-D VGI_UNROLL=1` — per-stream unrolled decoder. The common copy path is
  inlined with absolute state and no per-byte `jsr`/loop overhead; only the rare
  new-token parse and literal fetch use X. Both builds are byte-exact and both
  honour the buffer page passed to `vgm_init` (the ring page is held in a
  zero-page pointer and advanced per stream, so neither needs a fixed buffer
  address).

All four combinations are byte-exact against the VGC player, and
`test/vgi/measure.py` builds and checks all four.

## Using it

```
INCLUDE "lib/vgiplayer.h.asm"        ; declares 4 zero page bytes (see vgi_demo.asm)
...
INCLUDE "lib/vgiplayer.asm"          ; the player (needs -D VGI_UNROLL and -D VGI_V3)
```

API (identical to the VGC player):

- `vgm_init` — `A` = HI byte of a page-aligned `VGI_NUM_STREAMS`×256 workspace
  (**2 KB for a v3 build**, 2.75 KB for v2); `X`/`Y` = LO/HI of the `.vgi` data;
  `C=1` to loop. It also checks the file's version byte and refuses a file this
  build cannot play.
- `vgm_update` — call at 50 Hz; returns zero while playing, non-zero when the
  tune has finished (a final update silences the chip, mirroring the VGC
  player's end-of-stream behaviour).
- `sn_reset` / `sn_write` — byte-identical to `lib/vgcplayer.asm`.

See `vgi_demo.asm` for a complete bootable example (it brackets `vgm_update`
with palette writes so the per-frame cost is visible as a raster band):

```
beebasm -i vgi_demo.asm -D VGI_UNROLL=0 -D VGI_V3=1 -do vgi_demo.ssd -boot Main -title VGIPLAY
```

## Verifying correctness

```
cd test/vgi
pip install py65 numpy        # one-off
python measure.py             # set $BEEBASM if beebasm is not auto-found
```

It prints `SN76489 state IDENTICAL` for all four VGI builds and `RESULT: PASS`
when they match the stock VGC player frame-for-frame. It needs both `.vgi` files
of the test tune: `music/vgi/acid_demo.vgi` (v2) and `music/vgi/acid_demo.v3.vgi`
(v3), packed by `vgipacker.py` with and without `--v3`.
