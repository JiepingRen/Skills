#!/usr/bin/env python3
"""上传录音文件到文件服务器

用法: python upload.py <audio_file_path>

环境变量:
    FILE_SERVER_API: 文件服务器上传接口地址
"""
import os
import sys
import json
import requests

SUPPORTED_FORMATS = {"mp3", "wav", "m4a", "flac", "ogg", "wma", "aac", "webm", "amr"}


def main():
    if len(sys.argv) < 2:
        print("ERROR: 缺少文件路径参数", file=sys.stderr)
        print(f"用法: python {sys.argv[0]} <audio_file_path>", file=sys.stderr)
        sys.exit(1)

    file_path = sys.argv[1]

    # 校验文件
    if not os.path.isfile(file_path):
        print(f"ERROR: 文件不存在: {file_path}", file=sys.stderr)
        sys.exit(1)

    ext = os.path.splitext(file_path)[1].lstrip(".").lower()
    if ext not in SUPPORTED_FORMATS:
        print(f"ERROR: 不支持的音频格式: .{ext}", file=sys.stderr)
        print(f"支持的格式: {', '.join(sorted(SUPPORTED_FORMATS))}", file=sys.stderr)
        sys.exit(1)

    # 环境变量
    api_url = os.environ.get("FILE_SERVER_API", "").strip()
    if not api_url:
        print("ERROR: 环境变量 FILE_SERVER_API 未设置", file=sys.stderr)
        print("请设置文件服务器上传地址，例如:", file=sys.stderr)
        print("  export FILE_SERVER_API=https://your-file-server.com/api/upload", file=sys.stderr)
        sys.exit(1)

    # 上传
    filename = os.path.basename(file_path)
    print(f"正在上传: {filename} ...")

    try:
        with open(file_path, "rb") as f:
            resp = requests.post(api_url, files={"file": (filename, f)}, timeout=300)
    except requests.RequestException as e:
        print(f"ERROR: 上传请求失败: {e}", file=sys.stderr)
        sys.exit(1)

    if not resp.ok:
        print(f"ERROR: 上传失败 (HTTP {resp.status_code})", file=sys.stderr)
        print(resp.text, file=sys.stderr)
        sys.exit(1)

    # 解析响应
    try:
        data = resp.json()
        file_url = data.get("url") or data.get("data", {}).get("url") or data.get("file_url")
    except (json.JSONDecodeError, AttributeError):
        file_url = None

    if file_url:
        print(f"上传成功: {file_url}")
    else:
        print("上传成功，但无法解析文件 URL，原始响应:", file=sys.stderr)
        print(resp.text)


if __name__ == "__main__":
    main()
