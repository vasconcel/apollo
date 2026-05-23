"""Phase 5A: DomainLexiconEngine tests."""

from src.screening.domain_lexicon import DomainLexiconEngine


LEXICON_YAML = """
positive:
  - term: "technical interview"
    weight: 0.6
  - term: "developer recruitment"
    weight: 0.5
  - term: "candidate assessment"
    weight: 0.4
negative:
  - term: "salary"
    weight: 0.7
  - term: "job opening"
    weight: 0.6
  - term: "vacancy"
    weight: 0.6
  - term: "career path"
    weight: 0.3
"""


class TestDomainLexiconEngine:
    def test_compile_and_evaluate_positive(self):
        lex = DomainLexiconEngine()
        lex.compile({
            "positive": [{"term": "technical interview", "weight": 0.6}],
            "negative": []
        })
        ev = lex.evaluate(
            title="Technical Interview Preparation",
            abstract="How to prepare"
        )
        assert len(ev) == 1
        assert ev[0].evidence_type == "lexicon"
        assert ev[0].rule_id == "lex_pos_technical interview"
        assert ev[0].confidence == 0.6

    def test_compile_and_evaluate_negative(self):
        lex = DomainLexiconEngine()
        lex.compile({
            "positive": [],
            "negative": [{"term": "salary", "weight": 0.7}]
        })
        ev = lex.evaluate(
            title="Salary Negotiation Tips",
            abstract=""
        )
        assert len(ev) == 1
        assert ev[0].rule_id == "lex_neg_salary"
        assert ev[0].confidence == 0.7

    def test_lexicon_score_positive_domain(self):
        lex = DomainLexiconEngine()
        lex.compile({
            "positive": [{"term": "recruitment", "weight": 0.5}],
            "negative": []
        })
        score = lex.compute_lexicon_score(
            title="Recruitment Strategies",
            abstract=""
        )
        assert score > 0

    def test_lexicon_score_negative_domain(self):
        lex = DomainLexiconEngine()
        lex.compile({
            "positive": [],
            "negative": [{"term": "salary", "weight": 0.7}]
        })
        score = lex.compute_lexicon_score(
            title="Salary Survey Results",
            abstract=""
        )
        assert score < 0

    def test_lexicon_score_mixed(self):
        lex = DomainLexiconEngine()
        lex.compile({
            "positive": [{"term": "assessment", "weight": 0.4}],
            "negative": [{"term": "salary", "weight": 0.7}]
        })
        score = lex.compute_lexicon_score(
            title="Salary and Assessment Analysis",
            abstract=""
        )
        assert score < 0  # negative weight dominates

    def test_no_match_returns_empty(self):
        lex = DomainLexiconEngine()
        lex.compile({
            "positive": [{"term": "algorithm", "weight": 0.5}],
            "negative": []
        })
        ev = lex.evaluate(
            title="Software Engineering Practices",
            abstract=""
        )
        assert len(ev) == 0

    def test_stage_scoping(self):
        lex = DomainLexiconEngine()
        lex.compile({
            "positive": [
                {"term": "ec-specific", "stages": ["ec"]},
                {"term": "ic-specific", "stages": ["ic"]},
            ],
            "negative": []
        })
        ec_ev = lex.evaluate(title="ec-specific content", stage="ec")
        ic_ev = lex.evaluate(title="ec-specific content", stage="ic")
        assert len(ec_ev) == 1
        assert len(ic_ev) == 0

    def test_yaml_compilation(self):
        lex = DomainLexiconEngine()
        lex.compile_yaml(LEXICON_YAML)
        assert lex._initialized
        assert len(lex._compiled_positive) == 3
        assert len(lex._compiled_negative) == 4

    def test_not_initialized_returns_empty(self):
        lex = DomainLexiconEngine()
        ev = lex.evaluate(title="test")
        assert len(ev) == 0

    def test_to_dict(self):
        lex = DomainLexiconEngine()
        lex.compile({
            "positive": [{"term": "test", "weight": 0.5}],
            "negative": [{"term": "bad", "weight": 0.6}]
        })
        d = lex.to_dict()
        assert "positive_categories" in d
        assert "negative_categories" in d
        assert len(d["positive_categories"]) == 1
        assert len(d["negative_categories"]) == 1

    def test_simple_string_terms(self):
        lex = DomainLexiconEngine()
        lex.compile({
            "positive": ["simple match"],
            "negative": []
        })
        ev = lex.evaluate(title="Simple Match Test", abstract="")
        assert len(ev) == 1
        assert ev[0].confidence == 0.5  # default weight
