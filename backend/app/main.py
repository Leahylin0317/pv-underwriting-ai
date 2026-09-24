from fastapi import FastAPI

from app.api import router

app = FastAPI(
    title="分布式光伏财产险 AI 智能核保",
    description="分布式光伏投保材料解析、风险识别和核保决策接口。",
    version="0.1.0",
)

app.include_router(router)
