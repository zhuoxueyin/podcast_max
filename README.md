# podcast_max

AI 播客创作技能仓库。收录可被 AI 编程/创作代理直接加载使用的 Skill（可复用工作流），覆盖播客选题、文稿生产、质检与音频合成全链路。

## 目录结构

```
podcast_max/
├── skills/                      # 所有 Skill 的统一存放区
│   ├── README.md                # Skill 目录规范与新增指引
│   ├── podcast-studio/          # AI 播客创作流水线（基础版）
│   │   └── SKILL.md             # 技能入口：意图路由 + 主干节点 + 执行纪律
│   └── podcast-studio-wb/       # AI 播客创作流水线（增强版·全角色配音/BGM/SFX/复刻）
│       ├── SKILL.md             # 技能入口：意图路由 + 主干节点 + 执行纪律
│       ├── references/          # 亲子/音乐工作流 + 安审 + MiniMax 接口文档
│       ├── scripts/             # T2A / 分角色配音 / BGM/SFX / 音色设计 / 声音复刻
│       └── assets/templates/    # 生产模板（大纲/文稿/质检/进度表）
└── README.md
```

## Skills 一览

| Skill | 说明 | 入口 |
|---|---|---|
| `podcast-studio` | AI 播客创作流水线（基础版）：亲子播客（名著话本/童话改编/晚安故事）、音乐播客（OST盘点/歌手专题）、MiniMax T2A 文稿转音频 | [skills/podcast-studio/SKILL.md](skills/podcast-studio/SKILL.md) |
| `podcast-studio-wb` | AI 播客创作流水线（增强版）：在基础能力上增加 角色音色三通道（现成→描述生成→声音复刻）、整集全角色配音（`tts_cast.py` + 权威音色表 voice-map）、BGM/SFX 自动混音、安审红线与判例库 | [skills/podcast-studio-wb/SKILL.md](skills/podcast-studio-wb/SKILL.md) |

## 快速使用

```bash
# 文稿转音频（MiniMax T2A）——基础版
python skills/podcast-studio/scripts/minimax_tts.py 文稿.md -o E01.mp3

# 文稿转音频（MiniMax T2A）——增强版 podcast-studio-wb
python skills/podcast-studio-wb/scripts/tts_minimax.py 文稿.md -o E01.mp3

# 整集全角色配音 + BGM/SFX 混音（增强版，voice-map 指向项目权威音色表）
python skills/podcast-studio-wb/scripts/tts_cast.py --voice-map 00_角色音色表.md 分集文稿.md
```

新增 Skill 请遵循 [skills/README.md](skills/README.md) 中的目录规范。
