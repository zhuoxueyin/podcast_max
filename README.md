# podcast_max

AI 播客创作技能仓库。收录可被 AI 编程/创作代理直接加载使用的 Skill（可复用工作流），覆盖播客选题、文稿生产、质检与音频合成全链路。

## 目录结构

```
podcast_max/
├── skills/                      # 所有 Skill 的统一存放区
│   ├── README.md                # Skill 目录规范与新增指引
│   └── podcast-studio/          # AI 播客创作流水线（亲子/音乐/TTS）
│       ├── SKILL.md             # 技能入口：意图路由 + 主干节点 + 执行纪律
│       ├── references/          # 分类型完整工作流
│       ├── scripts/             # 可执行脚本（MiniMax T2A 合成等）
│       └── assets/templates/    # 生产模板（大纲/提示词/质检/进度表）
└── README.md
```

## Skills 一览

| Skill | 说明 | 入口 |
|---|---|---|
| `podcast-studio` | AI 播客创作流水线：亲子播客（名著话本/童话改编/晚安故事）、音乐播客（OST盘点/歌手专题）、MiniMax T2A 文稿转音频 | [skills/podcast-studio/SKILL.md](skills/podcast-studio/SKILL.md) |

## 快速使用

```bash
# 文稿转音频（MiniMax T2A）
python skills/podcast-studio/scripts/minimax_tts.py 文稿.md -o E01.mp3
```

新增 Skill 请遵循 [skills/README.md](skills/README.md) 中的目录规范。
