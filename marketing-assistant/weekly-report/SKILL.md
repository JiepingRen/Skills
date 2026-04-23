---
name: weekly-report
description: 销售周报生成 — 基于拜访记录自动汇总生成结构化销售周报
metadata:
  hermes:
    tags: [Sales, Weekly Report, CRM, Marketing]
  lobehub:
    source: custom
---

# 销售周报生成助手

> 适用场景：自动查询本周拜访记录，结合补充输入，生成结构化销售周报

## 一、使用流程

```
拜访记录(DB) ──→ 查询指定周期 ──→ 补充输入 ──→ Prompt 组装 ──→ LLM 生成 ──→ 周报草稿
visit_generations    按日期筛选      --text/--file    模板字段      调用 API     输出 & 落库
visit_raw_inputs
```

**依赖**: 本 skill 依赖 `visit-record` skill 产生的拜访记录数据（`visit_generations` 和 `visit_raw_inputs` 表）。

### 快速开始

```bash
# 1. 设置环境变量
export LLM_API=https://your-llm-service.com/api/chat
export DATABASE_URL=postgresql://user:pass@host:5432/dbname

# 2. 生成本周周报（自动查询拜访记录）
python scripts/generate.py --week 2026-04-13

# 3. 附带补充信息
python scripts/generate.py --week 2026-04-13 --text "本周还参加了行业展会..."

# 4. 自定义日期范围
python scripts/generate.py --start 2026-04-13 --end 2026-04-17

# 5. 仅预览 prompt
python scripts/generate.py --week 2026-04-13 --dry-run

# 6. 指定输出文件
python scripts/generate.py --week 2026-04-13 -o weekly-report.md
```

## 二、环境变量

| 变量名 | 说明 | 必填 | 示例 |
|--------|------|------|------|
| `LLM_API` | LLM 服务接口 | 是 | `https://llm.example.com/api/chat` |
| `DATABASE_URL` | 数据库连接地址 | 是（查询拜访记录） | `postgresql://user:pass@host:5432/dbname` |

## 三、脚本说明

### `scripts/generate.py`

**日期参数**：
- `--week YYYY-MM-DD` — 指定周一日期，自动计算到周日
- `--start` + `--end` — 自定义起止日期
- 不指定则默认本周

**补充输入**：
- `--text "文本"` — 额外信息（可多次）
- `--file path.txt` — 从文件读取额外信息

**其他参数**：
- `--visitor` — 按拜访人筛选拜访记录
- `--template` — 自定义周报模板（默认: `templates/default.json`）
- `-o` — 输出文件路径
- `--no-db` — 不保存周报生成记录
- `--dry-run` — 仅输出 prompt，不调用 LLM

**数据持久化**：
- 查询: `visit_generations` + `visit_raw_inputs`（来自 visit-record skill）
- 写入: `weekly_reports` 表（session_id, 周期, prompt, 响应, 草稿, 拜访记录数）

## 四、模板系统

默认模板: `templates/default.json`

**默认字段**: 汇报人、周报周期、本周拜访概览、重点进展、客户反馈汇总、竞品动态、问题与困难、下周计划、备注

## 五、参考文档

📄 周报生成策略与映射逻辑: [references/weekly-report-guide.md](./references/weekly-report-guide.md)

## 六、依赖

- `python3` >= 3.10
- `requests` — HTTP 请求（`pip install requests`）
- `sqlalchemy` + 数据库驱动 — 查询拜访记录 & 落库（`pip install sqlalchemy psycopg2-binary`）

---

*文档版本: v1.0*
*创建日期: 2026-04-22*
