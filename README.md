# 区域新能源发电预测与电网调度辅助平台

这是一个面向新能源功率预测、电网调度运行和数据分析岗位的个人机器学习项目。项目最初是单个光伏电站的发电量预测，当前版本已经扩展为区域级新能源发电预测、负荷需求预测、储能充放电建议和真实公开电网数据回测。

项目后端使用 FastAPI，模型使用 XGBoost，前端是轻量级 HTML/CSS/JavaScript 仪表盘。部署目标为 Zeabur。

## 项目做什么

- 使用 NASA POWER 小时级气象和太阳辐照数据，构建华南/西南代表城市的区域光伏发电数据集。
- 基于辐照度、温度、湿度、风速、装机容量等特征，训练区域光伏发电功率模型。
- 基于时间、天气和区域峰值负荷假设，构建区域负荷需求基准并训练负荷预测模型。
- 在光伏预测和负荷预测之上，加入规则型储能调度层，给出充电、放电或待机建议。
- 接入 CAISO OASIS 公开电网数据，完成 2025 年历史回测和 2026 年已发布时段滚动评估。
- 提供 Web 页面和 API，用于区域选择、气象输入、功率预测、发电负荷平衡分析、储能策略展示和 CAISO 回测可视化。

## 技术栈

| 模块 | 技术 |
| --- | --- |
| 数据源 | NASA POWER、CAISO OASIS |
| 后端服务 | FastAPI、Uvicorn |
| 机器学习 | XGBoost、scikit-learn、pandas、NumPy、joblib |
| 可视化 | Matplotlib、Seaborn |
| 前端 | HTML、CSS、原生 JavaScript |
| 部署 | Zeabur、Nixpacks |

## 项目结构

```text
solar-main/
|-- solar/
|   |-- app.py                               # FastAPI 应用和 API 路由
|   |-- regions.py                           # 区域代表城市与容量/负荷/储能假设
|   |-- solar_predictor.py                   # 模型封装和特征工程
|   |-- train_regional_model.py              # 区域光伏模型训练
|   |-- train_load_model.py                  # 区域负荷模型训练
|   |-- evaluate_regional_timesplit.py       # 区域模型时间切分评估
|   |-- train_caiso_backtest.py              # CAISO 真实数据回测
|   |-- train_model.py                       # 早期单电站模型训练脚本
|   |-- data_sources/nasa_power.py           # NASA POWER 数据获取
|   |-- data_sources/caiso_oasis.py          # CAISO OASIS 数据获取
|   |-- data_sources/caiso_batch_download.py # CAISO 按月断点下载脚本
|   |-- data/south_china_solar_power.csv     # 区域光伏发电数据集
|   |-- data/south_china_load_power.csv      # 区域发电-负荷数据集
|   |-- data/caiso_2024_2026_generation_load.csv
|   |-- data/caiso_2025_predictions.csv
|   |-- data/caiso_2026_predictions.csv
|   |-- south_china_solar_model.joblib       # 区域光伏模型
|   |-- south_china_load_model.joblib        # 区域负荷模型
|   |-- solar_model.joblib                   # 早期单电站模型
|   |-- static/index.html                    # Web 仪表盘
|   `-- requirements.txt                     # Python 依赖
|-- DEPLOYMENT.md                            # 部署说明
|-- MODEL_CARD.md                            # 模型说明和限制
|-- DESIGN_ITERATIONS.md                     # 前端设计迭代记录
|-- legacy/spring-boot-shell/                # 早期 Spring Boot 实验代码，当前不参与部署
|-- .python-version                          # Zeabur/Nixpacks Python 版本提示
|-- nixpacks.toml                            # Zeabur 部署配置
|-- deploy.sh                                # GitHub/部署准备脚本
`-- requirements.txt
```

生产路径是 `solar/` 下的 Python/FastAPI 应用。应用优先加载 `south_china_solar_model.joblib` 和 `south_china_load_model.joblib`。如果区域光伏模型不存在，才会退回到早期的单电站模型。

## 区域与数据

当前区域样本覆盖 6 个代表城市：

- 广东广州
- 广东深圳
- 广西南宁
- 云南昆明
- 贵州贵阳
- 海南海口

NASA POWER 使用的主要字段：

- `T2M`：2 米气温
- `RH2M`：2 米相对湿度
- `WS2M`：2 米风速
- `ALLSKY_SFC_SW_DWN`：地表短波辐照度

已生成的区域数据：

| 文件 | 时间范围 | 行数 | 说明 |
| --- | --- | ---: | --- |
| `solar/data/south_china_solar_power.csv` | 2024-01-01 至 2024-12-31 | 52,704 | 区域光伏功率数据 |
| `solar/data/south_china_load_power.csv` | 2024-01-01 至 2024-12-31 | 52,704 | 区域发电-负荷数据 |
| `solar/data/regional_timesplit_metrics.json` | 2024-10-01 至 2024-12-31 | - | 区域模型时间切分评估 |

其中 `SOLAR_POWER_MW` 和 `REGIONAL_LOAD_MW` 都是基于公开气象数据、时间特征和透明公式生成的基准标签，不是电网企业实测调度数据。

## 模型与调度逻辑

### 区域光伏预测

区域光伏模型使用 XGBoost Regressor，目标变量是 `SOLAR_POWER_MW`。主要特征包括：

- 时间特征：小时、月份、星期、周末、季节、是否白天
- 区域特征：区域编码、经纬度、装机容量
- 天气特征：气温、湿度、风速、辐照度、组件温度
- 交互特征：温度差、辐照度与容量、风速与辐照度等

### 区域负荷预测

负荷模型同样使用 XGBoost Regressor，目标变量是 `REGIONAL_LOAD_MW`。它在时间和天气特征之外加入了区域峰值负荷假设，用来估算不同区域在不同时间和天气条件下的负荷需求。

### 时间切分评估

为了避免只展示随机交叉验证，项目增加了按时间切分的区域模型评估脚本：

```bash
python3 solar/evaluate_regional_timesplit.py \
  --kind both \
  --train-end 2024-09-30 \
  --output solar/data/regional_timesplit_metrics.json
```

当前报告使用 2024-01-01 至 2024-09-30 训练，使用 2024-10-01 至 2024-12-31 测试：

| 模型 | 训练行数 | 测试行数 | MAE | RMSE | MAPE |
| --- | ---: | ---: | ---: | ---: | ---: |
| 区域光伏功率 | 39,456 | 13,248 | 0.30 MW | 0.83 MW | 1.20% |
| 区域负荷需求 | 39,456 | 13,248 | 422.14 MW | 516.59 MW | 10.30% |

这组指标仍然基于公式生成的区域标签，因此不能当作真实电网精度证明；它的作用是说明模型评估方式已经从随机打散验证，升级为更接近预测场景的“用过去预测未来”。

### 储能调度建议

储能层不是机器学习模型，而是一组可解释规则。输入包括：

- 光伏预测功率
- 负荷预测功率
- 当前 SOC
- 区域储能功率和容量假设
- 当前小时和负荷水平

输出包括充电/放电/待机动作、储能功率、储能后净负荷、削峰贡献、下一时刻 SOC 和文字说明。

## CAISO 真实数据回测

为了避免项目只停留在公式生成数据上，仓库加入了 CAISO OASIS 公开数据路线。CAISO 数据包含实际负荷、日前负荷预测、实际太阳能/风电出力和日前新能源预测。

当前仓库中保留了两组回测结果：

| 文件 | 时间范围 | 行数 | 用途 |
| --- | --- | ---: | --- |
| `solar/data/caiso_2024_2025_generation_load.csv` | 2024-01-01 至 2025-12-31 | 17,544 | 训练 + 2025 回测 |
| `solar/data/caiso_2025_predictions.csv` | 2025-01-01 至 2025-12-31 | 8,760 | 2025 预测结果 |
| `solar/data/caiso_2024_2026_generation_load.csv` | 2024-01-01 至 2026-06-01 | 21,191 | 训练 + 2026 滚动评估 |
| `solar/data/caiso_2026_predictions.csv` | 2026-01-01 至 2026-06-01 | 3,647 | 2026 已发布时段预测 |

2025 年回测结果，使用 2024 年数据训练，在 2025 年真实数据上评估：

| 目标 | 模型 MAE | 模型 RMSE | 模型 MAPE | CAISO 日前基线 MAE | 基线 RMSE | 基线 MAPE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 负荷 MW | 736.46 | 1,050.73 | 2.80% | 1,897.64 | 2,910.73 | 7.31% |
| 太阳能 MW | 506.64 | 918.96 | 164.09% | 748.80 | 1,467.58 | 85.63% |
| 太阳能 MW，白天有效出力 | 894.27 | 1,237.25 | 18.61% | 1,324.17 | 1,976.45 | 23.14% |
| 风电 MW | 250.70 | 338.99 | 47.84% | 242.53 | 336.24 | 38.32% |
| 净负荷 MW | 846.17 | 1,178.54 | 6.39% | - | - | - |

2026 年滚动评估，使用 2024-2025 年数据训练，在 2026-01-01 至 2026-06-01 的已发布真实数据上评估：

| 目标 | 模型 MAE | 模型 RMSE | 模型 MAPE | CAISO 日前基线 MAE | 基线 RMSE | 基线 MAPE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 负荷 MW | 1,032.77 | 1,612.05 | 4.07% | 2,429.99 | 3,781.53 | 9.68% |
| 太阳能 MW | 725.17 | 1,345.20 | 81.26% | 1,215.06 | 2,389.52 | 72.37% |
| 太阳能 MW，白天有效出力 | 1,386.05 | 1,879.39 | 16.41% | 2,329.69 | 3,338.85 | 24.76% |
| 风电 MW | 244.25 | 340.04 | 68.86% | 250.83 | 363.62 | 60.11% |
| 净负荷 MW | 1,098.19 | 1,700.47 | 8.80% | - | - | - |

太阳能全时段 MAPE 偏高，主要是夜间和低出力时段分母接近 0。展示项目时，更适合引用“白天有效出力”指标。

## 本地运行

建议使用 Python 3.11。macOS 上运行 XGBoost 可能需要先安装 OpenMP：

```bash
brew install libomp
```

安装依赖并启动服务：

```bash
cd /Users/wanna/solar_pred/solar-main
python3 -m venv .venv
source .venv/bin/activate
pip install -r solar/requirements.txt

cd solar
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

打开：

```text
http://localhost:8000
```

常用检查地址：

```text
http://localhost:8000/health
http://localhost:8000/docs
```

## Zeabur 部署

仓库已经包含 Zeabur/Nixpacks 配置：

- `.python-version`：指定 Python 3.11
- `nixpacks.toml`：安装 `solar/requirements.txt`，并通过 Uvicorn 启动 `solar/app.py`

Zeabur 部署步骤：

1. 将仓库推送到 GitHub。
2. 在 Zeabur 创建项目。
3. 添加 GitHub 仓库作为服务。
4. 让 Zeabur 使用仓库根目录下的 `nixpacks.toml`。
5. 部署完成后访问 Zeabur 分配的域名。

启动命令由 `nixpacks.toml` 指定：

```bash
cd solar && uvicorn app:app --host 0.0.0.0 --port ${PORT}
```

## API 概览

| 接口 | 方法 | 说明 |
| --- | --- | --- |
| `/` | GET | Web 页面 |
| `/health` | GET | 服务状态、模型状态和数据行数 |
| `/regions` | GET | 区域代表城市列表 |
| `/predict` | POST | 通用预测接口，兼容早期单电站模型和批量输入 |
| `/predict_region` | POST | 区域光伏发电功率预测 |
| `/predict_load` | POST | 区域负荷需求预测 |
| `/predict_dispatch` | POST | 发电、负荷、净负荷和调度建议 |
| `/predict_storage_dispatch` | POST | 储能充放电策略 |
| `/features` | GET | 当前模型特征列表 |
| `/caiso/backtests` | GET | CAISO 2025/2026 回测摘要 |
| `/feature_importance` | GET | 特征重要性 |
| `/plot/timeseries` | GET | 区域光伏趋势图 |
| `/plot/heatmap` | GET | 区域光伏热力图 |
| `/plot/load_balance` | GET | 光伏-负荷平衡图 |
| `/plot/storage_strategy` | GET | 储能策略图 |
| `/plot/caiso_backtest?period=2025&target=net_load` | GET | CAISO 真实值与预测值对比图 |

示例请求：

```json
{
  "region_id": "guangdong_guangzhou",
  "DATE_TIME": "2024-07-01 12:00:00",
  "AMBIENT_TEMPERATURE": 32.0,
  "RELATIVE_HUMIDITY": 72.0,
  "WIND_SPEED": 2.6,
  "IRRADIATION": 760.0,
  "storage_soc_percent": 50.0
}
```

示例返回：

```json
{
  "status": "success",
  "mode": "generation_load_dispatch",
  "solar_prediction_mw": 279.27,
  "load_prediction_mw": 6810.42,
  "dispatch_assessment": {
    "net_load_mw": 6531.15,
    "solar_share_percent": 4.10,
    "supply_level": "low",
    "ramp_risk": "low"
  },
  "storage_dispatch": {
    "action": "charge",
    "storage_power_mw": 69.82,
    "net_load_after_storage_mw": 6600.97,
    "next_soc_percent": 60.04
  }
}
```

## 重新生成数据和模型

重新拉取 NASA POWER 数据：

```bash
python3 solar/data_sources/nasa_power.py --start 20240101 --end 20241231
```

训练区域光伏模型：

```bash
python3 solar/train_regional_model.py
```

训练区域负荷模型：

```bash
python3 solar/train_load_model.py
```

重新运行 CAISO 回测：

```bash
python3 solar/train_caiso_backtest.py \
  --input solar/data/caiso_2024_2025_generation_load.csv \
  --train-start 2024-01-01 \
  --train-end 2024-12-31 \
  --predict-start 2025-01-01 \
  --predict-end 2025-12-31 \
  --output solar/data/caiso_2025_predictions.csv \
  --metrics-output solar/data/caiso_2025_backtest_metrics.json
```

## 当前限制

- 区域光伏和区域负荷的训练标签主要来自公开气象数据和透明基准公式，不是电网企业实测数据。
- 区域装机容量、峰值负荷和储能参数是演示假设。
- NASA POWER 是网格化公开气象数据，不等同于电站现场传感器数据。
- 储能策略是规则型建议，不是生产级优化调度或安全约束调度。
- CAISO 回测用于证明公开真实数据验证路线，但它代表的是 CAISO 系统，不代表华南区域电网。

## 后续可改进方向

- 引入更贴近业务场景的公开负荷数据或授权实测数据。
- 增加预测区间、不确定性评估和异常天气场景分析。
- 将储能规则升级为带约束的优化模型或模型预测控制。
- 增加 Pydantic 请求模型和自动化 API 测试。
- 增加批量场景上传、预测结果导出和历史方案管理。
