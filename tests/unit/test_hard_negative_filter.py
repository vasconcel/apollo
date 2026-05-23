"""Phase 5A: HardNegativeFilter tests."""

from src.screening.hard_negative_filter import HardNegativeFilter, HARD_NEGATIVE_PATTERNS, MATCH_REQUIRED_PATTERNS


class TestHardNegativeFilter:
    def test_job_posting_detected(self):
        f = HardNegativeFilter()
        is_hn, ev, cnt = f.evaluate(title="Job Posting: Senior Software Engineer", abstract="We are hiring a senior developer")
        assert is_hn is True
        assert cnt >= MATCH_REQUIRED_PATTERNS
        assert len(ev) > 0
        for e in ev:
            assert e.evidence_type == "exclusion_pattern"

    def test_salary_discussion_detected(self):
        f = HardNegativeFilter()
        is_hn, ev, cnt = f.evaluate(
            title="Salary Negotiation and Compensation Review",
            abstract="Analysis of salary increases and pay scales"
        )
        assert is_hn is True
        assert cnt >= MATCH_REQUIRED_PATTERNS

    def test_bootcamp_detected(self):
        f = HardNegativeFilter()
        is_hn, ev, cnt = f.evaluate(title="Learn to Code Bootcamp", abstract="Become a developer in 12 weeks")
        assert is_hn is True
        assert cnt >= MATCH_REQUIRED_PATTERNS

    def test_university_admission_detected(self):
        f = HardNegativeFilter()
        is_hn, ev, cnt = f.evaluate(
            title="Graduate School Admission Process and Application Deadline",
            abstract="How to get into our program with admission essay and entrance exam"
        )
        assert is_hn is True
        assert cnt >= MATCH_REQUIRED_PATTERNS

    def test_career_advice_detected(self):
        f = HardNegativeFilter()
        is_hn, ev, cnt = f.evaluate(title="Career Advice for Junior Developers", abstract="Tips for job search success")
        assert is_hn is True
        assert cnt >= MATCH_REQUIRED_PATTERNS

    def test_marketing_promo_detected(self):
        f = HardNegativeFilter()
        is_hn, ev, cnt = f.evaluate(title="Limited Time Offer", abstract="Buy now and save 50%")
        assert is_hn is True
        assert cnt >= MATCH_REQUIRED_PATTERNS

    def test_legitimate_research_not_hard_negative(self):
        f = HardNegativeFilter()
        is_hn, ev, cnt = f.evaluate(
            title="Empirical Study of Agile Development",
            abstract="We conducted a controlled experiment with 50 developers"
        )
        assert is_hn is False

    def test_systematic_review_not_hard_negative(self):
        f = HardNegativeFilter()
        is_hn, ev, cnt = f.evaluate(
            title="Systematic Literature Review of SE Practices",
            abstract="We searched 5 databases and analyzed 200 papers"
        )
        assert is_hn is False

    def test_empty_text_no_match(self):
        f = HardNegativeFilter()
        is_hn, ev, cnt = f.evaluate(title="", abstract="")
        assert is_hn is False
        assert cnt == 0
        assert len(ev) == 0

    def test_classify_returns_category(self):
        f = HardNegativeFilter()
        cat = f.classify("Job Posting: Senior Developer Position")
        assert cat == "job_posting"

    def test_list_rules(self):
        f = HardNegativeFilter()
        rules = f.list_rules()
        assert len(rules) == len(HARD_NEGATIVE_PATTERNS)
        for r in rules:
            assert "rule_id" in r
            assert "name" in r
            assert "patterns_count" in r
            assert r["patterns_count"] > 0

    def test_evidence_confidence_is_high(self):
        f = HardNegativeFilter()
        is_hn, ev, cnt = f.evaluate(title="Job Posting: Senior Dev", abstract="We are hiring now")
        assert is_hn is True
        for e in ev:
            assert e.confidence >= 0.95

    def test_recruitment_ad_detected(self):
        f = HardNegativeFilter()
        is_hn, ev, cnt = f.evaluate(title="Recruitment Agency", abstract="Talent acquisition services")
        assert is_hn is True
        assert cnt >= MATCH_REQUIRED_PATTERNS
