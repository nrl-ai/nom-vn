# Pydantic AI + nom-vn

[Pydantic AI](https://ai.pydantic.dev) is the type-safe agent
framework from the Pydantic team — minimal API surface, strong
typing, and tool registration via decorators.

This is the cleanest integration of the three: nom-vn's `RAG.ask()`
returns a Python value; Pydantic AI tools take Python callables.
Almost no glue.

## Install

```bash
pip install nom-vn[chat] pydantic-ai
```

## Recipe — nom.rag as a Pydantic AI tool

```python
from pydantic_ai import Agent, RunContext
from nom.rag import RAG

rag = RAG.from_documents(["benchmarks/data/wiki_vi/articles.jsonl"])

agent = Agent(
    "openai:gpt-4o-mini",  # or "anthropic:claude-haiku-4-5", or local Ollama via openai-compat
    system_prompt=(
        "Bạn là trợ lý nghiên cứu. Dùng search_vn để tìm thông tin tiếng Việt "
        "trước khi trả lời. Luôn trích dẫn nguồn."
    ),
)

@agent.tool
def search_vn(_: RunContext, question: str) -> str:
    """Search the Vietnamese knowledge base. Returns answer with citations."""
    answer = rag.ask(question)
    citations = "\n".join(
        f"  [{i+1}] {c.text[:140]}…" for i, c in enumerate(answer.citations)
    )
    return f"{answer.text}\n\n--- Sources ---\n{citations}"

result = agent.run_sync("Đà Nẵng có những danh lam thắng cảnh nào?")
print(result.output)
```

## Recipe — typed structured output

Pydantic AI's killer feature is typed agent results. Combine with
nom-vn's structured-extraction `schema=` parameter for end-to-end
type safety:

```python
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from nom.llm import OpenAI

class LegalCitation(BaseModel):
    article_number: str = Field(description="Số điều luật, e.g., 'Điều 51'")
    text: str = Field(description="Nội dung điều luật")
    relevance: float = Field(ge=0, le=1, description="Mức độ liên quan đến câu hỏi")

agent = Agent(
    "openai:gpt-4o-mini",
    output_type=list[LegalCitation],
    system_prompt="Trích xuất các điều luật liên quan từ văn bản.",
)
```

The `nom.rag.RAG` for retrieval + Pydantic AI for typed orchestration
is a strong combo for VN legal/structured tasks.

## Why this is a doc and not a package

Pydantic AI's API is the most stable of the three (the team
explicitly aims for the LangChain v0.3 retrospective: don't break
users). But coupling nom-vn to it would still mean shipping a
release every time pydantic-ai bumps. The 12-line wrapper above
is small enough to live in user code.

## See also

- [Google ADK integration](adk.md)
- [LangChain integration](langchain.md)
- [Pydantic AI Tools](https://ai.pydantic.dev/tools/)
