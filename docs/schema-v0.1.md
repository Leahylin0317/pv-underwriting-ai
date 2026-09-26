# 核保数据契约 Schema v0.1

## 1 目的

本文件定义材料接收、OCR、视觉识别、外部数据、规则判断和综合核保决策之间的统一数据格式。

技术人员一和技术人员二必须按照本契约交换数据。任何字段修改先更新本文件并经双方确认，不允许在各自模块中私自创建含义重复的字段。

## 2 当前业务范围

阶段一只处理：

\- 工商业屋顶式光伏
\- 车棚顶式光伏

以下场景属于拒保候选场景：

\- 农田
\- 林地
\- 畜牧场景
\- 渔业场景
\- 涉水环境
\- 滩涂
\- 山地
\- 沙漠化环境
\- 备案材料包含集中式、林光、渔光、滩涂等禁投关键词

阶段二的支架锈蚀、组件背板鼓包、防水层损坏和危险工艺识别暂不纳入本版本。

## 3 通用约束

1\. `schema\_version` 固定为 `0.1.0`。
2\. 所有置信度采用 0 到 1 之间的小数。
3\. 未识别成功的字段使用 `null`，不允许编造内容。
4\. `uncertain` 与 `not\_detected` 含义不同。
5\. 低置信度结果必须标记为 `uncertain`。
6\. 低质量或低置信度材料进入 `request\_more`，不能强行判断承保或拒保。
7\. 每个识别结果必须能够追溯到具体材料。
8\. 图片风险点应尽可能提供 bbox。
9\. bbox 使用 0 到 1 的归一化坐标。
10\. 组件参数和气象数据必须保留来源、单位及获取时间。
11\. 系统不输出具体保费金额。

## 4 顶层对象 UnderwritingCase

| 字段 | 类型 | 必填 | 产生方 | 含义 |
| --- | --- | --- | --- | --- |
| schema\_version | string | 是 | 系统 | 当前固定为 0.1.0 |
| case\_id | string | 是 | 系统 | 单次核保案件唯一编号 |
| project | ProjectInfo | 是 | 材料解析和用户输入 | 项目与被保险标的信息 |
| materials | Material\[] | 是 | 材料接收模块 | 本次提交的全部材料 |
| ocr\_fields | OcrField\[] | 是 | OCR Provider | 结构化文字识别结果 |
| findings | RiskFinding\[] | 是 | Vision Provider | 图片风险识别结果 |
| component\_profile | ComponentProfile 或 null | 否 | 组件参数 Provider | 组件型号及抗灾参数 |
| weather\_profile | WeatherProfile 或 null | 否 | 气象 Provider | 项目所在地气象风险 |
| catastrophe\_assessment | CatastropheAssessment 或 null | 否 | 风险量化模块 | 设备能力与气象风险比较结果 |
| material\_reviews | MaterialReview\[] | 是 | 规则引擎 | 每份材料的审核结论 |
| decision | UnderwritingDecision 或 null | 否 | 决策模块 | 整单综合核保意见 |
| processing\_trace | ProcessingTrace\[] | 是 | 各处理模块 | 模型、耗时和异常留痕 |

## 5 ProjectInfo 项目信息

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| project\_name | string 或 null | 是 | 项目名称，无法识别时为 null |
| insured\_name | string 或 null | 是 | 被保险人名称 |
| project\_entity | string 或 null | 否 | 备案证项目单位 |
| project\_type | enum | 是 | rooftop、carport、unsupported、unknown |
| installation\_type | enum | 是 | color\_steel\_roof、flat\_roof、tile\_roof、carport\_roof、unknown |
| site\_address | string 或 null | 是 | 被保险项目地址 |
| province | string 或 null | 否 | 省 |
| city | string 或 null | 否 | 市 |
| district | string 或 null | 否 | 区县 |
| longitude | number 或 null | 是 | 项目经度，缺失时触发补材 |
| latitude | number 或 null | 是 | 项目纬度，缺失时触发补材 |
| proposed\_start\_date | date 或 null | 是 | 计划起保日期 |
| component\_model | string 或 null | 是 | 组件型号，缺失时触发补材 |
| submission\_ip | string 或 null | 否 | 材料提交端 IP，仅用于审计 |

## 6 Material 材料对象

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| material\_id | string | 是 | 材料唯一编号 |
| category | enum | 是 | 材料类别 |
| file\_name | string | 是 | 原始文件名 |
| media\_type | string | 是 | image/jpeg、image/png、application/pdf 等 |
| sha256 | string 或 null | 否 | 文件摘要，用于证据追溯 |
| captured\_at | datetime 或 null | 否 | 水印或元数据中的拍摄时间 |
| longitude | number 或 null | 否 | 图片水印中的经度 |
| latitude | number 或 null | 否 | 图片水印中的纬度 |
| quality\_status | enum | 是 | usable、poor、unusable、unknown |
| quality\_confidence | number 或 null | 否 | 图片质量判断置信度 |
| quality\_issues | string\[] | 是 | blur、dark、wrong\_angle、key\_area\_missing 等 |
| parse\_status | enum | 是 | pending、success、partial、failed |

材料类别 `category`：

\- `panorama`
\- `roof\_connection`
\- `parapet`
\- `workshop`
\- `filing\_certificate`
\- `grid\_connection\_document`
\- `electrical\_grounding`
\- `component\_nameplate`
\- `inverter\_nameplate`
\- `combiner\_box`
\- `monitoring\_optional`
\- `other`

## 7 OcrField 文字识别结果

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| field\_id | string | 是 | OCR 字段唯一编号 |
| material\_id | string | 是 | 来源材料编号 |
| field\_name | string | 是 | project\_name、insured\_name、component\_model 等 |
| raw\_value | string 或 null | 是 | OCR 原始文字 |
| normalized\_value | string 或 null | 是 | 清洗后的标准值 |
| value\_status | enum | 是 | extracted、missing、uncertain |
| confidence | number | 是 | OCR 置信度 |
| bbox | Bbox 或 null | 否 | 文字在图片中的位置 |
| provider | string | 是 | OCR 服务名称 |
| model | string | 是 | 使用的模型或版本 |
| evidence\_text | string 或 null | 否 | 支撑结果的原始文字片段 |

## 8 RiskFinding 图片风险识别结果

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| finding\_id | string | 是 | 风险点唯一编号 |
| material\_id | string | 是 | 来源材料编号 |
| category | enum | 是 | 风险类别 |
| label | string | 是 | 面向报告展示的中文标签 |
| detection\_status | enum | 是 | detected、not\_detected、uncertain、not\_applicable |
| severity | enum | 是 | info、low、medium、high、critical、unknown |
| confidence | number | 是 | 识别置信度 |
| bbox | Bbox 或 null | 否 | 风险区域坐标 |
| evidence\_text | string | 是 | 模型识别依据 |
| provider | string | 是 | 视觉服务名称 |
| model | string | 是 | 模型名称或版本 |
| requires\_manual\_review | boolean | 是 | 是否需要人工复核 |

阶段一风险类别 `category`：

\- `agriculture\_environment`
\- `forest\_environment`
\- `livestock\_environment`
\- `fishery\_environment`
\- `water\_adjacent\_environment`
\- `tidal\_flat\_environment`
\- `mountain\_environment`
\- `desertification\_environment`
\- `severe\_shading`
\- `minor\_shading`
\- `aisle\_obstruction`
\- `missing\_parapet\_or\_guardrail`
\- `drainage\_abnormal`
\- `flammable\_material`
\- `hazardous\_material`

## 9 Bbox 风险位置

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| x\_min | number | 是 | 左边界，0 到 1 |
| y\_min | number | 是 | 上边界，0 到 1 |
| x\_max | number | 是 | 右边界，0 到 1 |
| y\_max | number | 是 | 下边界，0 到 1 |
| coordinate\_space | string | 是 | 固定为 normalized\_0\_1 |

必须满足：

\- `0 <= x\_min < x\_max <= 1`
\- `0 <= y\_min < y\_max <= 1`

## 10 ComponentProfile 组件抗灾参数

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| component\_model | string | 是 | 标准化组件型号 |
| manufacturer | string 或 null | 否 | 厂商 |
| rated\_power\_w | number 或 null | 否 | 标称功率，单位 W |
| hail\_resistance\_mm | number 或 null | 否 | 可抵御冰雹直径，单位 mm |
| wind\_load\_pa | number 或 null | 否 | 风荷载能力，单位 Pa |
| snow\_load\_pa | number 或 null | 否 | 雪荷载能力，单位 Pa |
| source\_url | string 或 null | 是 | 厂商或公开资料来源 |
| source\_name | string | 是 | 数据来源名称 |
| retrieved\_at | datetime | 是 | 数据获取时间 |
| match\_confidence | number | 是 | 型号匹配置信度 |

## 11 WeatherProfile 气象数据

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| longitude | number | 是 | 查询经度 |
| latitude | number | 是 | 查询纬度 |
| historical\_max\_wind\_m\_s | number 或 null | 否 | 历史最大风速，单位 m/s |
| historical\_max\_hail\_mm | number 或 null | 否 | 历史最大冰雹直径，单位 mm |
| historical\_max\_snow\_load\_pa | number 或 null | 否 | 历史雪荷载估计，单位 Pa |
| observation\_start | date 或 null | 否 | 历史数据起始日期 |
| observation\_end | date 或 null | 否 | 历史数据结束日期 |
| source\_name | string | 是 | 气象数据来源 |
| source\_url | string 或 null | 否 | 来源地址 |
| retrieved\_at | datetime | 是 | 获取时间 |

## 12 CatastropheAssessment 自然灾害量化

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| resistance\_level | enum | 是 | low、medium、high、unknown |
| expected\_loss\_risk | enum | 是 | low、medium、high、critical、unknown |
| factors | string\[] | 是 | 影响结果的因素 |
| explanation | string | 是 | 可解释的比较过程 |
| triggered\_rule\_ids | string\[] | 是 | 命中的规则编号 |
| requires\_manual\_review | boolean | 是 | 是否需要人工判断 |

该对象只输出风险等级和理由，不输出具体保费。

## 13 MaterialReview 逐项审核结果

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| material\_id | string | 是 | 被审核材料编号 |
| action | enum | 是 | pass、warning、surcharge、recommend_reject、conditional、request\_more、not\_applicable |
| triggered\_rule\_ids | string\[] | 是 | 命中的业务规则 |
| finding\_ids | string\[] | 是 | 引用的风险点 |
| ocr\_field\_ids | string\[] | 是 | 引用的 OCR 字段 |
| reasons | string\[] | 是 | 审核原因 |
| missing\_requirements | string\[] | 是 | 需要补充的内容 |
| requires\_manual\_review | boolean | 是 | 是否需要人工复核 |

## 14 UnderwritingDecision 综合核保意见

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| decision | enum | 是 | accept、recommend_reject、surcharge、conditional\_accept、request\_more、manual\_review |
| decisive\_rule\_ids | string\[] | 是 | 决定最终结论的规则 |
| reasons | string\[] | 是 | 综合判断理由 |
| conditions | string\[] | 是 | 附加承保条件 |
| warnings | string\[] | 是 | 风险提示 |
| missing\_requirements | string\[] | 是 | 需要补充的材料 |
| generated\_at | datetime | 是 | 结论生成时间 |

决策优先级暂定：

1\. `recommend_reject`
2\. `request\_more`
3\. `manual\_review`
4\. `surcharge`
5\. `conditional\_accept`
6\. `accept`

最终优先级须由金融成员确认。

## 15 ProcessingTrace 处理留痕

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| step | string | 是 | material\_parse、ocr、vision、component\_lookup、weather\_lookup、catastrophe\_assessment、rule\_engine、decision |
| provider | string | 是 | 执行模块或外部服务 |
| model | string 或 null | 否 | 模型名称和版本 |
| started\_at | datetime | 是 | 开始时间 |
| finished\_at | datetime | 是 | 完成时间 |
| latency\_ms | integer | 是 | 耗时 |
| status | enum | 是 | success、partial、failed |
| error\_code | string 或 null | 否 | 错误编号 |
| error\_message | string 或 null | 否 | 脱敏后的错误信息 |

## 16 需要金融成员确认的问题

1\. 低置信度阈值具体是多少？
2\. 缺少经纬度是否必须补材？
3\. 缺少组件型号是否必须补材？
4\. 拍摄日期超过起保前 15 日时，是提示还是补材？
5\. 项目单位与被保险人不一致时，是预警还是拒保？
6\. 项目地址与被保险地址不一致时，是预警还是拒保？
7\. 严重遮挡与轻微遮挡的业务边界是什么？
8\. 车间易燃物和危险品分别触发提示、加费还是拒保？
9\. 自然灾害风险等级如何触发加费或附加条件？
10\. 综合决策优先级是否认可？
11\. 无水印照片是提示还是必须补材？
12\. 哪些材料在首期属于强制材料？
