#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全角色声音试听台生成器

按权威音色表,为每个"不同音色"合成一句试听台词,并生成一个 HTML
试听页(index.html)方便逐个对比。每集换/加了角色后跑一次即可快速验收。

用法:
    python voice_samples.py --voice-map 00_角色音色表.md \
        --script 01_文稿/E01_石猴出世.md --out-dir 试听_角色声音

    # 不带 --script:每个角色用一句通用自述,适合只听声音、没剧稿时
    python voice_samples.py --voice-map 00_角色音色表.md --out-dir 试听_角色声音

    # 附加对比卡(如 voice_design 定制版 vs 系统音色)
    python voice_samples.py --voice-map ... --script ... --out-dir ... \
        --extra-card "老猴(定制版)|../试音_voice_design示例_老猴.mp3|ttv-voice-xxx|设计版老猴,与系统音色对比"

规则:
    - 同一 voice_id 的多个角色名(如 石猴/悟空)只合成一次,标签合并显示;
    - 台词优先取剧稿中该角色最先出现的一句(自动在断句处截断);
    - 试听用与正式合成一致的引擎参数(语速/音量/模型,取自 tts_cast)。

依赖: requests; 与 tts_cast/tts_minimax 同目录。
"""
import argparse
import html
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import tts_minimax as t   # noqa: E402
import tts_cast as tc     # noqa: E402  (复用剧本/音色表解析与引擎参数)


def cut_at_sentence(text, limit):
    """去空白 → 超长则在最近断句处截断,避免半个句子难听。"""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    head = text[:limit]
    cut = 0
    for m in re.finditer(r"[。！？…?!;；]", head):
        cut = m.end()
    return text[:cut] + "……" if cut else text[:limit] + "……"


def first_line_by_role(script):
    """剧稿中每个角色最先出现的连续台词(去掉换行)。"""
    result = {}
    if not script:
        return result
    vm, items = tc.parse_script(script)
    cur_role, cur_text = None, []
    for it in items:
        if it[0] != "v":
            continue
        role, text = it[1], it[2]
        if role != cur_role:
            if cur_role and cur_text:
                result.setdefault(cur_role, " ".join(cur_text))
            cur_role, cur_text = role, []
        if text.strip():
            cur_text.append(text.strip())
    if cur_role and cur_text:
        result.setdefault(cur_role, " ".join(cur_text))
    return result


def main():
    ap = argparse.ArgumentParser(description="全角色声音试听台生成器")
    ap.add_argument("--voice-map", required=True,
                    help="权威角色音色表(00_角色音色表.md)")
    ap.add_argument("--script", default=None,
                    help="可选:剧稿 .md,用于抽取各角色典型台词与出场顺序")
    ap.add_argument("--out-dir", default="试听_角色声音", help="输出目录")
    ap.add_argument("--max-chars", type=int, default=72,
                    help="台词截断长度(默认 72 字,自动在断句处切)")
    ap.add_argument("--extra-card", action="append", default=[],
                    help="附加对照卡,格式: 标签|音频相对路径|voice_id|备注(可多次)")
    args = ap.parse_args()

    voice_map = tc.load_voice_map(args.voice_map)
    if not voice_map:
        print("❌ 音色表里没有读到映射。")
        sys.exit(1)

    lines = first_line_by_role(args.script) if args.script else {}
    roles_in_script = list(lines.keys())

    # 出场顺序:剧稿先出现的在前,未出场的按音色表顺序补在后面
    order = [r for r in roles_in_script if r in voice_map]
    order += [r for r in voice_map if r not in order]

    # 同一 voice 只合成一次;别名角色名合并展示
    voice_to_roles = {}
    for r in order:
        v = voice_map[r]
        voice_to_roles.setdefault(v, []).append(r)
    if not voice_to_roles:
        print("❌ 没有可试听的角色。")
        sys.exit(1)

    os.makedirs(args.out_dir, exist_ok=True)
    print(f"== 逐音色试听合成(共 {len(voice_to_roles)} 个音色)==")
    cards = []  # (label, mp3文件名, voice, line, note)
    for i, (voice, roles) in enumerate(voice_to_roles.items(), 1):
        main_role = roles[0]
        label = " / ".join(roles) if len(roles) > 1 else roles[0]
        note = "同音色别名" if len(roles) > 1 else ""
        raw = lines.get(main_role, "")
        line = cut_at_sentence(raw, args.max_chars) if raw else \
            f"我是「{main_role}」,这就是我的声音,你听出来是谁了吗?"
        safe = re.sub(r"[\\/:*?\"<>|\s]+", "_", label)  # 文件名安全化
        fname = f"{i:02d}_{safe}_{tc.voice_fp(voice)}.mp3"
        fpath = os.path.join(args.out_dir, fname)
        if os.path.exists(fpath) and os.path.getsize(fpath) > 1000:
            print(f"  ↺ [{i:02d}] {label} 已存在,跳过: {fname}")
            cards.append((label, fname, voice, line, note))
            continue
        print(f"  ▶ [{i:02d}] {label} <{voice}>  {len(line)}字 ...", flush=True)
        try:
            audio, _ = t.synthesize(line, voice_id=voice,
                                    speed=tc.SPEED, vol=tc.VOL,
                                    pitch=tc.PITCH, model=tc.MODEL)
            t.save_audio(audio, fpath)
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ {label} 失败: {e}")
            continue
        cards.append((label, fname, voice, line, note))

    for extra in args.extra_card:
        parts = [p.strip() for p in extra.split("|")]
        if len(parts) < 2:
            print(f"⚠️  --extra-card 格式应为 标签|音频路径|voice_id|备注: {extra}")
            continue
        label, path = parts[0], parts[1]
        voice = parts[2] if len(parts) > 2 else "?"
        note = parts[3] if len(parts) > 3 else ""
        cards.append((label, path, voice, "", note))

    # ---------------- 写 HTML 试听台 ----------------
    def esc(s):
        return html.escape(s, quote=True)

    rows = []
    for i, (label, fname, voice, line, note) in enumerate(cards, 1):
        line_html = f'<p class="line">“{esc(line)}”</p>' if line else ""
        note_html = f'<span class="note">{esc(note)}</span>' if note else ""
        rows.append(f"""
        <div class="card">
          <div class="head"><h3>{i:02d} · {esc(label)}</h3>{note_html}</div>
          <p class="meta">{esc(voice)}</p>{line_html}
          <audio controls preload="none" src="{esc(fname)}"></audio>
        </div>""")
    index = os.path.join(args.out_dir, "index.html")
    page = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>角色声音试听台</title>
<style>
  body {{ font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
         margin: 0; background: #f6f3ec; color: #333; }}
  header {{ background: #3f3a2e; color: #f7f1e3; padding: 22px 28px; }}
  header h1 {{ margin: 0 0 6px; font-size: 22px; }}
  header p {{ margin: 0; font-size: 13px; opacity: .8; }}
  main {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
         gap: 16px; padding: 20px 24px 60px; max-width: 1200px; margin: auto; }}
  .card {{ background: #fff; border-radius: 14px; padding: 16px 18px;
          box-shadow: 0 2px 8px rgba(0,0,0,.06); }}
  .head {{ display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }}
  .head h3 {{ margin: 0; font-size: 17px; }}
  .note {{ font-size: 12px; color: #b06a1a; background: #fdeeda;
          border-radius: 99px; padding: 2px 8px; white-space: nowrap; }}
  .meta {{ margin: 6px 0 0; font-size: 12px; color: #999;
          word-break: break-all; font-family: Consolas, monospace; }}
  .line {{ margin: 10px 0 6px; font-size: 14px; color: #555; line-height: 1.6; }}
  audio {{ width: 100%; height: 36px; }}
</style></head>
<body>
<header>
  <h1>🎧 角色声音试听台</h1>
  <p>来源: 00_角色音色表.md · 引擎 speech-2.8-hd(speed {tc.SPEED}/vol {tc.VOL}/pitch {tc.PITCH})
     · 台词节选自剧稿, 在断句处截断</p>
</header>
<main>{''.join(rows)}
</main></body></html>"""
    with open(index, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"\n✅ 已生成 {len(cards)} 个试听音频与试听台: {index}")
    print("   在浏览器打开 index.html(或 python -m http.server 后访问)逐个对比。")


if __name__ == "__main__":
    main()
