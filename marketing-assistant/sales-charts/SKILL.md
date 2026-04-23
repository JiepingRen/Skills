---
name: sales-charts
description: 销售数据图表生成 — 基于销售数据生成可视化图表报告（KPI卡片、趋势图、漏斗图等）
metadata:
  hermes:
    tags: [Sales, Charts, Visualization, Data, Marketing]
  lobehub:
    source: custom
---

# 销售数据图表生成

> 适用场景：定期生成销售数据可视化报告，包含 KPI 概览、趋势分析、分类对比、转化漏斗等

## 一、使用流程

```
数据源(API/文件) ──→ 查询各图表数据 ──→ matplotlib 绘图 ──→ 输出报告
DATA_SOURCE_API       按 chart_id        8 种图表类型     png / html / json
或 --data-file        分别请求
```

### 快速开始

```bash
# 1. 设置环境变量
export DATA_SOURCE_API=https://your-data-api.com/api/sales
export DATABASE_URL=postgresql://user:pass@host:5432/dbname  # 可选

# 2. 生成当月报告（全部图表，PNG 格式）
python scripts/generate.py --period 2026-04 -o ./output

# 3. 生成季报 HTML
python scripts/generate.py --period 2026-Q1 --format html -o report.html

# 4. 只生成指定图表
python scripts/generate.py --period 2026-04 --charts revenue_trend,sales_funnel

# 5. 从本地数据文件生成（跳过 API）
python scripts/generate.py --period 2026-04 --data-file sample_data.json

# 6. 预览将生成的图表列表
python scripts/generate.py --period 2026-04 --dry-run

# 7. 导出原始数据 JSON
python scripts/generate.py --period 2026-04 --format json -o data.json
```

## 二、环境变量

| 变量名 | 说明 | 必填 | 示例 |
|--------|------|------|------|
| `DATA_SOURCE_API` | 销售数据查询接口 | 是（除非用 --data-file） | `https://data.example.com/api/sales` |
| `DATABASE_URL` | 数据库连接地址 | 否 | `postgresql://user:pass@host:5432/dbname` |

## 三、包含的图表

| 图表 | 类型 | 说明 |
|------|------|------|
| 核心KPI卡片 | kpi_card | 总销售额、增长率、完成率、新客户数、客单价 |
| 销售额趋势 | line | 月/周趋势折线图，含同比和目标对照线 |
| 区域业绩对比 | bar | 按区域/团队的柱状对比图 |
| 产品销售占比 | pie | 各产品线/品类占比饼图 |
| 销售转化漏斗 | funnel | 线索→意向→商机→报价→赢单 |
| 渠道贡献占比 | doughnut | 各渠道业绩贡献环形图 |
| 销售排名 Top10 | horizontal_bar | 销售人员业绩排名 |
| Top10 客户明细 | table | 大客户明细表 |

## 四、脚本说明

### `scripts/generate.py`

**周期参数**：
- `--period YYYY-MM` — 月报
- `--period YYYY-QN` — 季报（Q1~Q4）
- `--period YYYY` — 年报
- `--start` + `--end` — 自定义日期范围
- 不指定则默认当月

**输出参数**：
- `--format png|html|json` — 输出格式（默认 png）
- `-o` — 输出路径（文件或目录）
- `--charts` — 指定图表 ID，逗号分隔

**数据参数**：
- `--data-file` — 从本地 JSON 加载数据，跳过 API 查询

**其他**：
- `--no-db` — 不保存报告生成记录
- `--dry-run` — 仅展示图表列表和数据请求

**数据持久化**：`sales_chart_reports` 表

## 五、模板系统

默认模板: `templates/default.json`

模板定义图表列表及每个图表的类型、字段、数据源配置。可自定义模板增减图表。

## 六、参考文档

📄 数据格式规范与图表设计指南: [references/sales-charts-guide.md](./references/sales-charts-guide.md)

## 七、依赖

- `python3` >= 3.10
- `requests` — HTTP 请求（`pip install requests`）
- `matplotlib` + `numpy` — 图表绘制（`pip install matplotlib numpy`）
- `sqlalchemy` + 数据库驱动 — 落库（`pip install sqlalchemy psycopg2-binary`，可选）

---

*文档版本: v1.0*
*创建日期: 2026-04-22*
