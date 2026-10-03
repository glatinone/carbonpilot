"""Retrieval tests — behaviour contracts for the methodology corpus.

These assert how a query relates to what it should retrieve (a query about X
finds a passage about X; a passage's own rare word finds that passage) rather
than freezing the corpus size or any particular score. No database is needed:
the retriever is a pure function over immutable JSON.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from app.engine import retrieval
from app.engine.retrieval import CORPUS_PATH, load_corpus, search

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _indexed_text(passage: dict) -> str:
    """Mirror the fields the retriever indexes, so document frequency here
    means the same thing it means to the ranker."""
    return f"{passage['text']} {passage['section']} {passage['topic']}"


# --------------------------------------------------------------------------- #
# Retrieval behaviour
# --------------------------------------------------------------------------- #

def test_spend_based_query_retrieves_a_spend_based_passage() -> None:
    results = search("why is spend-based procurement so uncertain")
    assert results, "a spend-based query must retrieve something"
    assert any("spend-based" in r["text"] for r in results)


def test_scope_2_query_retrieves_a_scope_2_passage() -> None:
    results = search("scope 2 electricity location and market based")
    assert results
    assert any("scope 2" in r["text"].lower() for r in results)


def test_spike_query_ranks_the_robust_statistics_passage_first() -> None:
    results = search("detecting a spike with a robust z-score")
    assert results
    top = results[0]
    assert top["topic"] == "robust-statistics"
    # The winning passage must actually be about the robust method.
    assert "median" in top["text"].lower()
    assert "mad" in top["text"].lower()


def test_blank_query_returns_empty() -> None:
    assert search("") == []
    assert search("   ") == []


def test_stopword_only_query_returns_empty() -> None:
    assert search("the and of to a is it") == []


def test_unknown_term_returns_empty_without_raising() -> None:
    assert search("zzzqqq nonexistentterm") == []


def test_k_is_respected_and_top_result_is_stable() -> None:
    query = "scope 2 electricity emission factor"
    one = search(query, k=1)
    four = search(query, k=4)
    assert len(one) == 1
    assert len(four) == 4
    assert one[0]["id"] == four[0]["id"]
    assert one[0]["score"] == four[0]["score"]


def test_scores_are_positive_and_sorted_descending() -> None:
    results = search("emission factor activity data cloud spend procurement")
    assert results
    scores = [r["score"] for r in results]
    assert all(score > 0 for score in scores)
    assert scores == sorted(scores, reverse=True)


def test_identical_queries_return_identical_orderings() -> None:
    query = "scope 3 categories purchased goods and services"
    first = search(query, k=6)
    second = search(query, k=6)
    assert [r["id"] for r in first] == [r["id"] for r in second]
    assert [r["score"] for r in first] == [r["score"] for r in second]


def test_every_passage_is_retrievable_by_a_distinctive_word_from_its_own_text() -> None:
    """A passage's own rare vocabulary must pull that passage back out."""
    corpus = load_corpus()

    document_freq: Counter[str] = Counter()
    for passage in corpus:
        document_freq.update(set(_tokens(_indexed_text(passage))))

    for passage in corpus:
        own_terms = _tokens(passage["text"])
        assert own_terms, f"{passage['id']} has no searchable text"
        # Rarest first, then longest, then alphabetical: a deterministic pick.
        distinctive = min(own_terms, key=lambda t: (document_freq[t], -len(t), t))
        hits = {r["id"] for r in search(distinctive, k=5)}
        assert passage["id"] in hits, (
            f"{passage['id']} not retrieved by its own distinctive word "
            f"{distinctive!r} (document_freq={document_freq[distinctive]})"
        )


# --------------------------------------------------------------------------- #
# Corpus contract
# --------------------------------------------------------------------------- #

def test_corpus_path_points_at_the_methodology_file() -> None:
    assert isinstance(CORPUS_PATH, Path)
    assert CORPUS_PATH.name == "methodology.json"
    assert CORPUS_PATH.exists()


def test_corpus_passages_expose_the_public_fields() -> None:
    corpus = load_corpus()
    assert corpus, "corpus must not be empty"
    required = {"id", "source", "section", "topic", "text"}
    for passage in corpus:
        assert required <= set(passage), f"{passage.get('id')} is missing fields"
        assert passage["text"].strip(), f"{passage['id']} has empty text"

    ids = [passage["id"] for passage in corpus]
    assert len(ids) == len(set(ids)), "passage ids must be unique"


def test_public_search_shape() -> None:
    """Each result carries the passage fields plus a numeric score."""
    results = search("cloud emissions")
    assert results
    for item in results:
        assert {"id", "source", "section", "topic", "text", "score"} <= set(item)
        assert isinstance(item["score"], float)
