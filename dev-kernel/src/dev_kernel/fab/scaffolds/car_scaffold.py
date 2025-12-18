"""
Car Scaffold - Parametric car generation using Geometry Nodes.

This scaffold provides a parametric car body that agents can modify
by adjusting parameters rather than editing mesh topology directly.

Parameters control:
- Overall dimensions (length, width, height)
- Proportions (wheelbase, track width, overhang)
- Body style (sedan, SUV, sports)
- Wheel placement
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from .base import ParameterType, ScaffoldBase, ScaffoldParameter


@dataclass
class CarScaffoldParams:
    """Typed parameters for car scaffold."""

    # Overall dimensions (meters)
    length: float = 4.5
    width: float = 1.8
    height: float = 1.4

    # Proportions
    wheelbase: float = 2.7  # Distance between axles
    track_width: float = 1.5  # Distance between wheels (left-right)
    front_overhang: float = 0.8
    rear_overhang: float = 1.0

    # Body style
    body_style: str = "sedan"  # sedan, suv, sports, hatchback
    roof_slope: float = 0.3  # 0 = flat, 1 = steep

    # Wheel parameters
    wheel_radius: float = 0.35
    wheel_width: float = 0.22
    wheel_count: int = 4

    # Detail level
    subdivision_level: int = 2
    smoothing: bool = True


class CarScaffold(ScaffoldBase):
    """
    Parametric car scaffold using Geometry Nodes.

    Generates a car body mesh with proper proportions that can be
    further refined by agents. The scaffold ensures:
    - Correct scale for realistic cars
    - Proper wheel placement
    - Symmetric body structure
    - Modifiable parameters via Geometry Nodes inputs
    """

    SCAFFOLD_ID = "car_parametric_v001"
    SCAFFOLD_VERSION = "1.0.0"
    CATEGORY = "car"

    def _define_parameters(self) -> None:
        """Define all car scaffold parameters."""
        # Dimensions
        self.add_parameter(
            ScaffoldParameter(
                name="length",
                param_type=ParameterType.FLOAT,
                default=4.5,
                min_value=3.0,
                max_value=6.0,
                description="Overall car length",
                unit="m",
            )
        )
        self.add_parameter(
            ScaffoldParameter(
                name="width",
                param_type=ParameterType.FLOAT,
                default=1.8,
                min_value=1.4,
                max_value=2.5,
                description="Overall car width",
                unit="m",
            )
        )
        self.add_parameter(
            ScaffoldParameter(
                name="height",
                param_type=ParameterType.FLOAT,
                default=1.4,
                min_value=1.0,
                max_value=2.5,
                description="Overall car height",
                unit="m",
            )
        )

        # Proportions
        self.add_parameter(
            ScaffoldParameter(
                name="wheelbase",
                param_type=ParameterType.FLOAT,
                default=2.7,
                min_value=2.0,
                max_value=4.0,
                description="Distance between front and rear axles",
                unit="m",
            )
        )
        self.add_parameter(
            ScaffoldParameter(
                name="track_width",
                param_type=ParameterType.FLOAT,
                default=1.5,
                min_value=1.2,
                max_value=2.2,
                description="Distance between left and right wheels",
                unit="m",
            )
        )
        self.add_parameter(
            ScaffoldParameter(
                name="front_overhang",
                param_type=ParameterType.FLOAT,
                default=0.8,
                min_value=0.3,
                max_value=1.5,
                description="Distance from front axle to front of car",
                unit="m",
            )
        )
        self.add_parameter(
            ScaffoldParameter(
                name="rear_overhang",
                param_type=ParameterType.FLOAT,
                default=1.0,
                min_value=0.3,
                max_value=1.5,
                description="Distance from rear axle to back of car",
                unit="m",
            )
        )

        # Body style
        self.add_parameter(
            ScaffoldParameter(
                name="body_style",
                param_type=ParameterType.ENUM,
                default="sedan",
                enum_values=["sedan", "suv", "sports", "hatchback", "wagon"],
                description="Body style preset",
            )
        )
        self.add_parameter(
            ScaffoldParameter(
                name="roof_slope",
                param_type=ParameterType.FLOAT,
                default=0.3,
                min_value=0.0,
                max_value=1.0,
                description="Roof slope (0=flat, 1=steep)",
            )
        )

        # Wheels
        self.add_parameter(
            ScaffoldParameter(
                name="wheel_radius",
                param_type=ParameterType.FLOAT,
                default=0.35,
                min_value=0.25,
                max_value=0.5,
                description="Wheel radius",
                unit="m",
            )
        )
        self.add_parameter(
            ScaffoldParameter(
                name="wheel_width",
                param_type=ParameterType.FLOAT,
                default=0.22,
                min_value=0.15,
                max_value=0.35,
                description="Wheel/tire width",
                unit="m",
            )
        )

        # Detail
        self.add_parameter(
            ScaffoldParameter(
                name="subdivision_level",
                param_type=ParameterType.INT,
                default=2,
                min_value=0,
                max_value=4,
                description="Subdivision level for smooth body",
            )
        )
        self.add_parameter(
            ScaffoldParameter(
                name="smoothing",
                param_type=ParameterType.BOOL,
                default=True,
                description="Enable smooth shading",
            )
        )

    def generate_geometry_nodes_setup(self) -> str:
        """Generate Geometry Nodes setup script."""
        return '''
import bpy
import math

def create_car_geometry_nodes(obj):
    """Create Geometry Nodes modifier for parametric car."""

    # Create new node group
    node_group = bpy.data.node_groups.new(
        name="CarParametricScaffold",
        type='GeometryNodeTree'
    )

    # Create input/output nodes
    nodes = node_group.nodes
    links = node_group.links

    # Group Input
    group_input = nodes.new('NodeGroupInput')
    group_input.location = (-400, 0)

    # Group Output
    group_output = nodes.new('NodeGroupOutput')
    group_output.location = (400, 0)

    # Add input sockets
    node_group.interface.new_socket(
        name='Length', in_out='INPUT', socket_type='NodeSocketFloat'
    )
    node_group.interface.new_socket(
        name='Width', in_out='INPUT', socket_type='NodeSocketFloat'
    )
    node_group.interface.new_socket(
        name='Height', in_out='INPUT', socket_type='NodeSocketFloat'
    )
    node_group.interface.new_socket(
        name='Wheelbase', in_out='INPUT', socket_type='NodeSocketFloat'
    )
    node_group.interface.new_socket(
        name='Track Width', in_out='INPUT', socket_type='NodeSocketFloat'
    )
    node_group.interface.new_socket(
        name='Wheel Radius', in_out='INPUT', socket_type='NodeSocketFloat'
    )

    # Add output socket
    node_group.interface.new_socket(
        name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry'
    )

    # Create mesh primitive - Box for body
    box = nodes.new('GeometryNodeMeshCube')
    box.location = (-200, 0)

    # Transform for dimensions
    transform = nodes.new('GeometryNodeTransform')
    transform.location = (0, 0)

    # Combine XYZ for scale
    combine = nodes.new('ShaderNodeCombineXYZ')
    combine.location = (-200, -200)

    # Link nodes
    links.new(box.outputs['Mesh'], transform.inputs['Geometry'])
    links.new(group_input.outputs['Length'], combine.inputs['X'])
    links.new(group_input.outputs['Width'], combine.inputs['Y'])
    links.new(group_input.outputs['Height'], combine.inputs['Z'])
    links.new(combine.outputs['Vector'], transform.inputs['Scale'])
    links.new(transform.outputs['Geometry'], group_output.inputs['Geometry'])

    # Add modifier to object
    mod = obj.modifiers.new(name="CarScaffold", type='NODES')
    mod.node_group = node_group

    return mod


def setup_car_scaffold_inputs(mod, params):
    """Set Geometry Nodes modifier inputs from params dict."""
    if 'Length' in mod:
        mod['Length'] = params.get('length', 4.5)
    if 'Width' in mod:
        mod['Width'] = params.get('width', 1.8)
    if 'Height' in mod:
        mod['Height'] = params.get('height', 1.4)
    if 'Wheelbase' in mod:
        mod['Wheelbase'] = params.get('wheelbase', 2.7)
    if 'Track Width' in mod:
        mod['Track Width'] = params.get('track_width', 1.5)
    if 'Wheel Radius' in mod:
        mod['Wheel Radius'] = params.get('wheel_radius', 0.35)
'''

    def generate_blender_script(
        self,
        params: Dict[str, Any],
        output_path: Path,
    ) -> str:
        """Generate complete Blender script for car scaffold."""

        return f'''#!/usr/bin/env python3
"""
Auto-generated car scaffold script.
Scaffold: {self.SCAFFOLD_ID} v{self.SCAFFOLD_VERSION}
"""

import bpy
import math
from pathlib import Path

# Clear scene
bpy.ops.wm.read_factory_settings(use_empty=True)

# Parameters
params = {params!r}

length = params.get('length', 4.5)
width = params.get('width', 1.8)
height = params.get('height', 1.4)
wheelbase = params.get('wheelbase', 2.7)
track_width = params.get('track_width', 1.5)
front_overhang = params.get('front_overhang', 0.8)
rear_overhang = params.get('rear_overhang', 1.0)
wheel_radius = params.get('wheel_radius', 0.35)
wheel_width = params.get('wheel_width', 0.22)
body_style = params.get('body_style', 'sedan')
roof_slope = params.get('roof_slope', 0.3)
subdivision_level = params.get('subdivision_level', 2)
smoothing = params.get('smoothing', True)

# Create car body collection
car_collection = bpy.data.collections.new("Car_Scaffold")
bpy.context.scene.collection.children.link(car_collection)

def create_body():
    """Create car body mesh."""
    # Body style presets
    style_heights = {{
        'sedan': 1.0,
        'suv': 1.3,
        'sports': 0.85,
        'hatchback': 1.1,
        'wagon': 1.15,
    }}
    height_mult = style_heights.get(body_style, 1.0)
    actual_height = height * height_mult

    # Create base box
    bpy.ops.mesh.primitive_cube_add(size=1)
    body = bpy.context.active_object
    body.name = "Body"
    body.scale = (length, width, actual_height * 0.6)  # Lower body portion
    body.location = (0, 0, wheel_radius + actual_height * 0.3)

    # Apply scale
    bpy.ops.object.transform_apply(scale=True)

    # Create roof/cabin
    bpy.ops.mesh.primitive_cube_add(size=1)
    cabin = bpy.context.active_object
    cabin.name = "Cabin"

    # Cabin dimensions based on style
    cabin_length = length * 0.55
    cabin.scale = (cabin_length, width * 0.95, actual_height * 0.4)
    cabin.location = (
        length * 0.05,  # Slightly forward
        0,
        wheel_radius + actual_height * 0.6 + actual_height * 0.2
    )
    bpy.ops.object.transform_apply(scale=True)

    # Join body parts
    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True)
    cabin.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()

    # Smooth shading
    if smoothing:
        bpy.ops.object.shade_smooth()

    # Subdivision
    if subdivision_level > 0:
        mod = body.modifiers.new(name="Subdivision", type='SUBSURF')
        mod.levels = subdivision_level
        mod.render_levels = subdivision_level

    # Move to collection
    for col in body.users_collection:
        col.objects.unlink(body)
    car_collection.objects.link(body)

    return body

def create_wheel(name, location):
    """Create a wheel at given location."""
    # Tire (torus)
    bpy.ops.mesh.primitive_torus_add(
        major_radius=wheel_radius,
        minor_radius=wheel_width * 0.4,
        major_segments=32,
        minor_segments=16
    )
    tire = bpy.context.active_object
    tire.name = f"{{name}}_Tire"
    tire.location = location
    tire.rotation_euler = (math.pi / 2, 0, 0)

    # Rim (cylinder)
    bpy.ops.mesh.primitive_cylinder_add(
        radius=wheel_radius * 0.7,
        depth=wheel_width * 0.8,
        vertices=24
    )
    rim = bpy.context.active_object
    rim.name = f"{{name}}_Rim"
    rim.location = location
    rim.rotation_euler = (math.pi / 2, 0, 0)

    # Join tire and rim
    bpy.ops.object.select_all(action='DESELECT')
    tire.select_set(True)
    rim.select_set(True)
    bpy.context.view_layer.objects.active = tire
    bpy.ops.object.join()
    tire.name = name

    # Smooth shading
    if smoothing:
        bpy.ops.object.shade_smooth()

    # Move to collection
    for col in tire.users_collection:
        col.objects.unlink(tire)
    car_collection.objects.link(tire)

    return tire

def create_wheels():
    """Create all four wheels."""
    # Calculate wheel positions
    front_x = wheelbase / 2 - front_overhang / 2
    rear_x = -wheelbase / 2 + rear_overhang / 2
    y_offset = track_width / 2 + wheel_width / 2

    wheels = []

    # Front Left
    wheels.append(create_wheel("Wheel_FL", (front_x, y_offset, wheel_radius)))

    # Front Right
    wheels.append(create_wheel("Wheel_FR", (front_x, -y_offset, wheel_radius)))

    # Rear Left
    wheels.append(create_wheel("Wheel_RL", (rear_x, y_offset, wheel_radius)))

    # Rear Right
    wheels.append(create_wheel("Wheel_RR", (rear_x, -y_offset, wheel_radius)))

    return wheels

def create_material(name, color):
    """Create basic material."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    return mat

# Create car parts
body = create_body()
wheels = create_wheels()

# Create materials
body_mat = create_material("Body_Material", (0.2, 0.2, 0.2))
wheel_mat = create_material("Wheel_Material", (0.1, 0.1, 0.1))

# Assign materials
body.data.materials.append(body_mat)
for wheel in wheels:
    wheel.data.materials.append(wheel_mat)

# Center at origin with wheels on ground
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')

# Export GLB
output_path = Path(r"{str(output_path)}")
output_path.parent.mkdir(parents=True, exist_ok=True)

bpy.ops.export_scene.gltf(
    filepath=str(output_path),
    export_format='GLB',
    use_selection=False,
)

# Save blend file
blend_path = output_path.with_suffix('.blend')
bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

print(f"Scaffold exported to: {{output_path}}")
print(f"Blend file saved to: {{blend_path}}")
'''

    @classmethod
    def from_params(cls, params: CarScaffoldParams) -> "CarScaffold":
        """Create scaffold and set parameters from dataclass."""
        scaffold = cls()
        return scaffold
