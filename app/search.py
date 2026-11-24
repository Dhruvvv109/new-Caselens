"""
app/search.py — Hybrid semantic + statutory keyword search for CaseLens.
Combines dense embedding cosine similarity (0.8) with keyword and statutory section boosts (0.2).
Falls back cleanly to TF-IDF if sentence-transformers is unavailable.
"""

import json
import logging
import os
import re
import string
from typing import Any, Dict, List, Optional, Union

import numpy as np

from app import db

logger = logging.getLogger("caselens.search")

# Paths
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
EMB_PATH = os.path.join(DATA_DIR, "emb.npy")
META_PATH = os.path.join(DATA_DIR, "judgment_ids.json")
TFIDF_PATH = os.path.join(DATA_DIR, "tfidf.joblib")
TFIDF_MATRIX_PATH = os.path.join(DATA_DIR, "tfidf_matrix.npz")

# Module-level singletons
_model = None
_embeddings: Optional[np.ndarray] = None
_ids: Optional[List[str]] = None
_meta: Optional[List[Dict[str, Any]]] = None
_backend: str = "none"
_tfidf = None
_tfidf_matrix = None

# Known statutory section numbers and legal citation tokens
STATUTORY_KEYWORDS = [
    "138", "482", "125", "302", "438", "226", "143", "80c", "80-c",
    "376", "420", "406", "34", "120b", "120-b", "9", "13", "13b", "25", "27",
    "air", "scc", "scr", "ni act", "ipc", "crpc", "cpc", "hma"
]


def _compute_keyword_boost(query: str, text: str) -> float:
    """
    Given query string, extract tokens (split+lower+strip punctuation).
    Match against result text: count tokens found / (len(tokens)+1).
    Also boost if query contains section numbers like "138","482","125","302",
    "438","226","143","80C" or citation strings — add 0.15 per statutory match found.
    """
    if not query or not text:
        return 0.0

    raw_tokens = query.lower().split()
    tokens = [t.strip(string.punctuation) for t in raw_tokens if t.strip(string.punctuation)]
    if not tokens:
        return 0.0

    text_lower = text.lower()
    tokens_found = sum(1 for t in tokens if t in text_lower)
    match_ratio = tokens_found / (len(tokens) + 1)

    # Statutory section & citation matches
    query_lower = query.lower()
    statutory_matches = 0
    for stat in STATUTORY_KEYWORDS:
        # Check if statutory keyword is in query (as word or token)
        pattern = rf"(?:\b|_){re.escape(stat)}(?:\b|_)"
        if re.search(pattern, query_lower):
            if re.search(pattern, text_lower):
                statutory_matches += 1

    statutory_boost = statutory_matches * 0.15
    total_boost = min(1.0, match_ratio + statutory_boost)
    return float(total_boost)


def _split_into_sentences(text: str) -> List[str]:
    """Split text into sentences cleanly."""
    if not text:
        return []
    sents = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in sents if len(s.strip()) > 10]


def _extract_summary(doc_text: str, query: str, query_vec: Any, backend: str) -> str:
    """
    Summary: top 3 sentences by cosine-sim to query embedding (or TF-IDF fallback)
    + the holding sentence (contains 'held'/'therefore'), deduplicated,
    in original doc order, joined. Max 400 chars.
    """
    sentences = _split_into_sentences(doc_text)
    if not sentences:
        return doc_text[:400]

    if len(sentences) <= 3:
        summary_candidate = " ".join(sentences)
        return summary_candidate[:400]

    # Compute sentence similarities
    scored_indices = []
    if backend == "sentence-transformers" and _model is not None:
        try:
            sent_embs = _model.encode(sentences, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False)
            if query_vec is not None:
                sims = np.dot(sent_embs, query_vec)
            else:
                sims = np.zeros(len(sentences))
            for i, sim in enumerate(sims):
                scored_indices.append((i, float(sim)))
        except Exception:
            scored_indices = [(i, 0.0) for i in range(len(sentences))]
    elif backend == "tfidf" and _tfidf is not None:
        try:
            from sklearn.metrics.pairwise import cosine_similarity
            sent_vecs = _tfidf.transform(sentences)
            q_vec = query_vec if query_vec is not None else _tfidf.transform([query])
            sims = cosine_similarity(q_vec, sent_vecs)[0]
            for i, sim in enumerate(sims):
                scored_indices.append((i, float(sim)))
        except Exception:
            scored_indices = [(i, 0.0) for i in range(len(sentences))]
    else:
        # Fallback simple token overlap
        q_tokens = set(re.findall(r"\w+", query.lower()))
        for i, s in enumerate(sentences):
            s_tokens = set(re.findall(r"\w+", s.lower()))
            overlap = len(q_tokens & s_tokens)
            scored_indices.append((i, float(overlap)))

    # Top 3 sentences by similarity
    scored_indices.sort(key=lambda x: x[1], reverse=True)
    top_indices = {idx for idx, _ in scored_indices[:3]}

    # Add holding sentence (contains 'held' or 'therefore')
    for i, s in enumerate(sentences):
        if re.search(r"\b(held|therefore)\b", s, re.IGNORECASE):
            top_indices.add(i)
            break

    # Maintain original document order
    ordered_indices = sorted(top_indices)
    chosen_sentences = [sentences[i] for i in ordered_indices]
    summary = " ".join(chosen_sentences)

    if len(summary) > 400:
        # Truncate cleanly
        summary = summary[:397].rsplit(" ", 1)[0] + "..."
    return summary


def _highlight_snippet(text: str, query: str, max_chars: int = 200) -> str:
    """
    Highlighted text snippet: first 200 chars of text_content
    with query words wrapped in <mark>word</mark>.
    """
    if not text:
        return ""
    snippet = text[:max_chars]
    if not query:
        return snippet

    words = [re.escape(w.strip(string.punctuation)) for w in query.split() if len(w.strip(string.punctuation)) >= 2]
    if not words:
        return snippet

    pattern = re.compile(rf"\b({'|'.join(words)})\b", re.IGNORECASE)
    highlighted = pattern.sub(r"<mark>\1</mark>", snippet)
    return highlighted


def build_index(force: bool = False) -> None:
    """
    Build or load search index from judgments table.
    Tries sentence-transformers "all-MiniLM-L6-v2".
    Falls back to TF-IDF upon any error or missing dependency.
    """
    global _model, _embeddings, _ids, _meta, _backend, _tfidf, _tfidf_matrix

    os.makedirs(DATA_DIR, exist_ok=True)

    # 1. Try loading existing sentence-transformers index from disk
    if not force and os.path.exists(EMB_PATH) and os.path.exists(META_PATH):
        try:
            with open(META_PATH, "r", encoding="utf-8") as f:
                _meta = json.load(f)
            _ids = [m["id"] for m in _meta]
            _embeddings = np.load(EMB_PATH)

            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer("all-MiniLM-L6-v2")
            _backend = "sentence-transformers"
            logger.info("Loaded sentence-transformers index with %d items from %s", len(_meta), EMB_PATH)
            return
        except Exception as e:
            logger.warning("Failed to load existing ST index: %s. Rebuilding...", e)

    # 2. Try loading existing TF-IDF index from disk
    if not force and os.path.exists(TFIDF_PATH) and os.path.exists(TFIDF_MATRIX_PATH) and os.path.exists(META_PATH):
        try:
            import joblib
            from scipy import sparse
            with open(META_PATH, "r", encoding="utf-8") as f:
                _meta = json.load(f)
            _ids = [m["id"] for m in _meta]
            _tfidf = joblib.load(TFIDF_PATH)
            _tfidf_matrix = sparse.load_npz(TFIDF_MATRIX_PATH)
            _backend = "tfidf"
            logger.info("Loaded TF-IDF index with %d items from %s", len(_meta), TFIDF_PATH)
            return
        except Exception as e:
            logger.warning("Failed to load existing TF-IDF index: %s. Rebuilding...", e)

    # Rebuilding index from DB
    judgments = db.get_all_judgments()
    if not judgments:
        logger.warning("No judgments in database to build index.")
        _meta = []
        _ids = []
        _backend = "none"
        return

    _meta = [
        {
            "id": j["id"],
            "citation": j.get("citation", ""),
            "title": j.get("title", ""),
            "court": j.get("court", ""),
            "year": int(j.get("year", 0)),
            "case_type": j.get("case_type", ""),
            "subtheme": j.get("subtheme", ""),
            "text_content": j.get("text_content", ""),
            "outcome": j.get("outcome", ""),
        }
        for j in judgments
    ]
    _ids = [m["id"] for m in _meta]
    texts = [m["text_content"] for m in _meta]

    # Attempt sentence-transformers
    try:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        from sentence_transformers import SentenceTransformer
        logger.info("Attempting SentenceTransformer('all-MiniLM-L6-v2') build...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        _embeddings = _model.encode(texts, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False)
        np.save(EMB_PATH, _embeddings)
        with open(META_PATH, "w", encoding="utf-8") as f:
            json.dump(_meta, f, ensure_ascii=False, indent=2)
        _backend = "sentence-transformers"
        logger.info("Built sentence-transformers index with %d judgments.", len(_meta))
        return
    except Exception as exc:
        logger.warning("SentenceTransformer build failed (%s). Falling back to TF-IDF...", exc)

    # Fallback to TF-IDF
    try:
        import joblib
        from scipy import sparse
        from sklearn.feature_extraction.text import TfidfVectorizer

        _tfidf = TfidfVectorizer(ngram_range=(1, 2), max_features=20000)
        _tfidf_matrix = _tfidf.fit_transform(texts)
        joblib.dump(_tfidf, TFIDF_PATH)
        sparse.save_npz(TFIDF_MATRIX_PATH, _tfidf_matrix)
        with open(META_PATH, "w", encoding="utf-8") as f:
            json.dump(_meta, f, ensure_ascii=False, indent=2)
        _backend = "tfidf"
        logger.info("Built TF-IDF index with %d judgments.", len(_meta))
    except Exception as exc2:
        logger.error("TF-IDF index build failed as well: %s", exc2)
        _backend = "none"


def get_backend() -> str:
    """Return active search backend: 'sentence-transformers', 'tfidf', or 'none'."""
    return _backend


def embed_text(text: str) -> Union[np.ndarray, str]:
    """
    Compute embedding representation for text.
    Returns ndarray (if sentence-transformers) or str (if tfidf).
    """
    if _backend == "none" or _meta is None:
        build_index()

    if _backend == "sentence-transformers" and _model is not None:
        return _model.encode(text, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False)
    return text


def get_precedent_features(query_embedding_or_text: Union[np.ndarray, str], threshold: float = 0.5) -> Dict[str, Any]:
    """
    Returns {top1_similarity, mean_top5_similarity, count_above_threshold, similarity_spread}.
    Accepts ndarray (ST) or str (TF-IDF).
    """
    if _backend == "none" or _meta is None or len(_meta) == 0:
        build_index()

    if _backend == "sentence-transformers" and _embeddings is not None and len(_embeddings) > 0:
        if isinstance(query_embedding_or_text, str):
            q_emb = _model.encode(query_embedding_or_text, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False)
        else:
            q_emb = np.asarray(query_embedding_or_text).flatten()

        sims = np.dot(_embeddings, q_emb)
    elif _backend == "tfidf" and _tfidf_matrix is not None and _tfidf is not None:
        from sklearn.metrics.pairwise import cosine_similarity
        if isinstance(query_embedding_or_text, str):
            q_vec = _tfidf.transform([query_embedding_or_text])
        else:
            q_vec = query_embedding_or_text
        sims = cosine_similarity(q_vec, _tfidf_matrix)[0]
    else:
        return {
            "top1_similarity": 0.0,
            "mean_top5_similarity": 0.0,
            "count_above_threshold": 0,
            "similarity_spread": 0.0,
        }

    sorted_sims = np.sort(sims)[::-1]
    top1 = float(sorted_sims[0]) if len(sorted_sims) > 0 else 0.0
    mean_top5 = float(np.mean(sorted_sims[:5])) if len(sorted_sims) >= 5 else (float(np.mean(sorted_sims)) if len(sorted_sims) > 0 else 0.0)
    count_above = int(np.sum(sims >= threshold))
    spread = float(sorted_sims[0] - sorted_sims[4]) if len(sorted_sims) >= 5 else 0.0

    return {
        "top1_similarity": round(max(0.0, min(1.0, top1)), 3),
        "mean_top5_similarity": round(max(0.0, min(1.0, mean_top5)), 3),
        "count_above_threshold": count_above,
        "similarity_spread": round(max(0.0, spread), 3),
    }


def search(
    query: str,
    top_k: int = 8,
    case_type: Optional[str] = None,
    court: Optional[str] = None,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Hybrid search across judgments corpus.
    final_score = 0.8 * cosine_sim + 0.2 * keyword_boost.
    Filters applied BEFORE scoring.
    Returns: {"results": list, "backend": str, "total_corpus": int}
    """
    if _backend == "none" or _meta is None:
        build_index()

    total_corpus = len(_meta) if _meta else 0

    if not query or not query.strip():
        return {
            "results": [],
            "backend": _backend,
            "total_corpus": total_corpus,
            "empty": True,
        }

    clean_query = query.strip()
    top_k = max(1, int(top_k))

    # Compute similarity vector across corpus
    q_vec_for_summary = None
    if _backend == "sentence-transformers" and _model is not None and _embeddings is not None and len(_embeddings) > 0:
        q_emb = _model.encode(clean_query, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False)
        sims = np.dot(_embeddings, q_emb)
        q_vec_for_summary = q_emb
    elif _backend == "tfidf" and _tfidf is not None and _tfidf_matrix is not None:
        from sklearn.metrics.pairwise import cosine_similarity
        q_vec = _tfidf.transform([clean_query])
        sims = cosine_similarity(q_vec, _tfidf_matrix)[0]
        q_vec_for_summary = q_vec
    else:
        sims = np.zeros(total_corpus)

    # Filter candidates BEFORE scoring
    candidates = []
    case_type_clean = case_type.strip().lower() if case_type else None
    court_clean = court.strip().lower() if court else None

    for idx, doc in enumerate(_meta or []):
        # Apply filters
        if case_type_clean:
            doc_ct = doc.get("case_type", "").lower()
            if case_type_clean != doc_ct and case_type_clean not in doc_ct and doc_ct not in case_type_clean:
                continue

        if court_clean:
            doc_court = doc.get("court", "").lower()
            if court_clean not in doc_court:
                continue

        doc_year = int(doc.get("year", 0))
        if year_min is not None and doc_year < int(year_min):
            continue
        if year_max is not None and doc_year > int(year_max):
            continue

        raw_sim = float(sims[idx]) if idx < len(sims) else 0.0
        kw_boost = _compute_keyword_boost(clean_query, doc.get("text_content", ""))
        final_score = 0.8 * raw_sim + 0.2 * kw_boost

        candidates.append((idx, doc, raw_sim, kw_boost, final_score))

    # Sort descending by final_score
    candidates.sort(key=lambda x: x[4], reverse=True)
    top_candidates = candidates[:top_k]

    results = []
    for idx, doc, raw_sim, kw_boost, final_score in top_candidates:
        summary = _extract_summary(doc.get("text_content", ""), clean_query, q_vec_for_summary, _backend)
        snippet = _highlight_snippet(doc.get("text_content", ""), clean_query, max_chars=200)

        results.append({
            "id": doc.get("id"),
            "citation": doc.get("citation", ""),
            "title": doc.get("title", ""),
            "court": doc.get("court", ""),
            "year": doc.get("year"),
            "case_type": doc.get("case_type", ""),
            "subtheme": doc.get("subtheme", ""),
            "similarity": round(max(0.0, raw_sim), 3),
            "keyword_boost": round(kw_boost, 3),
            "score": round(final_score, 3),
            "summary": summary,
            "highlighted_text_snippet": snippet,
        })

    return {
        "results": results,
        "backend": _backend,
        "total_corpus": total_corpus,
    }
