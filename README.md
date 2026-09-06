# vgm-player-bbc

## VGM music players for the SN76489-based 6502 BBC Micro.

This project contains 6502 source code that will playback music using various file formats and playback techniques.

Despite the name of the project, the routines in this project do not play `.VGM` files "as-is" because VGM is quite a complex format that requires a lot of storage (for 8-bit computers anyway), so there are two principle ways the data is pre-processed into a more compact data format.

1. `VGMPLAY` Using [Vgm Converter](https://github.com/simondotm/vgm-converter) to create a compact `.RAW` or `.BIN` file version of the VGM data, which is then compressed using Exomizer.
2. `VGCPLAY` Using [Vgm Packer](https://github.com/simondotm/vgm-packer) to create a compressed `.VGC` file version of the VGM data, which is played back using a custom decoder.

For the second player, there are two types of playback engine:
1. Standard 50Hz playback
2. "Bass Enhanced" 50Hz playback with 6522 IRQ routines to synthesize squarewave frequencies below 122Hz that the 4Mhz SN76489 cannot normally reproduce

---

## `VGM` Player Usage

To create a compressed VGM file that will work with Vgm Player, use [Vgm Converter](https://github.com/simondotm/vgm-converter) as follows:

```
vgmconverter.py "file.vgm" -n -t bbc -q 50 -r "file.bin" -o "file.bbc.vgm" 
```
And then run [Exomizer](https://github.com/bitshifters/exomizer) (version 2.x) on the output binary to 
```
exomizer.exe raw -c -m 1024 "file.bin" -o "file.bin.exo"
```




---


## `VGC` Player Usage

To create a compressed VGC file that will work with Vgc Player, use [Vgm Packer](https://github.com/simondotm/vgm-packer) as follows:

```
vgm-packer.py "file.vgm" -o "file.vgc"
```
You can optionally add `-n` to use huffman for extra compression ratio (slightly slower decoding however as a tradeoff). 


### Compiling the source
Import `lib\vgcplayer.h.asm` and `lib\vgcplayer.asm` into your BeebAsm project. Note that you should `INCLUDE "lib/vgcplayer.h.asm"` at the point where you declare your zeropage vars - see `vgc_demo.asm` for an example.

#### `vgcplayer.asm`

You can assemble this module a couple of ways and there are defines in `vgcplayer.h.asm` as follows:

`ENABLE_HUFFMAN`
* If set to TRUE, the decoder will be able to load standard `.vgc` files as well as ones that have been huffman compressed by `vgmpacker.py`
* If set to FALSE, the decoder will not include any code to decode huffman `.vgc` files so make sure you do not compress your `.vgm` files using the `-n` option with `vgmpacker.py`.

Huffman decoding is a fair bit slower, but does save 5-10% in compression ratio, so I recommend only using it for situations where you need maximum compression and CPU runtime & code size is not an constraint. 

There are 2 main user routines:

`vgm_init()` - to initialize the player with a VGC data stream

`vgm_update()` - to refresh the player every 50Hz

See `vgcplayer.asm` for more information.

#### `vgc_demo.asm`
This is a BeebAsm project with some example 6502 code for the `vgcplayer.asm` library. Feel free to create a `.vgc` file from your favourite `.vgm`, and then just `INCBIN` it accordingly.

There are some examples in the `/music/vgc/` folder.

#### Memory Requirements
The standard decoder requires 8 zero page vars and ~740 bytes of code ram.

The Huffman enabled decoder requires 19 zero page vars and ~924 bytes of code ram.


Both decoders require a 2Kb page aligned workspace ram buffer which can be passed to the decoder via `vgm_init()`.

---

## `VGI` Player (incremental decode, bounded per-frame cost)

> Note: `lib/vgiplayer.asm`, `lib/vgiplayer.h.asm`, `vgi_demo.asm`,
> `test/vgi/` and `docs/vgi-player.md` were produced with the assistance of an
> AI model (Claude Opus 4.8 / `claude-opus-4-8`). Each file carries an
> AI-generated banner.

`lib/vgiplayer.asm` is an alternative VGM player with the **same user API** as
the VGC player (`vgm_init` / `vgm_update` / `sn_reset` / `sn_write`). It plays
`.vgi` files made by `vgipacker.py` (in the
[vgm-packer](https://github.com/simondotm/vgm-packer) repo).

The VGC player runs RLE+LZ4, so its decode cost **spikes** (cheap RLE-counter
frames, occasional expensive LZ4 refills). The VGI player runs a byte-aligned
LZSS per register column with **no RLE**, decoded **one value per stream per
frame**, so the per-frame cost is **bounded independently of match/run length**
— low, flat and predictable, which is what a raster-budgeted demo needs.
Verified byte-exact against the VGC player: over the 9602-frame `acid_demo` the
worst frame is **~1.9–2.7k cycles vs the VGC player's ~5.3k**.

It plays either of two file versions, chosen at build time:

* **v3** (`-D VGI_V3=1`) — **the one to use.** Each channel's tone period is a
  byte index into a table the packer builds, so there are 8 columns and not 11.
  Files are 21–29% smaller (about `.vgc`'s size), the workspace drops to
  **8×256 = 2 KB**, and with three fewer streams to decode it beats the stock
  VGC player at *both* ends — mean **985** cycles against 1788, worst frame
  **1894** against 5321.
* **v2** (`-D VGI_V3=0`) — 11 raw register columns, an 11×256 = 2.75 KB
  workspace, files ~1.4× `.vgc`. Mean 1149–1572, worst 2377–2677.

A build plays one version; `vgm_init` checks the file's version byte and refuses
a mismatch. The second `-D` flag is `VGI_UNROLL=0` (compact looped, default) or
`VGI_UNROLL=1` (faster unrolled); both are passed on every build.

* `vgi_demo.asm` — example BeebAsm project (build with `beebasm -i vgi_demo.asm
  -D VGI_UNROLL=0 -D VGI_V3=1 -do vgi_demo.ssd -boot Main -title VGIPLAY`). It brackets
  `vgm_update` with palette writes so the on-screen raster band height = the
  player's per-frame CPU cost.
* `test/vgi/` — builds the VGC player and all four VGI builds (looped/unrolled
  × v2/v3), plays a tune through a 6502 simulator and asserts the reconstructed
  SN76489 register state is identical each frame, then reports the per-frame cost (`pip install py65 numpy`, then
  `python measure.py`).
* `docs/vgi-player.md` — full analysis, the measured comparison and the design
  rationale.

