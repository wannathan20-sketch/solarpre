# 区域新能源发电预测与电网调度辅助平台

这是一个面向电网调度与新能源预测方向的个人机器学习项目。项目已从原来的单电站 Kaggle 光伏预测，升级为基于 NASA POWER 公开气象和太阳辐照数据的区域新能源发电功率预测、负荷需求预测和储能调度辅助原型。

## 已完成功能

1. 数据源改造：使用 NASA POWER 小时级气象/辐照 API。
2. 区域范围：广东广州、广东深圳、广西南宁、云南昆明、贵州贵阳、海南海口。
3. 目标变量：基于辐照度、组件温度、装机容量和性能比估算 `SOLAR_POWER_MW`。
4. 模型训练：使用 XGBoost 建立区域光伏发电功率估算模型。
5. 负荷预测：基于时间、天气和区域峰值负荷假设生成 `REGIONAL_LOAD_MW` 基准标签，并训练负荷模型。
6. 储能调度：基于光伏发电功率、负荷需求和 SOC 给出充电、放电或待机建议。
7. Web 展示：支持区域选择、气象输入、调度辅助分析、特征重要性、趋势图、热力图和储能策略图。
8. 真实数据验证：接入 CAISO 公开电网数据，完成 2025 年历史回测和 2026 年已发布时段滚动预测。

## 项目定位

项目主题从“单个光伏电站发电量预测”升级为：

> 区域新能源发电预测与电网调度辅助原型

这更贴近新能源功率预测、调度运行、数字电网、发电-负荷平衡分析、储能充放电辅助决策等岗位方向，同时避免把个人项目表述成任何具体单位的内部系统。

## 数据文件

```text
data/south_china_solar_power.csv
data/south_china_load_power.csv
```

当前数据覆盖 2024 年 6 个代表城市，共 52,704 条小时级记录。

## 模型文件

```text
south_china_solar_model.joblib
south_china_load_model.joblib
```

如果该模型存在，FastAPI 会优先进入 `regional_solar` 模式。

## 运行方式

```bash
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

访问：

```text
http://localhost:8000
```

## 重新生成数据和模型

```bash
python3 data_sources/nasa_power.py --start 20240101 --end 20241231
python3 train_regional_model.py
python3 train_load_model.py
```

## API

| Endpoint | Method | Description |
| --- | --- | --- |
| `/` | GET | 前端页面 |
| `/health` | GET | 服务与模型模式检查 |
| `/regions` | GET | 区域代表城市列表 |
| `/predict_region` | POST | 区域光伏发电功率预测 |
| `/predict_load` | POST | 区域负荷需求预测 |
| `/predict_dispatch` | POST | 发电-负荷平衡与调度提示 |
| `/predict_storage_dispatch` | POST | 储能充放电策略 |
| `/features` | GET | 模型特征列表 |
| `/feature_importance` | GET | 特征重要性 |
| `/plot/timeseries` | GET | 区域发电趋势图 |
| `/plot/heatmap` | GET | 区域发电热力图 |
| `/plot/load_balance` | GET | 发电-负荷平衡图 |
| `/plot/storage_strategy` | GET | 储能策略图 |

## 说明

当前 `SOLAR_POWER_MW` 和 `REGIONAL_LOAD_MW` 均由公开气象数据、时间特征和透明基准公式生成，不是任何电网企业的官方实测调度数据。该项目适合作为作品集原型，用于展示数据接入、特征工程、预测建模、API 服务、可视化和电网调度辅助分析思路。

项目同时包含一条真实公开数据验证路线：使用 CAISO 公开负荷、太阳能、风电和日前预测数据，训练 2024 年模型并回测 2025 年真实数据，再用 2024-2025 年训练数据预测 2026 年已发布时段。当前 2025 回测中，负荷预测 MAPE 为 2.80%，净负荷预测 MAPE 为 6.39%，太阳能白天有效时段 MAPE 为 18.61%；2026 年截至 2026-06-01 的滚动评估中，负荷预测 MAPE 为 4.07%，净负荷预测 MAPE 为 8.80%，太阳能白天有效时段 MAPE 为 16.41%。
