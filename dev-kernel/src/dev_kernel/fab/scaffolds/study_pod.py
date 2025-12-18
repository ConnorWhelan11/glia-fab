"""
Study Pod Scaffold - Parametric study space generation.

Creates individual study pods with customizable:
- Desk style (concrete, wood, glass, metal)
- Chair type (wooden, modern, stool, armchair)
- Book arrangements (stacks, singles, shelved)
- Personal items and accessories

Designed for the Outora Mega Library project but reusable for any
interior/study space generation.

Usage:
    from dev_kernel.fab.scaffolds.study_pod import StudyPodScaffold

    scaffold = StudyPodScaffold()
    script_path = scaffold.generate_script(
        params={
            "desk_style": "concrete",
            "chair_type": "wooden",
            "book_density": 0.7,
            "personal_items": ["lamp", "monitor", "plant"],
        },
        output_dir=Path("/tmp/pod_output"),
    )
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import ScaffoldBase, ScaffoldParameter, ScaffoldResult, ParameterType

logger = logging.getLogger(__name__)


# Available asset sources (map to Outora Library naming conventions)
DESK_STYLES = {
    "concrete": {
        "source": "ol_desk_concrete",
        "scale": (1.35, 1.35, 1.35),
        "material": None,  # Keep original
    },
    "wood": {
        "source": "ol_desk_wood",
        "scale": (1.0, 1.0, 1.0),
        "material": "ol_mat_wood_dark",
    },
    "glass": {
        "source": "ol_desk_glass",
        "scale": (1.0, 1.0, 1.0),
        "material": "ol_mat_glass",
    },
    "metal": {
        "source": "ol_desk_metal",
        "scale": (1.0, 1.0, 1.0),
        "material": "ol_mat_brass",
    },
}

CHAIR_TYPES = {
    "wooden": {
        "source": "WoodenChair_01",
        "scale": (0.85, 0.85, 0.85),
        "offset": (0, 1.2, 0),  # Behind desk
    },
    "modern": {
        "source": "ol_chair_modern",
        "scale": (1.0, 1.0, 1.0),
        "offset": (0, 1.0, 0),
    },
    "stool": {
        "source": "ol_stool",
        "scale": (1.0, 1.0, 1.0),
        "offset": (0, 0.8, 0),
    },
    "armchair": {
        "source": "ol_armchair",
        "scale": (1.0, 1.0, 1.0),
        "offset": (0, 1.4, 0),
    },
}

BOOK_SOURCES = [
    "ol_book_stack_a",
    "ol_book_stack_b",
    "ol_book_stack_c",
    "ol_book_stack_d",
    "ol_book_stack_e",
    "ol_book_stack_f",
    "ol_book_stack_g",
    "ol_book_stack_h",
]

PERSONAL_ITEMS = {
    "lamp": {
        "source": "desk_lamp_arm_01",
        "offset": (0.3, 0.3, 0.75),
        "scale": (1.0, 1.0, 1.0),
    },
    "monitor": {
        "sources": ["ol_monitor_base", "ol_monitor_screen", "ol_monitor_keyboard"],
        "offset": (0.0, 0.0, 0.75),
        "scale": (0.02, 0.02, 0.02),
    },
    "plant": {
        "source": "ol_plant_small",
        "offset": (-0.35, 0.2, 0.75),
        "scale": (0.5, 0.5, 0.5),
    },
    "globe": {
        "source": "ol_globe",
        "offset": (0.35, -0.2, 0.75),
        "scale": (0.3, 0.3, 0.3),
    },
    "telescope": {
        "source": "ol_telescope_small",
        "offset": (-0.4, 0.0, 0.75),
        "scale": (0.4, 0.4, 0.4),
    },
    "inkwell": {
        "source": "ol_inkwell",
        "offset": (0.2, -0.1, 0.75),
        "scale": (0.8, 0.8, 0.8),
    },
    "hourglass": {
        "source": "ol_hourglass",
        "offset": (-0.25, 0.15, 0.75),
        "scale": (0.6, 0.6, 0.6),
    },
}


class StudyPodScaffold(ScaffoldBase):
    """
    Procedural scaffold for generating study pods.

    A study pod consists of:
    - One desk (customizable style)
    - One chair (customizable type)
    - Book arrangements (density-controlled)
    - Personal items (selectable accessories)
    """

    SCAFFOLD_ID = "study_pod"
    CATEGORY = "furniture_set"
    SCAFFOLD_VERSION = "1.0.0"

    # Parameters defined via class variable for convenience
    PARAMETERS = [
        ScaffoldParameter(
            name="desk_style",
            param_type=ParameterType.ENUM,
            default="concrete",
            description="Style of desk",
            enum_values=list(DESK_STYLES.keys()),
        ),
        ScaffoldParameter(
            name="chair_type",
            param_type=ParameterType.ENUM,
            default="wooden",
            description="Type of chair",
            enum_values=list(CHAIR_TYPES.keys()),
        ),
        ScaffoldParameter(
            name="book_density",
            param_type=ParameterType.FLOAT,
            default=0.5,
            description="Density of books on desk (0-1)",
            min_value=0.0,
            max_value=1.0,
        ),
        ScaffoldParameter(
            name="book_style",
            param_type=ParameterType.ENUM,
            default="stacks",
            description="How books are arranged",
            enum_values=["stacks", "singles", "mixed", "none"],
        ),
        ScaffoldParameter(
            name="rotation_z",
            param_type=ParameterType.FLOAT,
            default=0.0,
            description="Rotation around Z axis (radians)",
            min_value=-6.28,
            max_value=6.28,
            unit="rad",
        ),
        ScaffoldParameter(
            name="position",
            param_type=ParameterType.VECTOR3,
            default=(0.0, 0.0, 0.0),
            description="World position (x, y, z)",
            unit="m",
        ),
        ScaffoldParameter(
            name="student_name",
            param_type=ParameterType.ENUM,
            default="anonymous",
            description="Name for the pod (used in object naming)",
            enum_values=None,  # Free-form string
        ),
        ScaffoldParameter(
            name="random_seed",
            param_type=ParameterType.INT,
            default=42,
            description="Seed for randomization (book placement, etc.)",
            min_value=0,
            max_value=999999,
        ),
    ]

    def _define_parameters(self) -> None:
        """Define scaffold parameters from class PARAMETERS list."""
        for param in self.PARAMETERS:
            self.add_parameter(param)

    def generate_geometry_nodes_setup(self) -> str:
        """Study pods use instancing, not Geometry Nodes."""
        return "# Study pods use object instancing, not Geometry Nodes"

    def generate_blender_script(
        self,
        params: Dict[str, Any],
        output_path: Path,
    ) -> str:
        """Generate Blender script for scaffold creation."""
        return self._generate_blender_script(
            params, output_path, output_path.with_suffix(".blend")
        )

    def generate_script(
        self,
        params: Dict[str, Any],
        output_dir: Path,
    ) -> Path:
        """Generate Blender Python script to create the study pod."""
        script_path = output_dir / f"{self.SCAFFOLD_ID}_generate.py"
        student_name = params.get("student_name", "anon")
        output_glb = output_dir / f"study_pod_{student_name}.glb"
        output_blend = output_dir / f"study_pod_{student_name}.blend"

        # Merge with defaults and validate
        final_params = self.get_defaults()
        final_params.update(params)

        valid, errors = self.validate_parameters(final_params)
        if not valid:
            logger.warning(f"Parameter validation warnings: {errors}")

        script_content = self._generate_blender_script(
            final_params, output_glb, output_blend
        )

        script_path.parent.mkdir(parents=True, exist_ok=True)
        with open(script_path, "w") as f:
            f.write(script_content)

        logger.info(f"Generated study pod script: {script_path}")
        return script_path

    def _generate_blender_script(
        self,
        params: Dict[str, Any],
        output_glb: Path,
        output_blend: Path,
    ) -> str:
        """Generate the Blender Python script content."""

        # Serialize params for embedding
        params_json = json.dumps(params, indent=2)

        desk_config = DESK_STYLES.get(params["desk_style"], DESK_STYLES["concrete"])
        chair_config = CHAIR_TYPES.get(params["chair_type"], CHAIR_TYPES["wooden"])

        return f'''#!/usr/bin/env python3
"""
Auto-generated Study Pod scaffold script.
Scaffold: {self.SCAFFOLD_ID} v{self.SCAFFOLD_VERSION}
Student: {params.get("student_name", "anonymous")}
"""

import bpy
import math
import random
from pathlib import Path
from mathutils import Vector, Matrix

# Parameters
PARAMS = {params_json}

# Asset configurations
DESK_SOURCE = "{desk_config['source']}"
DESK_SCALE = {desk_config['scale']}
CHAIR_SOURCE = "{chair_config['source']}"
CHAIR_SCALE = {chair_config['scale']}
CHAIR_OFFSET = {chair_config['offset']}

BOOK_SOURCES = {BOOK_SOURCES}
PERSONAL_ITEMS = {json.dumps(PERSONAL_ITEMS)}

OUTPUT_GLB = r"{output_glb}"
OUTPUT_BLEND = r"{output_blend}"


def find_source_object(name):
    """Find source object, checking common locations."""
    obj = bpy.data.objects.get(name)
    if obj:
        return obj
    
    # Check in OL_Assets or OL_PodSources collections
    for col_name in ["OL_Assets", "OL_PodSources", "OL_Furniture"]:
        col = bpy.data.collections.get(col_name)
        if col:
            for obj in col.objects:
                if obj.name == name or obj.name.startswith(name):
                    return obj
    
    print(f"[warning] Source object not found: {{name}}")
    return None


def instance_object(src, name, location, rotation_z=0.0, scale=(1,1,1)):
    """Create an instance (linked duplicate) of a source object."""
    if not src:
        return None
    
    inst = src.copy()
    if src.data:
        inst.data = src.data.copy()
    
    inst.name = name
    inst.location = location
    inst.rotation_euler = (0, 0, rotation_z)
    inst.scale = scale
    
    return inst


def create_simple_desk(name, style):
    """Create a simple desk if source not found."""
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0.375))
    desk = bpy.context.object
    desk.name = name
    desk.scale = (1.2, 0.6, 0.75)
    bpy.ops.object.transform_apply(scale=True)
    
    # Add simple wood material
    mat = bpy.data.materials.new(name=f"{{name}}_mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.3, 0.2, 0.1, 1)  # Brown
    bsdf.inputs["Roughness"].default_value = 0.6
    desk.data.materials.append(mat)
    
    return desk


def create_simple_chair(name):
    """Create a simple chair if source not found."""
    # Seat
    bpy.ops.mesh.primitive_cube_add(size=0.4, location=(0, 0, 0.45))
    seat = bpy.context.object
    seat.scale = (1.0, 1.0, 0.1)
    bpy.ops.object.transform_apply(scale=True)
    
    # Back
    bpy.ops.mesh.primitive_cube_add(size=0.4, location=(0, -0.18, 0.7))
    back = bpy.context.object
    back.scale = (1.0, 0.1, 0.6)
    bpy.ops.object.transform_apply(scale=True)
    
    # Join
    seat.select_set(True)
    back.select_set(True)
    bpy.context.view_layer.objects.active = seat
    bpy.ops.object.join()
    
    chair = bpy.context.object
    chair.name = name
    
    # Material
    mat = bpy.data.materials.new(name=f"{{name}}_mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.4, 0.25, 0.1, 1)
    chair.data.materials.append(mat)
    
    return chair


def create_book_stack(name, num_books=5):
    """Create a simple book stack."""
    books = []
    z = 0
    for i in range(num_books):
        bpy.ops.mesh.primitive_cube_add(size=0.1, location=(0, 0, z + 0.015))
        book = bpy.context.object
        book.scale = (0.8 + random.uniform(-0.1, 0.1), 
                      0.6 + random.uniform(-0.1, 0.1), 
                      0.15)
        bpy.ops.object.transform_apply(scale=True)
        
        # Random color
        mat = bpy.data.materials.new(name=f"book_{{i}}_mat")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = (
            random.uniform(0.2, 0.8),
            random.uniform(0.2, 0.6),
            random.uniform(0.2, 0.5),
            1
        )
        book.data.materials.append(mat)
        books.append(book)
        z += 0.03
    
    # Join all books
    for b in books:
        b.select_set(True)
    bpy.context.view_layer.objects.active = books[0]
    bpy.ops.object.join()
    
    stack = bpy.context.object
    stack.name = name
    return stack


def main():
    random.seed(PARAMS.get("random_seed", 42))
    
    # Create or get target collection
    pod_name = f"StudyPod_{{PARAMS.get('student_name', 'anon')}}"
    pod_col = bpy.data.collections.get(pod_name)
    if not pod_col:
        pod_col = bpy.data.collections.new(pod_name)
        bpy.context.scene.collection.children.link(pod_col)
    
    # Clear existing objects in collection
    for obj in list(pod_col.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    
    # Base position and rotation
    pos = tuple(PARAMS.get("position", (0, 0, 0)))
    rot_z = PARAMS.get("rotation_z", 0.0)
    
    created_objects = []
    
    # --- DESK ---
    desk_src = find_source_object(DESK_SOURCE)
    if desk_src:
        desk = instance_object(
            desk_src, 
            f"{{pod_name}}_desk",
            pos,
            rot_z,
            DESK_SCALE
        )
    else:
        desk = create_simple_desk(f"{{pod_name}}_desk", PARAMS.get("desk_style", "wood"))
        desk.location = pos
        desk.rotation_euler.z = rot_z
    
    if desk:
        pod_col.objects.link(desk)
        if desk.name in bpy.context.scene.collection.objects:
            bpy.context.scene.collection.objects.unlink(desk)
        created_objects.append(desk)
    
    # --- CHAIR ---
    chair_src = find_source_object(CHAIR_SOURCE)
    chair_pos = (
        pos[0] + CHAIR_OFFSET[0] * math.cos(rot_z) - CHAIR_OFFSET[1] * math.sin(rot_z),
        pos[1] + CHAIR_OFFSET[0] * math.sin(rot_z) + CHAIR_OFFSET[1] * math.cos(rot_z),
        pos[2] + CHAIR_OFFSET[2]
    )
    
    if chair_src:
        chair = instance_object(
            chair_src,
            f"{{pod_name}}_chair",
            chair_pos,
            rot_z + math.pi,  # Face desk
            CHAIR_SCALE
        )
    else:
        chair = create_simple_chair(f"{{pod_name}}_chair")
        chair.location = chair_pos
        chair.rotation_euler.z = rot_z + math.pi
    
    if chair:
        pod_col.objects.link(chair)
        if chair.name in bpy.context.scene.collection.objects:
            bpy.context.scene.collection.objects.unlink(chair)
        created_objects.append(chair)
    
    # --- BOOKS ---
    book_density = PARAMS.get("book_density", 0.5)
    book_style = PARAMS.get("book_style", "stacks")
    
    if book_style != "none" and book_density > 0:
        desk_top_z = 0.75  # Approximate desk height
        
        # Book placement slots on desk
        book_slots = [
            (-0.25, -0.15),
            (0.18, 0.05),
            (-0.35, 0.1),
            (0.25, -0.1),
        ]
        
        num_stacks = int(len(book_slots) * book_density)
        for i in range(num_stacks):
            slot = book_slots[i]
            book_world_pos = (
                pos[0] + slot[0] * math.cos(rot_z) - slot[1] * math.sin(rot_z),
                pos[1] + slot[0] * math.sin(rot_z) + slot[1] * math.cos(rot_z),
                pos[2] + desk_top_z
            )
            
            # Try to use source, else create simple
            book_src_name = random.choice(BOOK_SOURCES)
            book_src = find_source_object(book_src_name)
            
            if book_src:
                stack = instance_object(
                    book_src,
                    f"{{pod_name}}_books_{{i}}",
                    book_world_pos,
                    rot_z + random.uniform(-0.3, 0.3),
                    (0.02, 0.02, 0.02)
                )
            else:
                num_books = random.randint(3, 7) if book_style == "stacks" else 1
                stack = create_book_stack(f"{{pod_name}}_books_{{i}}", num_books)
                stack.location = book_world_pos
                stack.rotation_euler.z = rot_z + random.uniform(-0.3, 0.3)
                stack.scale = (0.15, 0.15, 0.15)
            
            if stack:
                pod_col.objects.link(stack)
                if stack.name in bpy.context.scene.collection.objects:
                    bpy.context.scene.collection.objects.unlink(stack)
                created_objects.append(stack)
    
    # --- PERSONAL ITEMS ---
    personal_items = PARAMS.get("personal_items", [])
    desk_top_z = 0.75
    
    for item_name in personal_items:
        if item_name not in PERSONAL_ITEMS:
            continue
        
        item_config = PERSONAL_ITEMS[item_name]
        offset = item_config.get("offset", (0, 0, 0.75))
        scale = item_config.get("scale", (1, 1, 1))
        
        item_world_pos = (
            pos[0] + offset[0] * math.cos(rot_z) - offset[1] * math.sin(rot_z),
            pos[1] + offset[0] * math.sin(rot_z) + offset[1] * math.cos(rot_z),
            pos[2] + offset[2]
        )
        
        if "sources" in item_config:
            # Multi-part item (like monitor)
            for src_name in item_config["sources"]:
                src = find_source_object(src_name)
                if src:
                    inst = instance_object(
                        src,
                        f"{{pod_name}}_{{item_name}}_{{src_name}}",
                        item_world_pos,
                        rot_z,
                        scale
                    )
                    if inst:
                        pod_col.objects.link(inst)
                        if inst.name in bpy.context.scene.collection.objects:
                            bpy.context.scene.collection.objects.unlink(inst)
                        created_objects.append(inst)
        else:
            src = find_source_object(item_config.get("source", ""))
            if src:
                inst = instance_object(
                    src,
                    f"{{pod_name}}_{{item_name}}",
                    item_world_pos,
                    rot_z,
                    scale
                )
                if inst:
                    pod_col.objects.link(inst)
                    if inst.name in bpy.context.scene.collection.objects:
                        bpy.context.scene.collection.objects.unlink(inst)
                    created_objects.append(inst)
    
    print(f"Created study pod '{{pod_name}}' with {{len(created_objects)}} objects")
    
    # --- EXPORT ---
    # Select all created objects
    bpy.ops.object.select_all(action='DESELECT')
    for obj in created_objects:
        obj.select_set(True)
    
    if created_objects:
        bpy.context.view_layer.objects.active = created_objects[0]
    
    # Export GLB
    try:
        bpy.ops.export_scene.gltf(
            filepath=OUTPUT_GLB,
            export_format='GLB',
            use_selection=True,
            export_apply=True,
            export_yup=True,
        )
        print(f"Exported GLB: {{OUTPUT_GLB}}")
    except Exception as e:
        print(f"GLB export failed: {{e}}")
    
    # Save .blend
    try:
        bpy.ops.wm.save_as_mainfile(filepath=OUTPUT_BLEND)
        print(f"Saved blend: {{OUTPUT_BLEND}}")
    except Exception as e:
        print(f"Blend save failed: {{e}}")


if __name__ == "__main__":
    main()
'''


# Convenience function for direct use
def create_study_pod(
    output_dir: Path,
    desk_style: str = "concrete",
    chair_type: str = "wooden",
    book_density: float = 0.5,
    personal_items: Optional[List[str]] = None,
    student_name: str = "anonymous",
    position: tuple = (0, 0, 0),
    rotation_z: float = 0.0,
    random_seed: int = 42,
) -> Path:
    """
    Convenience function to generate a study pod script.

    Returns path to the generated Blender script.
    """
    scaffold = StudyPodScaffold()

    params = {
        "desk_style": desk_style,
        "chair_type": chair_type,
        "book_density": book_density,
        "book_style": "stacks",
        "personal_items": personal_items or ["lamp"],
        "student_name": student_name,
        "position": position,
        "rotation_z": rotation_z,
        "random_seed": random_seed,
    }

    return scaffold.generate_script(params, output_dir)
