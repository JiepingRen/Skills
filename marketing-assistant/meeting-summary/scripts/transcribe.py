#!/usr/bin/env python3
"""调用 ASR 转写服务，将音频文件转为文字，并将结果落库

用法:
    python transcribe.py <audio_file_or_url> [-o output_file] [--no-db]

环境变量:
    ASR_API:      ASR 转写服务接口地址
    DATABASE_URL: 数据库连接地址 (例如 postgresql://user:pass@host:5432/dbname)
"""
import os
import sys
import json
import time
import hashlib
import argparse
from datetime import datetime, timezone

import requests

SUPPORTED_FORMATS = {"mp3", "wav", "m4a", "flac", "ogg", "wma", "aac", "webm", "amr"}
POLL_INTERVAL = 5
MAX_POLL = 120


def parse_args():
    parser = argparse.ArgumentParser(description="ASR 音频转写")
    parser.add_argument("input", help="音频文件路径或 URL")
    parser.add_argument("-o", "--output", help="输出文件路径", default=None)
    parser.add_argument("--no-db", action="store_true", help="跳过落库操作")
    return parser.parse_args()


def output_text(text: str, output_file: str | None):
    """输出转写文本到文件或 stdout"""
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"结果已保存: {output_file}", file=sys.stderr)
    else:
        print(text)


def extract_text(data: dict) -> str | None:
    """从响应 JSON 中提取转写文本"""
    for path in [
        lambda d: d.get("text"),
        lambda d: d.get("data", {}).get("text"),
        lambda d: d.get("result", {}).get("text"),
    ]:
        try:
            val = path(data)
            if val:
                return val
        except (AttributeError, TypeError):
            continue
    return None


def save_to_db(source: str, text: str):
    """将转写结果保存到数据库

    表结构 (transcriptions):
        id           SERIAL PRIMARY KEY
        source       TEXT NOT NULL      -- 原始文件路径或 URL
        source_hash  VARCHAR(64)        -- source 的 SHA-256，用于去重
        content      TEXT NOT NULL      -- 转写文本
        created_at   TIMESTAMPTZ        -- 入库时间
    """
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        print("WARN: 环境变量 DATABASE_URL 未设置，跳过落库", file=sys.stderr)
        return

    try:
        import sqlalchemy
    except ImportError:
        print("WARN: sqlalchemy 未安装，跳过落库 (pip install sqlalchemy psycopg2-binary)", file=sys.stderr)
        return

    source_hash = hashlib.sha256(source.encode()).hexdigest()
    now = datetime.now(timezone.utc)

    try:
        engine = sqlalchemy.create_engine(db_url)
        with engine.connect() as conn:
            # 自动建表（如不存在）
            conn.execute(sqlalchemy.text("""
                CREATE TABLE IF NOT EXISTS transcriptions (
                    id           SERIAL PRIMARY KEY,
                    source       TEXT NOT NULL,
                    source_hash  VARCHAR(64),
                    content      TEXT NOT NULL,
                    created_at   TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            conn.execute(
                sqlalchemy.text("""
                    INSERT INTO transcriptions (source, source_hash, content, created_at)
                    VALUES (:source, :source_hash, :content, :created_at)
                """),
                {"source": source, "source_hash": source_hash, "content": text, "created_at": now},
            )
            conn.commit()
        print("落库成功", file=sys.stderr)
    except Exception as e:
        print(f"WARN: 落库失败: {e}", file=sys.stderr)


def main():
    args = parse_args()
    input_val = args.input

    # 环境变量
    api_url = os.environ.get("ASR_API", "").strip()
    if not api_url:
        print("ERROR: 环境变量 ASR_API 未设置", file=sys.stderr)
        print("请设置 ASR 转写服务地址，例如:", file=sys.stderr)
        print("  export ASR_API=https://your-asr-service.com/api/transcribe", file=sys.stderr)
        sys.exit(1)

    # 提交转写任务
    is_url = input_val.startswith(("http://", "https://"))

    try:
        if is_url:
            print(f"正在提交转写任务 (URL): {input_val} ...", file=sys.stderr)
            resp = requests.post(
                api_url,
                json={"url": input_val},
                timeout=60,
            )
        else:
            # 本地文件
            if not os.path.isfile(input_val):
                print(f"ERROR: 文件不存在: {input_val}", file=sys.stderr)
                sys.exit(1)

            ext = os.path.splitext(input_val)[1].lstrip(".").lower()
            if ext not in SUPPORTED_FORMATS:
                print(f"ERROR: 不支持的音频格式: .{ext}", file=sys.stderr)
                sys.exit(1)

            filename = os.path.basename(input_val)
            print(f"正在提交转写任务 (文件): {filename} ...", file=sys.stderr)
            with open(input_val, "rb") as f:
                resp = requests.post(
                    api_url,
                    files={"file": (filename, f)},
                    timeout=300,
                )
    except requests.RequestException as e:
        print(f"ERROR: 提交转写任务失败: {e}", file=sys.stderr)
        sys.exit(1)

    if not resp.ok:
        print(f"ERROR: 提交转写任务失败 (HTTP {resp.status_code})", file=sys.stderr)
        print(resp.text, file=sys.stderr)
        sys.exit(1)

    try:
        body = resp.json()
    except json.JSONDecodeError:
        print("ERROR: 无法解析响应 JSON", file=sys.stderr)
        print(resp.text, file=sys.stderr)
        sys.exit(1)

    # 同步模式：直接返回文本
    text = extract_text(body)
    if text:
        print("转写完成（同步模式）", file=sys.stderr)
        output_text(text, args.output)
        if not args.no_db:
            save_to_db(input_val, text)
        return

    # 异步模式：获取任务 ID 并轮询
    task_id = body.get("task_id") or body.get("data", {}).get("task_id") or body.get("id")
    if not task_id:
        print("ERROR: 无法解析转写响应（未获取到 text 或 task_id）", file=sys.stderr)
        print(f"原始响应: {json.dumps(body, ensure_ascii=False)}", file=sys.stderr)
        sys.exit(1)

    print(f"转写任务已提交，任务ID: {task_id}，等待结果...", file=sys.stderr)

    # 轮询
    for i in range(1, MAX_POLL + 1):
        time.sleep(POLL_INTERVAL)

        try:
            poll_resp = requests.get(f"{api_url}/{task_id}", timeout=30)
        except requests.RequestException:
            print(f"WARN: 轮询失败，重试中 ({i}/{MAX_POLL})...", file=sys.stderr)
            continue

        if not poll_resp.ok:
            print(f"WARN: 轮询失败 (HTTP {poll_resp.status_code})，重试中 ({i}/{MAX_POLL})...", file=sys.stderr)
            continue

        try:
            poll_data = poll_resp.json()
        except json.JSONDecodeError:
            continue

        status = poll_data.get("status") or poll_data.get("data", {}).get("status", "")
        status = status.lower()

        if status in ("completed", "done", "success", "finished"):
            text = extract_text(poll_data)
            if text:
                print("转写完成", file=sys.stderr)
                output_text(text, args.output)
                if not args.no_db:
                    save_to_db(input_val, text)
                return
            else:
                print("ERROR: 任务完成但无法提取文本", file=sys.stderr)
                print(json.dumps(poll_data, ensure_ascii=False), file=sys.stderr)
                sys.exit(1)

        elif status in ("failed", "error"):
            print("ERROR: 转写任务失败", file=sys.stderr)
            print(json.dumps(poll_data, ensure_ascii=False), file=sys.stderr)
            sys.exit(1)

        else:
            print(f"轮询中... 状态: {status or 'unknown'} ({i}/{MAX_POLL})", file=sys.stderr)

    print(f"ERROR: 转写超时（已轮询 {MAX_POLL} 次）", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
