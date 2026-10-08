# 分布式光伏财产险 AI 智能核保

[赛题要求覆盖矩阵](docs/赛题要求覆盖矩阵.md)
[判断透明化与证据追溯](docs/判断透明化与证据追溯.md)
[官方材料规则对照](docs/官方材料规则对照.md)

[地图影像辅助复核说明](docs/地图影像辅助复核.md)


本项目提供一个可运行的分布式光伏财产险核保后端，用于检查投保材料、提取结构化字段、识别图片风险、查询组件与历史气象数据、执行确定性规则，并生成核保结论和 Markdown 报告。

## 当前能力

- 检查 JPEG、PNG、PDF、XLSX 文件的格式、可读性、大小和重复情况
- 对图片预检尺寸、亮度和拉普拉斯清晰度；这些是可解释的启发式指标，不作为模型置信度或最终质量证明
- 通过 OpenAI 兼容多模态接口执行图片 OCR 和风险识别
- 读取 Excel 设备清单并结构化提取类别、型号、品牌、数量和价格；单一明确的组件型号可补充案件录入字段
- 将多页 PDF 渲染为图片后逐页执行 OCR
- 按材料类别把文件路由到适用的 OCR 或视觉 Provider
- OCR/设备清单提取型号后先查本地 JSON 目录；配置经审核的在线组件目录后，仅为缺失参数查询并补充完全一致型号的数据，保留逐项来源
- 可通过独立的在线资料检索接口查找厂商规格书候选；候选链接需人工核对，不会直接生成抗灾参数
- 通过 Open-Meteo 历史气象 API 查询 10 米最大日阵风、最大持续风速、单日总降水/降雨/降水时数和降雪量；逐变量记录单位与有效覆盖，并保留实际天气网格元数据
- 展示组件厂家参数与历史气象证据；对不具备同口径依据的风、雹、雪指标不计算能力比，明确转人工核验
- 执行材料规则、保守整单决策和完整处理留痕
- 展示判断路径、逐材料证据关联、规则触发条件/处理作用、整单优先顺序和自动化失败影响；识别分数标为未校准参考值
- 输出结构化 JSON 和 Markdown 核保报告
- 通过 FastAPI 和 Swagger UI 提供真实及 Mock 接口
- 在本地 SQLite 中保存结构化案件结果，提供历史查询和人工复核留痕；原始上传文件不落盘
- 检查材料包最低要求：至少 5 张图片、2 张全景照、备案证及各必需材料类别，并登记正面平视和俯拍视角
- 对 8 类明确拒保环境记录项目现场/邻近周边/远处背景关系；只对证据明确关联项目现场的环境自动建议拒保，其他可疑环境转人工核验
- 多张互补全景按案件合并检查覆盖，只对所有全景均未给出结果的项目要求补充对应视角
- 对每张视觉材料强制检查清晰度；模糊、过暗、关键区域缺失或视角不适用时要求补拍
- 先用视觉模型识别全景照风险并判断是否有水印；仅确认有水印时运行 OCR 提取拍摄日期和坐标，校验是否处于拟起保日前 15 天内
- 对投保标的地址、备案/并网项目地址及照片水印地址或坐标做位置核验：单一来源要求补证，明显冲突先预警和人工复核，不根据自动比对直接拒保；经人工确认异地后可用案件复核接口记录拒保结论
- 交叉核验备案证中的项目名称、项目单位、地址和被保险人；禁投关键词命中时给出拒保建议
- 从组件铭牌 OCR 提取型号、额定功率和序列号，并核对型号与案件信息是否一致
- 检查屋顶连接件、组件、逆变器、接地和汇流箱的可见异常；不根据普通照片推断电气性能或接地电阻
- 将备案证、并网材料中的项目名称、项目单位和地址互相核验，并在报告中列出 OCR 原文、标准值、置信度和位置
- 对监控材料提示核保人员复核优惠资格；没有正式费率配置时不自动计算折扣或保费
- 对监控覆盖图识别优惠候选；覆盖有效性及优惠条件由核保人员按正式条款确认
- 对车间材料要求登记企业所属行业；高火险行业列表和加费确认项可配置，官方名单缺失时显式转人工核验
- 通过 `data/rules/challenge_open_ai_01.json` 维护赛题规则版本、自动拒保环境关系与置信度门槛、阶段二检查开关和高火险行业关键词；灾害能力比阈值保留为配置材料，但在正式比较口径获批前不会用于评级
- 可选阶段二演示检查：背板鼓包/变色、支架锈蚀/变形、防水层损坏、未保护裸露线缆、危险工艺、洁净车间和消防设施
- 将明确拒保事实设为整案优先动作，并在报告中保留证据、图片位置和规则编号

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
PV_VLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
PV_VLM_API_KEY=
PV_VLM_MODEL=qwen3.8-flash
PV_VLM_TIMEOUT_SECONDS=120
~~~

默认使用阿里云百炼的 Qwen3.8-Flash 多模态模型。请在百炼控制台创建 API Key 并填入本机 `.env`；如果控制台提供业务空间专属兼容地址，建议将 `PV_VLM_BASE_URL` 替换为该地址。不要将 API Key 发到聊天或提交到 Git。

配置完成后，在项目根目录运行真实视觉识别验证：

~~~powershell
python .\scripts\run_real_vision.py "C:\path\to\test-image.jpg" --category panorama
~~~

`--category` 可换成 `component_nameplate`、`roof_connection`、`workshop` 等材料类别。OCR 可用 `scripts/run_real_ocr.py` 验证。首个成功请求会确认账号、模型名、兼容地址和图文请求链路可用；比赛识别效果仍需用 A/B/C 标注真值评测。

可选配置：

~~~dotenv
PV_COMPONENT_CATALOG_PATH=
PV_COMPONENT_ONLINE_CATALOG_URL=
PV_COMPONENT_ONLINE_CATALOG_API_KEY=
PV_COMPONENT_APPROVED_SOURCE_DOMAINS=jasolar.com
PV_COMPONENT_SEARCH_API_KEY=
PV_AMAP_WEB_SERVICE_KEY=
PV_AMAP_JS_API_KEY=
PV_AMAP_JS_SECURITY_CODE=
PV_WEATHER_BASE_URL=https://archive-api.open-meteo.com/v1/archive
PV_WEATHER_LOOKBACK_DAYS=3650
PV_WEATHER_DATA_LAG_DAYS=7
PV_WEATHER_TIMEOUT_SECONDS=30
PV_MAP_TIMEOUT_SECONDS=10
PV_CASE_DB_PATH=outputs/pv-underwriting.sqlite3
~~~

填写 `PV_AMAP_WEB_SERVICE_KEY` 后，工作台可从材料 OCR 地址或手动地址查询高德地理编码候选。核保员确认候选后，系统使用高德坐标近似反算出的 WGS84 坐标，在正式核保时请求 Open-Meteo Historical Weather API，读取历史 10 米最大日阵风、最大日持续风速、单日总降水、单日降雨、单日有降水时数和最大单日降雪量；结果保留逐变量有效日数、单位、查询时段、实际网格、高程和网格距离。地址变更时已选坐标会自动清空。近似坐标只用于风险筛查，不是测绘结果。

图片质量不合格时，工作台可把 OCR 地址或项目地址交由高德 Web 服务解析，并在核保员确认后展示卫星图层供人工复核。卫星图层需要单独申请 Web 端（JS API）Key 和安全密钥，配置到 `PV_AMAP_JS_API_KEY`、`PV_AMAP_JS_SECURITY_CODE`；当前 Web 服务 Key 不能代替 JS API Key。JS API 凭证会在同意地图复核后交给浏览器，因此应在高德控制台限制允许域名。卫星影像并非实时数据，可能看不到拍摄日期。高德服务协议禁止抓取、存储或截图地图内容；系统因此不把地图画面转发给视觉模型，也不让卫星影像自动改变核保结论。详见 **docs/地图影像辅助复核.md**。
填写 `PV_AMAP_WEB_SERVICE_KEY` 后，工作台可按项目地址查询高德地理编码候选。用户必须核对并点击候选项，系统才会把近似转换后的 WGS84 经纬度用于 Open-Meteo 历史天气查询；地址变更时已选坐标会自动清空。该坐标只用于风险筛查，不是测绘结果。
同一个 Key 也用于把中国境内的详细项目地址与照片水印位置作保守比对。自动流程只采用唯一且达到门牌号、兴趣点或楼宇级别的候选；单一位置来源仍标为未经交叉核验，明显冲突只触发人工复核。仅项目所在地地址会发送给地图服务，位置距离的 1/5 公里分界只用于筛查，**不是业务认可的自动拒保阈值**。

**PV_COMPONENT_CATALOG_PATH** 留空时会使用 **data/catalogs/component_catalog_2026-10-01.json**。该目录保留原有的两个示例条目，并从《光伏组件抗灾参数目录_2026-10-01.xlsx》导入 69 条中国市场且官网逐项列示的型号；全部 364 条原始记录保存在 **data/reference/component_parameters_2026-10-01.json** 供复核，其他市场版本、简写及范围展开型号不参与自动匹配。导入脚本为 **scripts/import_component_workbook.py**，更新源表后可重新生成两份 JSON。正反面最大静态载荷作为独立参考字段保存，不会换算成抗风或雪载；空缺的灾害参数仍会触发人工复核。导入数据尚需逐条核对官网版本和安装条件，不能直接作为生产核保依据。

示例目录还收录了设备清单写法 `JAM72D42-630W` 的演示条目。型号匹配会统一大小写、全角字符、破折号字形和空格，但保留 `-`、`/`、`.` 等型号标点；不同后缀不会被当作同一型号，别名必须经核对后显式登记。该演示条目的 `630W` 与厂商 `/LB` 后缀对应关系仍须核对铭牌；由于型号匹配参考分仅 0.5，现已从自动匹配中排除。系统会把目录中同功率、不同后缀的型号列为候选，但只供核保员核对铭牌，不会自动套用候选参数。组件参数缺失时，工作台按“确认完整型号与厂商 → 厂商官网精确型号 → 厂商系列 → Solar-Stack 完整型号/系列 → 配置的受信域名 → 人工补正”检索资料。Solar-Stack 阶段会打开型号搜索页，供核保员按 **Documents → Datasheet** 查看原始规格书；未配置 Brave Search API Key 时，工作台提供浏览器搜索链接和 Solar-Stack 手动入口，但不会在后台抓取网页。搜索摘要不会自动变成核保参数。核保员逐字段填写 HTTPS 来源并确认型号后，`POST /api/v1/components/corrections` 会把经人工确认的值写入本机 `outputs/component-corrections.json`，只补目录空字段，不覆盖已有值；详情见 [组件参数检索与人工补正](docs/组件参数检索与人工补正.md)。

若已有**经过审核的在线组件目录服务**，将其 HTTPS 地址填入 `PV_COMPONENT_ONLINE_CATALOG_URL`。核保流程会在本地型号缺失或本地风、雹、雪等字段为空时，向该服务发送 `GET ?model=<完整型号>`。服务以 404 表示无记录，或返回 `{"verified":true,"profile":{...ComponentProfile 字段...}}`。`profile.parameter_sources` 必须为每个非空数值字段提供厂商 HTTPS 来源链接。系统只接受完全一致的型号及 `PV_COMPONENT_APPROVED_SOURCE_DOMAINS` 列表中的厂商来源；本地已有值不被覆盖。需要认证时可设置 `PV_COMPONENT_ONLINE_CATALOG_API_KEY`（Bearer），不要将密钥提交到仓库。气象部分通过 Open-Meteo 获取可用的历史风、降水和降雪背景数据；该服务不提供可用于核保的历史冰雹直径或当地规范设计雪荷载。

**.env** 已被 Git 忽略，不要把真实 API Key 写入 **.env.example** 或其他受版本控制的文件。

## 启动服务

队友测试请按 [README_队友测试.md](README_队友测试.md) 配置环境，并用以下通用命令启动：

~~~powershell
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
~~~

启动后访问：

- 材料评测台：<http://127.0.0.1:8000/>
- Swagger UI：<http://127.0.0.1:8000/docs>
- OpenAPI：<http://127.0.0.1:8000/openapi.json>
- 健康检查：<http://127.0.0.1:8000/health>

## 主要接口

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | /health | 服务健康检查 |
| GET | /ready | 检查模型、组件目录、天气配置和案件数据库就绪状态，不返回密钥 |
| GET | /api/v1/components/sources?model=... | 查询厂商资料候选，供人工核对和入库 |
| POST | /api/v1/components/corrections | 保存带逐字段 HTTPS 来源的人工核验组件参数，供后续案件补齐空字段 |
| GET | /api/v1/locations/resolve?address=... | 查询项目地址候选和天气查询用近似坐标 |
| POST | /api/v1/weather/history | 按详细地址或 WGS84 经纬度查询历史风、雨、雪、气温和气压；冰雹缺少可信数据源时明确标记未取得 |
| GET | / | 本地材料评测台 |
| POST | /api/v1/files/inspect | 检查上传文件 |
| POST | /api/v1/ocr/extract | 对单个图片或 PDF 执行真实 OCR |
| POST | /api/v1/vision/analyze | 对单张图片执行真实风险识别 |
| POST | /api/v1/underwriting/analyze | 上传整单材料并执行完整真实核保流水线 |
| POST | /api/v1/underwriting/jobs | 提交后台整单分析任务，返回任务编号 |
| GET | /api/v1/underwriting/jobs/{job_id} | 查询任务阶段、进度及完成后的结构化结果 |
| GET | /api/v1/cases | 查询历史案件摘要，可按机器结论和复核状态筛选 |
| GET | /api/v1/cases/{case_id} | 查询案件分析结果与人工复核历史 |
| GET | /api/v1/cases/{case_id}/report | 下载包含机器结论和人工复核意见的 Markdown 报告 |
| POST | /api/v1/cases/{case_id}/review | 记录人工核保最终结论和意见 |
| POST | /api/v1/cases/{case_id}/map-review/prepare | 用户同意后用高德解析地址并返回候选位置和卫星层配置 |
| POST | /api/v1/cases/{case_id}/map-review | 记录地图页面人工观察及其位置/日期不确定性 |
| POST | /api/v1/reports/render | 把结构化核保结果渲染为 Markdown 报告 |
| POST | /api/v1/analyze/mock | 执行 Mock 核保流水线 |
| POST | /api/v1/reports/mock | 生成 Mock 核保报告 |
| GET | /api/v1/auth/config | 查询本地认证是否启用 |
| POST | /api/v1/auth/login | 使用本地账号登录并获取会话令牌 |
| GET/POST | /api/v1/auth/users | 管理员查看或创建账号 |
| POST | /api/v1/auth/users/{username}/deactivate | 管理员停用账号并撤销会话 |
| PUT | /api/v1/auth/users/{username}/password | 管理员重置密码并撤销会话 |
| POST | /api/v1/auth/logout | 撤销当前会话 |

工作台可下载带机器与人工复核信息的 Markdown 报告，也可使用浏览器“打印 / 保存为 PDF”。

当图片质量预检或视觉模型标记图片模糊/信息不足时，核保员可选择地图辅助复核。该功能用高德地理编码解析用户确认的地址；配置 Web 端 JS API Key 和安全密钥后，工作台展示卫星图层供核保员人工核对。影像不是实时画面，日期可能未知；系统不抓取、截图或转发地图影像，也不把影像发给视觉模型。地图观察单独留痕，不自动覆盖原图结论或改变机器核保建议。完整配置及边界见 [地图影像辅助复核说明](docs/地图影像辅助复核.md)。
历史气象接口的输入、字段和数据边界见 [气象历史查询接口说明](docs/weather-history-api.md)。

整单真实核保接口使用 **multipart/form-data**：

- **files**：一个或多个 JPEG、PNG、PDF 文件；设备清单可上传 XLSX
- **manifest**：案件、项目和材料类别组成的 JSON 字符串
- 文件顺序必须与 **manifest.materials** 顺序一致
- 单文件上限为 20 MiB；整单上传内容上限为 100 MiB，超限请求会提前停止读取

XLSX 仅接受非宏 Office Open XML 工作簿；归档展开体积上限为 64 MiB。设备清单逐行解析并保留文件、工作表和行号来源，价格仅作为材料展示，不用于推算保额或保费。清单里的唯一组件型号可补充案件型号，但仍需用铭牌材料和可信规格数据核验。

整单分析结果会写入本地 SQLite 数据库，默认位于 **outputs/pv-underwriting.sqlite3**；可通过 **PV_CASE_DB_PATH** 指定路径。数据库保存 OCR、识别与核保结果，其中可能包含企业或个人信息。系统不保存原始上传文件。默认 **PV_AUTH_ENABLED=false**，适用于绑定本机的单人演示；如需多人演示，可在 `.env` 设置 `PV_AUTH_ENABLED=true`，并提供至少 12 位的 `PV_ADMIN_USERNAME`、`PV_ADMIN_PASSWORD`。首次启动会创建管理员账号；管理员可在工作台账号管理面板创建查看者、核保员或其他管理员、重置密码并停用账号，停用和重置密码会撤销该账号的既有会话。查看者可浏览案件和报告，核保员可提交分析并记录人工复核，管理员可管理账号。会话使用 8 小时有效期，密码以带随机盐的 scrypt 哈希保存，数据库仅保存会话令牌的 SHA-256 哈希。该本地认证用于演示，不含 MFA、登录限速或生产级密钥管理；即使启用认证，也不要直接将服务暴露到公网，部署前仍需 HTTPS、网络访问控制及安全评审。团队确定获批保留期限后，可通过 **PV_CASE_RETENTION_DAYS** 设置启动时自动清理天数（默认 `0`，即关闭）；这不替代加密和正式删除流程。

后台任务最多同时运行 2 个（每个服务进程），任务状态和进度写入同一 SQLite 数据库；任务本身在当前进程内执行，服务重启后未完成任务会标记为中断，不会自动重放。比赛演示请保持服务运行直至任务完成。

全景照可标注 `capture_view`，支持 `front_level`、`overhead`、`other`、`unknown`。例如：

~~~json
{
  "material_id": "panorama-front-01",
  "category": "panorama",
  "capture_view": "front_level"
}
~~~

材料不足、视角未确认或缺少备案证时，接口会返回具体补充要求。视角由提交方根据原图标注，系统不会从文件名推断视角。

## 本地检查

~~~powershell
ruff check .\backend\app .\scripts .\tests
New-Item -ItemType Directory -Force .\outputs | Out-Null
pytest -q --basetemp=.\outputs\pytest-all-temp
git diff --check
~~~

本地验证以当前工作区实际运行结果为准。比赛 A/B/C 盲测材料尚未接入，当前测试结果不代表识别准确率已经达到赛题验收线。GitHub Actions 会在 Python 3.11、3.12 和 3.13 上运行 lint 与测试。

## 效果评测（取得测试材料后）

将脱敏标注整理为 JSONL 真值文件，每行至少包含 `case_id` 和 `expected_decision`；拒保场景另填 `required_high_risk_categories`，规则验证填 `required_rule_ids`。如需测误报率，须声明 `findings_complete: true` 并提供完整 `expected_findings`；OCR 对照填 `expected_ocr_fields`；可用 `suite` 标记 A/B/C。预测文件每行放一份完整核保结果，或后台任务返回对象。评测器统计案件覆盖率、结论准确率、高风险召回、完整标注案件的风险点精确率/召回率与误报数、OCR 字段准确率、规则召回、边界框 IoU 命中率、A/B/C 分组指标及处理耗时。风险点精确率和 OCR 准确率的门槛可通过命令行参数显式设置，默认不代替业务团队设阈值：

取得 A/B/C 测试包后，先运行材料预检，检查图片数量、备案证文件名线索、设备表以及 C 包是否到位：

~~~powershell
python .\scripts\audit_competition_packages.py "C:\Users\hhp\Desktop\众安比赛\命题8" --output .\outputs\package-audit.json
~~~

预检不会读取图片或证件内容，也不会根据文件名推断拍摄视角；备案证和视角仍须人工核实。确认资料齐全并取得标注真值后，再运行下方的模型评测。

~~~powershell
python .\scripts\evaluate_cases.py --truth .\data\private\ground-truth.jsonl --predictions .\outputs\predictions.jsonl --output .\outputs\evaluation.json
~~~

可选附加门槛：`--minimum-finding-precision 0.90`、`--minimum-ocr-accuracy 0.95`。耗时统计是处理留痕中各步骤 `latency_ms` 的合计，用于比较同一环境下的回归结果，不视为端到端网络耗时。

默认通过门槛为结论准确率 ≥ 90%、高风险拒保场景召回率 100%。评测材料和预测输出可能含敏感信息，保持在 Git 忽略的数据目录中，不要提交到仓库。官方规则工作簿已取得并在[规则对照表](docs/官方材料规则对照.md)登记；高火险行业清单和完整 A/B/C 标注真值包仍未接入，代码及单元测试不能证明上述业务验收指标已达标。

使用 `pytest -q --basetemp=.\outputs\pytest-all-temp` 运行本地完整回归。通过软件测试只验证代码逻辑，不代表 A/B/C 准确率或业务验收门槛已达标。取得完整盲测包和标注真值后仍需开展专项回归。

## 数据来源与判断边界

- 历史最大 10 米日阵风、日持续风速、单日总降水、单日降雨、降水时数和最大单日降雪量来自 [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)。
- 降水/降雨/降雪指标只作为网格化气候背景；不单独推断洪水、内涝或屋面结构雪荷载。
- Open-Meteo 历史阵风来自网格化再分析资料；报告保留项目点和实际网格点、高程及有效日数，避免把请求日期误当成完整观测覆盖。
- 项目地址经高德解析得到的是 GCJ-02 坐标；系统在核保员确认后使用近似反算的 WGS84 坐标调用 Open-Meteo。坐标精度、网格化气象分辨率和地址匹配级别都需要人工复核。
- 10 米历史阵风不能直接转换成屋面项目设计风压；组件正反面最大静态载荷也不能当作风荷载或结构雪荷载。当前不再对这些不同口径的数据计算能力比。
- 组件目录的 69 个精确列示中国市场型号保留正反面最大静载及字段级来源；其中 9 个另有冰雹试验直径和冲击速度。这些数据用于证据展示，不足以单独推出现场承载结论。
- Open-Meteo 不提供可直接用于本项目的历史最大冰雹直径，也不返回当地规范设计风压或结构雪荷载。
- 降雪量/雪深不能直接等同为结构雪荷载，当前不会伪造冰雹直径、冰雹频次或结构雪荷载值。
- 冰雹、雪荷载或组件参数缺失时，系统明确标记数据缺口并要求人工复核。
- 最终承保、拒保、加费和附加条件仍需由授权核保人员确认。
- 材料门槛、检查项和裁决顺序用于比赛 Demo 首期验收；投入真实业务前需由核保业务负责人确认。
- 本机已取得《光伏自核材料及规则-v2.xlsx》；高火险行业清单和 C 包仍缺失。规则配置中的行业列表因此留空，留空会触发人工复核，不会推定行业安全。
- 风灾需要当地规范设计风压、场地/屋面和安装条件；冰雹需要可配对的现场事件和厂家试验方法；雪灾需要项目结构设计雪荷载及组件安装条件。现有默认 0.75/1.25 尚未经业务方确认，当前不用于灾害评级；资料口径未验证时保持未知并转人工复核。
- 照片质量启发式阈值尚未通过完整比赛样本校准；它用于发现明显低分辨率、过暗或细节不足的照片，最终检查仍须结合视觉模型和人工复核。
- 高风险环境目标为召回率 ≥ 90% 且拒保场景零漏检；在完整 A/B/C 真值包回归前，不能宣称已通过该指标。

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

## Sentinel-2 auxiliary imagery

The map-review panel can request Copernicus Sentinel-2 L2A imagery for a confirmed Amap address. It displays a recent, cloud-screened, approximately 10 m/pixel context image; an optional, separately consented VLM description is retained only as a human-review suggestion. The imagery never changes the underwriting decision.

Configure the server-side Copernicus OAuth client in `.env` using `PV_SENTINEL_HUB_CLIENT_ID` and `PV_SENTINEL_HUB_CLIENT_SECRET`. See [the Sentinel-2 auxiliary review guide](docs/sentinel2-environment-review.md) for limits, consent, the API request, audit fields, and official references. Do not commit `.env`.

## 风险识别实验室

访问 `/vision-lab`，或从材料测试页点击“风险识别实验室”。支持 JPEG/PNG 图片的单张与批量风险识别、风险框和水印框与分析字段联动、提示词版本编辑、人工评价与漏检标注、同图同模型记录对比及 JSON 导出。本模块不调用 OCR。测试原图和历史保存在当前浏览器的 IndexedDB；清理浏览器站点数据会删除它们。只有显式点击“应用为工作台默认”才会改变正式图片识别的默认提示词，配置保存在 `data/vision_prompt_default.json`。

### 视觉提示词 V2

风险识别使用公共规则 + 当前材料专属模板 + 统一 JSON 规范。模板位于
`backend/app/prompts/vision/`；必检清单来自规则引擎现有配置。
风险识别实验室分别展示并支持编辑公共/专属提示词，实时预览当前图片实际组合文本。
另存版本会保存全部材料模板；批量运行按每张图片类别选择模板。
V1 完整提示词保留供历史对比。工作台默认版本为 V2；自定义组合可显式应用为正式默认，
存储在 `data/vision_prompt_default.json`。测试记录包含公共规则、所用专属规则和实际完整提示词。

视觉模型接口默认直连（`PV_VLM_TRUST_ENV=false`），避免继承系统代理导致请求超时；
网络环境必须使用代理时可设为 `true`。模型返回非法 JSON 或不符合字段约束时，
自动附带校验反馈重试一次；仍失败则明确报错，不生成替代风险结论。
实验室错误提示区分网络连接、响应超时、上游 HTTP 错误和输出格式错误。

### 自动推荐照片类别

风险识别实验室上传 JPEG/PNG 后默认调用独立分类接口
`POST /api/v1/vision/lab/classify`。返回主类别、可见依据和最多三个其他候选用途。
实验室自动应用推荐类别，无需人工确认；模型参考分不代表分类准确率。
可关闭“上传后自动推荐类别”，或点击“重新分类”。分类失败时保留手动选择。
所用类别和分类建议随图片保存在当前浏览器；风险测试记录保留当时的分类建议和所用类别。
此功能接入风险识别实验室，不自动修改正式案件材料。

实验室支持“一键运行”（当前图片自动分类→风险识别）和“批量一键运行”。
分类失败或返回 other 时停止该流程并提示手动选择，不沿用旧类别生成风险结论。
“仅识别风险”使用当前选择的类别，适合手动指定类别或提示词对比。
