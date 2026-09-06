#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MiniMax T2A 语音合成脚本（podcast-studio skill）

用法:
  python minimax_tts.py 文稿.md -o E01.mp3 [--clean] [--voice VID] [--emotion happy]
         [--speed 1.0] [--model speech-2.8-hd] [--pron "处理/(chu3)(li3)"]...

鉴权优先级: --token 参数 > 环境变量 MINIMAX_API_KEY（代码不内置任何密钥）

环境变量设置（二选一，Windows 与 macOS/Linux 通用）:
  Windows PowerShell（当前会话）:  $env:MINIMAX_API_KEY="sk-..."
  Windows cmd（当前会话）:         set MINIMAX_API_KEY=sk-...
  Windows 永久（用户级）:           setx MINIMAX_API_KEY "sk-..."
  macOS/Linux（当前会话）:          export MINIMAX_API_KEY="sk-..."
  macOS/Linux 永久:  写入 ~/.zshrc 或 ~/.bash_profile 后 source 生效
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error

API_URL = "https://api.minimaxi.com/v1/t2a_v2"
API_URL_BAK = "https://api-bj.minimaxi.com/v1/t2a_v2"
CHUNK_LIMIT = 2800  # 单次请求字符上限保守值（官方限制 <10000，>3000 建议流式）


def clean_text(text: str) -> str:
    """清洗文稿：去 Markdown 标记/结构标签/制作标注，只留播讲正文。"""
    # 去掉 ## 制作标注 及其之后的内容
    text = re.split(r"\n#{1,3}\s*制作标注", text, maxsplit=1)[0]
    # 去 Markdown 强调/标题符号（先做，保证后续结构标签行能匹配）
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    # 去掉结构标签行，如 【①开场】【讲解1 · 伴随着你】（→ 过渡曲《XX》）
    text = re.sub(r"^【[^】]*】\s*$", "", text, flags=re.M)
    text = re.sub(r"^（→[^）]*）\s*$", "", text, flags=re.M)
    text = re.sub(r"^🎵.*$", "", text, flags=re.M)
    # 去其余 Markdown 符号
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"^>\s?", "", text, flags=re.M)
    text = re.sub(r"^---+\s*$", "", text, flags=re.M)
    # 压缩空行
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_chunks(text: str, limit: int = CHUNK_LIMIT):
    """按段落/句读切分长文本，每段不超过 limit 字符。"""
    paras = [p for p in re.split(r"\n+", text) if p.strip()]
    chunks, buf = [], ""
    for p in paras:
        p = p.strip()
        while len(p) > limit:  # 单段超长：按句末标点硬切
            cut = max(p.rfind(s, 0, limit) for s in "。！？!?.;；")
            cut = cut + 1 if cut > limit // 2 else limit
            if buf:
                chunks.append(buf)
                buf = ""
            chunks.append(p[:cut])
            p = p[cut:]
        if len(buf) + len(p) + 1 > limit:
            if buf:
                chunks.append(buf)
            buf = p
        else:
            buf = (buf + "\n" + p) if buf else p
    if buf:
        chunks.append(buf)
    return chunks


def call_t2a(token: str, text: str, args, retries: int = 2) -> bytes:
    body = {
        "model": args.model,
        "text": text,
        "stream": False,
        "voice_setting": {
            "voice_id": args.voice,
            "speed": args.speed,
            "vol": 1.0,
            "pitch": 0,
        },
        "audio_setting": {
            "sample_rate": 32000,
            "bitrate": 128000,
            "format": "mp3",
            "channel": 1,
        },
        "subtitle_enable": False,
        "language_boost": "Chinese",
    }
    if args.emotion:
        body["voice_setting"]["emotion"] = args.emotion
    if args.pron:
        body["pronunciation_dict"] = {"tone": args.pron}

    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    last_err = None
    for attempt in range(retries + 1):
        url = API_URL if attempt % 2 == 0 else API_URL_BAK
        try:
            req = urllib.request.Request(
                url, data=data,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            base = payload.get("base_resp") or {}
            if base.get("status_code") != 0:
                raise RuntimeError(f"API error {base.get('status_code')}: {base.get('status_msg')}")
            audio_hex = (payload.get("data") or {}).get("audio")
            if not audio_hex:
                raise RuntimeError("响应中无音频数据")
            return bytes.fromhex(audio_hex)
        except (urllib.error.URLError, RuntimeError, TimeoutError, json.JSONDecodeError) as e:
            last_err = e
            if attempt < retries:
                time.sleep(2 * (attempt + 1))
    raise SystemExit(f"T2A 请求失败（已重试 {retries} 次）: {last_err}")


def main():
    ap = argparse.ArgumentParser(description="MiniMax T2A 文稿转音频")
    ap.add_argument("input", help="文稿文件路径（UTF-8）")
    ap.add_argument("-o", "--output", required=True, help="输出 mp3 路径")
    ap.add_argument("--token", default=None, help="MiniMax API token")
    ap.add_argument("--voice", default="male-qn-qingse", help="voice_id（默认 male-qn-qingse，建议先试听确认）")
    ap.add_argument("--model", default="speech-2.8-hd", help="模型（默认 speech-2.8-hd）")
    ap.add_argument("--emotion", default=None, help="情绪，如 happy/calm/sad")
    ap.add_argument("--speed", type=float, default=1.0, help="语速 0.5-2.0")
    ap.add_argument("--clean", action="store_true", help="清洗 Markdown/结构标注后再合成")
    ap.add_argument("--pron", action="append", default=[], help='发音覆盖，可多次，如 --pron "处理/(chu3)(li3)"')
    args = ap.parse_args()

    token = args.token or os.environ.get("MINIMAX_API_KEY")
    if not token:
        raise SystemExit(
            "未找到 MiniMax API Key。请设置环境变量 MINIMAX_API_KEY，或用 --token 传入：\n"
            '  Windows PowerShell:  $env:MINIMAX_API_KEY="sk-..."\n'
            "  Windows cmd:         set MINIMAX_API_KEY=sk-...\n"
            '  macOS/Linux:         export MINIMAX_API_KEY="sk-..."'
        )

    with open(args.input, "r", encoding="utf-8") as f:
        text = f.read()
    if args.clean:
        text = clean_text(text)
    text = text.strip()
    if not text:
        raise SystemExit("文稿为空")

    chunks = split_chunks(text)
    print(f"共 {len(text)} 字符，分 {len(chunks)} 段合成...", file=sys.stderr)

    audio_parts = []
    for i, chunk in enumerate(chunks, 1):
        audio_parts.append(call_t2a(token, chunk, args))
        print(f"  段 {i}/{len(chunks)} 完成（{len(chunk)} 字符）", file=sys.stderr)

    with open(args.output, "wb") as f:
        for part in audio_parts:  # mp3 帧可直接顺序拼接
            f.write(part)
    size = os.path.getsize(args.output)
    print(f"✅ 已生成 {args.output}（{size/1024:.0f} KB）", file=sys.stderr)


if __name__ == "__main__":
    main()
