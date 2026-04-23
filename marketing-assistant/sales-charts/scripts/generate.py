#!/usr/bin/env python3
"""销售数据图表生成脚本 — 基于数据源和图表模板，生成可视化图表报告

用法:
    python generate.py --period 2026-04
    python generate.py --period 2026-Q1
    python generate.py --start 2026-01-01 --end 2026-03-31
    python generate.py --period 2026-04 --charts revenue_trend,sales_funnel
    python generate.py --period 2026-04 --format html -o report.html
    python generate.py --period 2026-04 --dry-run

环境变量:
    DATA_SOURCE_API: 销售数据查询接口地址
    DATABASE_URL:    数据库连接地址（可选，用于落库）
"""
import os
import sys
import json
import uuid
import argparse
from datetime import datetime, date, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_TEMPLATE = SCRIPT_DIR.parent / "templates" / "default.json"

# 尝试导入可视化库（延迟导入，在实际绘图时才需要）
MATPLOTLIB_AVAILABLE = False
try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm

    MATPLOTLIB_AVAILABLE = True
except ImportError:
    pass


# ─── 参数解析 ───


def parse_args():
    parser = argparse.ArgumentParser(description="销售数据图表生成")
    parser.add_argument("--period", type=str, help="报告周期 (YYYY-MM 月报, YYYY-QN 季报, YYYY 年报)")
    parser.add_argument("--start", type=str, help="自定义起始日期 (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="自定义结束日期 (YYYY-MM-DD)")
    parser.add_argument("--charts", type=str, help="指定生成的图表ID (逗号分隔)，默认全部")
    parser.add_argument("--template", type=str, default=str(DEFAULT_TEMPLATE), help="图表模板路径")
    parser.add_argument(
        "--format", choices=["png", "html", "json"], default="png",
        help="输出格式: png(图片), html(网页报告), json(原始数据)",
    )
    parser.add_argument("-o", "--output", help="输出路径（文件或目录）", default="./output")
    parser.add_argument("--no-db", action="store_true", help="跳过落库")
    parser.add_argument("--dry-run", action="store_true", help="仅展示将要生成的图表列表和数据请求，不实际生成")
    parser.add_argument("--data-file", type=str, help="从本地 JSON 文件加载数据（跳过 API 查询）")
    return parser.parse_args()


def resolve_period(args) -> tuple[str, str, str]:
    """解析报告周期，返回 (period_label, start_date, end_date)"""
    if args.start and args.end:
        return f"{args.start} ~ {args.end}", args.start, args.end

    if not args.period:
        # 默认当月
        today = date.today()
        args.period = today.strftime("%Y-%m")

    period = args.period.upper()

    if len(period) == 7 and "-" in period:
        # YYYY-MM
        year, month = period.split("-")
        start = f"{year}-{month}-01"
        # 计算月末
        m = int(month)
        if m == 12:
            end = f"{int(year) + 1}-01-01"
        else:
            end = f"{year}-{m + 1:02d}-01"
        return f"{year}年{month}月", start, end

    if "Q" in period:
        # YYYY-QN
        year, q = period.split("-Q") if "-Q" in period else (period[:4], period[-1])
        q = int(q)
        start_month = (q - 1) * 3 + 1
        end_month = q * 3
        start = f"{year}-{start_month:02d}-01"
        if end_month == 12:
            end = f"{int(year) + 1}-01-01"
        else:
            end = f"{year}-{end_month + 1:02d}-01"
        return f"{year}年Q{q}", start, end

    if len(period) == 4:
        # YYYY
        return f"{period}年", f"{period}-01-01", f"{int(period) + 1}-01-01"

    print(f"ERROR: 无法解析周期: {args.period}", file=sys.stderr)
    sys.exit(1)


# ─── 模板加载 ───


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


def filter_charts(template: dict, chart_ids: str | None) -> list[dict]:
    """筛选需要生成的图表"""
    charts = template.get("charts", [])
    if chart_ids:
        ids = set(chart_ids.split(","))
        charts = [c for c in charts if c["id"] in ids]
        if not charts:
            print(f"WARN: 未匹配到任何图表 ID: {chart_ids}", file=sys.stderr)
    return charts


# ─── 数据获取 ───


def fetch_data_from_api(charts: list[dict], start_date: str, end_date: str) -> dict:
    """从数据源 API 查询各图表所需数据"""
    api_url = os.environ.get("DATA_SOURCE_API", "").strip()
    if not api_url:
        print("ERROR: 环境变量 DATA_SOURCE_API 未设置", file=sys.stderr)
        print("请设置销售数据查询接口地址，例如:", file=sys.stderr)
        print("  export DATA_SOURCE_API=https://your-data-api.com/api/sales", file=sys.stderr)
        sys.exit(1)

    import requests

    chart_data = {}
    for chart in charts:
        chart_id = chart["id"]
        print(f"  查询数据: {chart['title']} ({chart_id})...", file=sys.stderr)

        try:
            resp = requests.post(
                api_url,
                json={
                    "chart_id": chart_id,
                    "chart_type": chart["chart_type"],
                    "start_date": start_date,
                    "end_date": end_date,
                },
                timeout=60,
            )
        except Exception as e:
            print(f"WARN: 查询 {chart_id} 失败: {e}", file=sys.stderr)
            chart_data[chart_id] = None
            continue

        if not resp.ok:
            print(f"WARN: 查询 {chart_id} 失败 (HTTP {resp.status_code})", file=sys.stderr)
            chart_data[chart_id] = None
            continue

        try:
            data = resp.json()
            chart_data[chart_id] = data.get("data") or data.get("result") or data
        except Exception:
            chart_data[chart_id] = None

    return chart_data


def load_data_from_file(data_file: str) -> dict:
    """从本地 JSON 文件加载数据"""
    try:
        with open(data_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR: 数据文件不存在: {data_file}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: 数据文件 JSON 解析失败: {e}", file=sys.stderr)
        sys.exit(1)


# ─── 图表绘制 ───


def setup_chinese_font():
    """尝试设置中文字体"""
    font_candidates = [
        "SimHei", "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC",
        "WenQuanYi Micro Hei", "Source Han Sans CN",
    ]
    for font_name in font_candidates:
        try:
            fm.findfont(font_name, fallback_to_default=False)
            plt.rcParams["font.sans-serif"] = [font_name]
            plt.rcParams["axes.unicode_minus"] = False
            return
        except Exception:
            continue
    print("WARN: 未找到中文字体，图表中文可能显示异常", file=sys.stderr)


def render_kpi_cards(chart: dict, data: dict | None, output_dir: Path) -> Path | None:
    """绘制 KPI 卡片"""
    if not MATPLOTLIB_AVAILABLE or data is None:
        return None

    metrics = chart.get("metrics", [])
    n = len(metrics)
    fig, axes = plt.subplots(1, n, figsize=(4 * n, 2.5))
    if n == 1:
        axes = [axes]

    for ax, metric in zip(axes, metrics):
        key = metric["key"]
        label = metric["label"]
        unit = metric.get("unit", "")
        value = data.get(key, "-")
        compare_val = data.get(f"{key}_compare", "")

        ax.text(0.5, 0.6, f"{value}{unit}", ha="center", va="center", fontsize=28, fontweight="bold")
        ax.text(0.5, 0.25, label, ha="center", va="center", fontsize=12, color="gray")
        if compare_val:
            color = "green" if str(compare_val).startswith("+") or (isinstance(compare_val, (int, float)) and compare_val > 0) else "red"
            ax.text(0.5, 0.05, f"{compare_val}", ha="center", va="center", fontsize=10, color=color)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")

    plt.tight_layout()
    path = output_dir / f"{chart['id']}.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def render_line_chart(chart: dict, data: dict | None, output_dir: Path) -> Path | None:
    if not MATPLOTLIB_AVAILABLE or data is None:
        return None

    fig, ax = plt.subplots(figsize=(10, 5))
    x_labels = data.get("labels", [])
    for series_name in chart.get("series", []):
        values = data.get(series_name, [])
        if values:
            ax.plot(x_labels, values, marker="o", label=series_name)

    ax.set_title(chart["title"])
    ax.set_xlabel(chart.get("x_axis", ""))
    ax.set_ylabel(chart.get("y_axis", ""))
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    plt.tight_layout()

    path = output_dir / f"{chart['id']}.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def render_bar_chart(chart: dict, data: dict | None, output_dir: Path) -> Path | None:
    if not MATPLOTLIB_AVAILABLE or data is None:
        return None

    import numpy as np

    fig, ax = plt.subplots(figsize=(10, 5))
    labels = data.get("labels", [])
    series_list = chart.get("series", [])
    x = np.arange(len(labels))
    width = 0.8 / max(len(series_list), 1)

    for i, series_name in enumerate(series_list):
        values = data.get(series_name, [])
        if values:
            ax.bar(x + i * width, values, width, label=series_name)

    ax.set_title(chart["title"])
    ax.set_xlabel(chart.get("x_axis", ""))
    ax.set_ylabel(chart.get("y_axis", ""))
    ax.set_xticks(x + width * (len(series_list) - 1) / 2)
    ax.set_xticklabels(labels, rotation=45)
    ax.legend()
    plt.tight_layout()

    path = output_dir / f"{chart['id']}.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def render_pie_chart(chart: dict, data: dict | None, output_dir: Path, doughnut: bool = False) -> Path | None:
    if not MATPLOTLIB_AVAILABLE or data is None:
        return None

    fig, ax = plt.subplots(figsize=(8, 6))
    labels = data.get("labels", [])
    values = data.get("values", [])

    wedgeprops = {"width": 0.4} if doughnut else {}
    ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90, wedgeprops=wedgeprops)
    ax.set_title(chart["title"])
    plt.tight_layout()

    path = output_dir / f"{chart['id']}.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def render_funnel_chart(chart: dict, data: dict | None, output_dir: Path) -> Path | None:
    if not MATPLOTLIB_AVAILABLE or data is None:
        return None

    fig, ax = plt.subplots(figsize=(8, 6))
    stages = data.get("stages", chart.get("stages", []))
    values = data.get("values", [])

    if not values:
        plt.close(fig)
        return None

    max_val = max(values)
    y_positions = list(range(len(stages) - 1, -1, -1))

    for i, (stage, val) in enumerate(zip(stages, values)):
        width = val / max_val * 0.8
        ax.barh(y_positions[i], width, height=0.6, left=(1 - width) / 2, color=plt.cm.Blues(0.3 + 0.7 * (1 - i / len(stages))))
        pct = f"({val / values[0] * 100:.0f}%)" if i > 0 else ""
        ax.text(0.5, y_positions[i], f"{stage}: {val} {pct}", ha="center", va="center", fontsize=11)

    ax.set_xlim(0, 1)
    ax.set_title(chart["title"])
    ax.axis("off")
    plt.tight_layout()

    path = output_dir / f"{chart['id']}.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def render_horizontal_bar(chart: dict, data: dict | None, output_dir: Path) -> Path | None:
    if not MATPLOTLIB_AVAILABLE or data is None:
        return None

    fig, ax = plt.subplots(figsize=(10, 6))
    labels = data.get("labels", [])
    values = data.get("values", [])

    ax.barh(labels, values)
    ax.set_title(chart["title"])
    ax.set_xlabel(chart.get("x_axis", ""))
    plt.tight_layout()

    path = output_dir / f"{chart['id']}.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def render_table(chart: dict, data: dict | None, output_dir: Path) -> Path | None:
    """将表格渲染为图片"""
    if not MATPLOTLIB_AVAILABLE or data is None:
        return None

    columns = chart.get("columns", [])
    rows = data.get("rows", [])

    if not rows:
        return None

    fig, ax = plt.subplots(figsize=(12, max(3, 0.5 * len(rows) + 1)))
    ax.axis("off")
    table = ax.table(cellText=rows, colLabels=columns, loc="center", cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.auto_set_column_width(list(range(len(columns))))
    ax.set_title(chart["title"], pad=20)
    plt.tight_layout()

    path = output_dir / f"{chart['id']}.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


RENDERERS = {
    "kpi_card": render_kpi_cards,
    "line": render_line_chart,
    "bar": render_bar_chart,
    "pie": lambda c, d, o: render_pie_chart(c, d, o, doughnut=False),
    "doughnut": lambda c, d, o: render_pie_chart(c, d, o, doughnut=True),
    "funnel": render_funnel_chart,
    "horizontal_bar": render_horizontal_bar,
    "table": render_table,
}


def render_chart(chart: dict, data: dict | None, output_dir: Path) -> Path | None:
    renderer = RENDERERS.get(chart["chart_type"])
    if not renderer:
        print(f"WARN: 不支持的图表类型: {chart['chart_type']}", file=sys.stderr)
        return None
    return renderer(chart, data, output_dir)


# ─── HTML 报告 ───


def generate_html_report(charts: list[dict], chart_files: dict[str, Path | None],
                         period_label: str, output_path: Path):
    """生成 HTML 报告"""
    import base64

    html_parts = [f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>销售数据报告 — {period_label}</title>
<style>
  body {{ font-family: "Microsoft YaHei", "PingFang SC", sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
  h1 {{ text-align: center; color: #333; }}
  .chart-container {{ background: white; border-radius: 8px; padding: 20px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
  .chart-container h2 {{ color: #555; border-bottom: 2px solid #eee; padding-bottom: 10px; }}
  .chart-container img {{ max-width: 100%; display: block; margin: 0 auto; }}
  .chart-container p.desc {{ color: #888; font-size: 14px; }}
  .no-data {{ color: #ccc; text-align: center; padding: 40px; font-size: 18px; }}
</style>
</head>
<body>
<h1>销售数据报告 — {period_label}</h1>
"""]

    for chart in charts:
        chart_file = chart_files.get(chart["id"])
        html_parts.append(f'<div class="chart-container">')
        html_parts.append(f'<h2>{chart["title"]}</h2>')
        html_parts.append(f'<p class="desc">{chart.get("description", "")}</p>')

        if chart_file and chart_file.exists():
            img_data = base64.b64encode(chart_file.read_bytes()).decode()
            html_parts.append(f'<img src="data:image/png;base64,{img_data}" alt="{chart["title"]}">')
        else:
            html_parts.append('<div class="no-data">暂无数据</div>')

        html_parts.append("</div>")

    html_parts.append("</body></html>")

    output_path.write_text("\n".join(html_parts), encoding="utf-8")
    print(f"HTML 报告已生成: {output_path}", file=sys.stderr)


# ─── 落库 ───


def save_report_record(session_id: str, period_label: str, start_date: str,
                       end_date: str, chart_count: int, output_format: str):
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        return

    try:
        import sqlalchemy
    except ImportError:
        return

    now = datetime.now(timezone.utc)
    try:
        engine = sqlalchemy.create_engine(db_url)
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text("""
                CREATE TABLE IF NOT EXISTS sales_chart_reports (
                    id              SERIAL PRIMARY KEY,
                    session_id      VARCHAR(64),
                    period_label    VARCHAR(64),
                    start_date      VARCHAR(10),
                    end_date        VARCHAR(10),
                    chart_count     INTEGER,
                    output_format   VARCHAR(16),
                    created_at      TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            conn.execute(
                sqlalchemy.text("""
                    INSERT INTO sales_chart_reports
                        (session_id, period_label, start_date, end_date, chart_count, output_format, created_at)
                    VALUES (:session_id, :period_label, :start_date, :end_date, :chart_count, :output_format, :created_at)
                """),
                {
                    "session_id": session_id, "period_label": period_label,
                    "start_date": start_date, "end_date": end_date,
                    "chart_count": chart_count, "output_format": output_format,
                    "created_at": now,
                },
            )
            conn.commit()
        print("报告记录落库成功", file=sys.stderr)
    except Exception as e:
        print(f"WARN: 报告记录落库失败: {e}", file=sys.stderr)


# ─── 主流程 ───


def main():
    args = parse_args()
    session_id = uuid.uuid4().hex[:16]

    # 1. 解析周期
    period_label, start_date, end_date = resolve_period(args)
    print(f"报告周期: {period_label} ({start_date} ~ {end_date})", file=sys.stderr)
    print(f"Session: {session_id}", file=sys.stderr)

    # 2. 加载模板 & 筛选图表
    template = load_template(args.template)
    charts = filter_charts(template, args.charts)
    print(f"将生成 {len(charts)} 个图表", file=sys.stderr)

    # 3. dry-run
    if args.dry_run:
        print("=== DRY RUN ===", file=sys.stderr)
        for chart in charts:
            ds_info = "data_source=null (待配置)" if chart.get("data_source") is None else f"data_source={chart['data_source']}"
            print(f"  [{chart['chart_type']:15s}] {chart['title']:20s} | {ds_info}")
        return

    # 4. 获取数据
    if args.data_file:
        print(f"从本地文件加载数据: {args.data_file}", file=sys.stderr)
        all_data = load_data_from_file(args.data_file)
    else:
        print("从 API 查询数据...", file=sys.stderr)
        all_data = fetch_data_from_api(charts, start_date, end_date)

    # 5. 创建输出目录
    output_path = Path(args.output)
    if args.format == "json":
        # JSON 直接输出
        result = {"period": period_label, "start": start_date, "end": end_date, "data": all_data}
        if output_path.suffix == ".json":
            output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"JSON 数据已保存: {output_path}", file=sys.stderr)
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        if not args.no_db:
            save_report_record(session_id, period_label, start_date, end_date, len(charts), "json")
        return

    if not MATPLOTLIB_AVAILABLE:
        print("ERROR: matplotlib 未安装，无法生成图表", file=sys.stderr)
        print("  pip install matplotlib numpy", file=sys.stderr)
        sys.exit(1)

    setup_chinese_font()

    output_dir = output_path if output_path.is_dir() or not output_path.suffix else output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    # 6. 渲染图表
    chart_files = {}
    for chart in charts:
        chart_id = chart["id"]
        data = all_data.get(chart_id) if isinstance(all_data, dict) else None
        print(f"  绘制: {chart['title']}...", file=sys.stderr)
        path = render_chart(chart, data, output_dir)
        chart_files[chart_id] = path
        if path:
            print(f"    → {path}", file=sys.stderr)
        else:
            print(f"    → 跳过（无数据或渲染失败）", file=sys.stderr)

    # 7. 生成 HTML 报告（如指定）
    if args.format == "html":
        html_path = output_path if output_path.suffix == ".html" else output_dir / "report.html"
        generate_html_report(charts, chart_files, period_label, html_path)

    # 8. 落库
    generated_count = sum(1 for v in chart_files.values() if v is not None)
    if not args.no_db:
        save_report_record(session_id, period_label, start_date, end_date, generated_count, args.format)

    print(f"图表生成完成: {generated_count}/{len(charts)} 个 (session: {session_id})", file=sys.stderr)


if __name__ == "__main__":
    main()
