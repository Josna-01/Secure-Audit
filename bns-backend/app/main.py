# app/main.py
import os
import logging
import time
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import uvicorn

# Prometheus
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

# app internals
from .multilabel_classifier import MultiLabelBNSClassifier

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bns-api")

app = FastAPI(title="BNS Multi-Label Classification & Explainability API", version="2.0")

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
ORIGINS = [FRONTEND_ORIGIN, "http://localhost:5174", "http://localhost:8080", "http://localhost:3000", "*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Prometheus metrics ---
PREDICT_COUNTER = Counter("bns_predict_requests_total", "Total number of /predict calls")
PREDICT_FAILURES = Counter("bns_predict_failures_total", "Number of failed /predict calls")
PREDICT_LATENCY = Histogram("bns_predict_latency_seconds", "Latency of /predict", buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0))

# Initialize Multi-Label Classifier
try:
    classifier = MultiLabelBNSClassifier()
    logger.info("MultiLabelBNSClassifier initialized successfully.")
except Exception as e:
    logger.exception("Failed to initialize MultiLabelBNSClassifier")
    classifier = None

# Request / Response Schemas
class PredictRequest(BaseModel):
    facts: str
    title: Optional[str] = None
    threshold: Optional[float] = 0.35
    top_k: Optional[int] = 15
    victim_age: Optional[int] = None
    victim_gender: Optional[str] = None
    num_offenders: Optional[int] = None
    weapon_used: Optional[bool] = None

class SectionPrediction(BaseModel):
    section_id: str
    title: str
    name: Optional[str] = None
    confidence: float
    confidence_percent: str
    score: float
    severity: str
    cognizable: Any
    bailable: Any
    category: str
    description: str
    meaning: Optional[str] = None
    legal_elements: Optional[List[str]] = []
    punishment: Optional[Any] = None
    explanation: str
    trigger_sentences: List[str]
    matched_keywords: Optional[List[str]] = []

class MultiLabelPredictResponse(BaseModel):
    bns: List[Dict[str, Any]]
    sections: Optional[List[Dict[str, Any]]] = []
    crime_type: str
    crime_categories: Optional[List[str]] = []
    total_sections: int
    threshold_applied: float

@app.get("/health")
async def health() -> dict:
    ok = classifier is not None
    return {"status": "ok" if ok else "error", "model_loaded": ok, "version": "2.0-multilabel"}

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    try:
        payload = generate_latest()
        return Response(content=payload, media_type=CONTENT_TYPE_LATEST)
    except Exception:
        return {"status": "ok"}

@app.post("/predict", response_model=Dict[str, Any])
async def predict(req: PredictRequest):
    """
    Multi-Label BNS Section Generator:
    Identifies EVERY applicable Bharatiya Nyaya Sanhita (BNS) section from the complete FIR narrative.
    Returns calibrated confidence scores, ranking from highest to lowest,
    along with triggering sentences and natural language XAI explanations.
    """
    if classifier is None:
        raise HTTPException(status_code=503, detail="BNS Classification Engine not loaded")
    if not req.facts or len(req.facts.strip()) < 5:
        raise HTTPException(status_code=400, detail="FIR description text is too short")

    PREDICT_COUNTER.inc()
    start = time.time()
    try:
        threshold = req.threshold if req.threshold is not None else 0.35
        top_k = req.top_k if req.top_k is not None else 15
        
        result = classifier.classify_multilabel(
            facts=req.facts,
            threshold=threshold,
            top_k=top_k,
            title=req.title
        )
    except Exception as e:
        PREDICT_FAILURES.inc()
        logger.exception("Inference failed")
        raise HTTPException(status_code=500, detail=str(e))
    
    latency = time.time() - start
    PREDICT_LATENCY.observe(latency)

    return result

@app.post("/predict_verbose")
async def predict_verbose(req: PredictRequest):
    """Verbose multi-label endpoint returning complete prediction metadata."""
    return await predict(req)

@app.post("/retrieve")
async def retrieve(req: PredictRequest):
    """Direct semantic retrieval across BNS statutory definitions."""
    if classifier is None:
        raise HTTPException(status_code=503, detail="Classifier not loaded")
    try:
        hits = classifier.classify_multilabel(facts=req.facts, threshold=0.1, top_k=req.top_k or 10)
        return {"hits": hits.get("bns", [])}
    except Exception as e:
        logger.exception("Retrieval failed")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8001)), reload=True)
