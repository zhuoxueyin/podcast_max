#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
程序化合成播客音效/背景音乐素材 (BGM & SFX)
================================================
无版权风险、可再生、可被真实采声同名替换。输出 44.1kHz 立体声 WAV 到目标目录。

用法:
    python make_sfx.py --out <素材目录>

约定文件名(供 tts_cast.py 的 [[SFX:键]] / [[BGM:键]] 引用):
    bgm_<名>.wav   背景音乐(铺底循环)
    sfx_<名>.wav   特效音(句间插入)

依赖: pip install numpy
"""
import argparse
import os
import wave

import numpy as np

SR = 44100
SEED = 20260906
rng = np.random.default_rng(SEED)


def _norm(x, peak=0.85):
    m = np.max(np.abs(x)) if x.size else 1.0
    if m < 1e-9:
        return x
    return x / m * peak


def _stereo(mono, spread_ms=0.006):
    n = int(SR * spread_ms)
    d = np.concatenate([np.zeros(n), mono[:-n]]) if n > 0 else mono
    left = mono * 0.96 + d * 0.04
    right = d * 0.96 + mono * 0.04
    return np.stack([left, right], axis=1)


def _save(path, samples, peak=0.85):
    samples = _norm(samples, peak)
    pcm = (np.clip(samples, -1, 1) * 32767).astype(np.int16)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print("OK", os.path.basename(path))


def note_freq(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def pluck(midi, dur, vol=1.0, attack=0.004, bright=0.5):
    """八音盒/拨弦音色:基频+泛音,指数衰减。"""
    f = note_freq(midi)
    n = int(SR * dur)
    t = np.arange(n) / SR
    env = np.minimum(t / attack, 1.0) * np.exp(-t * (3.2 + 2.4 * bright))
    wave = (np.sin(2 * np.pi * f * t)
            + bright * 0.5 * np.sin(2 * np.pi * 2 * f * t)
            + 0.18 * np.sin(2 * np.pi * 3 * f * t) * bright)
    return wave * env * vol


def _concat_notes(notes, bpm, gap_ratio=0.06):
    """notes: [(midi, beats)] 按 bpm 顺序铺入;带轻微连音。"""
    beat = 60.0 / bpm
    total = sum(b[1] * beat for b in notes)
    buf = np.zeros(int(total * SR) + int(SR))
    t0 = 0.0
    for midi, beats in notes:
        dur = beats * beat * (1 - gap_ratio)
        w = pluck(midi, dur, bright=0.55)
        s = int(t0 * SR)
        buf[s:s + len(w)] += w
        t0 += beats * beat
    return buf[:int(t0 * SR)]


def bgm_theme(out):
    """主题 BGM:五声音阶八音盒,轻快温暖,8 小节无缝循环(bpm=96)。"""
    bpm = 96
    beat = 60.0 / bpm
    # 和弦进行 C Am F G6(音高在 C4 区间)
    chords = [
        [60, 64, 67], [57, 60, 64], [53, 57, 60], [55, 57, 62],
    ]
    notes = []
    for bar, chord in enumerate(chords):
        base = chord[0]
        # 低音(根音,低八度)+ 每小节分解琶音
        notes.append((base - 12, 4.0))
        arp = chord[1:] + [chord[0] + 12]
        pattern = [arp[0], arp[1], arp[2], arp[1], arp[0], arp[2], arp[1], arp[2]]
        for i, m in enumerate(pattern):
            notes.append((m, 0.5))
        # 高音点缀(巴二/四拍): 五声音阶即兴
        spark = [72, 74, 76, 79, 81, 76, 74, 79][bar * 2:bar * 2 + 2]
        notes.append((spark[0], 0.5))
        notes.append((spark[1], 0.5))
    buf = _concat_notes(notes, bpm)
    loop = int(8 * 4 * beat * SR)  # 8 小节
    buf = buf[:loop]
    # 轻量氛围:极轻的底噪微风,避免干涩
    pad = rng.normal(0, 1, len(buf)) * 0.012
    buf += pad
    _save(out, _stereo(buf), peak=0.6)


def _noise_color(n, color="white"):
    w = rng.normal(0, 1, n)
    if color == "white":
        return w
    if color == "pink":
        b = np.ones(n) * w[0]
        out = np.empty(n)
        acc = 0.0
        for i in range(n):
            acc = 0.98 * acc + w[i] * 0.02
            out[i] = acc * 3
        return out
    # brown
    out = np.empty(n)
    acc = 0.0
    for i in range(n):
        acc = 0.985 * acc + w[i] * 0.02
        out[i] = acc
    return out / (np.max(np.abs(out)) + 1e-9)


def sfx_book_magic(out):
    """翻书金光:嘶声上扬 + 铃音闪烁。"""
    n = int(SR * 2.2)
    t = np.arange(n) / SR
    noise = rng.normal(0, 1, n)
    # 上扫幅度包络
    env = np.clip(t / 0.18, 0, 1) * np.exp(-t * 1.6)
    whoosh = noise * env
    # 滑音 + 颤音(魔法感)
    f = 500 + 900 * np.clip(t / 0.7, 0, 1)
    vib = 1 + 0.03 * np.sin(2 * np.pi * 9 * t)
    glide = 0.5 * np.sin(2 * np.pi * np.cumsum(f * vib) / SR) * env * 0.6
    # 铃音闪烁
    bells = np.zeros(n)
    for k, m in enumerate([88, 93, 96, 100]):
        w = pluck(m, 1.2, vol=0.5, bright=0.7)
        s = int((0.15 + k * 0.14) * SR)
        bells[s:s + len(w)] += w
    buf = whoosh * 0.7 + glide + bells
    _save(out, _stereo(buf), peak=0.8)


def sfx_monkeys(out):
    """猴群喧闹:一串吱吱啾啾的短促猴叫。"""
    dur = 4.5
    n = int(SR * dur)
    buf = np.zeros(n)
    # 背景叶动窸窣
    buf += _noise_color(n, "pink") * 0.08
    # 数十声猴叫
    for _ in range(46):
        t0 = rng.uniform(0.1, dur - 0.5)
        length = rng.uniform(0.06, 0.22)
        f0 = rng.uniform(1400, 3800)
        f1 = f0 * rng.uniform(0.7, 1.6)
        vol = rng.uniform(0.35, 1.0)
        ln = int(length * SR)
        tt = np.arange(ln) / SR
        f = np.linspace(f0, f1, ln)
        chirp = np.sin(2 * np.pi * np.cumsum(f) / SR)
        env = np.exp(-tt * 18) * np.minimum(tt / 0.004, 1)
        vib = 1 + 0.2 * np.sin(2 * np.pi * rng.uniform(20, 45) * tt)
        s = int(t0 * SR)
        seg = min(ln, n - s)
        if seg > 0:
            buf[s:s + seg] += (chirp * env * vib)[:seg] * vol
    _save(out, _stereo(buf), peak=0.7)


def sfx_waterfall(out):
    """瀑布轰鸣:低频隆隆 + 均匀水花嘶声。"""
    dur = 8.0
    n = int(SR * dur)
    t = np.arange(n) / SR
    rumble = _noise_color(n, "brown") * 0.9
    hiss = rng.normal(0, 1, n)
    # 拟声瀑布的涌动调制
    swell = 0.85 + 0.15 * np.sin(2 * np.pi * 0.4 * t + np.sin(2 * np.pi * 0.13 * t))
    buf = rumble * 0.8 * swell + hiss * 0.55 * swell
    fade = np.ones(n)
    fade[:int(0.1 * SR)] = np.linspace(0, 1, int(0.1 * SR))
    buf *= fade
    _save(out, _stereo(buf), peak=0.75)


def sfx_crash(out):
    """仙石崩裂:砰 + 轰隆余震。"""
    dur = 3.0
    n = int(SR * dur)
    t = np.arange(n) / SR
    crack = rng.normal(0, 1, int(SR * 0.08)) * np.exp(-np.arange(int(SR * 0.08)) / (0.02 * SR))
    buf = np.zeros(n)
    buf[:len(crack)] += crack
    boom = np.sin(2 * np.pi * 48 * t) * np.exp(-t * 1.6) * 0.9
    boom += _noise_color(n, "brown") * np.exp(-t * 1.2) * 0.7
    buf += boom
    buf[int(0.25 * SR):int(0.25 * SR) + int(SR)] += _noise_color(int(SR), "pink") * 0.3
    _save(out, _stereo(buf), peak=0.85)


def sfx_plunge(out):
    """单声扑通落水:闷响 + 溅水。"""
    dur = 1.0
    n = int(SR * dur)
    t = np.arange(n) / SR
    thump = np.sin(2 * np.pi * np.cumsum(np.linspace(140, 70, n)) / SR) * np.exp(-t * 14)
    splash = rng.normal(0, 1, n) * np.exp(-t * 9) * np.maximum(0, 1 - t / 0.35)
    buf = thump * 0.9 + splash * 0.5
    # 水花细碎回响
    k = int(0.18 * SR)
    if n - k > 0:
        m = n - k
        echo = rng.normal(0, 1, m) * np.exp(-np.arange(m) / (0.12 * SR))
        buf[k:] += echo * 0.2
    _save(out, _stereo(buf), peak=0.8)


def sfx_plunges_many(out):
    """下饺子般连串扑通。"""
    dur = 3.4
    n = int(SR * dur)
    buf = np.zeros(n)
    base = np.zeros(int(SR * 1.0))
    tt = np.arange(len(base)) / SR
    thump = np.sin(2 * np.pi * np.cumsum(np.linspace(150, 70, len(base))) / SR) * np.exp(-tt * 13)
    splash = rng.normal(0, 1, len(base)) * np.exp(-tt * 9) * np.maximum(0, 1 - tt / 0.3)
    single = (thump * 0.9 + splash * 0.5) * 0.9
    starts = [0.0, 0.32, 0.60, 0.84, 1.06, 1.30, 1.58, 1.90, 2.24, 2.62]
    for s0 in starts:
        s = int(s0 * SR)
        seg = min(len(single), n - s)
        if seg > 0:
            buf[s:s + seg] += single[:seg]
    _save(out, _stereo(buf), peak=0.8)


def sfx_sparkle(out):
    """别有洞天灵光:上行清脆铃音+空气感。"""
    dur = 2.8
    n = int(SR * dur)
    buf = np.zeros(n)
    seq = [(88, 0.0), (93, 0.09), (96, 0.18), (100, 0.27), (105, 0.38)]
    for m, t0 in seq:
        w = pluck(m, 1.6, vol=0.9, bright=0.8)
        s = int(t0 * SR)
        buf[s:s + len(w)] += w
    # 高空气氛
    air = rng.normal(0, 1, n) * 0.03 * np.exp(-np.arange(n) / (0.4 * SR))
    buf += air
    # 尾声轻轻上扬(与目标切片等长)
    k = int(0.5 * SR)
    s = n - k
    tt = np.arange(k) / SR
    tail = np.sin(2 * np.pi * np.cumsum(np.linspace(1100, 1650, k)) / SR) * np.linspace(0, 0.25, k)
    buf[s:s + k] += tail
    _save(out, _stereo(buf), peak=0.7)


def main():
    ap = argparse.ArgumentParser(description="生成播客 BGM/SFX 素材(WAV)")
    ap.add_argument("--out", default="素材", help="输出目录")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    jobs = {
        "bgm_主题花果山.wav": bgm_theme,
        "sfx_翻书金光.wav": sfx_book_magic,
        "sfx_猴群喧闹.wav": sfx_monkeys,
        "sfx_瀑布.wav": sfx_waterfall,
        "sfx_轰隆.wav": sfx_crash,
        "sfx_跳水.wav": sfx_plunge,
        "sfx_连跳水.wav": sfx_plunges_many,
        "sfx_灵光.wav": sfx_sparkle,
    }
    for name, fn in jobs.items():
        try:
            fn(os.path.join(args.out, name))
        except Exception as e:
            print("FAIL", name, e)
    print("素材生成完毕 ->", os.path.abspath(args.out))


if __name__ == "__main__":
    main()
