#!/usr/bin/env python3
"""
MiniMax 音色设计工具 (Voice Design)

按角色特色"造"一个专属音色:用一句话描述想要的声音,
服务端生成可复用的 voice_id,并返回试听音频。

用法:
    python voice_design.py --prompt "沉稳的老爷爷声,说话慢悠悠,带着笑意" \
        --preview "孩子们好呀,爷爷给你们讲个老故事……" --out 试音_老仙翁.mp3

    python voice_design.py --prompt-file prompt.txt --out 试音.mp3
        # --prompt 也可从文件读取;--preview 最长 500 字,超长自动截断

    python voice_design.py --prompt "……" --preview "……" \
        --voice-id ttv-voice-xxx --out 试音_改版.mp3
        # 指定 voice-id 重试/留档(同 ID 重复调用一般会重新生成该 ID 的音色)

设计流程(与角色音色表联动):
    1. 构思角色声音:年龄/性别 + 气质 + 语气节奏 + 口头禅。
    2. 跑本脚本拿 voice_id + 试听 mp3。
    3. 用 tts_minimax.py 拿该 voice_id 合成该角色的典型长台词再听一遍。
    4. 满意 → 把 voice_id 回填到项目根 `00_角色音色表.md`
       (常驻角色卡「当前音色」列 + 机器读区对应 key);
       不满 → 改 prompt 再来,或换系统音色候选。
    5. 正式合成时带 `--voice-map 00_角色音色表.md` 即全系列生效。

环境变量:MINIMAX_API_KEY / MINIMAX_BASE_URL(默认 https://api.minimaxi.com;
国内站可用 MINIMAX_BASE_URL=https://api.minimax.cn)。
费用:按 preview_text 字符计费(试听合成),见平台计费页。
"""
import argparse
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import tts_minimax as t  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="MiniMax 音色设计(Voice Design)")
    ap.add_argument("--prompt", default=None,
                    help="音色描述(必填,或改用 --prompt-file)")
    ap.add_argument("--prompt-file", default=None,
                    help="音色描述文本文件路径")
    ap.add_argument("--preview", default=None,
                    help="试听合成文本(≤500 字;默认给一句通用台词)")
    ap.add_argument("--voice-id", default=None,
                    help="可选:自定义音色 ID(不传由服务端生成)")
    ap.add_argument("--out", default="试音_voice_design.mp3", help="试听音频输出")
    args = ap.parse_args()

    prompt = args.prompt
    if args.prompt_file:
        with open(args.prompt_file, "r", encoding="utf-8") as f:
            prompt = f.read().strip()
    if not prompt:
        ap.error("请提供 --prompt 或 --prompt-file")
        sys.exit(1)

    preview = (args.preview or "小朋友们,欢迎收听《乌龟兔西游历险记》!我是……")
    if len(preview) > 500:
        print(f"⚠️  preview_text 超长({len(preview)}字),自动截断到 500 字")
        preview = preview[:500]

    print("== 正在设计音色 ==")
    print(f"  描述: {prompt[:200]}{'…' if len(prompt) > 200 else ''}")
    print(f"  试听文本 {len(preview)} 字 | 自定义 ID: {args.voice_id or '(自动生成)'}")
    try:
        voice_id, audio = t.voice_design(
            prompt, preview, voice_id=args.voice_id)
    except Exception as e:  # noqa: BLE001
        print(f"❌ 音色设计失败: {e}")
        sys.exit(1)

    t.save_audio(audio, args.out)
    print(f"\n🎙 生成音色 voice_id = {voice_id}")
    print("   复制该 ID 到项目根 `00_角色音色表.md`:")
    print("     ① 常驻角色卡「当前音色」列   ② 机器读区 0. 对应 key")
    print(f"   再用它合成整句确认: python tts_minimax.py --text \"……\" "
          f"--voice {voice_id} --out 试听2.mp3")


if __name__ == "__main__":
    main()
