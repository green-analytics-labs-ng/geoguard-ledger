from datetime import datetime

from pydantic import BaseModel


class AnomalyReportSchema(BaseModel):
    score: float
    flags: list[int]
    model_version: str
    summary: str


class DatasetCreate(BaseModel):
    dataset_hash: str
    anomaly_score: float
    anomaly_flags: list[int]
    model_version: str


class DatasetResponse(BaseModel):
    dataset_id: str
    dataset_hash: str
    status: str
    anomaly_score: float
    stellar_tx_hash: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
