from enum import StrEnum


class DetectionStatus(StrEnum):
    """视觉风险的识别状态。"""

    DETECTED = "detected"
    NOT_DETECTED = "not_detected"
    UNCERTAIN = "uncertain"
    NOT_APPLICABLE = "not_applicable"


class RiskSeverity(StrEnum):
    """风险严重程度。"""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class RiskCategory(StrEnum):
    """第一阶段支持的图片风险类别。"""

    AGRICULTURE_ENVIRONMENT = "agriculture_environment"
    FOREST_ENVIRONMENT = "forest_environment"
    LIVESTOCK_ENVIRONMENT = "livestock_environment"
    FISHERY_ENVIRONMENT = "fishery_environment"
    WATER_ADJACENT_ENVIRONMENT = "water_adjacent_environment"
    TIDAL_FLAT_ENVIRONMENT = "tidal_flat_environment"
    MOUNTAIN_ENVIRONMENT = "mountain_environment"
    DESERTIFICATION_ENVIRONMENT = "desertification_environment"
    SEVERE_SHADING = "severe_shading"
    MINOR_SHADING = "minor_shading"
    AISLE_OBSTRUCTION = "aisle_obstruction"
    MISSING_PARAPET_OR_GUARDRAIL = "missing_parapet_or_guardrail"
    DRAINAGE_ABNORMAL = "drainage_abnormal"
    FLAMMABLE_MATERIAL = "flammable_material"
    HAZARDOUS_MATERIAL = "hazardous_material"


class DecisionType(StrEnum):
    """综合核保结论类型。"""

    ACCEPT = "accept"
    RECOMMEND_REJECT = "recommend_reject"
    SURCHARGE = "surcharge"
    CONDITIONAL_ACCEPT = "conditional_accept"
    REQUEST_MORE = "request_more"
    MANUAL_REVIEW = "manual_review"

class ProjectType(StrEnum):
    """支持的光伏项目类型。"""

    ROOFTOP = "rooftop"
    CARPORT = "carport"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class InstallationType(StrEnum):
    """光伏项目安装载体类型。"""

    COLOR_STEEL_ROOF = "color_steel_roof"
    FLAT_ROOF = "flat_roof"
    TILE_ROOF = "tile_roof"
    CARPORT_ROOF = "carport_roof"
    UNKNOWN = "unknown"


class MaterialCategory(StrEnum):
    """投保材料类别。"""

    PANORAMA = "panorama"
    ROOF_CONNECTION = "roof_connection"
    PARAPET = "parapet"
    WORKSHOP = "workshop"
    FILING_CERTIFICATE = "filing_certificate"
    GRID_CONNECTION_DOCUMENT = "grid_connection_document"
    ELECTRICAL_GROUNDING = "electrical_grounding"
    COMPONENT_NAMEPLATE = "component_nameplate"
    INVERTER_NAMEPLATE = "inverter_nameplate"
    COMBINER_BOX = "combiner_box"
    MONITORING_OPTIONAL = "monitoring_optional"
    OTHER = "other"


class MaterialQualityStatus(StrEnum):
    """材料质量检查状态。"""

    USABLE = "usable"
    POOR = "poor"
    UNUSABLE = "unusable"
    UNKNOWN = "unknown"


class MaterialParseStatus(StrEnum):
    """材料解析状态。"""

    PENDING = "pending"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class OcrValueStatus(StrEnum):
    """OCR字段提取状态。"""

    EXTRACTED = "extracted"
    MISSING = "missing"
    UNCERTAIN = "uncertain"

class ResistanceLevel(StrEnum):
    """组件综合抗灾能力等级。"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class ExpectedLossRisk(StrEnum):
    """自然灾害预期损失风险等级。"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"

class MaterialReviewAction(StrEnum):
    """规则引擎对单份材料的处理动作。"""

    PASS = "pass"
    WARNING = "warning"
    SURCHARGE = "surcharge"
    RECOMMEND_REJECT = "recommend_reject"
    CONDITIONAL = "conditional"
    REQUEST_MORE = "request_more"
    NOT_APPLICABLE = "not_applicable"


class ProcessingStep(StrEnum):
    """核保流水线处理步骤。"""

    MATERIAL_PARSE = "material_parse"
    OCR = "ocr"
    VISION = "vision"
    COMPONENT_LOOKUP = "component_lookup"
    WEATHER_LOOKUP = "weather_lookup"
    CATASTROPHE_ASSESSMENT = "catastrophe_assessment"
    RULE_ENGINE = "rule_engine"
    DECISION = "decision"


class ProcessingStatus(StrEnum):
    """单个处理步骤的运行状态。"""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"