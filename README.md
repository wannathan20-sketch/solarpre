# EIA 真实电网数据预测与回测平台

这是一个基于 **EIA Open Data 小时级真实电网数据** 的机器学习回测项目。项目目标是用多年真实负荷、太阳能、风电和净负荷数据，验证时间序列预测流程，而不是使用公式生成的区域演示标签。

当前项目主线已经调整为 EIA-only：

- 使用 EIA Open Data 电力 API 获取 `CISO` 区域小时级真实电网数据。
- 使用 2021-2024 年数据训练模型，预测 2025 年，并用 2025 年真实数据回测。
- 使用 2021-2025 年数据训练模型，预测 2026 年已发布时段，并用 2026 年真实数据滚动评估。
- 前端、API、README 和测试都围绕 EIA 真实数据路线组织。
- 早期区域公式数据路线不再作为项目主叙事。

## 项目做什么

- 下载 EIA 小时级真实电网数据，包括负荷、负荷预测、太阳能发电、风电发电。
- 构建净负荷字段：`NET_LOAD_MW = LOAD_MW - SOLAR_MW - WIND_MW`。
- 训练 XGBoost 回归模型，分别预测负荷、太阳能、风电和净负荷。
- 按时间顺序做回测，避免随机打散造成的数据泄漏。
- 提供 FastAPI 接口和 Web 仪表盘，展示 2025/2026 回测摘要和预测曲线。

## 技术栈

| 模块 | 技术 |
| --- | --- |
| 数据源 | EIA Open Data electricity API |
| 后端服务 | FastAPI、Uvicorn |
| 机器学习 | XGBoost、scikit-learn、pandas、NumPy |
| 可视化 | Matplotlib、Seaborn |
| 前端 | HTML、CSS、原生 JavaScript |
| 部署 | Zeabur、Nixpacks |
| 测试 | unittest、GitHub Actions |

## 项目结构

```text
solar-main/
|-- solar/
|   |-- app.py                              # FastAPI 应用和 EIA 回测 API
|   |-- train_eia_backtest.py               # EIA 回测训练入口
|   |-- grid_backtest.py                    # 通用时间切分回测逻辑
|   |-- data_sources/eia_open_data.py        # EIA Open Data 下载与归一化
|   |-- data/eia_ciso_2021_2025_generation_load.csv
|   |-- data/eia_ciso_2021_2026_generation_load.csv
|   |-- data/eia_ciso_2025_predictions_from_2021_2024.csv
|   |-- data/eia_ciso_2026_predictions_from_2021_2025.csv
|   |-- static/index.html                   # EIA 真实数据回测仪表盘
|   `-- requirements.txt
|-- tests/                                 # API、数据源、调度与评估测试
|-- .github/workflows/tests.yml             # GitHub Actions 自动测试
|-- DEPLOYMENT.md                           # 部署说明
|-- MODEL_CARD.md                           # 模型说明和限制
|-- nixpacks.toml                           # Zeabur 部署配置
`-- requirements.txt
```

已生成的 EIA 数据和回测产物：

| 文件 | 时间范围 | 行数 | 说明 |
| --- | --- | ---: | --- |
| `solar/data/eia_ciso_2021_2025_generation_load.csv` | 2021-01-01 至 2025-12-31 | 43,824 | 2025 回测训练 + 验证数据 |
| `solar/data/eia_ciso_2021_2026_generation_load.csv` | 2021-01-01 至 2026-06-01 | 47,472 | 2026 滚动评估数据 |
| `solar/data/eia_ciso_2025_predictions_from_2021_2024.csv` | 2025-01-01 至 2025-12-31 | 8,712 | 2025 预测结果 |
| `solar/data/eia_ciso_2026_predictions_from_2021_2025.csv` | 2026-01-01 至 2026-06-01 | 3,625 | 2026 预测结果 |

## 数据来源

EIA Open Data 提供美国电力系统公开数据。当前项目默认使用 `CISO` respondent，即 EIA 对加州独立系统运营区域的标识。

主要字段：

| 字段 | 含义 |
| --- | --- |
| `DATE_TIME_LOCAL` | 小时时间戳 |
| `REGION_ID` | EIA respondent，例如 `CISO` |
| `REGION_NAME` | 区域名称 |
| `LOAD_MW` | 实际负荷 |
| `LOAD_FORECAST_MW` | 负荷预测 |
| `SOLAR_MW` | 实际太阳能发电 |
| `WIND_MW` | 实际风电发电 |
| `GENERATION_MW` | 太阳能 + 风电 |
| `NET_LOAD_MW` | 负荷扣除太阳能和风电后的净负荷 |
| `SOLAR_SHARE_PERCENT` | 太阳能占负荷比例 |

## 获取 EIA 数据

EIA API 需要免费 API key。配置方式：

```bash
export EIA_API_KEY="你的 EIA API key"
```

下载 2021-2025 数据：

```bash
python3 solar/data_sources/eia_open_data.py \
  --start 2021-01-01T00 \
  --end 2025-12-31T23 \
  --respondent CISO \
  --output solar/data/eia_ciso_2021_2025_generation_load.csv
```

下载 2021-2026 已发布数据：

```bash
python3 solar/data_sources/eia_open_data.py \
  --start 2021-01-01T00 \
  --end 2026-06-01T23 \
  --respondent CISO \
  --output solar/data/eia_ciso_2021_2026_generation_load.csv
```

## 回测实验

当前指标：

| 实验 | 目标 | MAE | RMSE | MAPE |
| --- | --- | ---: | ---: | ---: |
| 2021-2024 预测 2025 | 负荷 | 1260.85 MW | 1800.25 MW | 4.84% |
| 2021-2024 预测 2025 | 太阳能 | 1953.18 MW | 3026.09 MW | 661.51% |
| 2021-2024 预测 2025 | 太阳能有效发电时段 | 3559.34 MW | 4161.28 MW | 77.13% |
| 2021-2024 预测 2025 | 风电 | 910.43 MW | 1125.05 MW | 66.01% |
| 2021-2024 预测 2025 | 净负荷 | 1945.11 MW | 2808.06 MW | 16.38% |
| 2021-2025 预测 2026 | 负荷 | 1735.11 MW | 2473.94 MW | 6.84% |
| 2021-2025 预测 2026 | 太阳能 | 1616.44 MW | 2712.63 MW | 352.53% |
| 2021-2025 预测 2026 | 太阳能有效发电时段 | 3019.29 MW | 3789.87 MW | 49.81% |
| 2021-2025 预测 2026 | 风电 | 1058.31 MW | 1269.94 MW | 161.52% |
| 2021-2025 预测 2026 | 净负荷 | 1616.93 MW | 2103.33 MW | 11.85% |

太阳能全时段 MAPE 会被夜间或接近 0 MW 的小时放大，因此文档同时列出 `SOLAR_MW > 100 MW` 的有效发电时段指标。

2025 历史回测：

```bash
python3 solar/train_eia_backtest.py \
  --input solar/data/eia_ciso_2021_2025_generation_load.csv \
  --train-start 2021-01-01 \
  --train-end 2024-12-31 \
  --predict-start 2025-01-01 \
  --predict-end 2025-12-31 \
  --output solar/data/eia_ciso_2025_predictions_from_2021_2024.csv \
  --metrics-output solar/data/eia_ciso_2025_backtest_2021_2024_metrics.json
```

2026 滚动评估：

```bash
python3 solar/train_eia_backtest.py \
  --input solar/data/eia_ciso_2021_2026_generation_load.csv \
  --train-start 2021-01-01 \
  --train-end 2025-12-31 \
  --predict-start 2026-01-01 \
  --predict-end 2026-06-01 \
  --output solar/data/eia_ciso_2026_predictions_from_2021_2025.csv \
  --metrics-output solar/data/eia_ciso_2026_backtest_2021_2025_metrics.json
```

## 本地运行

```bash
pip install -r solar/requirements.txt
cd solar
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

打开：

```text
http://localhost:8000
```

## API 概览

| 接口 | 方法 | 说明 |
| --- | --- | --- |
| `/health` | GET | 服务状态和 EIA-only 模式 |
| `/eia/backtests` | GET | EIA 2025/2026 回测摘要 |
| `/plot/eia_backtest?period=2025&target=net_load` | GET | EIA 真实值与预测值对比图 |

可选 `target`：

- `load`
- `solar`
- `wind`
- `net_load`

## 部署

项目已准备 Zeabur/Nixpacks 部署配置：

```text
Root Directory: solar
Start Command: uvicorn app:app --host 0.0.0.0 --port $PORT
```

如果需要部署端动态下载 EIA 数据，需要在 Zeabur 环境变量中配置：

```text
EIA_API_KEY=你的 EIA API key
```

当前更推荐在本地生成 CSV/JSON 后提交或放入 Release/对象存储，再由部署环境读取静态数据文件。

## 当前限制

- EIA `CISO` 是美国加州电网区域，不代表中国本土电网。
- 当前模型是基线机器学习回测，不是生产级电力调度模型。
- 太阳能和风电预测主要依赖历史时间特征和可用公开字段，暂未加入天气预报、市场价格、检修、弃电等高级变量。
- 仓库中早期区域演示文件属于历史路线，不再作为主项目结论。

## 后续改进

- 增加 EIA 多区域对比，例如 CISO、ERCO、PJM、NYIS。
- 增加天气特征、节假日特征和异常事件标记。
- 增加预测区间和不确定性评估。
- 将大体积真实数据迁移到 Release、对象存储或数据版本管理工具。
