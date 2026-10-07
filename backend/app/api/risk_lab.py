"""Isolated catastrophe screening experiments using the production calculation engine."""
from datetime import UTC, date, datetime
from math import isfinite
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, model_validator
from starlette.concurrency import run_in_threadpool

from app.api.component_dependencies import get_component_provider
from app.api.weather_dependencies import build_weather_provider
from app.catastrophe.engine import CatastropheAssessmentEngine
from app.contracts import ComponentProfile, WeatherProfile
from app.providers.common import ProviderError
from app.rules.config import BusinessRulesConfig

router=APIRouter()
ROOT=Path(__file__).resolve().parents[3]/'frontend'

@router.get('/risk-lab',include_in_schema=False)
def page(): return FileResponse(ROOT/'risk-lab.html')

@router.get('/risk-lab.js',include_in_schema=False)
def script(): return FileResponse(ROOT/'risk-lab.js',media_type='application/javascript')

@router.get('/api/v1/risk/lab/config')
def config():
    rules=BusinessRulesConfig.load()
    return {'version':rules.version,'ruleset_id':rules.ruleset_id,'source_note':rules.source_note,
            'adequate_margin_ratio':rules.catastrophe_adequate_margin_ratio,
            'critical_shortfall_ratio':rules.catastrophe_critical_shortfall_ratio}

@router.get('/api/v1/risk/lab/component')
async def component(model:str=Query(min_length=1,max_length=150)):
    try:
        result=await run_in_threadpool(get_component_provider().lookup,model)
    except ProviderError as exc: raise HTTPException(502,'组件参数查询失败，请稍后重试') from exc
    if result is None: raise HTTPException(404,'目录未匹配到该完整型号，请核对铭牌；不会自动补全抗灾参数')
    return result

class WeatherRequest(BaseModel):
    longitude:float=Field(ge=-180,le=180,allow_inf_nan=False)
    latitude:float=Field(ge=-90,le=90,allow_inf_nan=False)
    observation_start:date|None=None
    observation_end:date|None=None
    @model_validator(mode='after')
    def dates(self):
        if bool(self.observation_start)!=bool(self.observation_end):raise ValueError('查询开始和结束日期须同时填写')
        if self.observation_start and self.observation_start>self.observation_end:raise ValueError('开始日期不能晚于结束日期')
        return self

@router.post('/api/v1/risk/lab/weather')
async def weather(data:WeatherRequest):
    provider=build_weather_provider()
    if data.observation_start:
        provider.observation_start=data.observation_start;provider.observation_end=data.observation_end
    try:return await run_in_threadpool(provider.lookup,longitude=data.longitude,latitude=data.latitude)
    except ProviderError as exc:raise HTTPException(502,'历史气象查询失败，请稍后重试；已有输入仍保留') from exc

class AssessmentRequest(BaseModel):
    mode:Literal['real','simulated']='real'
    component:ComponentProfile|None=None
    weather:WeatherProfile|None=None
    overrides:list[str]=Field(default_factory=list)
    adequate_margin_ratio:float|None=Field(default=None,gt=1,allow_inf_nan=False)
    critical_shortfall_ratio:float|None=Field(default=None,gt=0,lt=1,allow_inf_nan=False)
    @model_validator(mode='after')
    def finite_inputs(self):
        for profile in (self.component,self.weather):
            if profile is not None and any(isinstance(value,float) and not isfinite(value) for value in profile.model_dump().values()):
                raise ValueError('参数必须为有限数值')
        if self.weather and self.weather.historical_max_wind_m_s is not None:
            wind=self.weather.historical_max_wind_m_s
            if not isfinite(0.613*wind*wind):raise ValueError('风速超过可计算范围')
        return self

@router.post('/api/v1/risk/lab/assess')
def assess(data:AssessmentRequest):
    rules=BusinessRulesConfig.load()
    updates={}
    if data.adequate_margin_ratio is not None:updates['catastrophe_adequate_margin_ratio']=data.adequate_margin_ratio
    if data.critical_shortfall_ratio is not None:updates['catastrophe_critical_shortfall_ratio']=data.critical_shortfall_ratio
    actual=BusinessRulesConfig.model_validate({**rules.model_dump(),**updates})
    engine=CatastropheAssessmentEngine(actual)
    simulated=data.mode=='simulated' or bool(data.overrides) or any(getattr(actual,k)!=getattr(rules,k) for k in updates)
    result=engine.assess(component=data.component,weather=data.weather)
    return {'id':uuid4().hex,'created_at':datetime.now(UTC).isoformat(),'mode':'simulated' if simulated else 'real',
            'ruleset_id':rules.ruleset_id,'rules_version':rules.version,'thresholds_overridden':any(getattr(actual,k)!=getattr(rules,k) for k in updates),
            'input':data.model_dump(mode='json'),'assessment':result.model_dump(mode='json'),
            'comparisons':engine.comparisons(data.component,data.weather)}
