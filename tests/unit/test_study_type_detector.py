"""Phase 5A: StudyTypeDetector tests."""

from src.screening.study_type_detector import StudyTypeDetector, STUDY_TYPES


class TestStudyTypeDetector:
    def test_empirical_study(self):
        d = StudyTypeDetector()
        st, scores, rationale = d.classify(
            title="An Empirical Study of Developer Productivity",
            abstract="We conducted a controlled experiment with 100 participants"
        )
        assert st == "empirical_study", f"Got {st}"
        assert rationale
        assert scores[st] >= 2

    def test_systematic_review(self):
        d = StudyTypeDetector()
        st, scores, rationale = d.classify(
            title="Systematic Literature Review of Agile Methods",
            abstract="We performed a systematic review following PRISMA guidelines"
        )
        assert st == "systematic_review", f"Got {st}"
        assert rationale

    def test_tertiary_study(self):
        d = StudyTypeDetector()
        st, scores, rationale = d.classify(
            title="A Tertiary Study of Systematic Reviews in SE",
            abstract="We conducted a meta-synthesis of existing review papers"
        )
        assert st == "tertiary_study", f"Got {st}"

    def test_experience_report(self):
        d = StudyTypeDetector()
        st, scores, rationale = d.classify(
            title="Experience Report: Migrating to Microservices",
            abstract="We describe our experience building a distributed system"
        )
        assert st == "experience_report", f"Got {st}"

    def test_opinion_paper(self):
        d = StudyTypeDetector()
        st, scores, rationale = d.classify(
            title="Opinion Paper: The Future of Software Engineering",
            abstract="We argue that AI will transform how we develop software"
        )
        assert st == "opinion_paper", f"Got {st}"

    def test_tutorial(self):
        d = StudyTypeDetector()
        st, scores, rationale = d.classify(
            title="Tutorial: Getting Started with Rust",
            abstract="A step-by-step guide for beginners"
        )
        assert st == "tutorial", f"Got {st}"

    def test_editorial(self):
        d = StudyTypeDetector()
        st, scores, rationale = d.classify(
            title="Editorial: Introduction to Special Issue",
            abstract="Guest editor introduction for this volume"
        )
        assert st == "editorial", f"Got {st}"

    def test_cfp(self):
        d = StudyTypeDetector()
        st, scores, rationale = d.classify(
            title="Call for Papers: ICSE 2026",
            abstract="Important dates and submission guidelines for ICSE"
        )
        assert st == "cfp", f"Got {st}"

    def test_job_posting(self):
        d = StudyTypeDetector()
        st, scores, rationale = d.classify(
            title="Job Posting: Software Engineer at Google",
            abstract="We are hiring, salary range competitive"
        )
        assert st == "job_posting", f"Got {st}"

    def test_unknown_no_match(self):
        d = StudyTypeDetector(min_patterns=1)
        st, scores, rationale = d.classify(
            title="Completely Random Text",
            abstract="No matching patterns here at all whatsoever"
        )
        assert st == "unknown", f"Got {st}"
        assert not scores or all(v < 1 for v in scores.values())

    def test_confidence_bonus(self):
        d = StudyTypeDetector()
        assert d.get_confidence_bonus("empirical_study") > 0
        assert d.get_confidence_bonus("systematic_review") > 0
        assert d.get_confidence_bonus("opinion_paper") < 0
        assert d.get_confidence_bonus("tutorial") < 0
        assert d.get_confidence_bonus("unknown") == 0.0

    def test_document_type_boost(self):
        d = StudyTypeDetector(min_patterns=1)
        st, scores, rationale = d.classify(
            title="Review of Testing Techniques",
            abstract="Summary of existing approaches",
            document_type="review"
        )
        assert st == "systematic_review", f"Got {st}"

    def test_list_types(self):
        d = StudyTypeDetector()
        types = d.list_types()
        assert len(types) == len(STUDY_TYPES)
        for t in types:
            assert "id" in t
            assert "label" in t
            assert "patterns" in t
