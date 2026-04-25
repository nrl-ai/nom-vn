# Google ADK + nom-vn

[Google ADK](https://adk.dev) is a multi-provider agentic framework
(Gemini direct + Claude direct + LiteLLM connector for OpenAI, etc.).
nom-vn drops in as the **Vietnamese-RAG tool** behind any ADK agent.

## Install

```bash
pip install nom-vn[chat] google-adk
```

## Recipe 1 — nom.rag as an ADK Tool

The cleanest integration. Build the RAG corpus once, expose `.ask()`
as a tool callable, hand it to any `LlmAgent`:

```python
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from nom.rag import RAG

rag = RAG.from_documents(
    ["benchmarks/data/legal_vi/hien_phap_2013.txt"],
    # Use whatever LLM you want for the RAG synthesis step.
    # ADK's agent uses its own model below; this one only summarizes
    # the retrieved chunks into the answer.
)

def search_legal_corpus(question: str) -> str:
    """Search the Vietnamese legal corpus and return a cited answer."""
    answer = rag.ask(question)
    citations = "\n".join(
        f"[{i+1}] {c.text[:120]}…" for i, c in enumerate(answer.citations)
    )
    return f"{answer.text}\n\nCitations:\n{citations}"

agent = LlmAgent(
    name="vn_legal_advisor",
    model="gemini-2.5-flash",  # or "claude-sonnet-4-6", or LiteLlm(...)
    tools=[FunctionTool(search_legal_corpus)],
    instruction="Bạn là cố vấn pháp luật. Dùng search_legal_corpus để tra cứu.",
)
```

That's the whole integration.

## Recipe 2 — nom.llm as the agent's model

If you want ADK to use a Vietnamese-tuned model that ADK doesn't
ship a connector for, route through `nom.llm.OpenAI` pointed at any
OpenAI-compatible endpoint. Wrap it in a thin ADK model adapter:

```python
from google.adk.models import BaseLlm, LlmRequest, LlmResponse
from nom.llm import OpenAI

class NomLlm(BaseLlm):
    """Wrap nom.llm.OpenAI as an ADK model. Works with any OpenAI-
    compatible endpoint by setting base_url= in the OpenAI() ctor."""

    def __init__(self, llm: OpenAI):
        super().__init__(model=llm.model)
        self._llm = llm

    async def generate_content_async(self, req: LlmRequest, **_):
        prompt = "\n".join(p.text for p in req.contents[-1].parts if p.text)
        text = self._llm.complete(prompt, max_tokens=req.config.max_output_tokens or 2048)
        yield LlmResponse(content={"role": "model", "parts": [{"text": text}]})

agent = LlmAgent(
    name="vn_agent",
    model=NomLlm(OpenAI(
        model="deepseek-chat",
        base_url="https://api.deepseek.com/v1",
    )),
    tools=[...],
)
```

This is intentionally minimal — it covers `complete()` only. For
streaming or tool-use you'd extend the wrapper. Most VN use cases
don't need either at the model level (RAG handles tool-use externally).

## Why this lives in docs and not in nom-vn

ADK's `BaseLlm`, `FunctionTool`, `LlmAgent` are all unstable surfaces
this early in the framework's life — pinning nom-vn against them
would create a maintenance burden every time ADK refactors. The
wrapper is 30 lines. Keep it in your project.

## See also

- [LangChain integration](langchain.md)
- [Pydantic AI integration](pydantic_ai.md)
- [ADK official docs — Tools](https://adk.dev/tools/)
