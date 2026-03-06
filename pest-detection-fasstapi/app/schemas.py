from pydantic import BaseModel
from typing import Optional


class ClassificationResult(BaseModel):
    img_path: str
    pest_code: str
    confidence: float


class AnalyzeResponse(BaseModel):
    message: str
    detected: bool
    classifier_output: Optional[ClassificationResult] = None
    prescription_output: Optional[dict] = None
