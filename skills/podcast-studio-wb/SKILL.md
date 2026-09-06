---
name: podcast-studio-wb
description: 播客内容创作流水线技能（增强版），支持亲子播客（名著改编/童话洗稿）与音乐播客（音乐故事）两类创作 workflow。当用户提出播客创作需求（如"做一期西游记儿童故事""洗稿一篇安徒生童话""写一期某歌手的音乐播客""把文稿转成音频"）时使用。内置意图识别路由、可复用流程节点、儿童内容安审规则、MiniMax 语音合成、全角色分集配音（tts_cast）、以及角色音色三通道（现成→描述生成→声音复刻）。
---

# 播客创作工作台（Podcast Studio WB）

## 概述

本技能将播客创作沉淀为可复用的流水线，支持**多种创作类型**。核心能力：

1. **意图识别**：根据用户输入自动路由到对应的创作 workflow（亲子播客 / 音乐播客 / 纯 TTS 转音频）。
2. **流程节点复用**：不同 workflow 共享同一套底层节点（选题 → 文稿 → 质检 → 音频生成 → 交付），差异只在各节点的具体规则。
3. **安审合规**：儿童内容 12 条安审红线 + 判例库，音乐播客准确性核实规则。
4. **音频生成**：内置 MiniMax T2A 语音合成脚本，把文稿直接合成音频。
5. **角色音色三通道**：取角色音色按优先级 ① 现成系统音色 → ② 描述生成（Voice Design，`scripts/voice_design.py`）→ ③ 声音复刻（Voice Clone，`scripts/voice_clone.py`，需已授权素材）；voice_id 回填项目权威音色表即贯穿全系列。

## 意图识别（Workflow 路由）

收到创作需求后，先判断创作类型，再进入对应 workflow：

| 识别信号 | 创作类型 | 进入 workflow | 详细说明 |
|---|---|---|---|
| 名著/长篇故事连载（西游记、三国、水浒…） | 亲子播客·长篇改编 | `references/workflow_qinzi.md` 模式A | 需分集大纲 |
| 童话/短篇故事（安徒生、格林、伊索…） | 亲子播客·短篇洗稿 | `references/workflow_qinzi.md` 模式B | 一篇一集，需洗稿 |
| 音乐/歌曲/歌手/OST/盘点 | 音乐播客 | `references/workflow_music.md` | 需版权选曲 |
| 已有文稿，只要"转音频/配音/TTS" | 纯音频生成 | 直接走"音频生成"节点 | 跳过创作环节 |

**路由规则**：
- 关键词含"名著/连载/分集/第X集/西游记/三国/封神" → 亲子·长篇改编
- 关键词含"童话/睡前/晚安/安徒生/格林/寓言/洗稿" → 亲子·短篇洗稿
- 关键词含"歌曲/音乐/歌手/OST/金曲/盘点/港乐" → 音乐播客
- 关键词含"转音频/合成/配音/朗读/TTS/有声" → 纯音频生成

**无法判断时的默认行为**：优先向用户确认创作类型（一句话即可），同时给出候选判断。

## 共享流程节点

所有 workflow 都由以下可复用节点组成（顺序可调，节点可跳过）：

```
[选题] → [素材获取] → [文稿生成] → [质检合规] → [音频生成] → [交付管理]
```

各节点的通用说明：

1. **选题**：确定创作对象 + 定位（年龄/受众）。亲子播客需定年龄（默认 6~12 岁），音乐播客需定栏目/类别。
2. **素材获取**：亲子播客获取原著/原文（注意公版 vs 译文版权）；音乐播客获取歌曲信息 + 版权 fee。
3. **文稿生成**：按模板量产。亲子播客按"开场+正文+收尾"模板；音乐播客按"钩子+事件还原+歌曲讲解"模板。详见 `assets/templates/`。
4. **质检合规**：亲子播客过安审 12 条；音乐播客做准确性质检（杜绝幻觉）+ 多音字处理。详见 `references/shenhe_rules.md`。
5. **音频生成**：用 MiniMax T2A 合成音频。详见 `scripts/tts_minimax.py`。
6. **交付管理**：进度表 + 落盘存档，支持中断续作。

## 快速开始

### 亲子播客（长篇改编）

1. 读 `references/workflow_qinzi.md` 了解完整流程
2. 先出「全书分集大纲」让用户确认，再逐集写文稿
3. 每集文稿过安审（`references/shenhe_rules.md`）
4. 新角色定音色按「现成 → 描述生成 → 复刻」三通道（`scripts/voice_design.py` / `scripts/voice_clone.py`），voice_id 回填项目 `00_角色音色表.md`
5. 音频合成：整集分角色用 `scripts/tts_cast.py`（带 `--voice-map 00_角色音色表.md`），单段/试音用 `scripts/tts_minimax.py`

### 亲子播客（短篇洗稿）

1. 读原文，只提取情节链（思想层）
2. 用海螺风格原创重写（不贴译本文字，规避译文版权）
3. 过安审，红线内容按"儿童保护 > 文学性 > 原著还原"重构
4. 需要音频时调用 `scripts/tts_minimax.py`

### 音乐播客

1. 读 `references/workflow_music.md`
2. 选题 + 版权选曲（查 fee）
3. 文稿（钩子≤100字 + 事件还原 + 歌曲讲解）
4. 准确性质检 + 多音字替换
5. 封面（AI 生图 + 程序叠字） + 音频生成

## 资源索引

- `references/workflow_qinzi.md` — 亲子播客完整 workflow（长篇改编 + 短篇洗稿两种模式）
- `references/workflow_music.md` — 音乐播客完整 workflow
- `references/shenhe_rules.md` — 安审 12 条清单 + 判例库 + 版权红线
- `references/minimax_api.md` — MiniMax T2A / 音色设计 / 声音复刻 接口文档
- `scripts/tts_minimax.py` — MiniMax T2A 语音合成（单段合成 / 角色试音）
- `scripts/tts_cast.py` — 角色化剧本稿 → 分角色配音 + BGM/SFX 自动混音
- `scripts/voice_design.py` — 按声音描述生成专属音色（通道 B）
- `scripts/voice_clone.py` — 用已授权音频素材复刻声音（通道 C）
- `scripts/make_sfx.py` — 程序化合成 BGM/SFX 素材
- `scripts/quality_check.py` — 文稿质检脚本（字数/标点/多音字）
- `assets/templates/` — 各类文稿模板（亲子开场收尾、音乐播客结构等）
