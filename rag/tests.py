from unittest import TestCase

from rag.generator import CitationValidationError, citations_for_sources, validate_response
from rag.pipeline import answer_question
from rag.retriever import RetrievedChunk, Retriever


class FakeEmbeddingClient:
    def embed_query(self, question):
        return [1.0, 0.0]


class FakeVectorStore:
    def __init__(self):
        self.machine_filter = None

    def query(self, embedding, *, machine_id, n_results):
        self.machine_filter = machine_id
        return {
            "ids": [["hp-1", "ac-1"]],
            "documents": [["HP pressure is 4 bar.", "AC pressure is 2 bar."]],
            "metadatas": [[
                {"machine_id": "M-HP200", "manual_id": 1, "document_name": "hp.pdf", "revision": "1.0", "page_number": 1},
                {"machine_id": "M-AC90", "manual_id": 2, "document_name": "ac.pdf", "revision": "1.0", "page_number": 1},
            ]],
            "distances": [[0.2, 0.1]],
        }


class IsolationAndEvidenceTests(TestCase):
    def test_machine_filter_is_applied_and_other_machine_is_excluded(self):
        store = FakeVectorStore()
        chunks = Retriever(
            vector_store=store,
            embedding_client=FakeEmbeddingClient(),
            distance_cutoff=0.75,
        ).retrieve("pressure", "M-HP200")
        self.assertEqual(store.machine_filter, "M-HP200")
        self.assertEqual([chunk.machine_id for chunk in chunks], ["M-HP200"])

    def test_fabricated_source_id_is_rejected(self):
        chunk = RetrievedChunk("S1", "id", "M-HP200", 1, "hp.pdf", "1.0", 1, "text", 0.1)
        with self.assertRaises(CitationValidationError):
            validate_response(
                {"status": "ANSWERED", "answer": "Nope [S9]", "used_sources": ["S9"]},
                [chunk],
                machine_id="M-HP200",
            )

    def test_cutoff_short_circuits_without_calling_generator(self):
        class EmptyRetriever:
            def retrieve(self, question, machine_id):
                return []

        class ShouldNotRun:
            def generate(self, *args, **kwargs):
                raise AssertionError("LLM must not be called")

        result = answer_question(
            "unknown", "M-HP200", retriever=EmptyRetriever(), generator=ShouldNotRun()
        )
        self.assertEqual(result["status"], "INSUFFICIENT")
        self.assertEqual(result["sources"], [])

    def test_duplicate_chunks_on_same_page_collapse_to_one_citation(self):
        chunks = [
            RetrievedChunk("S1", "chunk-1", "M-HP200", 1, "hp.pdf", "1.0", 2, "first", 0.1),
            RetrievedChunk("S2", "chunk-2", "M-HP200", 1, "hp.pdf", "1.0", 2, "duplicate page", 0.2),
        ]
        result = validate_response(
            {"status": "ANSWERED", "answer": "The value is [S2].", "used_sources": ["S1", "S2"]},
            chunks,
            machine_id="M-HP200",
        )
        self.assertEqual(result["used_sources"], ["S1"])
        self.assertIn("[S1]", result["answer"])
        self.assertEqual(len(citations_for_sources(result["used_sources"], chunks)), 1)
