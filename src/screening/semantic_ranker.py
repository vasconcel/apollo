"""
Phase 2E: Lightweight local semantic ranking primitives.
Phase 4C: Corpus freezing, multi-signal agreement, semantic confidence bounds.
"""

from __future__ import annotations

import hashlib
from math import log
from typing import Dict, List, Optional, Tuple, Any

import numpy as np


class TfidfVectorizer:
    def __init__(self) -> None:
        self._vocab: Dict[str, int] = {}
        self._idf: Dict[int, float] = {}
        self._fitted = False

    def fit(self, documents: List[str]) -> TfidfVectorizer:
        doc_count = len(documents)
        df: Dict[str, int] = {}
        for doc in documents:
            terms = set(doc.lower().split())
            for term in terms:
                df[term] = df.get(term, 0) + 1
        self._vocab = {term: i for i, term in enumerate(sorted(df.keys()))}
        self._idf = {
            i: log((doc_count + 1) / (freq + 1)) + 1
            for term, freq in df.items()
            for i in [self._vocab[term]]
        }
        self._fitted = True
        return self

    def transform(self, documents: List[str]) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("Vectorizer not fitted")
        matrix = np.zeros((len(documents), len(self._vocab)), dtype=np.float64)
        for i, doc in enumerate(documents):
            terms = doc.lower().split()
            term_counts: Dict[str, int] = {}
            for t in terms:
                term_counts[t] = term_counts.get(t, 0) + 1
            max_tf = max(term_counts.values()) if term_counts else 1
            for term, count in term_counts.items():
                if term in self._vocab:
                    tf = count / max_tf
                    idx = self._vocab[term]
                    matrix[i, idx] = tf * self._idf[idx]
        return matrix

    def fit_transform(self, documents: List[str]) -> np.ndarray:
        return self.fit(documents).transform(documents)

    @property
    def fingerprint(self) -> str:
        if not self._fitted:
            return "unfitted"
        h = hashlib.sha256()
        h.update(str(sorted(self._vocab.items())).encode())
        h.update(str(sorted(self._idf.items())).encode())
        return h.hexdigest()[:16]


class BM25Ranker:
    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self._k1 = k1
        self._b = b
        self._documents: List[str] = []
        self._doc_terms: List[List[str]] = []
        self._avg_doc_len: float = 0.0
        self._doc_freq: Dict[str, int] = {}
        self._num_docs: int = 0
        self._fitted = False

    def fit(self, documents: List[str]) -> BM25Ranker:
        self._documents = documents
        self._doc_terms = [doc.lower().split() for doc in documents]
        self._num_docs = len(documents)
        self._avg_doc_len = (
            sum(len(t) for t in self._doc_terms) / max(self._num_docs, 1)
        )
        self._doc_freq = {}
        for terms in self._doc_terms:
            for term in set(terms):
                self._doc_freq[term] = self._doc_freq.get(term, 0) + 1
        self._fitted = True
        return self

    def score(self, query: str) -> List[float]:
        if not self._fitted:
            raise RuntimeError("BM25Ranker not fitted")
        query_terms = query.lower().split()
        scores = []
        for terms in self._doc_terms:
            doc_len = len(terms)
            score = 0.0
            for qt in query_terms:
                if qt not in self._doc_freq:
                    continue
                idf = log(
                    (self._num_docs - self._doc_freq[qt] + 0.5)
                    / (self._doc_freq[qt] + 0.5)
                    + 1
                )
                tf = terms.count(qt)
                score += idf * (
                    (tf * (self._k1 + 1))
                    / (tf + self._k1 * (1 - self._b + self._b * doc_len / self._avg_doc_len))
                )
            scores.append(score)
        return scores

    @property
    def fingerprint(self) -> str:
        if not self._fitted:
            return "unfitted"
        h = hashlib.sha256()
        h.update(str(self._documents).encode())
        h.update(f"k1={self._k1},b={self._b}".encode())
        return h.hexdigest()[:16]


class SemanticRanker:
    """Phase 4C: Semantic stability with corpus freezing and multi-signal agreement.

    Features:
      - Corpus fingerprint for reproducibility
      - Multi-signal agreement (requires 2 of 3 methods)
      - Semantic confidence bounds (never auto-include on semantics alone)
    """

    def __init__(self) -> None:
        self._tfidf = TfidfVectorizer()
        self._bm25 = BM25Ranker()
        self._embedder: Any = None
        self._documents: List[str] = []
        self._fitted = False

    def fit(self, documents: List[str]) -> SemanticRanker:
        self._documents = list(documents)
        self._tfidf.fit(documents)
        self._bm25.fit(documents)
        self._fitted = True
        return self

    @property
    def corpus_fingerprint(self) -> str:
        """Deterministic fingerprint of fitted corpus state."""
        if not self._fitted:
            return "unfitted"
        h = hashlib.sha256()
        h.update(str(self._documents).encode())
        h.update(self._tfidf.fingerprint.encode())
        h.update(self._bm25.fingerprint.encode())
        return h.hexdigest()[:32]

    @property
    def document_count(self) -> int:
        return len(self._documents)

    def _get_embedder(self) -> Any:
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer
            self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
        return self._embedder

    def tfidf_similarity(self, query: str) -> List[float]:
        if not self._fitted:
            raise RuntimeError("SemanticRanker not fitted")
        query_vec = self._tfidf.transform([query])[0]
        doc_vecs = self._tfidf.transform(self._documents)
        similarities = []
        for doc_vec in doc_vecs:
            dot = float(np.dot(query_vec, doc_vec))
            norm_q = float(np.linalg.norm(query_vec))
            norm_d = float(np.linalg.norm(doc_vec))
            if norm_q == 0 or norm_d == 0:
                similarities.append(0.0)
            else:
                similarities.append(dot / (norm_q * norm_d))
        return similarities

    def bm25_score(self, query: str) -> List[float]:
        if not self._fitted:
            raise RuntimeError("SemanticRanker not fitted")
        return self._bm25.score(query)

    def embedding_similarity(self, query: str) -> List[float]:
        embedder = self._get_embedder()
        query_emb = embedder.encode(query, normalize_embeddings=True)
        doc_embs = embedder.encode(self._documents, normalize_embeddings=True)
        similarities = np.dot(doc_embs, query_emb).tolist()
        return [float(s) for s in similarities]

    def rank(
        self, query: str, method: str = "bm25"
    ) -> List[Tuple[int, float]]:
        if method == "tfidf":
            scores = self.tfidf_similarity(query)
        elif method == "bm25":
            scores = self.bm25_score(query)
        elif method == "embedding":
            scores = self.embedding_similarity(query)
        else:
            raise ValueError(f"Unknown method: {method}")
        indexed = list(enumerate(scores))
        indexed.sort(key=lambda x: x[1], reverse=True)
        return indexed

    def aggregate_signals(self, query: str) -> Dict[str, float]:
        tfidf_scores = self.tfidf_similarity(query)
        bm25_scores = self.bm25_score(query)
        try:
            emb_scores = self.embedding_similarity(query)
        except Exception:
            emb_scores = [0.0] * len(self._documents)
        return {
            "tfidf_max": max(tfidf_scores) if tfidf_scores else 0.0,
            "tfidf_mean": float(np.mean(tfidf_scores)) if tfidf_scores else 0.0,
            "bm25_max": max(bm25_scores) if bm25_scores else 0.0,
            "bm25_mean": float(np.mean(bm25_scores)) if bm25_scores else 0.0,
            "embedding_max": max(emb_scores) if emb_scores else 0.0,
            "embedding_mean": float(np.mean(emb_scores)) if emb_scores else 0.0,
        }

    def multi_signal_agreement(
        self, query: str, threshold: float = 0.3
    ) -> Dict[str, Any]:
        """Phase 4C: Require agreement across at least 2 of 3 semantic signals.

        Semantic similarity alone must NEVER auto-include.
        Returns agreement verdict with supporting data.
        """
        tfidf_scores = self.tfidf_similarity(query)
        bm25_scores = self.bm25_score(query)
        try:
            emb_scores = self.embedding_similarity(query)
        except Exception:
            emb_scores = [0.0] * len(self._documents)

        methods_above = 0
        details = {}

        if tfidf_scores:
            tfidf_max = max(tfidf_scores)
            tfidf_above = tfidf_max >= threshold
            details["tfidf"] = {"max": tfidf_max, "above_threshold": tfidf_above}
            if tfidf_above:
                methods_above += 1

        if bm25_scores:
            bm25_max = max(bm25_scores)
            bm25_above = bm25_max >= threshold
            details["bm25"] = {"max": bm25_max, "above_threshold": bm25_above}
            if bm25_above:
                methods_above += 1

        if emb_scores:
            emb_max = max(emb_scores)
            emb_above = emb_max >= threshold
            details["embedding"] = {"max": emb_max, "above_threshold": emb_above}
            if emb_above:
                methods_above += 1

        return {
            "agreement": methods_above >= 2,
            "methods_above_threshold": methods_above,
            "total_methods": 3,
            "threshold": threshold,
            "details": details,
        }
