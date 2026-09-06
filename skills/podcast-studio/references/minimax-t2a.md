# MiniMax T2A 语音合成 · 接口要点与播讲文本规范

> 官方文档：https://platform.minimaxi.com/docs/api-reference/speech-t2a-http
> 脚本：`scripts/minimax_tts.py`（已封装分段、重试、hex 解码、文件拼接）

## 接口速查

- **Endpoint**：`POST https://api.minimaxi.com/v1/t2a_v2`（备用 `https://api-bj.minimaxi.com/v1/t2a_v2`）
- **鉴权**：`Authorization: Bearer <token>`。代码不内置任何密钥，必须通过环境变量 `MINIMAX_API_KEY` 或 `--token` 参数提供（优先级：`--token` > 环境变量）

**环境变量设置（Windows / macOS 通用）**：

| 平台 | 当前会话 | 永久生效 |
|---|---|---|
| Windows PowerShell | `$env:MINIMAX_API_KEY="sk-..."` | `setx MINIMAX_API_KEY "sk-..."`（新开窗口生效） |
| Windows cmd | `set MINIMAX_API_KEY=sk-...` | 同上（`setx`） |
| macOS / Linux | `export MINIMAX_API_KEY="sk-..."` | 写入 `~/.zshrc` 或 `~/.bash_profile` 后 `source` |

> 密钥只存放在本机环境变量中，不要写入代码、文档或聊天记录。
- **单次限制**：text < 10000 字符；> 3000 字符建议流式。脚本默认按 ~2800 字符分段后拼接 mp3
- **推荐模型**：`speech-2.8-hd`（高质量，支持语气词标签）；要快用 `speech-2.8-turbo`
- **返回**：非流式默认 `output_format=hex`，`data.audio` 为 hex 编码音频，需解码落盘；`base_resp.status_code=0` 为成功

## 请求体关键参数

```json
{
  "model": "speech-2.8-hd",
  "text": "要合成的文本",
  "stream": false,
  "voice_setting": {
    "voice_id": "male-qn-qingse",
    "speed": 1, "vol": 1, "pitch": 0,
    "emotion": "happy"
  },
  "pronunciation_dict": { "tone": ["处理/(chu3)(li3)"] },
  "audio_setting": { "sample_rate": 32000, "bitrate": 128000, "format": "mp3", "channel": 1 },
  "subtitle_enable": false
}
```

- `voice_id`：按栏目定位选音色（如亲子栏目选温暖亲和音色，音乐电台选沉稳主播音色）；不确定时先用默认试听一条给用户确认，再批量
- `emotion`：happy / sad / angry / calm 等，亲子故事可用 happy，深夜电台用 calm
- `language_boost`：中文内容设 `Chinese`；粤语内容 `Chinese,Yue`

## 播讲文本规范（喂给 TTS 前的文本处理）

1. **停顿控制**：两个可发音文本之间插 `<#x#>`，x 为秒（0.01-99.99）。章节切换建议 `<#1.2#>`，钩子前建议 `<#0.6#>`。不可连续多个停顿标记
2. **行内发音替换**：多音字可直接在文本内覆盖，如 `这(hé)平不是(huò)面`、`处理/(chu3)(li3)`（拼音带声调数字 1-5，英文小括号）
3. **批量替换优先**：高频多音字优先改近义词（如 港乐→香港歌坛），零星的用行内标注或 `pronunciation_dict`
4. **语气词标签**（仅 2.8 系列）：`(laughs)` `(sighs)` `(gasps)` `(breath)` `(humming)` 等，插在括号位置生效；儿童故事可少量点缀，不要滥用
5. **清洗文稿**：去掉 Markdown 标记、制作标注、安审说明、表情符号、`【①开场】`类结构标签后再合成——只保留播讲正文（脚本的 `--clean` 模式已内置常规清洗）
6. **年份读法**：播讲文稿中的年份按中文口语写（"一九八六年"而非"1986年"），避免 TTS 念成数字串

## 脚本用法

```bash
# 基础：文稿文件 → mp3（自动分段拼接）
python scripts/minimax_tts.py 文稿.md -o E01.mp3

# 指定音色/情绪/语速
python scripts/minimax_tts.py 文稿.md -o E01.mp3 --voice male-qn-qingse --emotion happy --speed 1.0

# 清洗模式（去 Markdown/标注后再合成）
python scripts/minimax_tts.py 文稿.md -o E01.mp3 --clean

# 多音字词典
python scripts/minimax_tts.py 文稿.md -o E01.mp3 --pron "处理/(chu3)(li3)" --pron "港乐/(gang1)(yue4)"
```

批量量产建议：先合成 1 集样音给用户确认音色与语速，确认后再批量跑全系列。
