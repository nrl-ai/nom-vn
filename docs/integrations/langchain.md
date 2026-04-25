# LangChain + nom-vn

LangChain is the most-deployed agent framework, with first-class
support for Retrievers, Tools, and Chat Models. nom-vn slots in at
two seams: as a `BaseRetriever` and as a `BaseChatModel`.

## Install

```bash
pip install nom-vn[chat,llm] langchain langchain-core
```

## Recipe 1 — nom.retrieve.Retriever as a LangChain BaseRetriever

LangChain's `BaseRetriever` only needs `_get_relevant_documents`:

```python
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from nom.rag import RAG

rag = RAG.from_documents(["hien_phap_2013.txt", "luat_doanh_nghiep.txt"])

class NomRetriever(BaseRetriever):
    """Wrap nom.rag.RAG's hybrid retrieval as a LangChain BaseRetriever."""

    k: int = 5

    def _get_relevant_documents(self, query: str, *, run_manager=None):
        # nom.rag.RAG bundles parsing → chunking → embedding → retrieval.
        # `.retrieve()` returns the ranked Hits without the LLM step.
        hits = rag.retrieve(query, top_k=self.k)
        return [
            Document(
                page_content=h.text,
                metadata={"score": h.score, "doc_idx": h.doc_idx, "chunk_idx": h.chunk_idx},
            )
            for h in hits
        ]

retriever = NomRetriever(k=5)
```

Plug into any LangChain chain:

```python
from langchain.chains import RetrievalQA
from langchain_openai import ChatOpenAI

qa = RetrievalQA.from_chain_type(
    llm=ChatOpenAI(model="gpt-4o-mini"),
    retriever=retriever,
    return_source_documents=True,
)
print(qa.invoke({"query": "Quyền cơ bản của công dân là gì?"}))
```

## Recipe 2 — nom.llm as a LangChain Chat Model

If you want LangChain to drive a Vietnamese-tuned model that doesn't
have a first-party LangChain package, wrap `nom.llm.OpenAI` with a
custom `base_url`:

```python
from typing import Any, List
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from nom.llm import OpenAI

class NomChatModel(BaseChatModel):
    """Wrap nom.llm.OpenAI as a LangChain BaseChatModel."""

    nom_llm: Any  # nom.llm.OpenAI / Anthropic / Ollama

    def _generate(self, messages: List[BaseMessage], **_) -> ChatResult:
        prompt = "\n".join(m.content for m in messages if isinstance(m.content, str))
        text = self.nom_llm.complete(prompt)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])

    @property
    def _llm_type(self) -> str:
        return self.nom_llm.name

llm = NomChatModel(nom_llm=OpenAI(
    model="deepseek-chat",
    base_url="https://api.deepseek.com/v1",
))
```

## Why this is a doc and not a package

`langchain-nom` would create a coupling problem: every LangChain
release (2-3 minor versions per quarter) could break us, and we'd
have to rev nom-vn in lockstep. The wrapper above is 25 lines —
keep it in your project, pin LangChain yourself.

## See also

- [Google ADK integration](adk.md)
- [Pydantic AI integration](pydantic_ai.md)
- [LangChain Custom Retrievers](https://python.langchain.com/docs/how_to/custom_retriever/)
