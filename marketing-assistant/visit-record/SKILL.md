---
name: visit-record
description: 拜访记录生成 — 基于多源输入（微信、邮件等）自动生成结构化拜访记录草稿
metadata:
  hermes:
    tags: [Sales, Visit, CRM, Marketing]
  lobehub:
    source: custom
---

# 拜访记录生成助手

> 适用场景：销售人员基于微信消息、邮件、备忘录等多源输入，快速生成结构化拜访记录

## 一、使用流程

```
多源输入 ──→ 收集 & 落库 ──→ Prompt 组装 ──→ LLM 生成 ──→ 拜访记录草稿
  微信         原始数据        模板字段        调用 API       输出 & 落库
  邮件
  备忘录 ...
```

### 快速开始

```bash
# 1. 设置环境变量
export LLM_API=https://your-llm-service.com/api/chat
export DATABASE_URL=postgresql://user:pass@host:5432/dbname  # 可选

# 2. 单条文本输入
python scripts/generate.py --text "今天去拜访了XX公司的张总，聊了新产品合作..." --source-type wechat

# 3. 多源输入
python scripts/generate.py \
  --text "微信聊天内容..." --source-type wechat \
  --file email.txt --source-type wechat email

# 4. 从管道读取
cat notes.txt | python scripts/generate.py --stdin --source-type note

# 5. 仅预览 prompt（不调用 LLM）
python scripts/generate.py --text "..." --dry-run

# 6. 指定输出文件和自定义模板
python scripts/generate.py --text "..." --template templates/custom.json -o draft.md
```

## 二、环境变量

| 变量名 | 说明 | 必填 | 示例 |
|--------|------|------|------|
| `LLM_API` | LLM 服务接口 | 是 | `https://llm.example.com/api/chat` |
| `DATABASE_URL` | 数据库连接地址 | 否 | `postgresql://user:pass@host:5432/dbname` |

## 三、脚本说明

### `scripts/generate.py`

**输入方式**（可组合使用）：
- `--text "文本"` — 直接输入（可多次指定）
- `--file path.txt` — 从文件读取（可多次指定）
- `--stdin` — 从管道读取
- `--source-type` — 按输入顺序指定来源类型：wechat, email, note, call, other

**其他参数**：
- `--template` — 指定拜访记录模板（默认: `templates/default.json`）
- `-o` — 输出文件路径
- `--no-db` — 跳过所有落库操作
- `--dry-run` — 仅输出组装好的 prompt，不调用 LLM

**数据持久化**：
- `visit_raw_inputs` 表 — 保存原始输入（session_id 关联）
- `visit_generations` 表 — 保存 prompt、LLM 原始响应、生成草稿

## 四、模板系统

默认模板：`templates/default.json`

模板定义拜访记录的字段结构，包括字段名、标签、是否必填、描述。可自定义模板放在 `templates/` 目录下。

**默认字段**：客户名称、拜访时间、拜访人、客户对接人、拜访目的、沟通要点、客户反馈、竞品信息、后续计划、备注

## 五、参考文档

📄 Prompt 模板与提取策略：[references/visit-record-guide.md](./references/visit-record-guide.md)

## 六、依赖

- `python3` >= 3.10
- `requests` — HTTP 请求（`pip install requests`）
- `sqlalchemy` + 数据库驱动 — 落库（`pip install sqlalchemy psycopg2-binary`，可选）

---

*文档版本：v1.0*
*创建日期：2026-04-22*
