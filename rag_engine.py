"""
rag_engine.py
-------------
Lightweight retrieval engine — no vector DB required.

Uses TF-IDF cosine similarity to find the most relevant
conversation segments for a given query string.

Usage:
    from rag_engine import RAGEngine
    engine = RAGEngine(segments)
    results = engine.query("authentication", top_k=3)
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import List, Tuple

from state_schema import AgentState


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _tf(tokens: List[str]) -> Counter:
    return Counter(tokens)


def _idf(corpus: List[List[str]]) -> dict:
    N = len(corpus)
    df: Counter = Counter()
    for doc in corpus:
        for term in set(doc):
            df[term] += 1
    return {term: math.log((N + 1) / (count + 1)) + 1 for term, count in df.items()}


def _tfidf_vec(tokens: List[str], idf: dict) -> dict:
    tf = _tf(tokens)
    return {t: tf[t] * idf.get(t, 1.0) for t in tf}


def _cosine(a: dict, b: dict) -> float:
    common = set(a) & set(b)
    if not common:
        return 0.0
    dot = sum(a[k] * b[k] for k in common)
    mag_a = math.sqrt(sum(v * v for v in a.values()))
    mag_b = math.sqrt(sum(v * v for v in b.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


class RAGEngine:
    """
    Build an in-memory TF-IDF index from a list of text segments
    and answer retrieval queries.
    """

    def __init__(self, segments: List[str]) -> None:
        self._segments = segments
        self._corpus = [_tokenize(s) for s in segments]
        self._idf = _idf(self._corpus)
        self._vecs = [_tfidf_vec(doc, self._idf) for doc in self._corpus]

    def query(self, query: str, top_k: int = 3) -> List[Tuple[float, str]]:
        """
        Return top_k (score, segment_text) tuples, sorted by descending relevance.
        """
        q_tokens = _tokenize(query)
        q_vec = _tfidf_vec(q_tokens, self._idf)
        scored = [
            (_cosine(q_vec, doc_vec), self._segments[i])
            for i, doc_vec in enumerate(self._vecs)
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [(score, text) for score, text in scored[:top_k] if score > 0]


def build_from_state(state: AgentState) -> RAGEngine:
    """Build a RAGEngine from the raw_input transcript lines."""
    lines = [line.strip() for line in state.raw_input.splitlines() if line.strip()]
    if not lines:
        lines = ["(empty conversation)"]
    return RAGEngine(lines)

