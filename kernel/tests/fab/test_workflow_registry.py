"""
Tests for ComfyUI workflow registry.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from cyntra.fab.workflow_registry import (
    Workflow,
    WorkflowInput,
    WorkflowOutput,
    WorkflowPerformance,
    WorkflowRegistry,
)


class TestWorkflowInput:
    """Tests for WorkflowInput dataclass."""

    def test_to_json_schema_string(self) -> None:
        inp = WorkflowInput(
            name="prompt",
            type="string",
            required=True,
            description="The prompt",
            node="1",
            examples=["example1", "example2"],
        )
        schema = inp.to_json_schema()

        assert schema["type"] == "string"
        assert schema["description"] == "The prompt"
        assert schema["examples"] == ["example1", "example2"]

    def test_to_json_schema_int_with_range(self) -> None:
        inp = WorkflowInput(
            name="steps",
            type="int",
            required=True,
            description="Inference steps",
            node="1",
            min=1,
            max=100,
        )
        schema = inp.to_json_schema()

        assert schema["type"] == "integer"
        assert schema["minimum"] == 1
        assert schema["maximum"] == 100

    def test_to_json_schema_float_with_range(self) -> None:
        inp = WorkflowInput(
            name="cfg",
            type="float",
            required=True,
            description="CFG scale",
            node="1",
            min=1.0,
            max=20.0,
            default=7.5,
        )
        schema = inp.to_json_schema()

        assert schema["type"] == "number"
        assert schema["minimum"] == 1.0
        assert schema["maximum"] == 20.0
        assert schema["default"] == 7.5

    def test_to_json_schema_bool(self) -> None:
        inp = WorkflowInput(
            name="enable",
            type="bool",
            required=False,
            description="Enable feature",
            node="1",
        )
        schema = inp.to_json_schema()

        assert schema["type"] == "boolean"

    def test_to_json_schema_image(self) -> None:
        inp = WorkflowInput(
            name="image",
            type="image",
            required=True,
            description="Input image",
            node="1",
        )
        schema = inp.to_json_schema()

        assert schema["type"] == "string"
        assert "(file path)" in schema["description"]


class TestWorkflow:
    """Tests for Workflow dataclass."""

    def test_to_json_schema(self) -> None:
        workflow = Workflow(
            id="test",
            file="test.json",
            name="Test",
            description="Test workflow",
            when_to_use="Testing",
            tags=["test"],
            category="test",
            inputs=[
                WorkflowInput(
                    name="prompt", type="string", required=True, description="Prompt", node="1"
                ),
                WorkflowInput(
                    name="steps", type="int", required=False, description="Steps", node="1"
                ),
            ],
            outputs=[],
            performance=WorkflowPerformance(),
            required_models=[],
            required_custom_nodes=[],
        )

        schema = workflow.to_json_schema()

        assert schema["type"] == "object"
        assert "prompt" in schema["properties"]
        assert "steps" in schema["properties"]
        assert "prompt" in schema["required"]
        assert "steps" not in schema["required"]

    def test_to_tool_description(self) -> None:
        workflow = Workflow(
            id="test",
            file="test.json",
            name="Test",
            description="Generate images from text",
            when_to_use="When you need to create images",
            tags=["test"],
            category="generation",
            inputs=[],
            outputs=[],
            performance=WorkflowPerformance(rtx_4090="10 seconds", vram_required="8GB"),
            required_models=[],
            required_custom_nodes=[],
        )

        desc = workflow.to_tool_description()

        assert "Generate images from text" in desc
        assert "When you need to create images" in desc
        assert "10 seconds" in desc
        assert "8GB" in desc

    def test_has_image_inputs(self) -> None:
        workflow_with_image = Workflow(
            id="test",
            file="test.json",
            name="Test",
            description="Test",
            when_to_use="Test",
            tags=[],
            category="test",
            inputs=[
                WorkflowInput(name="image", type="image", required=True, description="", node="1")
            ],
            outputs=[],
            performance=WorkflowPerformance(),
            required_models=[],
            required_custom_nodes=[],
        )

        workflow_without_image = Workflow(
            id="test2",
            file="test.json",
            name="Test",
            description="Test",
            when_to_use="Test",
            tags=[],
            category="test",
            inputs=[
                WorkflowInput(name="prompt", type="string", required=True, description="", node="1")
            ],
            outputs=[],
            performance=WorkflowPerformance(),
            required_models=[],
            required_custom_nodes=[],
        )

        assert workflow_with_image.has_image_inputs() is True
        assert workflow_without_image.has_image_inputs() is False


class TestWorkflowRegistry:
    """Tests for WorkflowRegistry class."""

    def test_load_valid_registry(self, tmp_path: Path) -> None:
        registry_data = {
            "version": 1,
            "workflows": [
                {
                    "id": "txt2img",
                    "file": "txt2img.json",
                    "name": "Text to Image",
                    "description": "Generate images from text",
                    "when_to_use": "When you need images",
                    "tags": ["generation"],
                    "category": "generation",
                    "inputs": [
                        {
                            "name": "prompt",
                            "type": "string",
                            "required": True,
                            "description": "Text prompt",
                            "node": "1",
                        }
                    ],
                    "outputs": [{"name": "image", "node": "9", "description": "Output image"}],
                }
            ],
        }

        registry_file = tmp_path / "registry.yaml"
        registry_file.write_text(yaml.dump(registry_data))

        registry = WorkflowRegistry.load(registry_file)

        assert registry.version == 1
        assert len(registry.workflows) == 1
        assert registry.workflows[0].id == "txt2img"
        assert registry.has_errors is False

    def test_load_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            WorkflowRegistry.load(tmp_path / "nonexistent.yaml")

    def test_load_invalid_yaml_structure(self, tmp_path: Path) -> None:
        registry_file = tmp_path / "registry.yaml"
        registry_file.write_text("just a string, not a dict")

        with pytest.raises(ValueError, match="must be a YAML object"):
            WorkflowRegistry.load(registry_file)

    def test_load_workflow_missing_required_field(self, tmp_path: Path) -> None:
        registry_data = {
            "version": 1,
            "workflows": [
                {
                    # Missing 'id' field
                    "file": "test.json",
                    "name": "Test",
                }
            ],
        }

        registry_file = tmp_path / "registry.yaml"
        registry_file.write_text(yaml.dump(registry_data))

        registry = WorkflowRegistry.load(registry_file)

        # Should load but with errors
        assert len(registry.workflows) == 0
        assert registry.has_errors is True
        assert len(registry.parse_errors) == 1
        assert registry.parse_errors[0]["error_type"] == "missing_field"

    def test_load_multiple_workflows_partial_failure(self, tmp_path: Path) -> None:
        registry_data = {
            "version": 1,
            "workflows": [
                {
                    "id": "valid",
                    "file": "valid.json",
                    "name": "Valid Workflow",
                    "description": "Works",
                    "when_to_use": "Testing",
                    "tags": [],
                    "category": "test",
                },
                {
                    # Missing required 'id' field
                    "file": "invalid.json",
                    "name": "Invalid Workflow",
                },
            ],
        }

        registry_file = tmp_path / "registry.yaml"
        registry_file.write_text(yaml.dump(registry_data))

        registry = WorkflowRegistry.load(registry_file)

        # Valid workflow should be loaded
        assert len(registry.workflows) == 1
        assert registry.workflows[0].id == "valid"

        # But errors should be tracked
        assert registry.has_errors is True
        assert len(registry.parse_errors) == 1

    def test_get_workflow(self, tmp_path: Path) -> None:
        registry_data = {
            "version": 1,
            "workflows": [
                {
                    "id": "workflow1",
                    "file": "w1.json",
                    "name": "Workflow 1",
                    "description": "",
                    "when_to_use": "",
                    "tags": [],
                    "category": "test",
                },
                {
                    "id": "workflow2",
                    "file": "w2.json",
                    "name": "Workflow 2",
                    "description": "",
                    "when_to_use": "",
                    "tags": [],
                    "category": "test",
                },
            ],
        }

        registry_file = tmp_path / "registry.yaml"
        registry_file.write_text(yaml.dump(registry_data))

        registry = WorkflowRegistry.load(registry_file)

        assert registry.get_workflow("workflow1") is not None
        assert registry.get_workflow("workflow2") is not None
        assert registry.get_workflow("nonexistent") is None

    def test_get_by_category(self, tmp_path: Path) -> None:
        registry_data = {
            "version": 1,
            "workflows": [
                {
                    "id": "gen1",
                    "file": "g1.json",
                    "name": "Gen 1",
                    "description": "",
                    "when_to_use": "",
                    "tags": [],
                    "category": "generation",
                },
                {
                    "id": "proc1",
                    "file": "p1.json",
                    "name": "Proc 1",
                    "description": "",
                    "when_to_use": "",
                    "tags": [],
                    "category": "processing",
                },
                {
                    "id": "gen2",
                    "file": "g2.json",
                    "name": "Gen 2",
                    "description": "",
                    "when_to_use": "",
                    "tags": [],
                    "category": "generation",
                },
            ],
        }

        registry_file = tmp_path / "registry.yaml"
        registry_file.write_text(yaml.dump(registry_data))

        registry = WorkflowRegistry.load(registry_file)

        gen_workflows = registry.get_by_category("generation")
        assert len(gen_workflows) == 2

        proc_workflows = registry.get_by_category("processing")
        assert len(proc_workflows) == 1

    def test_get_by_tag(self, tmp_path: Path) -> None:
        registry_data = {
            "version": 1,
            "workflows": [
                {
                    "id": "w1",
                    "file": "w1.json",
                    "name": "W1",
                    "description": "",
                    "when_to_use": "",
                    "tags": ["pbr", "material"],
                    "category": "test",
                },
                {
                    "id": "w2",
                    "file": "w2.json",
                    "name": "W2",
                    "description": "",
                    "when_to_use": "",
                    "tags": ["texture"],
                    "category": "test",
                },
            ],
        }

        registry_file = tmp_path / "registry.yaml"
        registry_file.write_text(yaml.dump(registry_data))

        registry = WorkflowRegistry.load(registry_file)

        pbr_workflows = registry.get_by_tag("pbr")
        assert len(pbr_workflows) == 1
        assert pbr_workflows[0].id == "w1"

    def test_search(self, tmp_path: Path) -> None:
        registry_data = {
            "version": 1,
            "workflows": [
                {
                    "id": "material_gen",
                    "file": "m.json",
                    "name": "Material Generator",
                    "description": "Creates PBR materials",
                    "when_to_use": "",
                    "tags": ["pbr"],
                    "category": "test",
                },
                {
                    "id": "upscale",
                    "file": "u.json",
                    "name": "Image Upscaler",
                    "description": "Upscales images",
                    "when_to_use": "",
                    "tags": [],
                    "category": "test",
                },
            ],
        }

        registry_file = tmp_path / "registry.yaml"
        registry_file.write_text(yaml.dump(registry_data))

        registry = WorkflowRegistry.load(registry_file)

        # Search by name
        results = registry.search("material")
        assert len(results) == 1
        assert results[0].id == "material_gen"

        # Search by description
        results = registry.search("pbr")
        assert len(results) == 1

        # Search by tag
        results = registry.search("pbr")
        assert len(results) == 1

    def test_list_categories(self, tmp_path: Path) -> None:
        registry_data = {
            "version": 1,
            "workflows": [
                {"id": "w1", "file": "w1.json", "name": "W1", "description": "", "when_to_use": "", "tags": [], "category": "generation"},
                {"id": "w2", "file": "w2.json", "name": "W2", "description": "", "when_to_use": "", "tags": [], "category": "processing"},
                {"id": "w3", "file": "w3.json", "name": "W3", "description": "", "when_to_use": "", "tags": [], "category": "generation"},
            ],
        }

        registry_file = tmp_path / "registry.yaml"
        registry_file.write_text(yaml.dump(registry_data))

        registry = WorkflowRegistry.load(registry_file)
        categories = registry.list_categories()

        assert len(categories) == 2
        assert "generation" in categories
        assert "processing" in categories

    def test_list_tags(self, tmp_path: Path) -> None:
        registry_data = {
            "version": 1,
            "workflows": [
                {"id": "w1", "file": "w1.json", "name": "W1", "description": "", "when_to_use": "", "tags": ["pbr", "material"], "category": "test"},
                {"id": "w2", "file": "w2.json", "name": "W2", "description": "", "when_to_use": "", "tags": ["texture", "pbr"], "category": "test"},
            ],
        }

        registry_file = tmp_path / "registry.yaml"
        registry_file.write_text(yaml.dump(registry_data))

        registry = WorkflowRegistry.load(registry_file)
        tags = registry.list_tags()

        assert len(tags) == 3
        assert "pbr" in tags
        assert "material" in tags
        assert "texture" in tags

    def test_get_workflow_path(self, tmp_path: Path) -> None:
        registry_data = {
            "version": 1,
            "workflows": [
                {"id": "test", "file": "workflows/test.json", "name": "Test", "description": "", "when_to_use": "", "tags": [], "category": "test"},
            ],
        }

        registry_file = tmp_path / "registry.yaml"
        registry_file.write_text(yaml.dump(registry_data))

        registry = WorkflowRegistry.load(registry_file)
        workflow = registry.workflows[0]

        path = registry.get_workflow_path(workflow)
        assert path == tmp_path / "workflows/test.json"

    def test_to_summary(self, tmp_path: Path) -> None:
        registry_data = {
            "version": 2,
            "workflows": [
                {"id": "test", "file": "test.json", "name": "Test", "description": "A test workflow", "when_to_use": "", "tags": ["tag1"], "category": "cat1"},
            ],
        }

        registry_file = tmp_path / "registry.yaml"
        registry_file.write_text(yaml.dump(registry_data))

        registry = WorkflowRegistry.load(registry_file)
        summary = registry.to_summary()

        assert summary["version"] == 2
        assert summary["workflow_count"] == 1
        assert "cat1" in summary["categories"]
        assert "tag1" in summary["tags"]
