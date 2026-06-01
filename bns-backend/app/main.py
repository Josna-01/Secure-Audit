# app/main.py
import os
import logging
import time
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uvicorn

# Prometheus
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

# app internals
from .model_wrapper import RAGHGATWrapper

# attempt import postprocess snapshot getter — fallback defined below
try:
    from .postprocess import get_metrics_snapshot, post_process_predictions
except Exception:
    def get_metrics_snapshot():
        return {}
    # minimal fallback post_process_predictions is included in model_wrapper's usage scope if needed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bns-api")

app = FastAPI(title="BNS Generator API", version="1.2")

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
# Allow both default Vite port (5173) and custom port (8080)
ORIGINS = [FRONTEND_ORIGIN, "http://localhost:8080"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Prometheus metrics --- (module-level)
PREDICT_COUNTER = Counter("bns_predict_requests_total", "Total number of /predict calls")
PREDICT_FAILURES = Counter("bns_predict_failures_total", "Number of failed /predict calls")
PREDICT_LATENCY = Histogram("bns_predict_latency_seconds", "Latency of /predict", buckets=(0.01,0.05,0.1,0.25,0.5,1.0,2.5,5.0))
POSTPROCESS_LATENCY = Histogram("bns_postprocess_latency_seconds", "Latency of postprocess")

# dynamic counters for postprocess internal metrics -> created on-demand and cached
_DYNAMIC_COUNTERS: Dict[str, Counter] = {}

def _sync_postprocess_metrics_to_prometheus():
    """Sync get_metrics_snapshot() counters into Prometheus counters (approximate, monotonic)."""
    try:
        snap = get_metrics_snapshot() or {}
    except Exception:
        snap = {}
    for k, v in snap.items():
        if k not in _DYNAMIC_COUNTERS:
            # create lazily
            _DYNAMIC_COUNTERS[k] = Counter(f"bns_pp_{k}", f"Postprocess metric {k}")
        counter = _DYNAMIC_COUNTERS[k]
        last = getattr(counter, "_last_val", 0)
        delta = v - last
        if delta > 0:
            counter.inc(delta)
        setattr(counter, "_last_val", v)

# request/response models
class PredictRequest(BaseModel):
    facts: str
    title: Optional[str] = None
    top_k: Optional[int] = 20
    victim_age: Optional[int] = None
    victim_gender: Optional[str] = None
    num_offenders: Optional[int] = None
    weapon_used: Optional[bool] = None

class SectionPrediction(BaseModel):
    section_id: str
    score: float
    evidence: Optional[str] = None

class PredictResponse(BaseModel):
    predicted_sections: List[SectionPrediction]
    crime_type: str
    rag_retrieval: Dict[str, Any]
    clarifications: Optional[List[Dict[str, str]]] = []

# model directory & wrapper init
MODEL_DIR = os.getenv("MODEL_DIR", os.path.join(os.getcwd(), "model_data"))
logger.info(f"MODEL_DIR set to {MODEL_DIR}")

try:
    model_wrapper = RAGHGATWrapper(model_dir=MODEL_DIR)
    logger.info("Model wrapper initialized successfully.")
except Exception as e:
    logger.exception("Failed to initialize model wrapper")
    model_wrapper = None

@app.get("/health")
async def health() -> dict:
    ok = model_wrapper is not None
    return {"status": "ok" if ok else "error", "model_loaded": ok}

@app.get("/metrics")
async def metrics():
    """
    Prometheus endpoint. Sync postprocess internal counters before returning.
    """
    try:
        _sync_postprocess_metrics_to_prometheus()
        payload = generate_latest()
        return Response(content=payload, media_type=CONTENT_TYPE_LATEST)
    except Exception:
        try:
            return {"metrics": get_metrics_snapshot()}
        except Exception:
            return {"metrics": {}}

@app.post("/predict", response_model=Dict[str, Any])
async def predict(req: PredictRequest):
    """
    Minimal generator: returns only BNS list (id, name, meaning) and crime_type.
    This is the 'generator' you requested: concise BNS output only.
    """
    if model_wrapper is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    if not req.facts or len(req.facts.strip()) < 5:
        raise HTTPException(status_code=400, detail="facts text too short")

    PREDICT_COUNTER.inc()
    start = time.time()
    try:
        raw_result = model_wrapper.predict(facts=req.facts, title=req.title, top_k=req.top_k)
    except Exception as e:
        PREDICT_FAILURES.inc()
        logger.exception("Inference failed")
        raise HTTPException(status_code=500, detail=str(e))
    predict_time = time.time() - start

    # postprocess timing
    pp_start = time.time()
    sections_meta = getattr(model_wrapper, "sections_meta", None)
    try:
        processed = post_process_predictions(
            raw_result=raw_result,
            facts=req.facts,
            sections_meta=sections_meta,
            victim_age=req.victim_age,
            victim_gender=req.victim_gender,
            num_offenders=req.num_offenders,
            weapon_used=req.weapon_used
        )
    except Exception:
        PREDICT_FAILURES.inc()
        logger.exception("Post-processing failed; returning minimal fallback")
        # fallback: convert raw retrieval to BNS-like shape (best-effort)
        fallback_bns = []
        retrieval_hits = raw_result.get("raw_retrieval", {}).get("hits", []) if isinstance(raw_result.get("raw_retrieval", {}), dict) else raw_result.get("raw_retrieval", [])
        for h in retrieval_hits[:5]:
            sid = str(h.get("section_id"))
            text = h.get("text", "")[:400]
            # try sections_meta for title
            name = None
            if sections_meta:
                for m in sections_meta:
                    if str(m.get("id")) == sid:
                        name = m.get("title") or (m.get("text","")[:80])
                        text = m.get("text","")[:400]
                        break
            # try bns fallback
            try:
                from .bns import BNS_SECTION_DETAILS
                info = BNS_SECTION_DETAILS.get(sid, {})
                name = name or info.get("title")
                text = text or info.get("description","")
            except Exception:
                pass
            fallback_bns.append({"section_id": sid, "name": name or sid, "meaning": text})
        processed = {"bns": fallback_bns, "crime_type": raw_result.get("crime_type","unknown"), "clarifications": []}
    pp_time = time.time() - pp_start

    PREDICT_LATENCY.observe(predict_time)
    POSTPROCESS_LATENCY.observe(pp_time)

    # response is BNS-only shape
    resp = {"bns": processed.get("bns", []), "crime_type": processed.get("crime_type", raw_result.get("crime_type", "unknown"))}
    return resp

@app.post("/predict_verbose", response_model=PredictResponse)
async def predict_verbose(req: PredictRequest):
    """
    Legacy verbose endpoint — returns predicted_sections, crime_type, rag_retrieval, clarifications.
    Helpful during migration.
    """
    if model_wrapper is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    if not req.facts or len(req.facts.strip()) < 5:
        raise HTTPException(status_code=400, detail="facts text too short")

    PREDICT_COUNTER.inc()
    start = time.time()
    try:
        raw_result = model_wrapper.predict(facts=req.facts, title=req.title, top_k=req.top_k)
    except Exception as e:
        PREDICT_FAILURES.inc()
        logger.exception("Inference failed")
        raise HTTPException(status_code=500, detail=str(e))
    predict_time = time.time() - start

    pp_start = time.time()
    sections_meta = getattr(model_wrapper, "sections_meta", None)
    try:
        processed = post_process_predictions(
            raw_result=raw_result,
            facts=req.facts,
            sections_meta=sections_meta,
            victim_age=req.victim_age,
            victim_gender=req.victim_gender,
            num_offenders=req.num_offenders,
            weapon_used=req.weapon_used
        )
    except Exception:
        PREDICT_FAILURES.inc()
        logger.exception("Post-processing failed; returning raw_result as fallback")
        # fallback building old-style predicted_sections from raw_result
        processed = {
            "predicted_sections": [
                {"section_id": s[0], "score": float(s[1]), "evidence": s[2]}
                for s in raw_result.get("sections", [])
                if float(s[1]) >= float(os.getenv("MIN_SECTION_SCORE", 0.45))
            ],
            "crime_type": raw_result.get("crime_type", "unknown"),
            "rag_retrieval": raw_result.get("raw_retrieval", {}),
            "clarifications": [{"field": "internal", "question": "postprocessing_failed"}]
        }
    pp_time = time.time() - pp_start

    PREDICT_LATENCY.observe(predict_time)
    POSTPROCESS_LATENCY.observe(pp_time)

    sections_out = []
    for s in processed.get("predicted_sections", []):
        sections_out.append({"section_id": s["section_id"], "score": float(s["score"]), "evidence": s.get("evidence", "")})

    resp = {
        "predicted_sections": sections_out,
        "crime_type": processed.get("crime_type", raw_result.get("crime_type", "unknown")),
        "rag_retrieval": processed.get("rag_retrieval", raw_result.get("raw_retrieval", {})),
        "clarifications": processed.get("clarifications", []),
    }
    return resp

@app.post("/retrieve")
async def retrieve(req: PredictRequest):
    if model_wrapper is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    try:
        hits = model_wrapper.retrieve(query_text=req.facts, top_k=req.top_k)
        return {"hits": hits}
    except Exception as e:
        logger.exception("Retrieval failed")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)
