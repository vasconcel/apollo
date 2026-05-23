"""Tests for semantic_ranker.py."""

import pytest
import numpy as np
from src.screening.semantic_ranker import TfidfVectorizer, BM25Ranker, SemanticRanker


DOCUMENTS = [
    "Empirical study on software engineering hiring practices",
    "Technical recruitment in the software industry",
    "A systematic literature review of agile methods",
    "Machine learning for predictive maintenance",
]


class TestTfidfVectorizer:
    def test_fit_transform_shape(self):
        vec = TfidfVectorizer()
        matrix = vec.fit_transform(DOCUMENTS)
        assert matrix.shape == (4, len(set(w.lower() for d in DOCUMENTS for w in d.split())))

    def test_transform_after_fit(self):
        vec = TfidfVectorizer()
        vec.fit(DOCUMENTS)
        matrix = vec.transform(["test document"])
        assert matrix.shape[0] == 1

    def test_similar_documents_have_higher_similarity(self):
        vec = TfidfVectorizer()
        vec.fit(DOCUMENTS)
        v1 = vec.transform(["software engineering hiring"])[0]
        v2 = vec.transform(DOCUMENTS)[0]  # document 0 is about SE hiring
        v3 = vec.transform(DOCUMENTS)[3]  # document 3 is about ML
        sim1 = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-10)
        sim2 = np.dot(v1, v3) / (np.linalg.norm(v1) * np.linalg.norm(v3) + 1e-10)
        assert sim1 > sim2

    def test_raises_if_not_fitted(self):
        vec = TfidfVectorizer()
        with pytest.raises(RuntimeError):
            vec.transform(["test"])

    def test_empty_document(self):
        vec = TfidfVectorizer()
        vec.fit(["", "some text"])
        matrix = vec.transform(["", "other"])
        assert matrix.shape == (2, 2)


class TestBM25Ranker:
    def test_fit_and_score(self):
        bm25 = BM25Ranker()
        bm25.fit(DOCUMENTS)
        scores = bm25.score("software engineering hiring")
        assert len(scores) == 4
        assert all(isinstance(s, float) for s in scores)

    def test_relevant_document_scores_higher(self):
        bm25 = BM25Ranker()
        bm25.fit(DOCUMENTS)
        scores = bm25.score("software engineering hiring")
        # document 0 mentions "software engineering" and "hiring"
        assert scores[0] > scores[3]

    def test_raises_if_not_fitted(self):
        bm25 = BM25Ranker()
        with pytest.raises(RuntimeError):
            bm25.score("test")

    def test_single_document(self):
        bm25 = BM25Ranker()
        bm25.fit(["only document"])
        scores = bm25.score("document")
        assert len(scores) == 1


class TestSemanticRanker:
    def test_fit(self):
        ranker = SemanticRanker()
        ranker.fit(DOCUMENTS)
        assert ranker._fitted is True

    def test_raises_if_not_fitted(self):
        ranker = SemanticRanker()
        with pytest.raises(RuntimeError):
            ranker.tfidf_similarity("test")
        with pytest.raises(RuntimeError):
            ranker.bm25_score("test")

    def test_tfidf_similarity_shape(self):
        ranker = SemanticRanker()
        ranker.fit(DOCUMENTS)
        scores = ranker.tfidf_similarity("software engineering")
        assert len(scores) == 4

    def test_bm25_score_shape(self):
        ranker = SemanticRanker()
        ranker.fit(DOCUMENTS)
        scores = ranker.bm25_score("software engineering")
        assert len(scores) == 4

    def test_rank_returns_sorted_tuples(self):
        ranker = SemanticRanker()
        ranker.fit(DOCUMENTS)
        ranked = ranker.rank("software engineering hiring", method="bm25")
        assert len(ranked) == 4
        # scores should be descending
        for i in range(len(ranked) - 1):
            assert ranked[i][1] >= ranked[i + 1][1]

    def test_rank_method_tfidf(self):
        ranker = SemanticRanker()
        ranker.fit(DOCUMENTS)
        ranked = ranker.rank("software engineering", method="tfidf")
        assert len(ranked) == 4

    def test_rank_invalid_method(self):
        ranker = SemanticRanker()
        ranker.fit(DOCUMENTS)
        with pytest.raises(ValueError, match="Unknown method"):
            ranker.rank("test", method="invalid")

    def test_aggregate_signals(self):
        ranker = SemanticRanker()
        ranker.fit(DOCUMENTS)
        signals = ranker.aggregate_signals("software engineering hiring")
        assert "tfidf_max" in signals
        assert "tfidf_mean" in signals
        assert "bm25_max" in signals
        assert "bm25_mean" in signals
        assert "embedding_max" in signals
        assert "embedding_mean" in signals
        assert signals["tfidf_mean"] >= 0
        assert signals["bm25_mean"] >= 0
