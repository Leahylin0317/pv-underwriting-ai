# 分布式光伏财产险 AI 智能核保

本项目提供一个可运行的 v0.1 后端，用于检查投保材料、提取结构化字段、识别图片风险、查询组件与历史气象数据、执行确定性规则，并生成核保结论和 Markdown 报告。

## 当前能力

- 检查 JPEG、PNG、PDF 文件的格式、可读性、大小和重复情况
- 通过 OpenAI 兼容多模态接口执行图片 OCR 和风险识别
- 将多页 PDF 渲染为图片后逐页执行 OCR
- 按材料类别把文件路由到适用的 OCR 或视觉 Provider
- 从本地 JSON 组件目录查询风荷载、雪荷载和抗冰雹参数
- 通过 Open-Meteo 历史气象 API 查询项目坐标的历史最大阵风
- 比较组件能力和风、雹、雪灾害指标，缺少可靠数据时转人工复核
- 执行材料规则、保守整单决策和完整处理留痕
- 输出结构化 JSON 和 Markdown 核保报告
- 通过 FastAPI 和 Swagger UI 提供真实及 Mock 接口

## 环境要求

- Python 3.11、3.12 或 3.13
- 建议使用独立 Conda 或虚拟环境

安装项目和开发依赖：

~~~powershell
python -m pip install -e ".[dev]"
~~~

## 配置

复制配置模板：

~~~powershell
Copy-Item .\.env.example .\.env
notepad .\.env
~~~

真实 OCR 和视觉接口需要填写：

~~~dotenv
PV_VLM_BASE_URL=
PV_VLM_API_KEY=
PV_VLM_MODEL=qwen3.8-flash
PV_VLM_TIMEOUT_SECONDS=60
~~~

可选配置：

~~~dotenv
PV_COMPONENT_CATALOG_PATH=
PV_WEATHER_BASE_URL=https://archive-api.open-meteo.com/v1/archive
PV_WEATHER_LOOKBACK_DAYS=3650
PV_WEATHER_DATA_LAG_DAYS=7
PV_WEATHER_TIMEOUT_SECONDS=30
~~~

**PV_COMPONENT_CATALOG_PATH** 留空时会使用 **data/examples/component_catalog.sample.json**。该文件仅包含演示数据，不得作为生产核保依据。

**.env** 已被 Git 忽略，不要把真实 API Key 写入 **.env.example** 或其他受版本控制的文件。

## 启动服务

~~~powershell
python -m uvicorn app.main:app --reload
~~~

启动后访问：

- Swagger UI：<http://127.0.0.1:8000/docs>
- OpenAPI：<http://127.0.0.1:8000/openapi.json>
- 健康检查：<http://127.0.0.1:8000/health>

## 主要接口

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | /health | 服务健康检查 |
| POST | /api/v1/files/inspect | 检查上传文件 |
| POST | /api/v1/ocr/extract | 对单个图片或 PDF 执行真实 OCR |
| POST | /api/v1/vision/analyze | 对单张图片执行真实风险识别 |
| POST | /api/v1/underwriting/analyze | 上传整单材料并执行完整真实核保流水线 |
| POST | /api/v1/reports/render | 把结构化核保结果渲染为 Markdown 报告 |
| POST | /api/v1/analyze/mock | 执行 Mock 核保流水线 |
| POST | /api/v1/reports/mock | 生成 Mock 核保报告 |

整单真实核保接口使用 **multipart/form-data**：

- **files**：一个或多个 JPEG、PNG、PDF 文件
- **manifest**：案件、项目和材料类别组成的 JSON 字符串
- 文件顺序必须与 **manifest.materials** 顺序一致

## 本地检查

~~~powershell
ruff check .\backend\app .\scripts .\tests
pytest -q --basetemp=.\outputs\pytest-all-temp
git diff --check
~~~

当前基线为 206 项测试通过。**StarletteDeprecationWarning** 来自当前 TestClient 依赖组合，不影响测试结果。

## 数据来源与判断边界

- 历史最大阵风来自 [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)。
- 当前风灾结果使用历史阵风动压与组件额定风荷载进行初步筛查，不替代结构工程设计验算。
- Open-Meteo 不提供可直接用于本项目的历史最大冰雹直径。
- 降雪深度不能直接等同为结构雪荷载，因此当前不会伪造冰雹或雪荷载值。
- 冰雹、雪荷载或组件参数缺失时，系统明确标记数据缺口并要求人工复核。
- 最终承保、拒保、加费和附加条件仍需由授权核保人员确认。

## 数据安全

禁止向仓库提交：

- API Key 和密码
- 官方受限测试图片
- 真实投保材料
- 未脱敏个人或企业信息
- 大模型或视觉模型权重
- 来源和授权不明确的数据集

## 协作方式

- **main** 保存已完成并通过检查的代码
- 核心框架使用 **feature/core-\*** 分支
- AI Provider 使用 **feature/ai-\*** 分支
- 每个任务通过 Pull Request 审核后合并
- 所有模块通过 **docs/schema-v0.1.md** 中的统一数据契约对接
