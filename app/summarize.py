import re
import logging
from functools import lru_cache

import numpy as np

logger = logging.getLogger(__name__)

# Keywords that boost a sentence's score
BOOST_KEYWORDS = {"held", "court", "observed", "therefore", "wherein", "directed"}

# Weight multiplier applied when a keyword is found
BOOST_WEIGHT = 1.25

# Cache up to 256 summaries so repeated calls for the same judgment text are free
@lru_cache(maxsize=256)
def _cached_summarize(text: str, num_sentences: int) -> str:
    return _summarize_uncached(text, num_sentences)


def _split_sentences(text: str) -> list[str]:
    """
    Split text into sentences.
    Uses a regex that handles common abbreviations and decimal numbers
    without splitting them, then falls back to ". " splitting.
    """
    # First try a regex-based splitter that respects common patterns
    raw = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
    sentences = []
    for s in raw:
        s = s.strip()
        if s:
            sentences.append(s)

    # Fallback: if only one chunk was returned, use naive split
    if len(sentences) <= 1:
        parts = text.split(". ")
        sentences = [p.strip() for p in parts if p.strip()]

    return sentences


def _has_boost_keyword(sentence: str) -> bool:
    lower = sentence.lower()
    return any(kw in lower for kw in BOOST_KEYWORDS)


def summarize(text: str, num_sentences: int = 4) -> str:
    if not text or not text.strip():
        return ""
    return _cached_summarize(text.strip(), num_sentences)


def _summarize_uncached(text: str, num_sentences: int) -> str:
    """
    Extractive summarizer.

    1. Splits *text* into sentences.
    2. Embeds all sentences with the shared sentence-transformer model.
    3. Computes centroid of all sentence embeddings.
    4. Scores each sentence by cosine similarity to the centroid,
       with a boost for legal keywords.
    5. Returns the top *num_sentences* sentences in original document order,
       joined by a single space.
    """
    if not text or not text.strip():
        return ""

    sentences = _split_sentences(text)

    if not sentences:
        return text.strip()

    # If we already have fewer sentences than requested, return as-is
    if len(sentences) <= num_sentences:
        return " ".join(sentences)

    # Import here to avoid a hard dependency at module level during testing
    try:
        from app.search import _get_model  # noqa: PLC0415
        model = _get_model()
        embeddings = model.encode(sentences, show_progress_bar=False, convert_to_numpy=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not embed sentences for summarization: %s", exc)
        # Fallback: return first num_sentences sentences
        return " ".join(sentences[:num_sentences])

    embeddings = embeddings.astype(np.float32)

    # Centroid embedding
    centroid = embeddings.mean(axis=0)
    centroid_norm = centroid / (np.linalg.norm(centroid) + 1e-10)

    # Per-sentence cosine similarity to centroid
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-10
    normed = embeddings / norms
    scores = normed @ centroid_norm  # shape (N,)

    # Apply keyword boost
    for i, sent in enumerate(sentences):
        if _has_boost_keyword(sent):
            scores[i] *= BOOST_WEIGHT

    # Pick top-k indices
    k = min(num_sentences, len(sentences))
    top_indices = set(np.argpartition(scores, -k)[-k:])

    # Return in original document order
    selected = [sent for idx, sent in enumerate(sentences) if idx in top_indices]
    return " ".join(selected)
