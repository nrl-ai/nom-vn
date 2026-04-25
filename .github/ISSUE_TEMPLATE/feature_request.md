---
name: Feature request
about: Suggest a new module, function, or capability
labels: enhancement
---

**Problem this would solve**

What pain do you (or your users) currently hit when building VN AI applications?

**Proposed API**

If you have a concrete API shape in mind, sketch it:

```python
from nom.something import new_thing

result = new_thing(input, option=value)
```

**Alternatives considered**

What other options exist? (existing libraries, custom code, ignoring it.)

**Out of scope?**

Nôm is a *toolkit*, not a *model*. We integrate, package, and tune — we don't ship LLM weights. If your request needs a new model, it probably belongs upstream.
