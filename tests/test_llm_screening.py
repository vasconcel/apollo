from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_mock import MockerFixture

from src.domain.enums import CriterionType, ScreeningStatus, SourceType
from src.domain.models import Criterion, Paper


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def paper() -> Paper:
    return Paper(
        id="p42",
        title="Continuous Integration in Large-Scale Agile Projects",
        source_type=SourceType.WL,
        publication_year=2023,
        abstract="This paper studies CI practices in large-scale agile.",
        metadata={"Authors": "Fowler et al."},
    )


@pytest.fixture
def criteria() -> list[Criterion]:
    return [
        Criterion(
            id="c-ic1",
            type=CriterionType.INCLUSION,
            code="IC1",
            description="Peer-reviewed study",
        ),
        Criterion(
            id="c-ec2",
            type=CriterionType.EXCLUSION,
            code="EC2",
            description="Not related to software engineering",
        ),
    ]


def _mock_ollama_response(content: str, status_code: int = 200):
    """Build a mock httpx.Response-like object that mimics the Ollama API."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.raise_for_status.return_value = None
    resp.json.return_value = {
        "choices": [{"message": {"content": content}}]
    }
    return resp


def _mock_ollama_client(mocker: MockerFixture, response: MagicMock):
    """Patch httpx.AsyncClient so the service uses our mock response."""
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=response)
    mocker.patch("httpx.AsyncClient", return_value=mock_client)
    return mock_client


# ── OllamaLLMService Tests ───────────────────────────────────────────────


class TestOllamaLLMServiceValidResponses:
    @pytest.mark.asyncio
    async def test_returns_included_decision(self, paper, criteria, mocker: MockerFixture):
        from src.infrastructure.services.ollama_service import OllamaLLMService

        llm_json = (
            '{"reasoning": "Meets IC1.", '
            '"criteria_evaluation": {"EC2": false, "IC1": true}, '
            '"decision": "INCLUDED"}'
        )
        _mock_ollama_client(mocker, _mock_ollama_response(llm_json))

        service = OllamaLLMService()
        decision = await service.screen_paper(paper, criteria)

        assert decision.paper_id == "p42"
        assert decision.status is ScreeningStatus.INCLUDED
        assert decision.confidence_score == 1.0
        assert decision.rationale == "Meets IC1."
        assert decision.applied_criteria_codes == ["IC1"]

    @pytest.mark.asyncio
    async def test_returns_excluded_decision(self, paper, criteria, mocker: MockerFixture):
        from src.infrastructure.services.ollama_service import OllamaLLMService

        llm_json = (
            '{"reasoning": "Fails EC2.", '
            '"criteria_evaluation": {"EC2": true, "IC1": false}, '
            '"decision": "EXCLUDED"}'
        )
        _mock_ollama_client(mocker, _mock_ollama_response(llm_json))

        service = OllamaLLMService()
        decision = await service.screen_paper(paper, criteria)

        assert decision.status is ScreeningStatus.EXCLUDED
        assert decision.confidence_score == 1.0

    @pytest.mark.asyncio
    async def test_returns_needs_review_decision(self, paper, criteria, mocker: MockerFixture):
        from src.infrastructure.services.ollama_service import OllamaLLMService

        llm_json = (
            '{"reasoning": "Uncertain about IC1.", '
            '"criteria_evaluation": {"EC2": false, "IC1": false}, '
            '"decision": "NEEDS_REVIEW"}'
        )
        _mock_ollama_client(mocker, _mock_ollama_response(llm_json))

        service = OllamaLLMService()
        decision = await service.screen_paper(paper, criteria)

        assert decision.status is ScreeningStatus.NEEDS_REVIEW
        assert decision.confidence_score == 0.5


class TestOllamaLLMServiceErrorHandling:
    @pytest.mark.asyncio
    async def test_invalid_json_falls_back_to_needs_review(self, paper, criteria, mocker: MockerFixture):
        from src.infrastructure.services.ollama_service import OllamaLLMService

        bad_content = '{"status": "INCLUDED", broken json here}'
        _mock_ollama_client(mocker, _mock_ollama_response(bad_content))

        service = OllamaLLMService()
        decision = await service.screen_paper(paper, criteria)

        assert decision.status is ScreeningStatus.NEEDS_REVIEW
        assert decision.confidence_score == 0.0
        assert "parse" in decision.rationale.lower() or "invalid" in decision.rationale.lower() or "malformed" in decision.rationale.lower()

    @pytest.mark.asyncio
    async def test_missing_status_field_falls_back_to_needs_review(self, paper, criteria, mocker: MockerFixture):
        from src.infrastructure.services.ollama_service import OllamaLLMService

        missing_status = (
            '{"confidence_score": 0.9, "rationale": "test", "applied_criteria_codes": []}'
        )
        _mock_ollama_client(mocker, _mock_ollama_response(missing_status))

        service = OllamaLLMService()
        decision = await service.screen_paper(paper, criteria)

        assert decision.status is ScreeningStatus.NEEDS_REVIEW
        assert decision.confidence_score == 0.0

    @pytest.mark.asyncio
    async def test_invalid_status_value_falls_back_to_needs_review(self, paper, criteria, mocker: MockerFixture):
        from src.infrastructure.services.ollama_service import OllamaLLMService

        bad_status = (
            '{"status": "BANANA", "confidence_score": 0.5, '
            '"rationale": "x", "applied_criteria_codes": []}'
        )
        _mock_ollama_client(mocker, _mock_ollama_response(bad_status))

        service = OllamaLLMService()
        decision = await service.screen_paper(paper, criteria)

        assert decision.status is ScreeningStatus.NEEDS_REVIEW
        assert decision.confidence_score == 0.0

    @pytest.mark.asyncio
    async def test_criteria_evaluation_produces_applied_codes(self, paper, criteria, mocker: MockerFixture):
        from src.infrastructure.services.ollama_service import OllamaLLMService

        llm_json = (
            '{"reasoning": "EC2 applies, IC1 does not.", '
            '"criteria_evaluation": {"EC2": true, "IC1": false}, '
            '"decision": "EXCLUDED"}'
        )
        _mock_ollama_client(mocker, _mock_ollama_response(llm_json))

        service = OllamaLLMService()
        decision = await service.screen_paper(paper, criteria)

        assert decision.status is ScreeningStatus.EXCLUDED
        assert decision.confidence_score == 1.0
        assert "EC2" in decision.applied_criteria_codes
        assert "IC1" not in decision.applied_criteria_codes

    @pytest.mark.asyncio
    async def test_old_status_format_backward_compat(self, paper, criteria, mocker: MockerFixture):
        from src.infrastructure.services.ollama_service import OllamaLLMService

        old_format = (
            '{"status": "INCLUDED", '
            '"rationale": "Meets IC1.", "applied_criteria_codes": ["IC1"]}'
        )
        _mock_ollama_client(mocker, _mock_ollama_response(old_format))

        service = OllamaLLMService()
        decision = await service.screen_paper(paper, criteria)

        assert decision.status is ScreeningStatus.INCLUDED
        assert decision.confidence_score == 1.0
        assert decision.rationale == "Meets IC1."
        assert decision.applied_criteria_codes == ["IC1"]

    @pytest.mark.asyncio
    async def test_httpx_http_error_falls_back_to_needs_review(self, paper, criteria, mocker: MockerFixture):
        from src.infrastructure.services.ollama_service import OllamaLLMService
        import httpx

        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mocker.patch("httpx.AsyncClient", return_value=mock_client)

        service = OllamaLLMService()
        decision = await service.screen_paper(paper, criteria)

        assert decision.status is ScreeningStatus.NEEDS_REVIEW
        assert decision.confidence_score == 0.0

    @pytest.mark.asyncio
    async def test_httpx_timeout_falls_back_to_needs_review(self, paper, criteria, mocker: MockerFixture):
        from src.infrastructure.services.ollama_service import OllamaLLMService
        import httpx

        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Request timed out"))
        mocker.patch("httpx.AsyncClient", return_value=mock_client)

        service = OllamaLLMService()
        decision = await service.screen_paper(paper, criteria)

        assert decision.status is ScreeningStatus.NEEDS_REVIEW
        assert decision.confidence_score == 0.0

    @pytest.mark.asyncio
    async def test_empty_criteria_still_works(self, paper, mocker: MockerFixture):
        from src.infrastructure.services.ollama_service import OllamaLLMService

        llm_json = (
            '{"reasoning": "OK", '
            '"criteria_evaluation": {}, '
            '"decision": "INCLUDED"}'
        )
        _mock_ollama_client(mocker, _mock_ollama_response(llm_json))

        service = OllamaLLMService()
        decision = await service.screen_paper(paper, criteria=[])

        assert decision.status is ScreeningStatus.INCLUDED


# ── Prompt verification ──────────────────────────────────────────────────


class TestPromptContent:
    @pytest.mark.asyncio
    async def test_prompt_contains_paper_title(self, paper, criteria, mocker: MockerFixture):
        from src.infrastructure.services.ollama_service import OllamaLLMService

        llm_json = (
            '{"status": "INCLUDED", "confidence_score": 0.9, '
            '"rationale": "x", "applied_criteria_codes": []}'
        )
        mock_client = _mock_ollama_client(mocker, _mock_ollama_response(llm_json))

        service = OllamaLLMService()
        await service.screen_paper(paper, criteria)

        call_kwargs = mock_client.post.call_args
        sent_messages = call_kwargs[1]["json"]["messages"]
        combined = " ".join(m["content"] for m in sent_messages)

        assert paper.title in combined

    @pytest.mark.asyncio
    async def test_prompt_contains_criteria_codes(self, paper, criteria, mocker: MockerFixture):
        from src.infrastructure.services.ollama_service import OllamaLLMService

        llm_json = (
            '{"status": "INCLUDED", "confidence_score": 0.9, '
            '"rationale": "x", "applied_criteria_codes": []}'
        )
        mock_client = _mock_ollama_client(mocker, _mock_ollama_response(llm_json))

        service = OllamaLLMService()
        await service.screen_paper(paper, criteria)

        call_kwargs = mock_client.post.call_args
        sent_messages = call_kwargs[1]["json"]["messages"]
        combined = " ".join(m["content"] for m in sent_messages)

        assert "IC1" in combined
        assert "EC2" in combined
