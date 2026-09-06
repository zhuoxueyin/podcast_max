#!/usr/bin/env python3
"""
MiniMax 语音合成脚本 (T2A)

将播客文稿合成为音频文件。

用法:
    python tts_minimax.py --text "要合成的文字" --out output.mp3
    python tts_minimax.py --file 文稿.txt --out output.mp3
    python tts_minimax.py --file 文稿.txt --voice male-qn-qingse --speed 1.0 --out output.mp3

本模块还提供 voice_design() —— MiniMax 音色设计:
    python voice_design.py --prompt "音色描述…" --preview "试听台词…" --out 试音.mp3

依赖:
    pip install requests

环境变量:
    MINIMAX_API_KEY    可选，设置后优先使用；否则使用脚本内默认 token
    MINIMAX_BASE_URL   可选，换 API 域名（如国内站 https://api.minimax.cn）
"""

import argparse
import os
import sys

try:
    import requests
except ImportError:
    print("缺少 requests 库，请先安装: pip install requests")
    sys.exit(1)

# Windows 控制台/GBK 下打印 emoji 等符号会 UnicodeEncodeError,统一兜底(不可编码字符替换为 ?)
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

# 默认 API Key（可被环境变量 MINIMAX_API_KEY 覆盖）
DEFAULT_API_KEY = "sk-cp-3m5CAUBk7Z9FpFvaExr0PbL5QkJeex2L9QC_WznrKNQDspzcPjKHpUwIyRTfYKebVyvRJC_tJvaz3E-6UVcpKGQ3Mw_8Ml1Yaq9R5vPOdHbxEuYU4IQc3Vo"

# API 域名（可被环境变量 MINIMAX_BASE_URL 覆盖，如国内站 https://api.minimax.cn）
_BASE_URL = os.environ.get("MINIMAX_BASE_URL", "https://api.minimaxi.com").rstrip("/")
T2A_URL = _BASE_URL + "/v1/t2a_v2"
VOICE_DESIGN_URL = _BASE_URL + "/v1/voice_design"
FILES_UPLOAD_URL = _BASE_URL + "/v1/files/upload"
VOICE_CLONE_URL = _BASE_URL + "/v1/voice_clone"
# 快速复刻所用模型(与正式合成一致)
CLONE_MODEL = "speech-2.8-hd"


def get_api_key():
    """优先取环境变量，否则用默认 token。"""
    return os.environ.get("MINIMAX_API_KEY", DEFAULT_API_KEY)


def synthesize(text, voice_id="male-qn-qingse", speed=1.0, vol=1.0, pitch=0.0,
               model="speech-2.8-hd", sample_rate=32000, bitrate=128000,
               fmt="mp3", channel=1, emotion=None, output_format="hex"):
    """
    调用 MiniMax T2A 接口合成音频。

    返回 (audio_hex, extra_info)，失败时抛出异常。
    """
    payload = {
        "model": model,
        "text": text,
        "stream": False,
        "voice_setting": {
            "voice_id": voice_id,
            "speed": int(speed),
            "vol": int(vol),
            "pitch": int(pitch),
        },
        "audio_setting": {
            "sample_rate": sample_rate,
            "bitrate": bitrate,
            "format": fmt,
            "channel": channel,
        },
        "output_format": output_format,
    }
    if emotion:
        payload["voice_setting"]["emotion"] = emotion

    headers = {
        "Authorization": f"Bearer {get_api_key()}",
        "Content-Type": "application/json",
    }

    resp = requests.post(T2A_URL, json=payload, headers=headers, timeout=120)
    resp.raise_for_status()
    result = resp.json()

    base_resp = result.get("base_resp", {})
    if base_resp.get("status_code") != 0:
        raise RuntimeError(
            f"MiniMax 接口返回错误: {base_resp.get('status_code')} {base_resp.get('status_msg')}"
        )

    data = result.get("data", {})
    audio = data.get("audio", "")
    if output_format == "url":
        # 返回的是 URL，直接下载
        audio_resp = requests.get(audio, timeout=120)
        audio_resp.raise_for_status()
        return audio_resp.content, result.get("extra_info", {})
    else:
        # hex 编码，转 bytes
        return bytes.fromhex(audio), result.get("extra_info", {})


def voice_design(prompt, preview_text, voice_id=None, aigc_watermark=False,
                 timeout=180):
    """
    调用 MiniMax 音色设计(Voice Design)接口,按自然语言描述生成专属音色。

    参数:
        prompt:         音色描述文本,如 "沉稳的知识型男声,语速偏慢,像讲故事的老师……"
        preview_text:   用于合成试听音频的文本,≤500 字符
        voice_id:       可选,自定义音色 ID;不传则服务端自动生成
        aigc_watermark: 是否在试听音频末尾加音频节奏标识(默认否)

    返回 (voice_id, trial_audio_bytes);失败抛出异常。
    生成的 voice_id 可直接用于 synthesize(text, voice_id=...) 做正式配音。
    """
    if len(preview_text) > 500:
        raise ValueError(f"preview_text 最长 500 字符,当前 {len(preview_text)}")

    payload = {
        "prompt": prompt,
        "preview_text": preview_text,
        "aigc_watermark": aigc_watermark,
    }
    if voice_id:
        payload["voice_id"] = voice_id

    headers = {
        "Authorization": f"Bearer {get_api_key()}",
        "Content-Type": "application/json",
    }
    resp = requests.post(VOICE_DESIGN_URL, json=payload, headers=headers,
                         timeout=timeout)
    resp.raise_for_status()
    result = resp.json()

    base_resp = result.get("base_resp", {})
    if base_resp.get("status_code") != 0:
        raise RuntimeError(
            f"MiniMax 音色设计返回错误: {base_resp.get('status_code')} "
            f"{base_resp.get('status_msg')}"
        )

    vid = result.get("voice_id", "")
    trial_hex = result.get("trial_audio", "")
    if not vid or not trial_hex:
        raise RuntimeError("MiniMax 音色设计响应缺少 voice_id/trial_audio")
    return vid, bytes.fromhex(trial_hex)


def upload_audio(path, purpose="voice_clone", timeout=300):
    """
    上传音频到 MiniMax 文件管理(POST /v1/files/upload),返回 file_id。

    参数:
        path:    本地音频路径(支持 mp3/m4a/wav, ≤20MB)
        purpose: 'voice_clone'  = 待复刻主音频(时长 10s~5min)
                 'prompt_audio' = 快速复刻示例音频(时长 <8s)
    返回 str 形式的 file_id(后续传给 clone_voice)。
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"音频不存在: {path}")
    if os.path.getsize(path) > 20 * 1024 * 1024:
        raise ValueError("音频超过 20MB,无法上传")
    headers = {"Authorization": f"Bearer {get_api_key()}"}
    fname = os.path.basename(path)
    with open(path, "rb") as f:
        resp = requests.post(FILES_UPLOAD_URL, headers=headers,
                             data={"purpose": purpose},
                             files={"file": (fname, f)}, timeout=timeout)
    resp.raise_for_status()
    result = resp.json()
    base = result.get("base_resp", {})
    if base.get("status_code") != 0:
        raise RuntimeError(
            f"上传失败: {base.get('status_code')} {base.get('status_msg')}")
    fid = result.get("file", {}).get("file_id", "")
    if not fid:
        raise RuntimeError("上传响应缺少 file_id")
    print(f"  ✓ 已上传 {os.path.basename(path)} ({purpose}) -> file_id={fid}")
    return fid


def clone_voice(file_id, voice_id, clone_prompt=None, text=None,
                model=CLONE_MODEL, need_noise_reduction=True,
                need_volume_normalization=True, aigc_watermark=False,
                timeout=600):
    """
    音色快速复刻(POST /v1/voice_clone)。

    参数:
        file_id:   待复刻主音频的 file_id(upload_audio 返回值)
        voice_id:  自定义音色 ID(8~256 位,首字符英文字母,仅字母数字_-,
                   末位不能是 -/_)。之后 T2A 直接以该 ID 合成,响应不回传它。
        clone_prompt: dict,形如 {"prompt_audio": <file_id>, "prompt_text": <转写>},
                      用于传入一段 <8s 的示例音频,提升相似度与稳定性。
        text:      可选试听文本(≤1000 字符);传入后服务端用克隆音色生成
                   demo_audio(会另收 T2A 费用)。此时 model 必填(已给默认)。
    返回完整响应 dict(含 base_resp / demo_audio / extra_info)。
    """
    payload = {
        "file_id": file_id,
        "voice_id": voice_id,
        "need_noise_reduction": need_noise_reduction,
        "need_volume_normalization": need_volume_normalization,
        "aigc_watermark": aigc_watermark,
    }
    if clone_prompt:
        payload["clone_prompt"] = clone_prompt
    if text:
        payload["text"] = text
        payload["model"] = model
    headers = {"Authorization": f"Bearer {get_api_key()}",
               "Content-Type": "application/json"}
    resp = requests.post(VOICE_CLONE_URL, json=payload, headers=headers,
                         timeout=timeout)
    resp.raise_for_status()
    result = resp.json()
    base = result.get("base_resp", {})
    if base.get("status_code") != 0:
        raise RuntimeError(
            f"快速复刻失败: {base.get('status_code')} {base.get('status_msg')}"
            f"\n提示: 1036 之类错误可查看该 status_msg;"
            f"如需 ASR 校验可给 text_validation 传入样本转写文本")
    return result


def save_audio(audio_bytes, output_path):
    """保存音频到文件。"""
    with open(output_path, "wb") as f:
        f.write(audio_bytes)
    print(f"✅ 音频已保存: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="MiniMax 语音合成")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", help="要合成的文字")
    group.add_argument("--file", help="要合成的文稿文件路径（txt/md）")
    parser.add_argument("--voice", default="male-qn-qingse", help="音色 ID")
    parser.add_argument("--speed", type=float, default=1.0, help="语速")
    parser.add_argument("--vol", type=float, default=1.0, help="音量")
    parser.add_argument("--pitch", type=float, default=0.0, help="音调")
    parser.add_argument("--emotion", default=None, help="情绪 (happy/sad 等)")
    parser.add_argument("--model", default="speech-2.8-hd", help="模型版本")
    parser.add_argument("--out", default="output.mp3", help="输出文件路径")
    parser.add_argument("--url", action="store_true", help="使用 url 输出格式")
    args = parser.parse_args()

    # 读取文本
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            text = f.read()
    else:
        text = args.text

    if not text.strip():
        print("错误: 文本为空")
        sys.exit(1)

    output_format = "url" if args.url else "hex"
    print(f"开始合成，文本长度 {len(text)} 字符...")
    audio, extra_info = synthesize(
        text,
        voice_id=args.voice,
        speed=args.speed,
        vol=args.vol,
        pitch=args.pitch,
        model=args.model,
        emotion=args.emotion,
        output_format=output_format,
    )
    save_audio(audio, args.out)

    if extra_info:
        print(f"  时长: {extra_info.get('audio_length', '?')}ms "
              f"| 字数: {extra_info.get('word_count', '?')} "
              f"| 采样率: {extra_info.get('audio_sample_rate', '?')}")


if __name__ == "__main__":
    main()
