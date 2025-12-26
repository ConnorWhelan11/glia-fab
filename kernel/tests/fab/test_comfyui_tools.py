"""
Tests for ComfyUI MCP tools and input validation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from cyntra.mcp.comfyui_tools import (
    ValidationError,
    validate_workflow_input,
    validate_workflow_inputs,
)
from cyntra.fab.workflow_registry import Workflow, WorkflowInput, WorkflowOutput, WorkflowPerformance


def create_mock_input(
    name: str = "test",
    type_: str = "string",
    required: bool = False,
    min_: float | None = None,
    max_: float | None = None,
    default: Any = None,
) -> WorkflowInput:
    """Create a mock WorkflowInput for testing."""
    return WorkflowInput(
        name=name,
        type=type_,
        required=required,
        description=f"Test {name}",
        node="1",
        node_field="text",
        default=default,
        min=min_,
        max=max_,
    )


def create_mock_workflow(inputs: list[WorkflowInput] | None = None) -> Workflow:
    """Create a mock Workflow for testing."""
    return Workflow(
        id="test_workflow",
        file="test.json",
        name="Test Workflow",
        description="A test workflow",
        when_to_use="For testing",
        tags=["test"],
        category="test",
        inputs=inputs or [],
        outputs=[WorkflowOutput(name="output", node="2", description="Output")],
        performance=WorkflowPerformance(),
        required_models=[],
        required_custom_nodes=[],
    )


class TestValidateWorkflowInput:
    """Tests for validate_workflow_input function."""

    # String validation
    def test_string_valid(self) -> None:
        inp = create_mock_input(type_="string")
        assert validate_workflow_input(inp, "hello") == "hello"

    def test_string_converts_int(self) -> None:
        inp = create_mock_input(type_="string")
        assert validate_workflow_input(inp, 123) == "123"

    def test_string_converts_float(self) -> None:
        inp = create_mock_input(type_="string")
        assert validate_workflow_input(inp, 1.5) == "1.5"

    # Int validation
    def test_int_valid(self) -> None:
        inp = create_mock_input(type_="int")
        assert validate_workflow_input(inp, 42) == 42

    def test_int_converts_string(self) -> None:
        inp = create_mock_input(type_="int")
        assert validate_workflow_input(inp, "42") == 42

    def test_int_invalid_string(self) -> None:
        inp = create_mock_input(name="steps", type_="int")
        with pytest.raises(ValidationError, match="Cannot convert 'steps' to int"):
            validate_workflow_input(inp, "not-a-number")

    def test_int_respects_min(self) -> None:
        inp = create_mock_input(name="steps", type_="int", min_=1)
        with pytest.raises(ValidationError, match="below minimum"):
            validate_workflow_input(inp, 0)

    def test_int_respects_max(self) -> None:
        inp = create_mock_input(name="steps", type_="int", max_=100)
        with pytest.raises(ValidationError, match="exceeds maximum"):
            validate_workflow_input(inp, 101)

    def test_int_within_range(self) -> None:
        inp = create_mock_input(type_="int", min_=1, max_=100)
        assert validate_workflow_input(inp, 50) == 50

    # Float validation
    def test_float_valid(self) -> None:
        inp = create_mock_input(type_="float")
        assert validate_workflow_input(inp, 0.5) == 0.5

    def test_float_converts_int(self) -> None:
        inp = create_mock_input(type_="float")
        assert validate_workflow_input(inp, 5) == 5.0

    def test_float_converts_string(self) -> None:
        inp = create_mock_input(type_="float")
        assert validate_workflow_input(inp, "0.75") == 0.75

    def test_float_invalid_string(self) -> None:
        inp = create_mock_input(name="cfg_scale", type_="float")
        with pytest.raises(ValidationError, match="Cannot convert 'cfg_scale' to float"):
            validate_workflow_input(inp, "invalid")

    def test_float_respects_min(self) -> None:
        inp = create_mock_input(name="cfg", type_="float", min_=1.0)
        with pytest.raises(ValidationError, match="below minimum"):
            validate_workflow_input(inp, 0.5)

    def test_float_respects_max(self) -> None:
        inp = create_mock_input(name="cfg", type_="float", max_=20.0)
        with pytest.raises(ValidationError, match="exceeds maximum"):
            validate_workflow_input(inp, 25.0)

    # Bool validation
    def test_bool_true(self) -> None:
        inp = create_mock_input(type_="bool")
        assert validate_workflow_input(inp, True) is True

    def test_bool_false(self) -> None:
        inp = create_mock_input(type_="bool")
        assert validate_workflow_input(inp, False) is False

    def test_bool_from_string_true(self) -> None:
        inp = create_mock_input(type_="bool")
        assert validate_workflow_input(inp, "true") is True
        assert validate_workflow_input(inp, "1") is True
        assert validate_workflow_input(inp, "yes") is True
        assert validate_workflow_input(inp, "on") is True

    def test_bool_from_string_false(self) -> None:
        inp = create_mock_input(type_="bool")
        assert validate_workflow_input(inp, "false") is False
        assert validate_workflow_input(inp, "0") is False
        assert validate_workflow_input(inp, "no") is False

    # Required validation
    def test_required_missing_raises(self) -> None:
        inp = create_mock_input(name="prompt", required=True)
        with pytest.raises(ValidationError, match="Required parameter 'prompt' is missing"):
            validate_workflow_input(inp, None)

    def test_optional_missing_returns_default(self) -> None:
        inp = create_mock_input(required=False, default="default_value")
        assert validate_workflow_input(inp, None) == "default_value"

    def test_optional_missing_no_default(self) -> None:
        inp = create_mock_input(required=False)
        assert validate_workflow_input(inp, None) is None

    # Image validation
    def test_image_not_string_raises(self) -> None:
        inp = create_mock_input(name="image", type_="image")
        with pytest.raises(ValidationError, match="Image path 'image' must be a string"):
            validate_workflow_input(inp, 123)

    def test_image_file_not_found_raises(self) -> None:
        inp = create_mock_input(name="image", type_="image")
        with pytest.raises(ValidationError, match="Image file not found"):
            validate_workflow_input(inp, "/nonexistent/path/image.png")

    def test_image_valid_path(self, tmp_path: Path) -> None:
        # Create a temporary image file
        img_file = tmp_path / "test.png"
        img_file.touch()

        inp = create_mock_input(name="image", type_="image")
        result = validate_workflow_input(inp, str(img_file))
        assert result == str(img_file)


class TestValidateWorkflowInputs:
    """Tests for validate_workflow_inputs function."""

    def test_all_valid(self) -> None:
        inputs = [
            create_mock_input(name="prompt", type_="string", required=True),
            create_mock_input(name="steps", type_="int", min_=1, max_=100),
            create_mock_input(name="cfg", type_="float", min_=1.0, max_=20.0),
        ]
        workflow = create_mock_workflow(inputs)

        validated, errors = validate_workflow_inputs(
            workflow,
            {"prompt": "test prompt", "steps": 20, "cfg": 7.5},
        )

        assert len(errors) == 0
        assert validated["prompt"] == "test prompt"
        assert validated["steps"] == 20
        assert validated["cfg"] == 7.5

    def test_collects_all_errors(self) -> None:
        inputs = [
            create_mock_input(name="prompt", type_="string", required=True),
            create_mock_input(name="steps", type_="int", min_=1),
            create_mock_input(name="cfg", type_="float", max_=20.0),
        ]
        workflow = create_mock_workflow(inputs)

        validated, errors = validate_workflow_inputs(
            workflow,
            {"steps": 0, "cfg": 25.0},  # Missing prompt, steps below min, cfg above max
        )

        assert len(errors) == 3
        assert any("prompt" in e for e in errors)
        assert any("steps" in e for e in errors)
        assert any("cfg" in e for e in errors)

    def test_skips_optional_missing(self) -> None:
        inputs = [
            create_mock_input(name="prompt", type_="string", required=True),
            create_mock_input(name="seed", type_="int", required=False),
        ]
        workflow = create_mock_workflow(inputs)

        validated, errors = validate_workflow_inputs(
            workflow,
            {"prompt": "test"},  # seed not provided
        )

        assert len(errors) == 0
        assert "seed" not in validated
        assert validated["prompt"] == "test"

    def test_uses_defaults(self) -> None:
        inputs = [
            create_mock_input(name="steps", type_="int", required=False, default=20),
        ]
        workflow = create_mock_workflow(inputs)

        validated, errors = validate_workflow_inputs(workflow, {})

        assert len(errors) == 0
        assert validated["steps"] == 20

    def test_empty_inputs(self) -> None:
        workflow = create_mock_workflow(inputs=[])
        validated, errors = validate_workflow_inputs(workflow, {"extra": "ignored"})

        assert len(errors) == 0
        assert len(validated) == 0
