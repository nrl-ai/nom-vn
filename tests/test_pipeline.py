"""Smoke tests for the v0.1 pipeline shape.

These tests lock the public interface of ``nom.doc.pipeline`` and the stage
classes so v0.1 can land real implementations without breaking callers.
"""

from __future__ import annotations

import pytest

from nom.doc import (
    OCR,
    Context,
    Extract,
    Load,
    Normalize,
    Parse,
    Pipeline,
    Validate,
    default_pipeline,
)


class TestContext:
    def test_minimal_construction(self) -> None:
        ctx = Context(source="hello.pdf")
        assert ctx.source == "hello.pdf"
        assert ctx.fmt is None
        assert ctx.pages_text == []
        assert ctx.text == ""
        assert ctx.output == {}

    def test_can_be_mutated_in_place(self) -> None:
        ctx = Context(source="x.pdf")
        ctx.fmt = "pdf"
        ctx.pages_text.append("page 1")
        ctx.output["key"] = "value"
        assert ctx.fmt == "pdf"
        assert ctx.pages_text == ["page 1"]
        assert ctx.output == {"key": "value"}


class TestStageClasses:
    def test_each_stage_has_name(self) -> None:
        assert Load().name == "Load"
        assert Parse().name == "Parse"
        assert OCR().name == "OCR"
        assert Normalize().name == "Normalize"

        # Extract requires an llm — pass None just to assert the name.
        assert Extract(llm=None).name == "Extract"
        assert Validate().name == "Validate"

    def test_stages_raise_not_implemented_in_v0(self) -> None:
        # All default stages are placeholders in v0.0.1.
        for stage in [Load(), Parse(), OCR(), Normalize(), Extract(llm=None), Validate()]:
            with pytest.raises(NotImplementedError, match=r"v0\.1"):
                stage.run(Context(source="x.pdf"))


class TestPipeline:
    def test_construct_with_stages(self) -> None:
        pipe = Pipeline([Load(), Parse()])
        assert len(pipe.stages) == 2
        assert "Load" in repr(pipe)
        assert "Parse" in repr(pipe)
        assert "→" in repr(pipe)

    def test_empty_pipeline_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"at least one"):
            Pipeline([])

    def test_default_pipeline_has_six_stages(self) -> None:
        pipe = default_pipeline()
        names = [s.name for s in pipe.stages]
        assert names == ["Load", "Parse", "OCR", "Normalize", "Extract", "Validate"]

    def test_running_default_pipeline_raises_in_v0(self) -> None:
        pipe = default_pipeline()
        with pytest.raises(NotImplementedError, match=r"v0\.1"):
            pipe.run("hello.pdf", schema={"key": str})
