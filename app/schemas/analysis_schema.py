from pydantic import BaseModel
from typing import Any
from datetime import datetime


class AnalysisRequest(BaseModel):
    pdf_ids: list[str]
    analysis_type: str
    custom_prompt: str | None = None


class AnalysisResult(BaseModel):
    id: str
    analysis_type: str
    result_json: Any
    pdf_names: list[str]
    created_at: datetime


class AnalysisHistoryResponse(BaseModel):
    analyses: list[AnalysisResult]
    total: int
