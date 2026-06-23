#!/usr/bin/env python
# ******************************************************************
# AI-GENERATED CODE
# ------------------------------------------------------------------
# measure.py - prove the optimised VGC player is byte-exact and time it.
# Generated with the assistance of an AI model: Claude Opus 4.8
# (claude-opus-4-8).
#
# Builds sim.asm twice (OPT=0 original, OPT=1 optimised) with beebasm,
# runs each in a py65 6502 simulator, plays the tune through once (no
# loop), captures every byte written to the SN76489 data port (&FE4F)
# and asserts the two streams are identical. Also reports per-frame
# cycle cost so the speedup is visible.
#
# Requirements: beebasm on PATH (or set BEEBASM), and `pip install py65
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
MAX_FRAMES = 100000   # safety cap (acid_demo is far shorter)


def labels(p):
    return eval(re.sub(r'(\d+)L', r'\1', open(p).read()))[0]


def build(opt):
    lp = os.path.join(HERE, "labels%d.txt" % opt)
    # no -do: a bare SAVE writes the raw binary "Vgc" that py65 loads
    subprocess.run([BEEBASM, "-i", "sim.asm", "-D", "OPT=%d" % opt,
                    "-d", "-labels", lp], cwd=HERE, check=True,
                   stdout=subprocess.DEVNULL)
    return open(os.path.join(HERE, "Vgc"), "rb").read(), labels(lp)


def run(img, lab):
    cap = []
    mem = ObservableMemory()
    for i, b in enumerate(img):
        mem[0x1100 + i] = b
    mem.subscribe_to_write([0xFE4F], lambda a, v: cap.append(v))
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

    perframe = []
    VU = lab["vgm_update"]
    for _ in range(MAX_FRAMES):
        push_ret()
        mpu.pc = VU
        mpu.a = 0
        c0 = mpu.processorCycles
        while mpu.pc != RET:
            mpu.step()
        perframe.append(mpu.processorCycles - c0)
        if mpu.a != 0:        # vgm_update returns non-zero when finished
            break
    return cap, perframe


def stats(name, pf):
    a = np.array(pf)
    print("  %-10s frames %d  min %4d  mean %5.0f  p99 %5d  max %5d  total %d"
          % (name, len(a), a.min(), a.mean(),
             int(np.percentile(a, 99)), a.max(), a.sum()))
    return a


def main():
    print("building original (OPT=0) ...")
    bimg, blab = build(0)
    print("building optimised (OPT=1) ...")
    oimg, olab = build(1)

    bcap, bpf = run(bimg, blab)
    ocap, opf = run(oimg, olab)

    ok = (ocap == bcap)
    print("\nSN76489 output: %s  (%d writes)" %
          ("IDENTICAL" if ok else "*** DIFFERS ***", len(bcap)))
    b = stats("original", bpf)
    o = stats("optimised", opf)
    if ok:
        print("\nspeedup: mean %.2fx  max %.2fx  total %.2fx  "
              "(saved %d cycles over %d frames)" %
              (b.mean() / o.mean(), b.max() / o.max(), b.sum() / o.sum(),
               b.sum() - o.sum(), len(bpf)))
    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
