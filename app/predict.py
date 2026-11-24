"""
app/predict.py — Case duration prediction and triage scoring for CaseLens.
Uses GradientBoostingRegressor trained on synthetic Indian litigation patterns.
Features include case type, litigation progress, party count, and precedent similarity metrics.
"""

import logging
import os
import random
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import root_mean_squared_error

logger = logging.getLogger("caselens.predict")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "models")
MODEL_PATH = os.path.join(MODELS_DIR, "gbr_model.joblib")
RESIDUAL_STD_PATH = os.path.join(MODELS_DIR, "residual_std.txt")

# Case type encoding map
CASE_TYPE_ENCODING: Dict[str, int] = {
    "Property/Civil": 0,
    "Civil/Property": 0,
    "Civil": 0,
    "Criminal": 1,
    "Family": 2,
    "Labour & Service": 3,
    "Labour": 3,
    "Service": 3,
    "Consumer": 4,
    "Tax": 5,
    "Constitutional/Writ": 6,
    "Constitutional": 6,
    "Writ": 6,
    "Contract/Commercial": 7,
    "Contract": 7,
    "Commercial": 7,
}

FEATURE_ORDER: List[str] = [
    "case_type_encoded",
    "days_since_filing",
    "hearings_so_far",
    "num_parties",
    "is_appeal",
    "top1_similarity",
    "mean_top5_similarity",
    "count_above_threshold",
    "similarity_spread",
]

# Baseline days mapped by encoded case type
BASE_DAYS_BY_CODE: Dict[int, float] = {
    0: 600.0,  # Property/Civil
    1: 400.0,  # Criminal
    2: 500.0,  # Family
    3: 550.0,  # Labour & Service
    4: 280.0,  # Consumer
    5: 450.0,  # Tax
    6: 700.0,  # Constitutional/Writ
    7: 520.0,  # Contract/Commercial
}

# Module-level singletons
_model: Optional[GradientBoostingRegressor] = None
_residual_std: float = 70.0


def compute_priority_score(
    predicted_days: float,
    mean_top5: float,
    count_above: float,
    case_type_encoded: int = 0,
) -> float:
    """
    Compute triage priority score (0-100).
    raw = (predicted_days / 1400) * 60 + (1 - mean_top5) * 25 + max(0, (5 - count_above)) * 3
    Return min(100.0, max(0.0, round(raw, 1)))
    """
    raw = (predicted_days / 1400.0) * 60.0 + (1.0 - mean_top5) * 25.0 + max(0.0, (5.0 - count_above)) * 3.0
    return float(min(100.0, max(0.0, round(raw, 1))))


def compute_buckets_by_percentile(scores: List[float]) -> List[str]:
    """
    Sort scores, top 20% = "Fast-track", bottom 20% = "Needs attention", rest = "Standard".
    Return list in SAME ORDER as input scores.
    """
    if not scores:
        return []

    n = len(scores)
    if n == 1:
        return ["Standard"]

    # Rank indices by score descending (top scores get top priority)
    sorted_indices = sorted(range(n), key=lambda i: scores[i], reverse=True)
    top_cutoff = max(1, int(round(n * 0.20)))
    bottom_cutoff = n - max(1, int(round(n * 0.20)))

    buckets = ["Standard"] * n
    for rank, idx in enumerate(sorted_indices):
        if rank < top_cutoff:
            buckets[idx] = "Fast-track"
        elif rank >= bottom_cutoff:
            buckets[idx] = "Needs attention"
        else:
            buckets[idx] = "Standard"

    return buckets


def train_model(save: bool = True) -> Dict[str, Any]:
    """
    Generate 3000 synthetic rows with documented litigation formula:
    days = base * (1 - 0.35 * mean_top5_similarity) * (1 + 0.12 * (num_parties - 2))
           + 100 * is_appeal + 25 * hearings_so_far + gauss(0, 70)
    clip to [30, 1400]
    Fit GradientBoostingRegressor and save model + residual_std.
    """
    global _model, _residual_std

    np.random.seed(42)
    random.seed(42)
    n_samples = 3000

    X_list = []
    y_list = []

    for _ in range(n_samples):
        ct_code = random.randint(0, 7)
        base = BASE_DAYS_BY_CODE.get(ct_code, 500.0)

        days_since = random.randint(30, 2000)
        hearings = random.randint(1, 30)
        num_parties = random.randint(2, 6)
        is_appeal = 1 if random.random() < 0.20 else 0

        top1 = random.uniform(0.10, 0.95)
        mean5 = random.uniform(0.10, top1)
        count_above = random.randint(0, 15)
        spread = random.uniform(0.0, 0.30)

        # Documented formula
        days = (
            base * (1.0 - 0.35 * mean5) * (1.0 + 0.12 * (num_parties - 2))
            + 100.0 * is_appeal
            + 25.0 * hearings
            + random.gauss(0, 70.0)
        )
        days = max(30.0, min(1400.0, days))

        row = [
            float(ct_code),
            float(days_since),
            float(hearings),
            float(num_parties),
            float(is_appeal),
            float(top1),
            float(mean5),
            float(count_above),
            float(spread),
        ]
        X_list.append(row)
        y_list.append(days)

    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.float32)

    gbr = GradientBoostingRegressor(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.1,
        random_state=42,
    )
    gbr.fit(X, y)

    preds = gbr.predict(X)
    rmse = float(root_mean_squared_error(y, preds))
    res_std = float(np.std(y - preds))

    _model = gbr
    _residual_std = res_std

    importances = gbr.feature_importances_
    feat_importances = [
        {"feature": name, "importance": round(float(imp), 4)}
        for name, imp in zip(FEATURE_ORDER, importances)
    ]
    feat_importances.sort(key=lambda x: x["importance"], reverse=True)

    if save:
        os.makedirs(MODELS_DIR, exist_ok=True)
        joblib.dump(gbr, MODEL_PATH)
        with open(RESIDUAL_STD_PATH, "w", encoding="utf-8") as f:
            f.write(f"{res_std:.2f}\n")
        logger.info("Saved GBR model to %s and residual_std (%.2f) to %s", MODEL_PATH, res_std, RESIDUAL_STD_PATH)

    return {
        "rmse": round(rmse, 2),
        "feature_importances": feat_importances,
    }


def load_model() -> None:
    """Load model and residual_std from disk if available."""
    global _model, _residual_std

    if os.path.exists(MODEL_PATH):
        try:
            _model = joblib.load(MODEL_PATH)
            logger.info("Loaded GBR model from %s", MODEL_PATH)
        except Exception as e:
            logger.warning("Failed to load model from %s: %s", MODEL_PATH, e)
            _model = None

    if os.path.exists(RESIDUAL_STD_PATH):
        try:
            with open(RESIDUAL_STD_PATH, "r", encoding="utf-8") as f:
                val = f.read().strip()
                _residual_std = float(val)
        except Exception as e:
            logger.warning("Failed to load residual std: %s", e)
            _residual_std = 70.0


def get_model_info() -> List[Dict[str, Any]]:
    """Return feature importances as list of {feature, importance}."""
    global _model
    if _model is None:
        load_model()
    if _model is None:
        train_model(save=True)

    if _model is not None and hasattr(_model, "feature_importances_"):
        importances = _model.feature_importances_
        res = [
            {"feature": name, "importance": round(float(imp), 4)}
            for name, imp in zip(FEATURE_ORDER, importances)
        ]
        res.sort(key=lambda x: x["importance"], reverse=True)
        return res
    return []


def predict_case(features_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Predict duration bands, priority score, and explanation for a case.
    features_dict contains case_type_encoded, days_since_filing, hearings_so_far,
    num_parties, is_appeal, top1_similarity, mean_top5_similarity,
    count_above_threshold, similarity_spread.
    Returns: {predicted_days, lower_band, upper_band, bucket, priority_score, why_text}
    """
    global _model, _residual_std

    if _model is None:
        load_model()
    if _model is None:
        train_model(save=True)

    # Encode case_type if string passed
    ct_val = features_dict.get("case_type_encoded")
    if ct_val is None:
        raw_type = features_dict.get("case_type", "")
        ct_val = CASE_TYPE_ENCODING.get(raw_type, 0)

    days_since = float(features_dict.get("days_since_filing", 120))
    hearings = float(features_dict.get("hearings_so_far", 0))
    num_parties = float(features_dict.get("num_parties", 2))
    is_appeal = float(features_dict.get("is_appeal", 0))
    top1 = float(features_dict.get("top1_similarity", 0.0))
    mean5 = float(features_dict.get("mean_top5_similarity", 0.0))
    count_above = float(features_dict.get("count_above_threshold", 0))
    spread = float(features_dict.get("similarity_spread", 0.0))

    x = np.array(
        [[ct_val, days_since, hearings, num_parties, is_appeal, top1, mean5, count_above, spread]],
        dtype=np.float32,
    )

    pred_raw = float(_model.predict(x)[0])
    predicted_days = int(round(max(30.0, min(1400.0, pred_raw))))

    lower_band = max(0, int(round(predicted_days - _residual_std)))
    upper_band = int(round(predicted_days + _residual_std))

    priority_score = compute_priority_score(predicted_days, mean5, count_above, int(ct_val))

    # Placeholder bucket until global percentile re-ranking is applied
    if priority_score >= 70.0:
        bucket = "Fast-track"
    elif priority_score <= 35.0:
        bucket = "Needs attention"
    else:
        bucket = "Standard"

    top1_pct = round(top1 * 100)
    why_text = f"{int(count_above)} close precedents, top match {top1_pct}%, {int(hearings)} hearings so far"

    return {
        "predicted_days": predicted_days,
        "lower_band": lower_band,
        "upper_band": upper_band,
        "bucket": bucket,
        "priority_score": priority_score,
        "why_text": why_text,
    }
