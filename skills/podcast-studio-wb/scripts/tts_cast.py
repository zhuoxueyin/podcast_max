#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
角色化剧本稿 → 分角色配音 + BGM/SFX 自动混音 (MiniMax T2A)

输入剧本稿格式(见 skill assets/templates/qinzi_episode.md):
    # 音色表 旁白=female-chengshu;阿慢=male-qn-jingying;跳跳=female-shaonv;…
    【角色】台词…(可多行,下一行无标记则续接同角色)
    [[SFX:名]]   在素材目录找 sfx_名.wav,插在句间
    [[BGM:名]]   切换背景音乐(素材目录 bgm_名.wav),整集铺底
    # 注释 / --- 分隔线 / 空行 均跳过

用法:
    python tts_cast.py --script E01_石猴出世.md \
        --assets 素材目录 --out E01_终混.mp3 [--no-bgm] [--voice-out E01_纯语音.mp3]
    python tts_cast.py --script Exx.md --assets 素材目录 \
        --voice-map 00_角色音色表.md --out Exx_终混.mp3   # 用权威角色音色表覆盖集稿音色表

音色来源(优先级从低到高):
    1) 集稿头部 `# 音色表 角色=voice_id;...` 行
    2) --voice-map 文件(解析同格式的 `音色表` 行),同名角色覆盖 → 全系列换音色只改一处
语音段缓存按「音色指纹」命名:换音色后只有受影响角色的段落重新合成,其余段走缓存。

依赖: requests / numpy / ffmpeg(imageio-ffmpeg 提供二进制即可)
实现: TTS 分段合成 → ffmpeg 解码为 32k/16bit 单声道 → numpy 顺序拼接 + BGM 铺底 → 导出 mp3
"""
import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import time
import wave

import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import tts_minimax as t  # noqa: E402

PAUSE_MS = 260          # 语音段/音效之间的呼吸间隔(毫秒)
BGM_GAIN = 0.16         # BGM 铺底音量(相对,≈ -16dB)
BGM_FADE_IN_S = 1.5
BGM_FADE_OUT_S = 6.0
PEAK = 0.90             # 每段归一化目标峰值
SR = 32000
# 与 tts_minimax.synthesize 调用保持一致(改这里即全局换引擎参数)
SPEED, VOL, PITCH, MODEL = 1, 1, 0, "speech-2.8-hd"


def get_ffmpeg():
    try:
        import imageio_ffmpeg
        p = imageio_ffmpeg.get_ffmpeg_exe()
        if os.path.exists(p):
            return p
    except Exception:
        pass
    env = os.environ.get("FFMPEG")
    if env and os.path.exists(env):
        return env
    which = shutil.which("ffmpeg")
    if which:
        return which
    print("❌ 找不到 ffmpeg。请安装并加入 PATH,或 pip install imageio-ffmpeg。")
    sys.exit(1)


FFMPEG = None


# ----------------------------- 剧本解析 -----------------------------

def parse_script(path):
    """返回 (voice_map, items)。items: ('v',role,text) / ('sfx',name) / ('bgm',name)"""
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    voice_map = {}
    items = []
    cur = None
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("---"):
            continue
        m = re.match(r"^#\s*音色表\s*(.+)$", line)
        if m:
            for pair in m.group(1).split(";"):
                pair = pair.strip()
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    voice_map[k.strip()] = v.strip()
            continue
        if line.startswith("#"):
            continue
        if line.startswith(("-", ">", "*", "=")) or line.startswith("<!--"):
            continue
        m = re.match(r"^\[\[SFX:([^\]]+)\]\]$", line)
        if m:
            if cur:
                items.append(cur); cur = None
            items.append(("sfx", m.group(1).strip()))
            continue
        m = re.match(r"^\[\[BGM:([^\]]+)\]\]$", line)
        if m:
            if cur:
                items.append(cur); cur = None
            items.append(("bgm", m.group(1).strip()))
            continue
        m = re.match(r"^【(.+?)】\s*(.*)$", line)
        if m:
            if cur:
                items.append(cur)
            cur = ("v", m.group(1).strip(), m.group(2).strip())
            continue
        if cur:
            cur = (cur[0], cur[1], cur[2] + "\n" + line)
        else:
            print(f"⚠️  裸文字行(缺角色标记),已跳过: {line[:40]}")
    if cur:
        items.append(cur)
    # 相邻同角色合并(减少 TTS 调用)
    merged = []
    for it in items:
        if (it[0] == "v" and merged and merged[-1][0] == "v"
                and merged[-1][1] == it[1]):
            merged[-1] = (merged[-1][0], merged[-1][1],
                          merged[-1][2] + "\n" + it[2])
        else:
            merged.append(it)
    return voice_map, merged


def load_voice_map(path):
    """从外部音色表文件读取映射(与集稿 `# 音色表` 行同格式)。

    逐行扫描匹配 `# 音色表 角色=voice_id;...`,多个匹配行会合并;
    后出现的同名角色覆盖先前的 → 可作为全系列权威表,覆盖集稿内的旧映射。
    """
    voice_map = {}
    if not os.path.exists(path):
        print(f"❌ --voice-map 文件不存在: {path}")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        for raw in f.read().splitlines():
            m = re.match(r"^\s*#\s*音色表\s+(.+)$", raw)
            if not m:
                continue
            for pair in m.group(1).split(";"):
                pair = pair.strip()
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    voice_map[k.strip()] = v.strip()
    if voice_map:
        print(f"  从音色表加载 {len(voice_map)} 条映射: {os.path.basename(path)}")
    return voice_map


def voice_fp(voice):
    """按音色(及语速/音量/音调/模型)生成稳定短指纹,用于缓存文件名。"""
    return hashlib.md5(
        f"{voice}|{SPEED}|{VOL}|{PITCH}|{MODEL}".encode("utf-8")
    ).hexdigest()[:8]


# ----------------------------- 音频工具 -----------------------------

def _decode_wav(src, dst):
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", src,
                    "-ar", str(SR), "-ac", "1", "-sample_fmt", "s16", dst],
                   check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)


def _read_wav(path):
    with wave.open(path, "rb") as w:
        assert w.getnchannels() == 1 and w.getsampwidth() == 2
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return data.astype(np.float32) / 32768.0


def _write_wav(path, samples):
    pcm = (np.clip(samples, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def _silence(ms):
    return np.zeros(int(SR * ms / 1000), dtype=np.float32)


def _norm_to_peak(x):
    m = np.max(np.abs(x)) if x.size else 0.0
    if m < 1e-4 or m > PEAK:
        return x if m < 1e-4 else x * (PEAK / m)
    return x


def asset_array(assets, kind, name):
    """kind='sfx'/'bgm' → 解码素材为 float32 数组。"""
    path = os.path.join(assets, f"{kind}_{name}.wav")
    if not os.path.exists(path):
        print(f"❌ 素材缺失: {path}")
        sys.exit(1)
    tmp = os.path.join(assets, f"._{kind}_{name}.wav")
    _decode_wav(path, tmp)
    a = _read_wav(tmp)
    os.remove(tmp)
    return _norm_to_peak(a)


# ----------------------------- 配音 -----------------------------

def synth_seg(seg, retry=3):
    if os.path.exists(seg["file"]) and os.path.getsize(seg["file"]) > 1000:
        return True
    for i in range(retry):
        try:
            print(f"  ▶ [{seg['idx']:02d}] {seg['role']} <{seg['voice']}> "
                  f"{len(seg['text'])}字 ...", flush=True)
            audio, info = t.synthesize(seg["text"], voice_id=seg["voice"],
                                       speed=SPEED, vol=VOL, pitch=PITCH,
                                       model=MODEL)
            with open(seg["file"], "wb") as f:
                f.write(audio)
            ms = (info or {}).get("audio_length", "?")
            print(f"     ✓ {ms}ms", flush=True)
            return True
        except Exception as e:
            print(f"     ✗ 第{i+1}次失败: {str(e)[:120]}", flush=True)
            time.sleep(2)
    return False


# ----------------------------- 混音 -----------------------------

def mix_plan(plan, assets, no_bgm=False, voice_out=None, final_out=None):
    # 主轨(对位语音+音效)与纯语音轨各自累加
    def assemble(use_sfx):
        parts = [_silence(220)]
        for p in plan:
            if p["type"] == "v":
                tmp = os.path.join(os.path.dirname(p["file"]), "._d.wav")
                _decode_wav(p["file"], tmp)
                seg = _norm_to_peak(_read_wav(tmp))
                os.remove(tmp)
                parts.append(_silence(PAUSE_MS))
                parts.append(seg)
            elif p["type"] == "sfx" and use_sfx:
                parts.append(_silence(PAUSE_MS))
                parts.append(_norm_to_peak(
                    asset_array(assets, "sfx", p["name"])))
        if parts:
            parts.append(_silence(400))
        return np.concatenate(parts) if parts else np.zeros(0, np.float32)

    main = assemble(use_sfx=True)
    if voice_out:
        _write_wav(os.path.join(os.path.dirname(final_out), "._vo.wav"),
                   assemble(use_sfx=False))

    if not no_bgm:
        bgm_name = next((p["name"] for p in reversed(plan)
                         if p["type"] == "bgm"), None)
        if bgm_name:
            bgm = _norm_to_peak(asset_array(assets, "bgm", bgm_name))
            need = len(main)
            if len(bgm) < need:
                bgm = np.tile(bgm, int(np.ceil(need / len(bgm))))
            bgm = bgm[:need]
            # 淡入淡出(音量恒定 0.16 下用线性窗)
            fi = int(BGM_FADE_IN_S * SR)
            bgm[:fi] *= np.linspace(0, 1, fi)
            fo = int(BGM_FADE_OUT_S * SR)
            if fo < len(bgm):
                bgm[-fo:] *= np.linspace(1, 0, fo)
            bgm = bgm * BGM_GAIN
            if len(bgm) > len(main):
                bgm = bgm[:len(main)]
            main = main + bgm
        else:
            print("⚠️  剧本中没有 [[BGM:...]] 事件,输出无背景音乐。")

    m = np.max(np.abs(main)) if main.size else 1.0
    if m > 0.98:
        main = main * (0.98 / m)

    def export_mp3(path, samples, br):
        wav_tmp = os.path.join(os.path.dirname(final_out), "._mix.wav")
        _write_wav(wav_tmp, samples)
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", wav_tmp,
                        "-codec:a", "libmp3lame", "-b:a", br, "-ar",
                        str(SR), path], check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
        os.remove(wav_tmp)
        print(f"✅ {path}  时长 {len(samples) / SR:.1f}s")

    if voice_out:
        vo_wav = os.path.join(os.path.dirname(final_out), "._vo.wav")
        export_mp3(voice_out, _read_wav(vo_wav), "128k")
        os.remove(vo_wav)
    export_mp3(final_out, main, "160k")


def main():
    global FFMPEG
    FFMPEG = get_ffmpeg()
    ap = argparse.ArgumentParser(description="角色化剧本稿 → 分角色配音+混音")
    ap.add_argument("--script", required=True, help="剧本稿 .md 路径")
    ap.add_argument("--assets", required=True, help="素材目录(含 bgm_*.wav/sfx_*.wav)")
    ap.add_argument("--out", default=None, help="终混 mp3 输出路径")
    ap.add_argument("--voice-out", default=None, help="可选:另存纯语音 mp3")
    ap.add_argument("--voice-map", default=None,
                    help="权威角色音色表路径(同 `# 音色表` 行格式),同名角色覆盖集稿音色表")
    ap.add_argument("--no-bgm", action="store_true", help="跳过背景音乐")
    ap.add_argument("--keep", action="store_true", help="保留分角色临时音频")
    args = ap.parse_args()
    if not args.out:
        args.out = os.path.splitext(args.script)[0] + "_终混.mp3"

    print("== 解析剧本稿 ==")
    voice_map, items = parse_script(args.script)
    if args.voice_map:
        ext = load_voice_map(args.voice_map)
        if not ext:
            print("⚠️  --voice-map 未读到有效映射,继续使用集稿音色表。")
        for k, v in ext.items():
            voice_map[k] = v  # 外部权威表覆盖集稿同名角色
    if not voice_map:
        print("错误:缺少角色音色映射。请在集稿头部加 `# 音色表` 行,"
              "或通过 --voice-map 传入权威音色表(如 00_角色音色表.md)。")
        sys.exit(1)
    base = os.path.splitext(args.out)[0]
    work = base + "_work"
    os.makedirs(work, exist_ok=True)
    plan = []
    vi = 0
    for it in items:
        if it[0] == "v":
            _, role, text = it
            if role not in voice_map:
                print(f"❌ 角色「{role}」未在音色表注册:{voice_map}")
                sys.exit(1)
            voice = voice_map[role]
            plan.append({"type": "v", "role": role, "voice": voice,
                         "text": text, "idx": vi,
                         "file": os.path.join(
                             work, f"v{vi:03d}_{role}_{voice_fp(voice)}.mp3")})
            vi += 1
        elif it[0] == "sfx":
            plan.append({"type": "sfx", "name": it[1]})
        else:
            plan.append({"type": "bgm", "name": it[1]})
    nv = sum(1 for p in plan if p["type"] == "v")
    nsfx = sum(1 for p in plan if p["type"] == "sfx")
    print(f"  语音段 {nv} | SFX {nsfx} 处 | BGM {sum(1 for p in plan if p['type']=='bgm')} 次")
    print("== 分角色 TTS(可中断重跑,已完成段自动跳过)==")
    for p in plan:
        if p["type"] == "v" and not synth_seg(p):
            print("❌ 有语音段失败,重跑本命令即可续做。")
            sys.exit(1)
    print("== 混音 ==")
    mix_plan(plan, args.assets, no_bgm=args.no_bgm,
             voice_out=args.voice_out, final_out=args.out)
    if not args.keep:
        for fn in os.listdir(work):
            os.remove(os.path.join(work, fn))
        os.rmdir(work)
    print("完成。")


if __name__ == "__main__":
    main()
