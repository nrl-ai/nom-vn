"""Query-side retrieval improvements — HyDE + multi-query expansion.

These transform the *question* before it hits the retriever, trading
one extra LLM call upfront for better retrieval recall on questions
whose phrasing differs from the corpus phrasing.

Both functions are pure helpers. They take an :class:`nom.llm.LLM`
and a question, and return either a hypothetical answer (HyDE) or a
list of rewrites (multi-query). The :class:`nom.rag.RAG` class wires
them in via the ``query_strategy=`` kwarg on :meth:`RAG.ask`, but you
can also call them directly when wiring nom-vn into another framework.

Both are bench-gated: we ship the primitives without claiming a
specific quality improvement until we have a real VN benchmark
corpus to measure against (CLAUDE.md principle 12). Empirically these
techniques help on Q&A-shaped queries and hurt on keyword-shaped
queries — measure on your data before flipping the default.

References:
- HyDE: Gao et al., "Precise Zero-Shot Dense Retrieval without
  Relevance Labels", https://arxiv.org/abs/2212.10496
- Multi-query: a folklore technique formalized in LangChain's
  MultiQueryRetriever; the LLM-rewrite-then-retrieve-and-merge
  pattern predates that implementation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nom.llm import LLM

__all__ = ["hyde", "multi_query"]


_HYDE_PROMPT_VI = (
    "Hãy viết một đoạn văn ngắn (3-5 câu) trả lời câu hỏi dưới đây như "
    "thể bạn đang trích từ một tài liệu. Không cần chính xác — chỉ cần "
    "viết theo phong cách và từ vựng của một câu trả lời thực tế.\n\n"
    "Câu hỏi: {question}\n\nĐoạn văn:"
)


def hyde(question: str, llm: LLM, *, max_tokens: int = 256) -> str:
    """Generate a Hypothetical Document Embedding query.

    Asks the LLM to write a short passage that *would answer* the
    question, in the register and vocabulary of a real document.
    The returned text is meant to be embedded and used in place of
    the original question for dense retrieval.

    Why it helps: questions and answers use different vocabulary
    (the lexical-gap problem). "Thủ đô của Việt Nam là gì?" and
    "Hà Nội là thủ đô của nước Việt Nam." share little surface
    overlap; their embeddings should be close, but a question-only
    embedding is not always close to answer-style text in the
    corpus.

    Args:
        question: the user's question, in Vietnamese.
        llm: any :class:`nom.llm.LLM` adapter — Ollama works fine for
            this generation step (it's a small one-shot call).
        max_tokens: cap on the hypothetical-answer length. Default 256.

    Returns:
        The LLM's hypothetical-answer paragraph as a plain string.

    Example:
        >>> from nom.llm import Ollama
        >>> from nom.rag.queries import hyde
        >>> q = "Quyền cơ bản của công dân là gì?"
        >>> hypothetical = hyde(q, Ollama(model="qwen3:1.7b"))
        >>> # `hypothetical` now reads like an excerpt from a
        >>> # legal document — embed it and run dense retrieval.
    """
    if not question.strip():
        raise ValueError("hyde() requires a non-empty question")
    prompt = _HYDE_PROMPT_VI.format(question=question.strip())
    return llm.complete(prompt, max_tokens=max_tokens).strip()


_MULTI_QUERY_PROMPT_VI = (
    "Bạn nhận được một câu hỏi tiếng Việt. Hãy viết lại câu hỏi đó "
    "thành {n} cách diễn đạt khác nhau, mỗi cách trên một dòng. "
    "Không đánh số, không thêm dấu gạch đầu dòng, không thêm bình "
    "luận — chỉ {n} dòng, mỗi dòng là một cách diễn đạt độc lập.\n\n"
    "Câu hỏi gốc: {question}\n\n{n} cách diễn đạt:"
)


def multi_query(question: str, llm: LLM, *, n: int = 3, max_tokens: int = 256) -> list[str]:
    """Generate ``n`` paraphrases of the question for retrieval merging.

    The original question is always included in the returned list,
    so a caller doing ``for q in multi_query(...): retrieve(q)``
    covers the original phrasing plus ``n`` rewrites.

    Why it helps: a question's first phrasing might miss the
    corpus's wording even when the answer is there. Retrieving
    over multiple phrasings and merging via RRF smooths out that
    brittleness.

    Args:
        question: the user's question.
        llm: any :class:`nom.llm.LLM` adapter.
        n: number of *rewrites* (the original is added on top).
            Default 3 → 4 total queries. >5 starts hitting
            diminishing returns; >10 wastes tokens.
        max_tokens: cap on the LLM rewrite output. Default 256.

    Returns:
        A list of length ``n + 1`` where index 0 is the original
        question and indices 1..n are LLM-generated rewrites.

    Example:
        >>> from nom.llm import Ollama
        >>> from nom.rag.queries import multi_query
        >>> queries = multi_query("Thủ đô là gì?", Ollama(), n=2)
        >>> # ["Thủ đô là gì?", "Đâu là thủ đô...?", "Thành phố nào là...?"]
    """
    if not question.strip():
        raise ValueError("multi_query() requires a non-empty question")
    if n < 1:
        raise ValueError(f"multi_query(n=) must be >= 1, got {n}")
    prompt = _MULTI_QUERY_PROMPT_VI.format(question=question.strip(), n=n)
    raw = llm.complete(prompt, max_tokens=max_tokens)
    rewrites = [line.strip() for line in raw.strip().splitlines() if line.strip()]
    # Take only n rewrites (LLMs sometimes emit more), prepend the original.
    return [question.strip(), *rewrites[:n]]
