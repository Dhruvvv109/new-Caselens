from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import datagen, db, predict, search

logger = logging.getLogger("caselens.main")
logging.basicConfig(level=logging.INFO)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_case_type_encoded(case_type: str) -> int:
    """Safely map case_type string to its integer encoding."""
    if hasattr(predict, "CASE_TYPE_ENCODING"):
        enc = predict.CASE_TYPE_ENCODING
        if case_type in enc:
            return enc[case_type]
        alt_map = {
            "Civil/Property": "Property/Civil",
            "Property/Civil": "Civil/Property",
            "Labour": "Labour & Service",
            "Labour & Service": "Labour",
            "Contract": "Contract/Commercial",
            "Contract/Commercial": "Contract",
        }
        alt = alt_map.get(case_type)
        if alt and alt in enc:
            return enc[alt]
    return 0


def _days_since_filing(filing_date_str: Optional[str]) -> int:
    """Calculate elapsed days since filing date."""
    if not filing_date_str:
        return 180
    try:
        cleaned = str(filing_date_str).split("T")[0]
        d = date.fromisoformat(cleaned)
        return max(0, (date.today() - d).days)
    except Exception:
        return 180


def _refresh_pending_features() -> None:
    """Compute and store precedent features & predictions for all pending cases."""
    all_cases_resp = db.get_pending_cases(page_size=200)
    all_cases = all_cases_resp["cases"] if isinstance(all_cases_resp, dict) and "cases" in all_cases_resp else all_cases_resp
    cases_needing_refresh = [c for c in all_cases if c.get("priority_score", 0) == 0]
    if not cases_needing_refresh:
        return

    today = date.today()
    for c in cases_needing_refresh:
        desc = c.get("description", "")
        vec = search.embed_text(desc)
        prec = search.get_precedent_features(vec)

        filing_str = c.get("filing_date", str(today))
        days_since = _days_since_filing(filing_str)

        feat = {
            "case_type_encoded": _get_case_type_encoded(c.get("case_type", "")),
            "days_since_filing": days_since,
            "hearings_so_far": c.get("hearings_so_far", 0),
            "num_parties": c.get("num_parties", 2),
            "is_appeal": c.get("is_appeal", 0),
            **prec,
        }
        pred = predict.predict_case(feat)
        db.update_case_features(c["id"], {**prec, **pred})

    # After all computed, apply percentile buckets
    all_cases_updated = db.get_pending_cases(page_size=200)
    cases_list = all_cases_updated["cases"] if isinstance(all_cases_updated, dict) and "cases" in all_cases_updated else all_cases_updated
    scores = [c.get("priority_score", 0.0) for c in cases_list]
    buckets = predict.compute_buckets_by_percentile(scores)
    for case, bucket in zip(cases_list, buckets):
        db.update_case_features(case["id"], {"bucket": bucket})


def _refresh_one_case_buckets(case_id: Optional[int] = None) -> None:
    """Recalculate percentile buckets across all cases."""
    all_cases_resp = db.get_pending_cases(page_size=1000)
    cases_list = all_cases_resp["cases"] if isinstance(all_cases_resp, dict) and "cases" in all_cases_resp else all_cases_resp
    if not cases_list:
        return
    scores = [c.get("priority_score", 0.0) for c in cases_list]
    buckets = predict.compute_buckets_by_percentile(scores)
    for case, bucket in zip(cases_list, buckets):
        db.update_case_features(case["id"], {"bucket": bucket})


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    On startup:
    1. db.init_db()
    2. if db.is_db_empty(): generate and bulk insert synthetic data
    3. search.build_index()
    4. predict.load_model()
    5. if model not loaded: predict.train_model(save=True); predict.load_model()
    6. _refresh_pending_features()
    """
    logger.info("CaseLens startup: initializing database...")
    db.init_db()

    if db.is_db_empty():
        logger.info("DB empty — generating data...")
        judgments = datagen.generate_judgments(seed=42)
        db.bulk_insert_judgments(judgments)
        cases = datagen.generate_pending_cases(seed=42)
        db.bulk_insert_pending_cases(cases)
        logger.info("Data generated. Building index...")

    logger.info("CaseLens startup: building/loading search index...")
    search.build_index()

    logger.info("CaseLens startup: loading prediction model...")
    try:
        predict.load_model()
    except Exception as exc:
        logger.warning("predict.load_model() returned error: %s", exc)

    model_obj = getattr(predict, "_model", None) or getattr(predict, "_gbr_model", None) or getattr(predict, "_lgbm_model", None)
    if model_obj is None or getattr(model_obj, "__class__", None).__name__ == "_StubPredictor":
        logger.info("GBR model missing or stub active — training model...")
        try:
            predict.train_model(save=True)
            predict.load_model()
        except Exception as exc:
            logger.warning("predict.train_model() error: %s", exc)

    logger.info("CaseLens startup: refreshing pending case features and buckets...")
    try:
        _refresh_pending_features()
    except Exception as exc:
        logger.warning("Failed refreshing pending features during startup: %s", exc)

    logger.info("CaseLens startup complete.")
    yield
    logger.info("CaseLens shutdown.")


# ---------------------------------------------------------------------------
# App Initialization & Middleware
# ---------------------------------------------------------------------------

app = FastAPI(
    title="CaseLens API",
    description="Legal case analytics: semantic search, precedent matching, timeline prediction.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query string")
    top_k: int = Field(8, ge=1, le=50, description="Number of results to return")
    case_type: Optional[str] = None
    court: Optional[str] = None
    year_min: Optional[int] = None
    year_max: Optional[int] = None


class ScoreRequest(BaseModel):
    description: str = Field(..., min_length=1)
    case_type: str = Field(...)
    court: str = ""
    hearings_so_far: int = 0
    num_parties: int = 2
    is_appeal: int = 0
    filing_date: str = Field(..., description="YYYY-MM-DD")


class AddCaseRequest(BaseModel):
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    case_type: str = Field(...)
    court: str = Field(...)
    hearings_so_far: int = 0
    num_parties: int = 2
    is_appeal: int = 0
    filing_date: str = Field(..., description="YYYY-MM-DD")
    status: str = "Pending"
    case_no: Optional[str] = None
    next_hearing_date: Optional[str] = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/api/overview")
async def get_overview() -> Dict[str, Any]:
    """Return overview KPIs, top priority queue, search backend, and corpus size."""
    try:
        stats = db.get_overview_stats()
        queue = db.get_top_queue(10)

        for q in queue:
            if "summary" not in q or not q["summary"]:
                desc = q.get("description", "")
                try:
                    from app import summarize
                    q["summary"] = summarize.summarize(desc, num_sentences=2)
                except Exception:
                    q["summary"] = (desc[:180] + "...") if len(desc) > 180 else desc

        backend = search.get_backend() if hasattr(search, "get_backend") else "sentence-transformers"
        idx_size = stats.get("judgment_count", 0)

        return {
            **stats,
            "top_queue": queue,
            "search_backend": backend,
            "index_size": idx_size,
        }
    except Exception as exc:
        logger.exception("Error in GET /api/overview: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/search")
async def post_search(req: SearchRequest) -> Dict[str, Any]:
    """Semantic and hybrid search over the judgment corpus."""
    try:
        res = search.search(
            query=req.query,
            top_k=req.top_k,
            case_type=req.case_type,
            court=req.court,
            year_min=req.year_min,
            year_max=req.year_max,
        )
        return res
    except Exception as exc:
        logger.exception("Error in POST /api/search: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/cases")
async def get_cases(
    bucket: Optional[str] = Query(None),
    case_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    sort: str = Query("priority"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> Dict[str, Any]:
    """Return paginated pending cases filtered by bucket, type, status, or search query."""
    try:
        return db.get_pending_cases(
            bucket=bucket,
            case_type=case_type,
            status=status,
            q=q,
            sort=sort,
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        logger.exception("Error in GET /api/cases: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/cases/{case_id:int}")
async def get_case_detail(case_id: int) -> Dict[str, Any]:
    """Return single pending case with precedent similarity, predictions, and top-5 precedent judgments."""
    try:
        case = db.get_pending_case(case_id)
        if not case:
            raise HTTPException(status_code=404, detail=f"Case with ID {case_id} not found.")

        desc = case.get("description", "")
        vec = search.embed_text(desc)
        search_res = search.search(desc, top_k=5)
        precedents = search_res.get("results", []) if isinstance(search_res, dict) else search_res

        days_since = _days_since_filing(case.get("filing_date"))

        pred_feat = {
            "case_type_encoded": _get_case_type_encoded(case.get("case_type", "")),
            "days_since_filing": days_since,
            "hearings_so_far": case.get("hearings_so_far", 0),
            "num_parties": case.get("num_parties", 2),
            "is_appeal": case.get("is_appeal", 0),
            "top1_similarity": case.get("top1_similarity", 0.0),
            "mean_top5_similarity": case.get("mean_top5_similarity", 0.0),
            "count_above_threshold": case.get("count_above_threshold", 0),
            "similarity_spread": case.get("similarity_spread", 0.0),
        }

        prediction = {
            "predicted_days": case.get("predicted_days", 0),
            "lower_band": case.get("lower_band", 0),
            "upper_band": case.get("upper_band", 0),
            "bucket": case.get("bucket", "Standard"),
            "priority_score": case.get("priority_score", 0.0),
            "why_text": case.get("why_text", ""),
        }

        precedent_features = {
            k: case.get(k, 0)
            for k in [
                "top1_similarity",
                "mean_top5_similarity",
                "count_above_threshold",
                "similarity_spread",
            ]
        }

        return {
            "case": case,
            "precedents": precedents,
            "prediction": prediction,
            "precedent_features": precedent_features,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error in GET /api/cases/%s: %s", case_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/cases", status_code=status.HTTP_201_CREATED)
async def create_case(req: AddCaseRequest) -> Dict[str, Any]:
    """Add a new case, compute features, predict timeline/priority, persist, and re-bucket."""
    try:
        vec = search.embed_text(req.description)
        prec = search.get_precedent_features(vec)

        days_since = _days_since_filing(req.filing_date)

        feat = {
            "case_type_encoded": _get_case_type_encoded(req.case_type),
            "days_since_filing": days_since,
            "hearings_so_far": req.hearings_so_far,
            "num_parties": req.num_parties,
            "is_appeal": req.is_appeal,
            **prec,
        }
        pred = predict.predict_case(feat)

        today = date.today()
        case_no = req.case_no
        if not case_no:
            prefix = "".join([w[:2].upper() for w in req.case_type.split("/") if w])[:4] or "CASE"
            case_no = f"{prefix}/{today.year}/{int(datetime.now().timestamp() * 1000) % 100000:05d}"

        next_hearing = req.next_hearing_date or (today + timedelta(days=30)).isoformat()

        record = {
            "case_no": case_no,
            "title": req.title,
            "description": req.description,
            "case_type": req.case_type,
            "court": req.court,
            "filing_date": req.filing_date,
            "hearings_so_far": req.hearings_so_far,
            "num_parties": req.num_parties,
            "is_appeal": req.is_appeal,
            "status": req.status,
            "next_hearing_date": next_hearing,
            **prec,
            **pred,
        }

        new_id = db.insert_pending_case(record)
        _refresh_one_case_buckets(new_id)

        case = db.get_pending_case(new_id)
        if not case:
            raise HTTPException(status_code=500, detail="Failed to retrieve inserted case.")

        search_res = search.search(req.description, top_k=5)
        precedents = search_res.get("results", []) if isinstance(search_res, dict) else search_res

        prediction = {
            "predicted_days": case.get("predicted_days", pred.get("predicted_days", 0)),
            "lower_band": case.get("lower_band", pred.get("lower_band", 0)),
            "upper_band": case.get("upper_band", pred.get("upper_band", 0)),
            "bucket": case.get("bucket", pred.get("bucket", "Standard")),
            "priority_score": case.get("priority_score", pred.get("priority_score", 0.0)),
            "why_text": case.get("why_text", pred.get("why_text", "")),
        }

        precedent_features = {
            k: case.get(k, prec.get(k, 0))
            for k in [
                "top1_similarity",
                "mean_top5_similarity",
                "count_above_threshold",
                "similarity_spread",
            ]
        }

        return {
            "case": case,
            "precedents": precedents,
            "prediction": prediction,
            "precedent_features": precedent_features,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error in POST /api/cases: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/cases/score")
async def score_case(req: ScoreRequest) -> Dict[str, Any]:
    """Score an arbitrary case description on the fly without persistence."""
    try:
        vec = search.embed_text(req.description)
        prec = search.get_precedent_features(vec)
        days_since = _days_since_filing(req.filing_date)

        feat = {
            "case_type_encoded": _get_case_type_encoded(req.case_type),
            "days_since_filing": days_since,
            "hearings_so_far": req.hearings_so_far,
            "num_parties": req.num_parties,
            "is_appeal": req.is_appeal,
            **prec,
        }
        pred = predict.predict_case(feat)

        search_res = search.search(req.description, top_k=5)
        precedents = search_res.get("results", []) if isinstance(search_res, dict) else search_res

        return {
            "prediction": pred,
            "precedent_features": prec,
            "precedents": precedents,
        }
    except Exception as exc:
        logger.exception("Error in POST /api/cases/score: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/judgments/{judgment_id}")
async def get_judgment(judgment_id: str) -> Dict[str, Any]:
    """Return a single judgment from the corpus by ID or citation."""
    try:
        j = db.get_judgment(judgment_id)
        if not j:
            raise HTTPException(status_code=404, detail=f"Judgment '{judgment_id}' not found.")
        return j
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error in GET /api/judgments/%s: %s", judgment_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/model/info")
async def get_model_info() -> Dict[str, Any]:
    """Return model feature importances and metadata."""
    try:
        return {"feature_importances": predict.get_model_info()}
    except Exception as exc:
        logger.exception("Error in GET /api/model/info: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Static Files — mount LAST so API routes always take precedence
# ---------------------------------------------------------------------------

static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
if os.path.isdir(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
