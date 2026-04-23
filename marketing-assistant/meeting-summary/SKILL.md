---
name: marketing-assistant
description: 会议录音转写与纪要生成 — 上传录音、ASR 转写、AI 生成结构化会议纪要
metadata:
  hermes:
    tags: [Meeting, ASR, Transcription, Summary, Marketing]
  lobehub:
    source: custom
---

# 会议记录总结助手

> 适用场景：会议录音文件 → 文字转写 → 结构化会议纪要

## 一、使用流程

```
录音文件 ──→ 上传文件服务器 ──→ ASR 转写 ──→ AI 生成会议纪要
  .mp3        upload.py        transcribe.py     Prompt 模板
  .wav
  .m4a ...
```

### 快速开始

```bash
# 1. 设置环境变量
export FILE_SERVER_API=https://your-file-server.com/api/upload
export ASR_API=https://your-asr-service.com/api/transcribe

# 2. 上传录音文件
python scripts/upload.py /path/to/meeting.mp3

# 3. 转写为文字
python scripts/transcribe.py /path/to/meeting.mp3 -o transcript.txt

# 4. 使用 AI 生成会议纪要（参考 references/meeting-summary-guide.md 中的 Prompt 模板）
```

## 二、环境变量

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `FILE_SERVER_API` | 文件服务器上传接口 | `https://fs.example.com/api/upload` |
| `ASR_API` | ASR 转写服务接口 | `https://asr.example.com/api/transcribe` |
| `DATABASE_URL` | 数据库连接地址 | `postgresql://user:pass@host:5432/dbname` |

## 三、支持的音频格式

mp3, wav, m4a, flac, ogg, wma, aac, webm, amr

## 四、脚本说明

### `scripts/upload.py`
- 校验文件存在性和格式
- 通过 `FILE_SERVER_API` 上传文件
- 返回文件 URL

### `scripts/transcribe.py`
- 支持本地文件和 URL 两种输入
- 支持同步和异步（轮询）两种 ASR 响应模式
- 转写完成后自动落库（`DATABASE_URL` 环境变量，自动建表）
- `-o` 参数指定输出文件，`--no-db` 跳过落库

## 五、会议纪要生成

📄 Prompt 模板与格式规范：[references/meeting-summary-guide.md](./references/meeting-summary-guide.md)

**输出包含**：
- 会议基本信息（主题、时间、参会人）
- 议题与讨论要点
- 决议清单
- 待办事项（含负责人、截止时间）

## 六、依赖

- `python3` >= 3.10
- `requests` — HTTP 请求（`pip install requests`）
- `sqlalchemy` + 数据库驱动 — 落库（`pip install sqlalchemy psycopg2-binary`，可选）

---

*文档版本：v1.0*
*创建日期：2026-04-22*
