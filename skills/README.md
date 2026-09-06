# Skills 目录规范

本目录是仓库中所有 Skill 的统一存放区。每个 Skill 是一个独立文件夹，可被支持 Skill 协议的 AI 代理（如 Kimi Work、Claude Code 等）直接加载。

## 标准结构

```
skills/
└── <skill-name>/                # 全小写、中划线命名，与 SKILL.md 的 name 字段一致
    ├── SKILL.md                 # 必需。技能入口：YAML frontmatter + 路由/流程/纪律
    ├── references/              # 可选。按需加载的详细文档（工作流、接口要点、清单）
    ├── scripts/                 # 可选。可执行脚本（Python/Shell），供流程节点调用
    └── assets/                  # 可选。模板、示例、静态资源
        └── templates/
```

## SKILL.md 约定

- 顶部必须包含 YAML frontmatter：

  ```yaml
  ---
  name: <skill-name>
  description: <一句话说明 + 触发条件/关键词，帮助代理做意图路由>
  ---
  ```

- 正文首屏给出**意图路由表**或**快速开始**，让代理一进文件就知道该读哪个 reference、跑哪个脚本。
- 长流程拆到 `references/` 下分文件存放，SKILL.md 只保留路由与主干纪律，避免单次加载过重。
- 引用目录内文件使用相对路径，保证 Skill 整体可搬运。

## 新增 Skill 步骤

1. `mkdir skills/<skill-name>`，按上方结构创建 `SKILL.md`。
2. 把详细流程放入 `references/`，可执行逻辑放入 `scripts/`，模板放入 `assets/templates/`。
3. 在根目录 `README.md` 的 "Skills 一览" 表中登记一行（名称、说明、入口链接）。

## 现有 Skills

- `podcast-studio` — AI 播客创作流水线（亲子播客 / 音乐播客 / MiniMax T2A 音频合成）。
