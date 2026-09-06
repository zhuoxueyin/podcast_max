#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MiniMax 音色快速复刻 (Voice Clone)

把一段"目标人声"音频快速复刻成专属 voice_id,之后可直接用于正式 T2A 配音。

流程(对应官方文档三接口):
    1) 归一化/探测本地音频(ffmpeg 转 48k/16bit/mono,wave 模块不支持 float wav)
    2) upload_audio purpose=voice_clone  → file_id(主音频, 需 10s~5min)
       (可选) purpose=prompt_audio        → file_id(示例音频, <8s)
    3) clone_voice(file_id, voice_id, ...) → 成功即拥有自定义 voice_id
    4) 若传了 --text, 服务端用克隆音色朗读并返回 demo_audio, 下载到 --out

用法:
    python voice_clone.py --audio 孙悟空wav.wav --voice-id SunWuKong_20260906 \
        --text "俺老孙来也!" --out 试音_孙悟空复刻.mp3

    # 可选:附加一段 <8s 示例音频提升相似度(需同时给 --prompt-text 转写)
    python voice_clone.py --audio main.wav --prompt-audio sample.wav \
        --prompt-text "这是示例台词……" --voice-id MyVoice01 --text "试听" --out a.mp3

依赖: requests; ffmpeg(imageio-ffmpeg 或 PATH)。
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile
import wave

try:
    import requests
except ImportError:
    print("缺少 requests 库,请先安装: pip install requests")
    sys.exit(1)

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import tts_cast as tc          # noqa: E402  仅复用 get_ffmpeg
import tts_minimax as t        # noqa: E402

MIN_S, MAX_S = 10, 300   # 主音频时长区间(秒)
MAX_MB = 20


def probe_and_norm(src, workdir):
    """统一转 48k/16bit/单声道 wav(兼容 float wav),返回 (规范文件路径, 时长秒)。"""
    ff = tc.get_ffmpeg()
    dst = os.path.join(workdir, "norm_input.wav")
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", src,
                    "-ar", "48000", "-ac", "1", "-sample_fmt", "s16", dst],
                   check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)
    with wave.open(dst, "rb") as w:
        dur = w.getnframes() / w.getframerate()
    return dst, dur


def main():
    ap = argparse.ArgumentParser(description="MiniMax 音色快速复刻")
    ap.add_argument("--audio", required=True, help="待复刻主音频(10s~5min)")
    ap.add_argument("--voice-id", required=True,
                    help="自定义音色 ID(8~256 位,首字符英文字母,仅字母数字 _ -,末位不能是 -/_)")
    ap.add_argument("--prompt-audio", default=None,
                    help="可选:一段 <8s 示例音频,提升相似度")
    ap.add_argument("--prompt-text", default=None,
                    help="--prompt-audio 对应音频的转写文本(给了 prompt-audio 则必填)")
    ap.add_argument("--text", default=None,
                    help="可选:复刻试听文本(≤1000 字),服务端生成 demo_audio")
    ap.add_argument("--out", default=None,
                    help="试听 demo 音频下载路径(--text 时建议给)")
    ap.add_argument("--no-norm", action="store_true",
                    help="跳过 ffmpeg 归一化,直接用原文件上传")
    args = ap.parse_args()

    if args.prompt_audio and not args.prompt_text:
        print("❌ 给了 --prompt-audio 必须同时给 --prompt-text(该段音频的转写文本)")
        sys.exit(1)
    if args.text and not args.out:
        print("⚠️  --text 会产生 demo_audio,建议给 --out 下载;否则仅打印 voice_id。")

    workdir = tempfile.mkdtemp(prefix="mmclone_")
    try:
        # ---- 1) 归一化 + 探测时长 ----
        if args.no_norm:
            main_audio, main_dur = args.audio, None
            print("--no-norm: 跳过归一化,未探测时长(请自行确保 10s~5min)")
        else:
            main_audio, main_dur = probe_and_norm(args.audio, workdir)
            print(f"主音频时长: {main_dur:.1f}s(要求 {MIN_S}s~{MAX_S}s)")
            if main_dur < MIN_S:
                print(f"❌ 主音频不足 {MIN_S} 秒,复刻质量会差;请提供更长音频。")
                sys.exit(1)

        # ---- 2) 上传主音频 ----
        print("== 上传主音频 ==")
        main_file_id = t.upload_audio(main_audio, purpose="voice_clone")

        # ---- 2b) 可选:上传示例音频 ----
        clone_prompt = None
        if args.prompt_audio:
            print("== 上传示例音频(prompt) ==")
            p_tmp, p_dur = probe_and_norm(args.prompt_audio, workdir)
            if p_dur >= 8:
                print(f"⚠️  示例音频 {p_dur:.1f}s ≥8s,可能不合规(prompt 需 <8s)")
            pfid = t.upload_audio(p_tmp, purpose="prompt_audio")
            clone_prompt = {"prompt_audio": pfid,
                            "prompt_text": args.prompt_text}

        # ---- 3) 快速复刻 ----
        print(f"== 快速复刻 voice_id = {args.voice_id} ==")
        result = t.clone_voice(main_file_id, args.voice_id,
                               clone_prompt=clone_prompt, text=args.text)
        print(f"  ✓ 复刻成功: {args.voice_id}  "
              f"风控命中={result.get('input_sensitive', False)}")

        # ---- 4) 下载试听 ----
        demo = result.get("demo_audio", "")
        if args.text and demo and args.out:
            print("== 下载试听 demo ==")
            resp = requests.get(demo, timeout=180)
            resp.raise_for_status()
            t.save_audio(resp.content, args.out)
            print(f"  试听文本: {args.text}")
        elif args.out and not demo:
            print("⚠️  未返回 demo_audio(未传 --text 或服务端未生成)。")

        print("\n✅ 完成。之后正式配音直接用这个 voice_id:")
        print(f"   python tts_minimax.py --voice {args.voice_id} "
              f"--text '台词' --out x.mp3")
    finally:
        for fn in os.listdir(workdir):
            try:
                os.remove(os.path.join(workdir, fn))
            except OSError:
                pass
        os.rmdir(workdir)


if __name__ == "__main__":
    main()
