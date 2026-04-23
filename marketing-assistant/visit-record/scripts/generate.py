#!/usr/bin/env python3
"""拜访记录生成脚本 — 基于多源输入生成结构化拜访记录草稿

用法:
    python generate.py --text "微信聊天内容..." --source-type wechat
    python generate.py --file email.txt --source-type email
    python generate.py --text "内容1" --text "内容2" --source-type wechat email
    cat notes.txt | python generate.py --stdin --source-type note
    python generate.py --text "..." --dry-run
    python generate.py --text "..." --template templates/custom.json -o draft.md

环境变量:
    LLM_API:      LLM 服务接口地址
    DATABASE_URL: 数据库连接地址 (可选)
"""
import os
import sys
import json
import uuid
import argparse
from datetime import datetime, timezone
from pathlib import Path

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_TEMPLATE = SCRIPT_DIR.parent / "templates" / "default.json"
GUIDE_PATH = SCRIPT_DIR.parent / "references" / "visit-record-guide.md"

SOURCE_TYPES = ("wechat", "email", "note", "call", "other")


# ─── 参数解析 ───


def parse_args():
    parser = argparse.ArgumentParser(description="拜访记录生成")
    parser.add_argument("--text", action="append", default=[], help="直接输入文本（可多次指定）")
    parser.add_argument("--file", action="append", default=[], help="从文件读取输入（可多次指定）")
    parser.add_argument("--stdin", action="store_true", help="从 stdin 读取输入")
    parser.add_argument(
        "--source-type", nargs="+", default=[],
        help=f"输入来源类型，与 --text/--file 按顺序对应。可选: {', '.join(SOURCE_TYPES)}",
    )
    parser.add_argument("--template", type=str, default=str(DEFAULT_TEMPLATE), help="拜访记录模板路径")
    parser.add_argument("-o", "--output", help="输出文件路径", default=None)
    parser.add_argument("--no-db", action="store_true", help="跳过所有落库操作")
    parser.add_argument("--dry-run", action="store_true", help="仅输出 prompt，不调用 LLM")
    return parser.parse_args()


# ─── 输入收集 ───


def collect_inputs(args) -> list[dict]:
    """收集所有输入源，返回 [{source_type, content}]"""
    inputs = []
    source_types = args.source_type

    # --text 输入
    for i, text in enumerate(args.text):
        st = source_types[i] if i < len(source_types) else "other"
        inputs.append({"source_type": st, "content": text.strip()})

    # --file 输入
    offset = len(args.text)
    for i, fpath in enumerate(args.file):
        idx = offset + i
        st = source_types[idx] if idx < len(source_types) else "other"
        try:
            content = Path(fpath).read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            print(f"ERROR: 文件不存在: {fpath}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"ERROR: 读取文件失败 {fpath}: {e}", file=sys.stderr)
            sys.exit(1)
        inputs.append({"source_type": st, "content": content})

    # --stdin 输入
    if args.stdin:
        idx = offset + len(args.file)
        st = source_types[idx] if idx < len(source_types) else "other"
        content = sys.stdin.read().strip()
        if content:
            inputs.append({"source_type": st, "content": content})

    if not inputs:
        print("ERROR: 未提供任何输入，请使用 --text、--file 或 --stdin", file=sys.stderr)
        sys.exit(1)

    return inputs


# ─── 模板加载 ───


def load_template(template_path: str) -> dict:
    """加载拜访记录模板"""
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR: 模板文件不存在: {template_path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: 模板 JSON 解析失败: {e}", file=sys.stderr)
        sys.exit(1)


# ─── Prompt 构建 ───


def build_prompt(inputs: list[dict], template: dict) -> str:
    """基于输入和模板构建 LLM prompt"""
    # 模板字段描述
    fields_desc = []
    for field in template.get("fields", []):
        req = "（必填）" if field.get("required") else "（选填）"
        fields_desc.append(f"- **{field['label']}** {req}: {field.get('description', '')}")
    fields_text = "\n".join(fields_desc)

    # 原始输入
    source_label = {"wechat": "微信消息", "email": "邮件", "note": "备忘录", "call": "通话记录", "other": "其他"}
    inputs_text = []
    for i, inp in enumerate(inputs, 1):
        label = source_label.get(inp["source_type"], inp["source_type"])
        inputs_text.append(f"### 输入 {i}（来源: {label}）\n\n{inp['content']}")
    inputs_joined = "\n\n".join(inputs_text)

    prompt = f"""你是一位专业的销售助理。请根据以下多源输入信息，生成一份结构化的拜访记录草稿。

## 要求

1. 从输入中提取关键信息，填充拜访记录的各个字段
2. 微信消息等口语化内容需转换为正式书面表达
3. 邮件内容提取关键信息，去除寒暄和格式化内容
4. 如某字段信息不足，标注"[待补充]"
5. 保持客观，不添加输入中未提及的信息
6. 后续计划要具体、可执行，包含时间节点

## 拜访记录字段

{fields_text}

## 原始输入

{inputs_joined}

## 输出格式

请按以下 Markdown 格式输出拜访记录草稿：

# 拜访记录

| 字段 | 内容 |
|------|------|
| 客户名称 | ... |
| 拜访时间 | ... |
| 拜访人 | ... |
| 客户对接人 | ... |

## 拜访目的
...

## 沟通要点
1. ...
2. ...

## 客户反馈
...

## 竞品信息
...

## 后续计划
| 行动项 | 负责人 | 预计时间 |
|--------|--------|----------|

## 备注
...
"""
    return prompt


# ─── 数据库操作 ───


def save_raw_inputs(session_id: str, inputs: list[dict]):
    """保存原始输入到数据库"""
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        print("WARN: DATABASE_URL 未设置，跳过原始数据落库", file=sys.stderr)
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
                CREATE TABLE IF NOT EXISTS visit_raw_inputs (
                    id            SERIAL PRIMARY KEY,
                    session_id    VARCHAR(64),
                    source_type   VARCHAR(32),
                    content       TEXT NOT NULL,
                    created_at    TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            for inp in inputs:
                conn.execute(
                    sqlalchemy.text("""
                        INSERT INTO visit_raw_inputs (session_id, source_type, content, created_at)
                        VALUES (:session_id, :source_type, :content, :created_at)
                    """),
                    {
                        "session_id": session_id,
                        "source_type": inp["source_type"],
                        "content": inp["content"],
                        "created_at": now,
                    },
                )
            conn.commit()
        print("原始数据落库成功", file=sys.stderr)
    except Exception as e:
        print(f"WARN: 原始数据落库失败: {e}", file=sys.stderr)


def save_generation(session_id: str, template_name: str, prompt: str, raw_response: str, draft: str):
    """保存生成记录到数据库"""
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        print("WARN: DATABASE_URL 未设置，跳过生成记录落库", file=sys.stderr)
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
                CREATE TABLE IF NOT EXISTS visit_generations (
                    id            SERIAL PRIMARY KEY,
                    session_id    VARCHAR(64),
                    template_name VARCHAR(128),
                    prompt        TEXT,
                    raw_response  TEXT,
                    draft         TEXT,
                    created_at    TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            conn.execute(
                sqlalchemy.text("""
                    INSERT INTO visit_generations (session_id, template_name, prompt, raw_response, draft, created_at)
                    VALUES (:session_id, :template_name, :prompt, :raw_response, :draft, :created_at)
                """),
                {
                    "session_id": session_id,
                    "template_name": template_name,
                    "prompt": prompt,
                    "raw_response": raw_response,
                    "draft": draft,
                    "created_at": now,
                },
            )
            conn.commit()
        print("生成记录落库成功", file=sys.stderr)
    except Exception as e:
        print(f"WARN: 生成记录落库失败: {e}", file=sys.stderr)


# ─── LLM 调用 ───


def call_llm(prompt: str) -> tuple[str, str]:
    """调用 LLM API，返回 (raw_response, draft_text)"""
    api_url = os.environ.get("LLM_API", "").strip()
    if not api_url:
        print("ERROR: 环境变量 LLM_API 未设置", file=sys.stderr)
        print("请设置 LLM 服务地址，例如:", file=sys.stderr)
        print("  export LLM_API=https://your-llm-service.com/api/chat", file=sys.stderr)
        sys.exit(1)

    try:
        resp = requests.post(
            api_url,
            json={"prompt": prompt, "max_tokens": 4096},
            timeout=120,
        )
    except requests.RequestException as e:
        print(f"ERROR: LLM 请求失败: {e}", file=sys.stderr)
        sys.exit(1)

    if not resp.ok:
        print(f"ERROR: LLM 请求失败 (HTTP {resp.status_code})", file=sys.stderr)
        print(resp.text, file=sys.stderr)
        sys.exit(1)

    raw_response = resp.text

    # 尝试多种响应格式提取文本
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
    """输出拜访记录草稿"""
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(draft)
        print(f"草稿已保存: {output_file}", file=sys.stderr)
    else:
        print(draft)


# ─── 主流程 ───


def main():
    args = parse_args()
    session_id = uuid.uuid4().hex[:16]

    # 1. 收集输入
    inputs = collect_inputs(args)
    print(f"已收集 {len(inputs)} 条输入 (session: {session_id})", file=sys.stderr)

    # 2. 加载模板
    template = load_template(args.template)
    template_name = template.get("name", Path(args.template).stem)

    # 3. 保存原始数据
    if not args.no_db:
        save_raw_inputs(session_id, inputs)

    # 4. 构建 prompt
    prompt = build_prompt(inputs, template)

    # 5. dry-run 模式
    if args.dry_run:
        print("=== DRY RUN: Prompt ===", file=sys.stderr)
        print(prompt)
        return

    # 6. 调用 LLM
    raw_response, draft = call_llm(prompt)

    # 7. 保存中间数据
    if not args.no_db:
        save_generation(session_id, template_name, prompt, raw_response, draft)

    # 8. 输出草稿
    output_draft(draft, args.output)
    print(f"拜访记录草稿生成完成 (session: {session_id})", file=sys.stderr)


if __name__ == "__main__":
    main()
