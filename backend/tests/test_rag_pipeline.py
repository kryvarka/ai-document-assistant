from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.rag_pipeline import RAGPipeline


@pytest.fixture
def mock_vector_store():
    store = MagicMock()
    mock_data = {
        "documents": [["Chunk 1 content about AI.", "Chunk 2 content about ML."]],
        "metadatas": [
            [
                {"filename": "doc1.pdf", "chunk_index": 0, "document_id": "abc"},
                {"filename": "doc1.pdf", "chunk_index": 1, "document_id": "abc"},
            ]
        ],
        "distances": [[0.2, 0.4]],
    }
    store.query.return_value = mock_data
    store.aquery = AsyncMock(side_effect=lambda *args, **kwargs: store.query(*args, **kwargs))
    return store


@pytest.fixture
def mock_llm_service():
    service = MagicMock()
    service.build_prompt.return_value = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Question about AI"},
    ]
    service.generate = AsyncMock(return_value="AI is a field of computer science.")
    return service


@pytest.fixture
def pipeline(mock_vector_store, mock_llm_service):
    return RAGPipeline(vector_store=mock_vector_store, llm_service=mock_llm_service)


class TestRAGPipeline:
    async def test_query_returns_answer_and_sources(self, pipeline):
        answer, sources = await pipeline.query("What is AI?")
        assert answer == "AI is a field of computer science."
        assert len(sources) == 2
        assert sources[0].document_name == "doc1.pdf"

    async def test_query_with_no_results(self, pipeline, mock_vector_store):
        mock_vector_store.query.return_value = {
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }
        answer, sources = await pipeline.query("Unknown topic")
        assert "couldn't find" in answer.lower()
        assert sources == []

    async def test_relevance_scores_calculated(self, pipeline):
        _, sources = await pipeline.query("What is AI?")
        assert sources[0].relevance_score == 0.8
        assert sources[1].relevance_score == 0.6

    async def test_source_content_truncated(self, pipeline, mock_vector_store):
        long_content = "A" * 500
        mock_vector_store.query.return_value = {
            "documents": [[long_content]],
            "metadatas": [[{"filename": "doc.pdf", "chunk_index": 0, "document_id": "x"}]],
            "distances": [[0.1]],
        }
        _, sources = await pipeline.query("Test")
        assert sources[0].content.endswith("...")
        assert len(sources[0].content) == 303

    async def test_document_id_filter_passed(self, pipeline, mock_vector_store):
        await pipeline.query("Test", document_ids=["doc1", "doc2"])
        call_kwargs = mock_vector_store.query.call_args[1]
        assert call_kwargs["where"] == {"document_id": {"$in": ["doc1", "doc2"]}}
