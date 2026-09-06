#!/usr/bin/env python
# ******************************************************************
# AI-GENERATED CODE
# ------------------------------------------------------------------
# measure.py - prove the VGI player drives the SN76489 identically to
# the stock VGC player, and time it. Generated with the assistance of
# an AI model: Claude Opus 4.8 (claude-opus-4-8).
#
# Builds five players with beebasm - the VGC player (sim_vgc.asm) and the
# VGI player four times (sim_vgi.asm over VGI_UNROLL x VGI_V3) - over the
# SAME tune (acid_demo, as both .vgc and .vgi). Each is run in a py65 6502
# simulator; every byte written to the SN76489 data port (&FE4F) is captured
# per frame and replayed through a model of the chip's latch/registers, so we
# compare the RECONSTRUCTED per-frame register state of each player.
#
# This is the right comparison because the two formats write the chip
# differently: VGC uses RLE and writes only the registers that changed each
# frame, while VGI writes all 11 register columns every frame (skipping only
# unchanged noise). The raw write streams therefore differ in length, but the
# resulting chip STATE must be identical frame-for-frame - that is what this
# asserts.
#
# Requirements: beebasm on PATH (or set $BEEBASM), and `pip install py65
# numpy`. Run from this directory:  python measure.py
# ******************************************************************
import os
import re
import sys
import subprocess

import numpy as np
from py65.devices.mpu6502 import MPU
from py65.memory import ObservableMemory

HERE = os.path.dirname(os.path.abspath(__file__))
# default to the beebasm shipped alongside these repos; override with $BEEBASM
DEFAULT_BEEBASM = os.path.normpath(
    os.path.join(HERE, "..", "..", "..", "..", "bin", "beebasm.exe"))
BEEBASM = os.environ.get("BEEBASM", DEFAULT_BEEBASM)
RET = 0x9000          # sentinel return address pushed before each call
LOAD = 0x1100         # ORG of the sim images
MAX_FRAMES = 100000   # safety cap (acid_demo is ~9600 frames)


def labels(p):
    return eval(re.sub(r'(\d+)L', r'\1', open(p).read()))[0]


def build(src, defines, out, tag):
    lp = os.path.join(HERE, "labels_%s.txt" % tag)
    cmd = [BEEBASM, "-i", src]
    for k, v in defines.items():
        cmd += ["-D", "%s=%s" % (k, v)]
    cmd += ["-d", "-labels", lp]
    # no -do: a bare SAVE writes the raw binary that py65 loads
    subprocess.run(cmd, cwd=HERE, check=True, stdout=subprocess.DEVNULL)
    return open(os.path.join(HERE, out), "rb").read(), labels(lp)


def run(img, lab):
    """Run vgm_init then vgm_update frame-by-frame. Returns (frames, perframe)
    where frames is a list of per-frame write-byte lists for frames that
    returned 'still playing' (A==0); the terminating update (A!=0, which only
    silences the chip) is not recorded."""
    frame_writes = []
    mem = ObservableMemory()
    for i, b in enumerate(img):
        mem[LOAD + i] = b
    mem.subscribe_to_write([0xFE4F], lambda a, v: frame_writes.append(v))
    mpu = MPU(memory=mem)

    def push_ret():
        sp = mpu.sp
        mem[0x100 + sp] = ((RET - 1) >> 8) & 0xff
        mem[0x100 + ((sp - 1) & 0xff)] = (RET - 1) & 0xff
        mpu.sp = (sp - 2) & 0xff

    # vgm_init(A=buffer hi, X/Y=data ptr, C=0 -> no loop so it ends)
    bhi = lab["vgm_stream_buffers"] >> 8
    d = lab["vgm_data"]
    mpu.a, mpu.x, mpu.y = bhi, d & 0xff, (d >> 8) & 0xff
    mpu.p &= ~1
    push_ret()
    mpu.pc = lab["vgm_init"]
    while mpu.pc != RET:
        mpu.step()

    frames, perframe = [], []
    VU = lab["vgm_update"]
    for _ in range(MAX_FRAMES):
        del frame_writes[:]
        push_ret()
        mpu.pc = VU
        mpu.a = 0
        c0 = mpu.processorCycles
        while mpu.pc != RET:
            mpu.step()
        if mpu.a != 0:        # terminating update (silence only) - not a frame
            break
        frames.append(list(frame_writes))
        perframe.append(mpu.processorCycles - c0)
    return frames, perframe


def reconstruct(frames):
    """Replay each frame's SN76489 writes through a model of the chip and
    snapshot the 11 logical register values after each frame. Columns:
    0 tone0lo 1 tone0hi 2 tone1lo 3 tone1hi 4 tone2lo 5 tone2hi
    6 noise 7 vol0 8 vol1 9 vol2 10 vol3."""
    state = [0] * 11
    latched_tone = None       # channel awaiting a 6-bit data byte, or None
    snaps = []
    for writes in frames:
        for b in writes:
            if b & 0x80:                       # %1 cc t dddd : latch + data
                cc = (b >> 5) & 3
                is_vol = (b >> 4) & 1
                d4 = b & 0x0f
                if is_vol:
                    state[7 + cc] = d4          # vol0..vol3
                    latched_tone = None
                elif cc < 3:
                    state[2 * cc] = d4          # tone lo (4 bits)
                    latched_tone = cc           # expect hi-bits data byte next
                else:
                    state[6] = d4               # noise control
                    latched_tone = None
            else:                               # %0 xxxxxx : tone hi (6 bits)
                if latched_tone is not None:
                    state[2 * latched_tone + 1] = b & 0x3f
        snaps.append(tuple(state))
    return snaps


def stats(name, pf):
    a = np.array(pf)
    print("  %-16s frames %d  min %4d  mean %5.0f  p99 %5d  max %5d"
          % (name, len(a), a.min(), a.mean(), int(np.percentile(a, 99)), a.max()))
    return a


def compare(name, vgi_snaps, vgc_snaps):
    n = min(len(vgi_snaps), len(vgc_snaps))
    diff = next((i for i in range(n) if vgi_snaps[i] != vgc_snaps[i]), None)
    if diff is None and len(vgi_snaps) == len(vgc_snaps):
        print("  %-16s SN76489 state IDENTICAL over all %d frames" % (name, n))
        return True
    if diff is None:
        print("  %-16s state matches over %d common frames, but frame counts "
              "differ (VGI %d, VGC %d)" % (name, n, len(vgi_snaps), len(vgc_snaps)))
        return False
    print("  %-16s *** DIFFERS at frame %d ***\n      VGI=%s\n      VGC=%s"
          % (name, diff, vgi_snaps[diff], vgc_snaps[diff]))
    return False


def main():
    print("building VGC (stock) ...")
    vgc_img, vgc_lab = build("sim_vgc.asm", {}, "Vgc", "vgc")
    print("building VGI v2 looped (VGI_UNROLL=0 VGI_V3=0) ...")
    vl_img, vl_lab = build("sim_vgi.asm", {"VGI_UNROLL": "0", "VGI_V3": "0"},
                           "Vgi", "vgi_looped")
    print("building VGI v2 unrolled (VGI_UNROLL=1 VGI_V3=0) ...")
    vu_img, vu_lab = build("sim_vgi.asm", {"VGI_UNROLL": "1", "VGI_V3": "0"},
                           "Vgi", "vgi_unroll")
    print("building VGI v3 looped (VGI_UNROLL=0 VGI_V3=1) ...")
    v3l_img, v3l_lab = build("sim_vgi.asm", {"VGI_UNROLL": "0", "VGI_V3": "1"},
                             "Vgi", "vgi_v3_looped")
    print("building VGI v3 unrolled (VGI_UNROLL=1 VGI_V3=1) ...")
    v3u_img, v3u_lab = build("sim_vgi.asm", {"VGI_UNROLL": "1", "VGI_V3": "1"},
                             "Vgi", "vgi_v3_unroll")

    vgc_f, vgc_pf = run(vgc_img, vgc_lab)
    vl_f, vl_pf = run(vl_img, vl_lab)
    vu_f, vu_pf = run(vu_img, vu_lab)
    v3l_f, v3l_pf = run(v3l_img, v3l_lab)
    v3u_f, v3u_pf = run(v3u_img, v3u_lab)

    vgc_s = reconstruct(vgc_f)
    vl_s = reconstruct(vl_f)
    vu_s = reconstruct(vu_f)
    v3l_s = reconstruct(v3l_f)
    v3u_s = reconstruct(v3u_f)

    print("\nbyte-exact check (reconstructed SN76489 register state vs VGC):")
    ok_l = compare("VGI v2 looped", vl_s, vgc_s)
    ok_u = compare("VGI v2 unrolled", vu_s, vgc_s)
    # v3 reads a different FILE - 8 indexed columns instead of 11 raw ones - so
    # these two are the check that the format change is invisible to the chip.
    ok_3l = compare("VGI v3 looped", v3l_s, vgc_s)
    ok_3u = compare("VGI v3 unrolled", v3u_s, vgc_s)
    # the builds must of course agree with each other too
    ok_lu = (vl_s == vu_s) and (v3l_s == v3u_s)
    print("  %-16s %s" % ("looped==unrolled", "YES" if ok_lu else "*** NO ***"))

    print("\nper-frame cost incl. SN writes (cycles @ 2 MHz):")
    stats("VGC (stock)", vgc_pf)
    stats("VGI v2 looped", vl_pf)
    stats("VGI v2 unrolled", vu_pf)
    stats("VGI v3 looped", v3l_pf)
    stats("VGI v3 unrolled", v3u_pf)
    print("  note: VGI writes all 11 registers every frame; VGC writes only the")
    print("        ones its RLE says changed - so this includes that difference.")
    print("        v3 decodes 8 columns instead of 11 and expands the three tone")
    print("        periods through a table, which is where its saving comes from.")

    ok = ok_l and ok_u and ok_3l and ok_3u and ok_lu
    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
