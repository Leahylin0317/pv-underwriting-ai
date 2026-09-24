from pydantic import Field

from app.contracts import ContractModel, Material, ProjectInfo


class MockAnalyzeRequest(ContractModel):
    """Mock 核保接口接收的请求数据。"""

    case_id: str = Field(min_length=1)
    project: ProjectInfo
    materials: list[Material] = Field(min_length=1)
