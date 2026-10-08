"""Ordered, evidence-first search for missing photovoltaic module parameters."""

import re
from dataclasses import asdict, dataclass
from urllib.parse import quote_plus, urlparse

import httpx

from app.providers.common import ProviderError

_MODEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 /_.+-]{1,99}$")
_TEXT_PATTERN = re.compile(r"^[\w\u4e00-\u9fff .+()/-]{2,100}$")
_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"

# This is an intentionally small, reviewable map. Unknown brand names require an
# explicit trusted-domain configuration instead of guessing a manufacturer's site.
MANUFACTURER_DOMAINS: dict[str, tuple[str, ...]] = {
    "ja solar": ("jasolar.com",),
    "jasolar": ("jasolar.com",),
    "晶澳": ("jasolar.com",),
    "晶澳太阳能": ("jasolar.com",),
    "longi": ("longi.com",),
    "隆基": ("longi.com",),
    "jinkosolar": ("jinkosolar.com",),
    "jinko solar": ("jinkosolar.com",),
    "晶科": ("jinkosolar.com",),
    "trina solar": ("trinasolar.com",),
    "trina": ("trinasolar.com",),
    "天合": ("trinasolar.com",),
    "canadian solar": ("canadiansolar.com",),
    "阿特斯": ("canadiansolar.com",),
    "risen": ("risenenergy.com",),
    "risen energy": ("risenenergy.com",),
    "东方日升": ("risenenergy.com",),
    "qcells": ("qcells.com",),
    "韩华": ("qcells.com",),
}


@dataclass(frozen=True)
class ComponentDocumentLead:
    title: str
    url: str
    description: str
    stage: str
    source_domain: str
    model_match: str
    verified: bool = False


@dataclass(frozen=True)
class ComponentSearchStage:
    stage: str
    label: str
    query: str | None
    status: str
    documents: list[ComponentDocumentLead]
    note: str


class ComponentResearchAgent:
    """Search in user-specified order; results are leads, never model parameters."""

    def __init__(
        self,
        api_key: str = "",
        *,
        trusted_domains: tuple[str, ...] = (),
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.api_key = api_key.strip()
        self.trusted_domains = tuple(
            sorted({_normalize_domain(domain) for domain in trusted_domains if domain.strip()})
        )
        self.transport = transport

    def search(
        self,
        *,
        model: str,
        manufacturer: str = "",
        series: str = "",
    ) -> list[ComponentSearchStage]:
        model = model.strip()
        manufacturer = manufacturer.strip()
        series = series.strip()
        if not _MODEL_PATTERN.fullmatch(model):
            raise ValueError("invalid component model")
        if manufacturer and not _TEXT_PATTERN.fullmatch(manufacturer):
            raise ValueError("invalid manufacturer")
        if series and not _MODEL_PATTERN.fullmatch(series):
            raise ValueError("invalid component series")

        solar_stack_url = (
            "https://www.solar-stack.com/en/panel?q=" + quote_plus(model)
        )
        identity_known = bool(manufacturer)
        identity_stage = ComponentSearchStage(
            stage="identify_manufacturer_and_model",
            label="识别厂商与完整型号",
            query=None,
            status="ready" if identity_known else "needs_input",
            documents=[],
            note=(
                f"厂商：{manufacturer}；完整型号：{model}；"
                f"系列：{series or '未提供'}。核对铭牌前仍按候选信息处理。"
                if identity_known
                else f"完整型号：{model}；厂商和系列未确认，请先核对铭牌。"
            ),
        )
        if not self.api_key:
            return [
                identity_stage,
                ComponentSearchStage(
                    stage="search_api_unconfigured",
                    label="在线检索暂不可用",
                    query=None,
                    status="skipped",
                    documents=[],
                    note=(
                        "未配置 Brave Search API Key；仍可打开 Solar-Stack 型号搜索页，"
                        "按 Documents → Datasheet 查看原始规格书。"
                    ),
                )
            ]

        manufacturer_domains = _manufacturer_domains(manufacturer)
        stages: list[ComponentSearchStage] = [identity_stage]
        queries: list[tuple[str, str, str, tuple[str, ...]]] = []
        if manufacturer_domains:
            queries.append((
                "manufacturer_exact",
                "厂商官网精确型号",
                f'site:{manufacturer_domains[0]} "{model}" module datasheet',
                manufacturer_domains,
            ))
            if series and series.casefold() != model.casefold():
                queries.append((
                    "manufacturer_series",
                    "厂商官网系列资料",
                    f'site:{manufacturer_domains[0]} "{series}" module datasheet',
                    manufacturer_domains,
                ))
        else:
            stages.append(ComponentSearchStage(
                stage="manufacturer_domain_unknown",
                label="厂商官网精确型号 / 系列",
                query=None,
                status="skipped",
                documents=[],
                note="未识别厂商官网域名；请在表单补全标准厂商名称或配置受信域名。",
            ))

        queries.append((
            "solar_stack_exact",
            "Solar-Stack 完整型号原始资料",
            f'site:solar-stack.com/en/panel "{model}"',
            ("solar-stack.com",),
        ))
        if series and series.casefold() != model.casefold():
            queries.append((
                "solar_stack_series",
                "Solar-Stack 系列资料",
                f'site:solar-stack.com/en/panel "{series}"',
                ("solar-stack.com",),
            ))

        if self.trusted_domains:
            domain_query = " OR ".join(f"site:{domain}" for domain in self.trusted_domains)
            queries.append((
                "trusted_web",
                "已配置受信域名检索",
                f'({domain_query}) "{model}" photovoltaic datasheet',
                self.trusted_domains,
            ))
        queries.append((
            "general_web",
            "全网网页检索（来源需人工核验）",
            f'"{model}" photovoltaic module datasheet',
            (),
        ))

        for stage_id, label, query, allowed_domains in queries:
            try:
                documents = self._search_query(
                    query=query,
                    stage=stage_id,
                    requested_model=model,
                    allowed_domains=allowed_domains,
                )
            except ProviderError:
                stages.append(ComponentSearchStage(
                    stage=stage_id,
                    label=label,
                    query=query,
                    status="failed",
                    documents=[],
                    note=(
                        "搜索服务暂不可用；未采纳搜索摘要。可使用下方 Solar-Stack 链接"
                        "或直接前往厂商官网的 Datasheet 页面。"
                    ),
                ))
                break
            status = "found" if documents else "no_results"
            stages.append(ComponentSearchStage(
                stage=stage_id,
                label=label,
                query=query,
                status=status,
                documents=documents,
                note=(
                    "结果仅作为资料入口；打开原始规格书确认完整型号、版本、单位和测试条件。"
                    if documents
                    else "本阶段未找到符合域名限制的结果，继续下一阶段。"
                ),
            ))
            if any(
                document.model_match == "exact_model_text_present"
                for document in documents
            ):
                break

        # The UI page is a no-key fallback and is kept explicit even when the
        # search API itself could not locate the model page.
        stages.append(ComponentSearchStage(
            stage="solar_stack_manual_navigation",
            label="Solar-Stack 手动查看 Datasheet",
            query=solar_stack_url,
            status="available",
            documents=[ComponentDocumentLead(
                title=f"在 Solar-Stack 搜索 {model}",
                url=solar_stack_url,
                description="进入型号或系列页面，再选择 Documents → Datasheet；核对 Datasheet 中的型号后人工录入。",
                stage="solar_stack_manual_navigation",
                source_domain="solar-stack.com",
                model_match="exact_query",
            )],
            note=(
                "Solar-Stack 是第三方资料导航/数据库；记录其型号页和 Datasheet 原始来源，"
                "不可将搜索摘要直接填作核保参数。"
            ),
        ))
        return stages

    def _search_query(
        self,
        *,
        query: str,
        stage: str,
        requested_model: str,
        allowed_domains: tuple[str, ...],
    ) -> list[ComponentDocumentLead]:
        if not self.api_key:
            return []
        try:
            with httpx.Client(timeout=15.0, transport=self.transport) as client:
                response = client.get(
                    _SEARCH_URL,
                    params={"q": query, "count": 8},
                    headers={"X-Subscription-Token": self.api_key},
                )
                response.raise_for_status()
                results = response.json().get("web", {}).get("results", [])
        except (httpx.HTTPError, ValueError, AttributeError, TypeError) as exc:
            raise ProviderError("component source search failed") from exc

        leads: list[ComponentDocumentLead] = []
        seen: set[str] = set()
        for item in results:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            if not isinstance(url, str):
                continue
            parsed = urlparse(url)
            host = (parsed.hostname or "").lower()
            if (
                parsed.scheme != "https"
                or not host
                or (
                    allowed_domains
                    and not any(_host_matches(host, domain) for domain in allowed_domains)
                )
                or url in seen
            ):
                continue
            seen.add(url)
            title = str(item.get("title") or "")[:300]
            description = str(item.get("description") or "")[:600]
            haystack = f"{title} {description} {url}".casefold()
            leads.append(ComponentDocumentLead(
                title=title,
                url=url,
                description=description,
                stage=stage,
                source_domain=host,
                model_match=(
                    "exact_model_text_present"
                    if requested_model.casefold() in haystack
                    else "domain_and_query_match_only"
                ),
            ))
        return leads


def _normalize_domain(value: str) -> str:
    domain = value.strip().lower().lstrip(".")
    if not domain or ":" in domain or "/" in domain or "@" in domain:
        raise ValueError("invalid trusted component source domain")
    if not re.fullmatch(r"[a-z0-9.-]+", domain):
        raise ValueError("invalid trusted component source domain")
    return domain


def _manufacturer_domains(manufacturer: str) -> tuple[str, ...]:
    normalized = re.sub(r"\s+", " ", manufacturer).strip().casefold()
    return MANUFACTURER_DOMAINS.get(normalized, ())


def _host_matches(host: str, domain: str) -> bool:
    normalized_domain = _normalize_domain(domain)
    return host == normalized_domain or host.endswith("." + normalized_domain)


def stage_as_dict(stage: ComponentSearchStage) -> dict[str, object]:
    return asdict(stage)
