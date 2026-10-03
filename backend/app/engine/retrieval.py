"""Deterministic retrieval over the CarbonPilot methodology corpus.

The agent must be able to cite *why* a figure is what it is, not only hand back
a number. This module answers "which methodology passage backs this claim?"
with a pure-stdlib BM25 ranker, so retrieval is reproducible, offline and
cheap. It never raises on an unknown term: a missing citation is an empty
result, never an invented one — the same discipline the calculation engine
applies to emission factors.
"""

from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

CORPUS_PATH = Path(__file__).resolve().parent.parent / "data" / "methodology.json"

# Okapi BM25 defaults: k1 controls term-frequency saturation, b controls length
# normalisation. These are the standard reference values.
BM25_K1 = 1.5
BM25_B = 0.75

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Function words carry no topical signal. Dropping them stops a query like
# "the and of" from matching every passage, and keeps the "no results" path
# honest.
_STOPWORDS = frozenset(
    """
    a about above after again against all am an and any are aren as at be because
    been before being below between both but by can cannot could couldn did didn
    do does doesn doing don down during each few for from further had hadn has
    hasn have haven having he her here hers herself him himself his how i if in
    into is isn it its itself just me more most mustn my myself no nor not now
    of off on once only or other ought our ours ourselves out over own same
    shan she should shouldn so some such than that the their theirs them
    themselves then there these they this those through to too under until up
    very was wasn we were weren what when where which while who whom why with
    won would wouldn you your yours yourself yourselves
    """.split()
)


def _tokenize(text: str) -> list[str]:
    """Lowercased word/number tokens; punctuation and hyphens are separators."""
    return _TOKEN_RE.findall(text.lower())


def _content_tokens(text: str) -> list[str]:
    return [token for token in _tokenize(text) if token not in _STOPWORDS]


def _searchable_text(passage: dict) -> str:
    """The text a passage is indexed under: its body plus its short labels."""
    return " ".join(
        (passage.get("text", ""), passage.get("section", ""), passage.get("topic", ""))
    )


class _CorpusIndex(NamedTuple):
    passages: tuple[dict, ...]
    lengths: tuple[int, ...]
    avgdl: float
    postings: dict[str, dict[int, int]]  # term -> {document index: frequency}


@lru_cache
def load_corpus() -> list[dict]:
    """Load the methodology passages from the JSON corpus.

    Cached because the corpus is immutable reference data: parsing it once per
    process keeps every search allocation-free on the I/O side.
    """
    with CORPUS_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)["passages"]


@lru_cache
def _build_index() -> _CorpusIndex:
    """Tokenise the corpus once; every search reuses this immutable index."""
    passages = tuple(load_corpus())
    postings: dict[str, dict[int, int]] = {}
    lengths: list[int] = []
    for doc_index, passage in enumerate(passages):
        tokens = _content_tokens(_searchable_text(passage))
        lengths.append(len(tokens))
        for token in tokens:
            bucket = postings.setdefault(token, {})
            bucket[doc_index] = bucket.get(doc_index, 0) + 1
    avgdl = sum(lengths) / len(lengths) if lengths else 0.0
    return _CorpusIndex(passages, tuple(lengths), avgdl, postings)


def _idf(n_docs: int, doc_freq: int) -> float:
    """BM25 inverse document frequency, strictly positive for a known term."""
    return math.log((n_docs - doc_freq + 0.5) / (doc_freq + 0.5) + 1.0)


def search(query: str, k: int = 4) -> list[dict]:
    """Rank corpus passages against ``query``, best first.

    Each result is the passage's fields plus a positive ``score``. Ordering is
    fully deterministic: equal scores fall back to the passage id, so identical
    input always yields an identical list. A blank query, a stopword-only query
    or a query whose every term is unknown to the corpus returns ``[]`` rather
    than raising — an empty citation is a valid answer, a fabricated one is not.
    """
    if not query or k <= 0:
        return []

    terms = list(dict.fromkeys(_content_tokens(query)))
    if not terms:
        return []

    index = _build_index()
    n_docs = len(index.passages)
    if n_docs == 0:
        return []
    avgdl = index.avgdl or 1.0

    scores: dict[int, float] = {}
    for term in terms:
        postings = index.postings.get(term)
        if not postings:
            continue  # unknown term: contributes nothing, never raises
        idf = _idf(n_docs, len(postings))
        for doc_index, freq in postings.items():
            length = index.lengths[doc_index]
            denominator = freq + BM25_K1 * (1.0 - BM25_B + BM25_B * (length / avgdl))
            scores[doc_index] = scores.get(doc_index, 0.0) + (
                idf * freq * (BM25_K1 + 1.0) / denominator
            )

    ranked = [(doc_index, score) for doc_index, score in scores.items() if score > 0.0]
    ranked.sort(key=lambda pair: (-pair[1], index.passages[pair[0]]["id"]))
    return [
        {**index.passages[doc_index], "score": round(score, 6)}
        for doc_index, score in ranked[:k]
    ]
