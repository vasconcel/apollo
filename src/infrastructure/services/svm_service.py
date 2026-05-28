import logging
from typing import Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier

from src.domain.models import Paper

logger = logging.getLogger(__name__)

_SVM_CONFIDENCE_THRESHOLD = 0.90


class SVMService:
    def __init__(self) -> None:
        self._vectorizer = TfidfVectorizer(max_features=5000, ngram_range=(1, 2))
        self._classifier: Optional[SGDClassifier] = None
        self.is_trained: bool = False

    def train(self, papers: list[Paper], human_decisions: dict[str, str]) -> bool:
        texts: list[str] = []
        labels: list[str] = []

        for p in papers:
            decision = human_decisions.get(p.id)
            if decision is None:
                continue
            text = f"{p.title} {p.abstract or ''}"
            texts.append(text)
            labels.append(decision)

        if len(texts) < 5:
            logger.info("SVM: only %d audited papers, need ≥5 — skipping training", len(texts))
            return False

        unique_labels = set(labels)
        if len(unique_labels) < 2:
            logger.info("SVM: only one class (%s) present — skipping training", next(iter(unique_labels)))
            return False

        try:
            X = self._vectorizer.fit_transform(texts)
            y = [1 if d == "YES" else 0 for d in labels]

            self._classifier = SGDClassifier(
                loss="log_loss",
                penalty="l2",
                alpha=1e-4,
                max_iter=1000,
                tol=1e-3,
                random_state=42,
            )
            self._classifier.fit(X, y)
            self.is_trained = True
            logger.info(
                "SVM trained on %d audited papers (%d YES, %d NO)",
                len(texts),
                sum(y),
                len(y) - sum(y),
            )
            return True
        except Exception as exc:
            logger.error("SVM training failed: %s", exc)
            return False

    def predict_exclusion(self, paper: Paper) -> tuple[bool, float]:
        if not self.is_trained or self._classifier is None:
            return False, 0.0

        text = f"{paper.title} {paper.abstract or ''}"
        X = self._vectorizer.transform([text])
        proba = self._classifier.predict_proba(X)[0]

        no_index = 0 if self._classifier.classes_[0] == 0 else 1
        confidence = float(proba[no_index])

        if confidence >= _SVM_CONFIDENCE_THRESHOLD:
            return True, confidence

        return False, confidence
