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
    REJECT = "reject"
    SURCHARGE = "surcharge"
    CONDITIONAL_ACCEPT = "conditional_accept"
    REQUEST_MORE = "request_more"
    MANUAL_REVIEW = "manual_review"