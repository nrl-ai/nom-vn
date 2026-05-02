"""Built-in tools for ``nom.agents``.

Tools are plain Python objects implementing the
:class:`nom.agents.Tool` Protocol — anything callable with a JSON
schema works. The built-ins shipped here cover the common cases:

- :class:`RAGTool` — answer questions from indexed documents
- :class:`HTTPGetTool` — fetch a URL
- :class:`PythonEvalTool` — sandboxed expression evaluator (read-only)
- :class:`FileReadTool` — read a file inside an allowed root
"""

from __future__ import annotations
