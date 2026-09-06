# MiniMax 语音合成 T2A 接口文档

## 接口信息

- **请求 URL**：`https://api.minimaxi.com/v1/t2a_v2`（备用：`https://api-bj.minimaxi.com/v1/t2a_v2`）
- **请求方法**：`POST`
- **鉴权**：HTTP Header `Authorization: Bearer <API_KEY>`
- **Content-Type**：`application/json`

## 请求体参数

### 必填

| 参数 | 类型 | 说明 |
|---|---|---|
| `model` | string | `speech-2.8-hd` / `speech-2.8-turbo` / `speech-2.6-hd` / `speech-2.6-turbo` / `speech-02-hd` / `speech-02-turbo` 等 |
| `text` | string | 合成文本，< 10000 字符 |

### 常用可选

| 参数 | 说明 |
|---|---|
| `stream` | 是否流式，默认 false |
| `voice_setting` | 音色设置（voice_id/speed/vol/pitch/emotion） |
| `audio_setting` | 音频格式（sample_rate/bitrate/format/channel） |
| `pronunciation_dict` | 发音字典（多音字/拼音标注） |
| `output_format` | `hex`（默认）/ `url`（url 有效期 24 小时） |
| `subtitle_enable` | 是否开启字幕 |

### voice_setting

| 参数 | 说明 | 示例 |
|---|---|---|
| `voice_id` | 音色 ID | `male-qn-qingse` |
| `speed` | 语速 | 1 |
| `vol` | 音量 | 1 |
| `pitch` | 音调 | 0 |
| `emotion` | 情绪 | `happy` |

### audio_setting

| 参数 | 说明 | 示例 |
|---|---|---|
| `sample_rate` | 采样率 | 32000 |
| `bitrate` | 比特率 | 128000 |
| `format` | 格式 | `mp3` |
| `channel` | 声道数 | 1 |

## 文本特殊标记

- **停顿**：`<#x#>` 标记，x 为停顿时长（秒），范围 [0.01, 99.99]
- **行内发音**：英文小括号包裹拼音（带声调数字 1-5），如 `处理/(chu3)(li3)`
- **语气词标签**（仅 2.8 系列）：`(laughs)` `(chuckle)` `(coughs)` `(sighs)`
- **段落切换**：换行符

## 返回格式（非流式）

```json
{
  "data": { "audio": "<hex编码的audio>", "status": 2 },
  "extra_info": {
    "audio_length": 9900,
    "audio_sample_rate": 32000,
    "audio_size": 160323,
    "bitrate": 128000,
    "word_count": 52,
    "usage_characters": 26,
    "audio_format": "mp3",
    "audio_channel": 1
  },
  "base_resp": { "status_code": 0, "status_msg": "success" }
}
```

- `data.audio`：hex 编码的音频（或 URL，取决于 output_format）
- `base_resp.status_code`：0 表示成功

## 音色参考（亲子/儿童向）

完整系统音色清单见 MiniMax 官方（音色管理/FAQ system-voice-id）。中文常用系统音色（ID 内勿改空格与括号）：

| voice_id | 名称 | 适合角色 |
|---|---|---|
| `male-qn-qingse` | 青涩青年 | 少年/青年配角 |
| `male-qn-jingying` | 精英青年 | 沉稳主角（如阿慢） |
| `male-qn-badao` / `male-qn-daxuesheng` | 霸道青年 / 青年大学生 | 反派 / 猴群带头 |
| `female-shaonv` | 少女 | 活泼主角（如跳跳） |
| `female-tianmei` / `female-yujie` / `female-chengshu` | 甜美 / 御姐 / 成熟女性 | 甜美配角 / 反派女 / 温柔旁白 |
| `clever_boy` / `cute_boy` / `lovely_girl` | 聪明男童/可爱男童/萌萌女童 | 少年主角（如石猴）/ 孩童 |
| `Chinese (Mandarin)_Radio_Host` | 电台男主播 | 温暖磁性叙述 |
| `Chinese (Mandarin)_Male_Announcer` | 播报男声 | 正式报幕 |
| `Chinese (Mandarin)_Humorous_Elder` | 搞笑大爷 | 老年搞笑/沧桑角色 |
| `Chinese (Mandarin)_Kind-hearted_Elder` | 花甲奶奶 | 慈祥老年女性 |
| `Chinese (Mandarin)_Unrestrained_Young_Man` | 不羁青年 | 嚣张妖怪 |
| `Chinese (Mandarin)_Warm_Bestie` | 温暖闺蜜 | 知心姐姐声 |

> 试音规则：正式启用前用 1~2 句话实测；角色音色在系列大纲「角色卡」固化，一集之内不得换音色。

## 脚本使用

直接调用 `scripts/tts_minimax.py`，无需手动构造请求：

```bash
python scripts/tts_minimax.py --text "文稿内容" --voice male-qn-qingse --out output.mp3
```

或读取文件：

```bash
python scripts/tts_minimax.py --file 文稿.txt --out output.mp3
```

## 音色设计接口（Voice Design · 按角色特色定制音色）

系统音色不够贴角色时，用自然语言"设计"专属音色；拿到的 `voice_id` 与系统音色一样可直接用于 T2A，是"角色卡音色可换"的进阶通道。

- **接口**：`POST {MINIMAX_BASE_URL}/v1/voice_design`
  域名与 T2A 同站（默认 `https://api.minimaxi.com`；国内站设 `MINIMAX_BASE_URL=https://api.minimax.cn`）
- **鉴权**：`Authorization: Bearer <API_KEY>`

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `prompt` | string | 是 | 音色描述文本（自然语言） |
| `preview_text` | string | 是 | 试听音频合成文本，最长 500 字符 |
| `voice_id` | string | 否 | 自定义音色 ID；不传则自动生成（形如 `ttv-voice-…`） |
| `aigc_watermark` | bool | 否 | 试听末尾加节奏标识，默认 false |

### 响应

```json
{ "trial_audio": "<hex 音频>", "voice_id": "ttv-voice-20250607-xxxxxxxx",
  "base_resp": { "status_code": 0 } }
```

### 命令行用法（推荐）

```bash
python scripts/voice_design.py --prompt "慈祥的老爷爷声,干哑带笑,慢悠悠一句一顿" \
    --preview "孩子们好呀,爷爷给你们讲个老故事……" --out 试音_老仙翁.mp3
python scripts/voice_design.py --prompt "……" --preview "……" \
    --voice-id ttv-voice-xxx --out 试音_改版.mp3   # 指定 ID 重试/留档
```

### prompt 写法与工作流

- prompt 配方：`[性别/年龄/身份] + [气质] + [语气节奏] + [声线/参照] + [口头禅气息]`；preview_text 用该角色最典型的台词，才能听出"像不像"。
- 工作流闭环：`voice_design.py 生成 voice_id → 试听 → 回填项目根 00_角色音色表.md（常驻卡当前音色 + 机器读区）→ tts_cast --voice-map 全系列生效`。
- 费用：试听合成按字符计费（平台示价约 2 元/万字符，preview ≤500 字单次成本可忽略）。

## 声音复刻接口（Voice Clone · 用素材复刻特定人声音色）

系统音色与描述生成都够不着"某个具体声音"时（如复刻某版悟空原声），上传目标人声素材把声音"复刻"成自定义 voice_id，与系统音色同用法直接 T2A。材料要求：**主音频 10s~5min、≤20MB**；可选附一段 **<8s 示例音频** + 其转写文本以提升相似度。

### 步骤（对应官方 voice-cloning 系列三接口）

1. **上传主音频** → `POST {MINIMAX_BASE_URL}/v1/files/upload`（multipart，`purpose=voice_clone`）→ 返回 `file_id`
2. **（可选）上传示例音频** → 同接口 `purpose=prompt_audio`（<8s）→ `file_id`；复刻时以 `clone_prompt = { prompt_audio: file_id, prompt_text: <该段转写> }` 传入
3. **快速复刻** → `POST {MINIMAX_BASE_URL}/v1/voice_clone`
   - body：`file_id`、`voice_id`（8~256 位，首字符英文字母，仅字母数字 `_` `-`，末位不能是 `-`/`_`）、`need_noise_reduction`、`need_volume_normalization`
   - 可选：`text`（试听文本 ≤1000 字，传入则返回克隆音色 demo_audio，另收 T2A 费）+ `model`
4. 拿到 `voice_id` 后直接 `python scripts/tts_minimax.py --voice <voice_id>` 正式合成；回填项目 `00_角色音色表.md` → 全系列生效

> 接口实现见 `scripts/tts_minimax.py` 的 `upload_audio()` / `clone_voice()`；一键 CLI 见 `scripts/voice_clone.py`。

### 命令行用法（推荐）

```bash
# 主流程：素材 → 复刻 → 下载试听
python scripts/voice_clone.py --audio 孙悟空wav.wav --voice-id SunWuKong_Classic_20260906 \
    --text "俺老孙来也!" --out 试音_孙悟空复刻.mp3

# 可选：附一段 <8s 示例音频提升相似度（--prompt-text 为其转写，必填）
python scripts/voice_clone.py --audio main.wav --prompt-audio sample.wav \
    --prompt-text "示例台词……" --voice-id MyVoice01 --text "试听" --out a.mp3
```

### 注意事项

- 平台文档：上传复刻声音 / 上传示例声音 / 快速复刻见 MiniMax 官方 voice-cloning API（本 skill 已按三接口落地并实测通过）。
- **素材须已授权**：复刻会高度还原目标音色，公开商用/儿童节目严禁未授权明星与第三方人声；平台风控命中（`input_sensitive`）会直接失败。
- 主音频 <10s 脚本拒绝（质量差）；>20MB 上传失败；示例音频 ≥8s 不合规会告警。
- 语音段缓存按「音色指纹」命名，复刻 voice_id 换入权威表后，`tts_cast --voice-map` 重跑只重合成受影响角色段。

### 音色能力总览（本项目沉淀，按优先级 A→B→C）

| 通道 | 工具 | 输入 | 适用场景 | voice_id 形态 |
|---|---|---|---|---|
| A 现成系统音色 | `tts_minimax.py` | 系统 voice_id | 大多数角色/临时配角，够用即启用 | `male-qn-…` / `female-…` 等 |
| B 描述生成 | `voice_design.py` | 自然语言描述 + 典型台词 | 无合适现成、要"按人设造声"的常驻主角 | `ttv-voice-…` |
| C 声音复刻 | `voice_clone.py` | 已授权人声素材 | 要求"像某个具体声音"（如悟空原声） | 自定义，如 `SunWuKong_Classic_20260906` |

> 优先级：**能选现成不描述，能描述不复刻**；复刻只用于"就要这个声音"的场景。三通道产出的 voice_id 回填 `00_角色音色表.md` 后完全等价，全系列一致生效。

