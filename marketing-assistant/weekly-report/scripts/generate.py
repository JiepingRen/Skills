#!/usr/bin/env python3
"""周报生成脚本 — 查询拜访记录，结合补充输入，生成结构化销售周报

用法:
    python generate.py --week 2026-04-13
    python generate.py --week 2026-04-13 --text "本周还参加了行业展会..."
    python generate.py --start 2026-04-13 --end 2026-04-17
    python generate.py --week 2026-04-13 --dry-run
    python generate.py --week 2026-04-13 --template templates/custom.json -o report.md

环境变量:
    LLM_API:      LLM 服务接口地址
    DATABASE_URL: 数据库连接地址（用于查询拜访记录）
"""
import os
import sys
import json
import uuid
import argparse
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_TEMPLATE = SCRIPT_DIR.parent / "templates" / "default.json"


# ─── 参数解析 ───


def parse_args():
    parser = argparse.ArgumentParser(description="销售周报生成")
    parser.add_argument("--week", type=str, help="周报起始日期 (YYYY-MM-DD)，自动计算到该周周日")
    parser.add_argument("--start", type=str, help="自定义起始日期 (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="自定义结束日期 (YYYY-MM-DD)")
    parser.add_argument("--visitor", type=str, help="按拜访人筛选（对应拜访记录中的 visitor 字段）")
    parser.add_argument("--text", action="append", default=[], help="补充输入文本（可多次指定）")
    parser.add_argument("--file", action="append", default=[], help="补充输入文件（可多次指定）")
    parser.add_argument("--template", type=str, default=str(DEFAULT_TEMPLATE), help="周报模板路径")
    parser.add_argument("-o", "--output", help="输出文件路径", default=None)
    parser.add_argument("--no-db", action="store_true", help="跳过落库（不保存周报生成记录）")
    parser.add_argument("--dry-run", action="store_true", help="仅输出 prompt，不调用 LLM")
    return parser.parse_args()


def resolve_date_range(args) -> tuple[date, date]:
    """解析周报日期范围"""
    if args.start and args.end:
        return date.fromisoformat(args.start), date.fromisoformat(args.end)

    if args.week:
        start = date.fromisoformat(args.week)
        # 调整到周一
        start = start - timedelta(days=start.weekday())
        end = start + timedelta(days=6)
        return start, end

    # 默认: 本周
    today = date.today()
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    return start, end


# ─── 拜访记录查询 ───


def query_visit_records(start: date, end: date, visitor: str | None = None) -> list[dict]:
    """从数据库查询指定周期内的拜访记录"""
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        print("WARN: DATABASE_URL 未设置，无法查询拜访记录", file=sys.stderr)
        return []

    try:
        import sqlalchemy
    except ImportError:
        print("WARN: sqlalchemy 未安装，无法查询拜访记录", file=sys.stderr)
        return []

    try:
        engine = sqlalchemy.create_engine(db_url)
        with engine.connect() as conn:
            # 查询 visit_generations 表中指定时间段的生成记录
            query = """
                SELECT g.session_id, g.template_name, g.draft, g.created_at
                FROM visit_generations g
                WHERE g.created_at >= :start_date
                  AND g.created_at < :end_date
                ORDER BY g.created_at ASC
            """
            params = {
                "start_date": datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc),
                "end_date": datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc),
            }

            rows = conn.execute(sqlalchemy.text(query), params).fetchall()

            records = []
            for row in rows:
                session_id = row[0]

                # 查询该 session 的原始输入
                raw_query = """
                    SELECT source_type, content
                    FROM visit_raw_inputs
                    WHERE session_id = :session_id
                    ORDER BY id ASC
                """
                raw_rows = conn.execute(
                    sqlalchemy.text(raw_query), {"session_id": session_id}
                ).fetchall()

                records.append({
                    "session_id": session_id,
                    "draft": row[2],
                    "created_at": row[3].isoformat() if row[3] else None,
                    "raw_inputs": [{"source_type": r[0], "content": r[1]} for r in raw_rows],
                })

            return records

    except Exception as e:
        print(f"WARN: 查询拜访记录失败: {e}", file=sys.stderr)
        return []


# ─── 补充输入收集 ───


def collect_extra_inputs(args) -> list[str]:
    """收集补充输入"""
    extras = list(args.text)
    for fpath in args.file:
        try:
            extras.append(Path(fpath).read_text(encoding="utf-8").strip())
        except Exception as e:
            print(f"WARN: 读取补充文件失败 {fpath}: {e}", file=sys.stderr)
    return extras


# ─── 模板 & Prompt ───


def load_template(template_path: str) -> dict:
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR: 模板文件不存在: {template_path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: 模板 JSON 解析失败: {e}", file=sys.stderr)
        sys.exit(1)


def build_prompt(
    start: date,
    end: date,
    visit_records: list[dict],
    extra_inputs: list[str],
    template: dict,
) -> str:
    # 模板字段
    fields_desc = []
    for field in template.get("fields", []):
        req = "（必填）" if field.get("required") else "（选填）"
        fields_desc.append(f"- **{field['label']}** {req}: {field.get('description', '')}")
    fields_text = "\n".join(fields_desc)

    # 拜访记录
    if visit_records:
        records_parts = []
        for i, rec in enumerate(visit_records, 1):
            records_parts.append(f"### 拜访记录 {i} ({rec.get('created_at', '未知时间')})\n\n{rec['draft']}")
        records_text = "\n\n---\n\n".join(records_parts)
    else:
        records_text = "（本周期内无拜访记录）"

    # 补充输入
    extras_text = ""
    if extra_inputs:
        parts = [f"### 补充信息 {i}\n\n{text}" for i, text in enumerate(extra_inputs, 1)]
        extras_text = f"\n\n## 补充输入\n\n" + "\n\n".join(parts)

    prompt = f"""你是一位专业的销售管理助理。请根据以下拜访记录和补充信息，生成一份结构化的销售周报。

## 周报周期

{start.isoformat()} ~ {end.isoformat()}

## 要求

1. 从拜访记录中提取和汇总信息，填充周报各字段
2. 拜访概览需统计拜访次数、客户数量
3. 重点进展按客户/项目分条整理
4. 客户反馈和竞品信息需跨记录汇总去重
5. 下周计划基于本周拜访记录中的"后续计划"整理
6. 如某字段信息不足，标注"[待补充]"
7. 语言简洁专业

## 周报字段

{fields_text}

## 本周拜访记录

{records_text}{extras_text}

## 输出格式

# 销售周报

**汇报人**: ...
**周报周期**: {start.isoformat()} ~ {end.isoformat()}

## 本周拜访概览
- 拜访次数: X 次
- 覆盖客户: ...
| 日期 | 客户 | 对接人 | 主要议题 |
|------|------|--------|----------|

## 重点进展
1. **[客户名称]**: ...
2. ...

## 客户反馈汇总
...

## 竞品动态
...

## 问题与困难
...

## 下周计划
| 计划事项 | 目标客户 | 预期成果 |
|----------|----------|----------|

## 备注
...
"""
    return prompt


# ─── 数据库保存 ───


def save_weekly_report(session_id: str, start: date, end: date, template_name: str,
                       prompt: str, raw_response: str, draft: str, visit_count: int):
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        print("WARN: DATABASE_URL 未设置，跳过周报落库", file=sys.stderr)
        return

    try:
        import sqlalchemy
    except ImportError:
        print("WARN: sqlalchemy 未安装，跳过落库", file=sys.stderr)
        return

    now = datetime.now(timezone.utc)
    try:
        engine = sqlalchemy.create_engine(db_url)
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text("""
                CREATE TABLE IF NOT EXISTS weekly_reports (
                    id              SERIAL PRIMARY KEY,
                    session_id      VARCHAR(64),
                    week_start      DATE,
                    week_end        DATE,
                    template_name   VARCHAR(128),
                    visit_count     INTEGER,
                    prompt          TEXT,
                    raw_response    TEXT,
                    draft           TEXT,
                    created_at      TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            conn.execute(
                sqlalchemy.text("""
                    INSERT INTO weekly_reports
                        (session_id, week_start, week_end, template_name, visit_count, prompt, raw_response, draft, created_at)
                    VALUES
                        (:session_id, :week_start, :week_end, :template_name, :visit_count, :prompt, :raw_response, :draft, :created_at)
                """),
                {
                    "session_id": session_id,
                    "week_start": start,
                    "week_end": end,
                    "template_name": template_name,
                    "visit_count": visit_count,
                    "prompt": prompt,
                    "raw_response": raw_response,
                    "draft": draft,
                    "created_at": now,
                },
            )
            conn.commit()
        print("周报落库成功", file=sys.stderr)
    except Exception as e:
        print(f"WARN: 周报落库失败: {e}", file=sys.stderr)


# ─── LLM 调用 ───


def call_llm(prompt: str) -> tuple[str, str]:
    api_url = os.environ.get("LLM_API", "").strip()
    if not api_url:
        print("ERROR: 环境变量 LLM_API 未设置", file=sys.stderr)
        print("  export LLM_API=https://your-llm-service.com/api/chat", file=sys.stderr)
        sys.exit(1)

    try:
        resp = requests.post(api_url, json={"prompt": prompt, "max_tokens": 4096}, timeout=120)
    except requests.RequestException as e:
        print(f"ERROR: LLM 请求失败: {e}", file=sys.stderr)
        sys.exit(1)

    if not resp.ok:
        print(f"ERROR: LLM 请求失败 (HTTP {resp.status_code})", file=sys.stderr)
        print(resp.text, file=sys.stderr)
        sys.exit(1)

    raw_response = resp.text
    try:
        data = resp.json()
        draft = (
            data.get("text")
            or data.get("content")
            or data.get("data", {}).get("text")
            or data.get("choices", [{}])[0].get("message", {}).get("content")
            or data.get("choices", [{}])[0].get("text")
        )
    except (json.JSONDecodeError, IndexError, AttributeError):
        draft = None

    if not draft:
        print("WARN: 无法从 LLM 响应中提取文本，返回原始响应", file=sys.stderr)
        draft = raw_response

    return raw_response, draft


# ─── 输出 ───


def output_draft(draft: str, output_file: str | None):
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(draft)
        print(f"周报已保存: {output_file}", file=sys.stderr)
    else:
        print(draft)


# ─── 主流程 ───


def main():
    args = parse_args()
    session_id = uuid.uuid4().hex[:16]

    # 1. 解析日期范围
    start, end = resolve_date_range(args)
    print(f"周报周期: {start} ~ {end} (session: {session_id})", file=sys.stderr)

    # 2. 查询拜访记录
    visit_records = query_visit_records(start, end, args.visitor)
    print(f"查询到 {len(visit_records)} 条拜访记录", file=sys.stderr)

    # 3. 收集补充输入
    extra_inputs = collect_extra_inputs(args)
    if extra_inputs:
        print(f"收集到 {len(extra_inputs)} 条补充输入", file=sys.stderr)

    # 4. 加载模板
    template = load_template(args.template)
    template_name = template.get("name", Path(args.template).stem)

    # 5. 构建 prompt
    prompt = build_prompt(start, end, visit_records, extra_inputs, template)

    # 6. dry-run
    if args.dry_run:
        print("=== DRY RUN: Prompt ===", file=sys.stderr)
        print(prompt)
        return

    # 7. 调用 LLM
    raw_response, draft = call_llm(prompt)

    # 8. 落库
    if not args.no_db:
        save_weekly_report(session_id, start, end, template_name, prompt, raw_response, draft, len(visit_records))

    # 9. 输出
    output_draft(draft, args.output)
    print(f"周报生成完成 (session: {session_id})", file=sys.stderr)


if __name__ == "__main__":
    main()
