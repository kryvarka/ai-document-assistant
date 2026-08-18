import argparse
import asyncio
import json
import shutil
import sys
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
SAMPLE_DOCS = BACKEND_DIR.parent / "sample_docs"
GOLDEN_SET = Path(__file__).resolve().parent / "golden_set.json"

REFUSAL_MARKERS = ("couldn't find", "could not find", "not contain", "no relevant")


@dataclass
class CaseResult:
    case_id: str
    question: str
    retrieved_documents: list[str] = field(default_factory=list)
    expected_document: str | None = None
    rank: int | None = None
    answer: str = ""
    matched_keywords: list[str] = field(default_factory=list)
    missing_keywords: list[str] = field(default_factory=list)
    refused: bool = False
    expect_answer: bool = True

    @property
    def retrieval_ok(self) -> bool:
        if not self.expect_answer:
            return True
        return self.rank is not None

    @property
    def grounding_ok(self) -> bool:
        if not self.expect_answer:
            return self.refused
        return not self.missing_keywords


async def _index_sample_documents(vector_store, collection: str, user_id: str) -> int:
    from src.services.document_processor import chunk_text, extract_text

    total = 0
    for path in sorted(SAMPLE_DOCS.iterdir()):
        if path.suffix.lower() not in {".pdf", ".md", ".txt", ".docx"}:
            continue
        chunks = chunk_text(extract_text(path))
        document_id = str(uuid.uuid4())
        await vector_store.aadd_documents(
            collection_name=collection,
            chunks=chunks,
            metadatas=[
                {
                    "document_id": document_id,
                    "filename": path.name,
                    "chunk_index": i,
                    "file_type": path.suffix,
                    "user_id": user_id,
                }
                for i in range(len(chunks))
            ],
            ids=[f"{document_id}_chunk_{i}" for i in range(len(chunks))],
        )
        print(f"  indexed {path.name}: {len(chunks)} chunks")
        total += len(chunks)
    return total


async def _evaluate_case(
    pipeline, case: dict, collection: str, user_id: str, retrieval_only: bool = False
) -> CaseResult:
    from src.services import rag_pipeline as rag_module

    result = CaseResult(
        case_id=case["id"],
        question=case["question"],
        expected_document=case.get("expected_document"),
        expect_answer=case.get("expect_answer", True),
    )

    original_collection = rag_module.DOCUMENTS_COLLECTION
    rag_module.DOCUMENTS_COLLECTION = collection
    try:
        if retrieval_only:
            raw = await pipeline._vector_store.aquery(
                collection_name=collection,
                query_text=case["question"],
                where={"user_id": user_id},
            )
            _, sources = pipeline._build_context(raw)
            answer = "" if sources else "I couldn't find any sufficiently relevant information."
        else:
            answer, sources = await pipeline.query(question=case["question"], user_id=user_id)
    finally:
        rag_module.DOCUMENTS_COLLECTION = original_collection

    result.answer = answer
    result.retrieved_documents = [s.document_name for s in sources]
    result.refused = any(marker in answer.lower() for marker in REFUSAL_MARKERS)

    if result.expected_document and result.expected_document in result.retrieved_documents:
        result.rank = result.retrieved_documents.index(result.expected_document) + 1

    lowered = answer.lower()
    for keyword in case.get("expected_keywords", []):
        target = result.matched_keywords if keyword.lower() in lowered else result.missing_keywords
        target.append(keyword)

    return result


def _report(
    results: list[CaseResult], min_recall: float, min_grounding: float, retrieval_only: bool
) -> int:
    answerable = [r for r in results if r.expect_answer]
    out_of_scope = [r for r in results if not r.expect_answer]

    recall = sum(r.rank is not None for r in answerable) / max(len(answerable), 1)
    mrr = sum(1 / r.rank for r in answerable if r.rank) / max(len(answerable), 1)
    grounding = sum(r.grounding_ok for r in answerable) / max(len(answerable), 1)
    refusal = sum(r.refused for r in out_of_scope) / max(len(out_of_scope), 1)

    print("\n" + "=" * 78)
    print(f"{'case':<24} {'retrieval':<11} {'grounding':<11} rank  detail")
    print("-" * 78)
    for r in results:
        detail = ""
        if retrieval_only and r.expect_answer:
            detail = ", ".join(dict.fromkeys(r.retrieved_documents))
        elif r.expect_answer and r.missing_keywords:
            detail = f"missing: {', '.join(r.missing_keywords)}"
        elif not r.expect_answer:
            detail = "refused" if r.refused else "ANSWERED (should refuse)"
        print(
            f"{r.case_id:<24} "
            f"{'ok' if r.retrieval_ok else 'MISS':<11} "
            f"{'ok' if r.grounding_ok else 'WEAK':<11} "
            f"{r.rank or '-'!s:<5} {detail}"
        )

    print("-" * 78)
    print(f"Recall@k          : {recall:.2%}  (threshold {min_recall:.0%})")
    print(f"MRR               : {mrr:.3f}")
    if retrieval_only:
        print("Keyword grounding : skipped (--retrieval-only)")
    else:
        print(f"Keyword grounding : {grounding:.2%}  (threshold {min_grounding:.0%})")
    print(f"Refusal accuracy  : {refusal:.2%}  ({len(out_of_scope)} out-of-scope questions)")
    print("=" * 78)

    failures = []
    if recall < min_recall:
        failures.append(f"recall {recall:.2%} < {min_recall:.0%}")
    if not retrieval_only and grounding < min_grounding:
        failures.append(f"grounding {grounding:.2%} < {min_grounding:.0%}")
    if refusal < 1.0:
        failures.append(f"refusal accuracy {refusal:.2%} < 100%")

    if failures:
        print("FAILED: " + "; ".join(failures))
        return 1
    print("PASSED")
    return 0


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--retrieval-only",
        action="store_true",
        help="Score retrieval only. Cheap enough for CI: no generation calls.",
    )
    parser.add_argument("--min-recall", type=float, default=0.8)
    parser.add_argument("--min-grounding", type=float, default=0.7)
    parser.add_argument(
        "--pace-seconds",
        type=float,
        default=13.0,
        help="Delay between cases; the Gemini free tier allows ~5 requests/minute.",
    )
    args = parser.parse_args()

    scratch = Path(tempfile.mkdtemp(prefix="docqa-eval-"))
    import os

    os.environ["CHROMA_PERSIST_DIR"] = str(scratch)

    from src.config import settings
    from src.services.llm_service import llm_service
    from src.services.rag_pipeline import RAGPipeline
    from src.services.vector_store import vector_store

    if not settings.gemini_api_key:
        print("GEMINI_API_KEY is not set — the evaluation needs a live API key.")
        return 2

    vector_store.initialize()
    llm_service.initialize()
    pipeline = RAGPipeline(vector_store=vector_store, llm_service=llm_service)

    collection = f"eval_{uuid.uuid4().hex[:8]}"
    user_id = "eval-user"

    try:
        print(f"Indexing sample documents from {SAMPLE_DOCS} ...")
        chunk_total = await _index_sample_documents(vector_store, collection, user_id)
        print(f"  {chunk_total} chunks indexed into '{collection}'")

        cases = json.loads(GOLDEN_SET.read_text())["cases"]
        mode = "retrieval only" if args.retrieval_only else f"retrieval + {settings.llm_model}"
        print(f"\nRunning {len(cases)} golden cases ({mode}) ...")
        results = []
        for index, case in enumerate(cases):
            if index and not args.retrieval_only:
                await asyncio.sleep(args.pace_seconds)
            result = await _evaluate_case(
                pipeline, case, collection, user_id, retrieval_only=args.retrieval_only
            )
            print(f"  [{index + 1}/{len(cases)}] {result.case_id}")
            results.append(result)
        return _report(results, args.min_recall, args.min_grounding, args.retrieval_only)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
