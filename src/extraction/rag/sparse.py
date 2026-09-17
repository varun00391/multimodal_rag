from __future__ import annotations

import hashlib
import math
import re
from collections import Counter

_TOKEN = re.compile(r"[a-z0-9]+")
_INDEX_MOD = 2_147_483_647
_BM25_K1 = 1.2
_BM25_B = 0.75


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def token_index(token: str) -> int:
    digest = hashlib.sha256(token.encode("utf-8")).digest()[:8]
    value = int.from_bytes(digest, "big") % _INDEX_MOD
    return value or 1


def sparse_tf(text: str) -> dict[int, float]:
    counts: dict[int, float] = {}
    for token, freq in Counter(tokenize(text)).items():
        idx = token_index(token)
        counts[idx] = counts.get(idx, 0.0) + float(freq)
    return counts


def sparse_pairs(text: str) -> tuple[list[int], list[float]]:
    counts = sparse_tf(text)
    if not counts:
        return [], []
    indices = list(counts)
    return indices, [counts[idx] for idx in indices]


def bm25_score(
    query_tf: dict[int, float],
    doc_tf: dict[int, float],
    doc_count: int,
    df: dict[int, int],
    avgdl: float,
) -> float:
    if not query_tf or not doc_tf or doc_count <= 0:
        return 0.0
    dl = sum(doc_tf.values()) or 1.0
    avg = avgdl or dl
    score = 0.0
    for term, _qtf in query_tf.items():
        tf = doc_tf.get(term, 0.0)
        if tf <= 0:
            continue
        n_q = df.get(term, 0)
        idf = math.log(1.0 + (doc_count - n_q + 0.5) / (n_q + 0.5))
        denom = tf + _BM25_K1 * (1.0 - _BM25_B + _BM25_B * dl / avg)
        score += idf * (tf * (_BM25_K1 + 1.0)) / denom
    return score
