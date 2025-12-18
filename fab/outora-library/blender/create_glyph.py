"""
Glyph Creation Script

Creates the Out of Scope Glyph - an ambient AI presence avatar.
This script builds the complete Glyph model according to the design spec.

Usage (from Blender Scripting):
    import importlib, create_glyph
    importlib.reload(create_glyph)
    create_glyph.create_glyph()
"""

import bpy
import bmesh
from mathutils import Vector, Euler
import math


def hex_to_rgb(hex_color):
    """Convert hex color to RGB tuple (0-1 range)."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) / 255.0 for i in (0, 2, 4))


def create_glyph_collection():
    """Create or return the OL_GLYPH collection."""
    glyph_collection = bpy.data.collections.get("OL_GLYPH")
    if not glyph_collection:
        glyph_collection = bpy.data.collections.new("OL_GLYPH")
        bpy.context.scene.collection.children.link(glyph_collection)
    return glyph_collection


def create_glyph_core(glyph_collection):
    """Create the Glyph core (smooth UV sphere, slightly squashed).

    Uses high-resolution UV sphere (64×32) for smooth silhouette.
    """
    bm = bmesh.new()
    # High-res UV sphere for smooth appearance
    segments = 64  # horizontal resolution
    rings = 32  # vertical resolution
    radius = 1.0

    bmesh.ops.create_uvsphere(
        bm,
        u_segments=segments,
        v_segments=rings,
        radius=radius,
    )
    mesh = bpy.data.meshes.new("ol_glyph_core")
    bm.to_mesh(mesh)
    bm.free()

    core_obj = bpy.data.objects.new("ol_glyph_core", mesh)
    glyph_collection.objects.link(core_obj)
    core_obj.scale = (1.0, 1.0, 0.92)  # Subtle vertical squash
    core_obj.location = (0, 0, 0)

    # Shade Smooth
    bpy.context.view_layer.objects.active = core_obj
    bpy.ops.object.shade_smooth()

    # Optional Subsurf modifier (level 1, not needed with 64×32 but kept for extra smoothness)
    subsurf = core_obj.modifiers.new(name="Subdivision", type="SUBSURF")
    subsurf.levels = 1
    subsurf.render_levels = 1

    return core_obj


def create_glyph_rings(glyph_collection):
    """Create orbiting rings around the core.

    Rings are positioned to ensure a 'face window' is always visible from front.
    Rotations specified in degrees, converted to radians.
    """
    # Ring configs: radius, rotation (X, Y, Z) in degrees
    ring_configs = [
        {"radius": 1.4, "rot": (20, 0, 0)},
        {"radius": 1.5, "rot": (-25, 35, 0)},
        {"radius": 1.6, "rot": (0, 45, 15)},
        {"radius": 1.45, "rot": (60, -15, 0)},
    ]

    rings = []
    for i, config in enumerate(ring_configs):
        bpy.ops.mesh.primitive_torus_add(
            major_radius=config["radius"],
            minor_radius=0.015,  # Thinner wire-like
            major_segments=48,
            minor_segments=8,
            location=(0, 0, 0),
        )
        ring_obj = bpy.context.active_object
        ring_obj.name = f"ol_glyph_ring_{i+1:02d}"

        # Move to collection
        if ring_obj.name in bpy.context.scene.collection.objects:
            bpy.context.scene.collection.objects.unlink(ring_obj)
        glyph_collection.objects.link(ring_obj)

        # Convert degrees to radians and apply rotation
        rot_rad = tuple(math.radians(deg) for deg in config["rot"])
        ring_obj.rotation_euler = Euler(rot_rad, "XYZ")

        # Shade Smooth
        bpy.context.view_layer.objects.active = ring_obj
        bpy.ops.object.shade_smooth()

        # Optional Subsurf modifier (level 1)
        subsurf = ring_obj.modifiers.new(name="Subdivision", type="SUBSURF")
        subsurf.levels = 1
        subsurf.render_levels = 1

        rings.append(ring_obj)

    return rings


def create_glyph_eyes(glyph_collection):
    """Create the two eye dashes with beveled edges (pill-shaped)."""
    eye_width = 0.20
    eye_height = 0.01
    eye_depth = 0.03
    eye_spacing = 0.25
    eye_y_offset = 0.1  # Slightly above center

    eyes = []
    for side, x_offset in [("l", -eye_spacing / 2), ("r", eye_spacing / 2)]:
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=(eye_width, eye_depth, eye_height), verts=bm.verts)
        mesh = bpy.data.meshes.new(f"ol_glyph_eye_{side}")
        bm.to_mesh(mesh)
        bm.free()

        eye = bpy.data.objects.new(f"ol_glyph_eye_{side}", mesh)
        glyph_collection.objects.link(eye)
        eye.location = (x_offset, 1.0 + eye_depth / 2, eye_y_offset)

        # Add Bevel modifier for soft pill shape
        bevel = eye.modifiers.new(name="Bevel", type="BEVEL")
        bevel.width = 0.01
        bevel.segments = 3
        bevel.profile = 0.7

        eyes.append(eye)

    return eyes


def create_glyph_brow(glyph_collection):
    """Create the brow bar above the eyes with beveled edges."""
    brow_width = 0.5
    brow_height = 0.01
    brow_depth = 0.03
    brow_y_offset = 0.25  # Above eyes

    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(brow_width, brow_depth, brow_height), verts=bm.verts)
    mesh = bpy.data.meshes.new("ol_glyph_brow")
    bm.to_mesh(mesh)
    bm.free()

    brow = bpy.data.objects.new("ol_glyph_brow", mesh)
    glyph_collection.objects.link(brow)
    brow.location = (0, 1.0 + brow_depth / 2, brow_y_offset)

    # Add Bevel modifier (same as eyes)
    bevel = brow.modifiers.new(name="Bevel", type="BEVEL")
    bevel.width = 0.01
    bevel.segments = 3
    bevel.profile = 0.7

    return brow


def create_glyph_materials():
    """Create all materials for the Glyph."""
    materials = {}

    # Core Material
    core_mat = bpy.data.materials.new(name="ol_mat_glyph_core")
    core_mat.use_nodes = True
    nodes = core_mat.node_tree.nodes
    links = core_mat.node_tree.links
    nodes.clear()

    output = nodes.new(type="ShaderNodeOutputMaterial")
    emission = nodes.new(type="ShaderNodeEmission")
    color_ramp = nodes.new(type="ShaderNodeValToRGB")
    fresnel = nodes.new(type="ShaderNodeFresnel")

    core_color = hex_to_rgb("#E8F7FF")  # Very pale cyan
    glow_color = hex_to_rgb("#44E0FF")  # Teal/cyan

    fresnel.inputs["IOR"].default_value = 1.3
    color_ramp.color_ramp.elements[0].color = (*core_color, 1.0)
    color_ramp.color_ramp.elements[1].color = (*glow_color, 1.0)
    color_ramp.color_ramp.elements[0].position = 0.1  # Inner
    color_ramp.color_ramp.elements[1].position = 0.9  # Outer
    emission.inputs["Strength"].default_value = 5.0

    links.new(fresnel.outputs["Fac"], color_ramp.inputs["Fac"])
    links.new(color_ramp.outputs["Color"], emission.inputs["Color"])
    links.new(emission.outputs["Emission"], output.inputs["Surface"])
    materials["core"] = core_mat

    # Ring Material
    ring_mat = bpy.data.materials.new(name="ol_mat_glyph_ring")
    ring_mat.use_nodes = True
    nodes = ring_mat.node_tree.nodes
    links = ring_mat.node_tree.links
    nodes.clear()

    output = nodes.new(type="ShaderNodeOutputMaterial")
    emission = nodes.new(type="ShaderNodeEmission")
    transparent = nodes.new(type="ShaderNodeBsdfTransparent")
    mix_shader = nodes.new(type="ShaderNodeMixShader")
    fresnel = nodes.new(type="ShaderNodeFresnel")

    fresnel.inputs["IOR"].default_value = 1.5
    ring_color = (0.2, 0.8, 1.0, 1.0)  # Cyan/teal
    emission.inputs["Color"].default_value = ring_color
    emission.inputs["Strength"].default_value = 3.0
    transparent.inputs["Color"].default_value = (
        *ring_color[:3],
        0.05,
    )  # Faint transparent
    mix_shader.inputs["Fac"].default_value = 0.6

    links.new(fresnel.outputs["Fac"], mix_shader.inputs["Fac"])
    links.new(transparent.outputs["BSDF"], mix_shader.inputs[1])
    links.new(emission.outputs["Emission"], mix_shader.inputs[2])
    links.new(mix_shader.outputs["Shader"], output.inputs["Surface"])
    materials["ring"] = ring_mat

    # Eye Material
    eye_mat = bpy.data.materials.new(name="ol_mat_glyph_eye")
    eye_mat.use_nodes = True
    nodes = eye_mat.node_tree.nodes
    links = eye_mat.node_tree.links
    nodes.clear()

    output = nodes.new(type="ShaderNodeOutputMaterial")
    emission = nodes.new(type="ShaderNodeEmission")
    eye_color = (0.85, 0.95, 1.0, 1.0)  # Slightly dimmer off-white
    emission.inputs["Color"].default_value = eye_color
    emission.inputs["Strength"].default_value = 1.5
    links.new(emission.outputs["Emission"], output.inputs["Surface"])
    materials["eye"] = eye_mat

    # Brow Material
    brow_mat = bpy.data.materials.new(name="ol_mat_glyph_brow")
    brow_mat.use_nodes = True
    nodes = brow_mat.node_tree.nodes
    links = brow_mat.node_tree.links
    nodes.clear()

    output = nodes.new(type="ShaderNodeOutputMaterial")
    emission = nodes.new(type="ShaderNodeEmission")
    brow_color = (0.8, 0.9, 1.0, 1.0)  # Subtle off-white
    emission.inputs["Color"].default_value = brow_color
    emission.inputs["Strength"].default_value = 1.2
    links.new(emission.outputs["Emission"], output.inputs["Surface"])
    materials["brow"] = brow_mat

    return materials


def assign_materials(core_obj, rings, eyes, brow, materials):
    """Assign materials to all Glyph objects."""
    core_obj.data.materials.append(materials["core"])
    for ring in rings:
        ring.data.materials.append(materials["ring"])
    for eye in eyes:
        eye.data.materials.append(materials["eye"])
    brow.data.materials.append(materials["brow"])


def create_glyph_root(glyph_collection, core_obj, rings, eyes, brow):
    """Create parent empty and parent all objects."""
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0))
    parent_empty = bpy.context.active_object
    parent_empty.name = "ol_glyph_root"
    parent_empty.empty_display_size = 2.0

    if parent_empty.name in bpy.context.scene.collection.objects:
        bpy.context.scene.collection.objects.unlink(parent_empty)
    glyph_collection.objects.link(parent_empty)

    # Parent all objects
    all_objects = [core_obj] + rings + eyes + [brow]
    for obj in all_objects:
        obj.parent = parent_empty
        obj.matrix_parent_inverse = parent_empty.matrix_world.inverted()

    return parent_empty


def setup_render_settings():
    """Configure Eevee renderer.

    Note: Bloom settings may need to be enabled manually in Blender's
    Render Properties panel. This function sets the engine to Eevee.
    """
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"

    # Note: Bloom is typically enabled via View Layer Properties > Effects > Bloom
    # or through Compositor. For scripted control, you may need to use:
    # view_layer.use_pass_combined = True
    # and enable bloom in compositor nodes

    print("✓ Render settings configured (Eevee engine)")
    print("  Note: Enable Bloom manually in View Layer Properties > Effects > Bloom")


def add_cycles_modifier(obj, data_path, array_index=None):
    """Safely add Cycles modifier to an object's animation fcurves.

    Args:
        obj: Object with animation_data
        data_path: FCurve data path (e.g., "location", "scale")
        array_index: Optional array index (e.g., 2 for Z axis)
    """
    if not obj.animation_data or not obj.animation_data.action:
        return

    try:
        for fcurve in obj.animation_data.action.fcurves:
            if fcurve.data_path == data_path:
                if array_index is None or fcurve.array_index == array_index:
                    # Check if Cycles modifier already exists
                    has_cycles = any(mod.type == "CYCLES" for mod in fcurve.modifiers)
                    if not has_cycles:
                        fcurve.modifiers.new(type="CYCLES")
    except (AttributeError, RuntimeError):
        # FCurves might not be accessible yet, skip silently
        pass


def setup_idle_animation(root, core, rings):
    """Create Idle animation state (breathing, float, ring orbit).

    Timeline: frames 1-120 (2s at 60fps, 4s at 30fps)
    All animations use Cycles modifier for seamless loops.
    """
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 120

    # Ensure we're in Object mode
    bpy.ops.object.mode_set(mode="OBJECT")

    # Root Float (vertical bob)
    root.animation_data_create()
    root_action = bpy.data.actions.new(name="Glyph_Idle_Root")
    root.animation_data.action = root_action

    # Set keyframes for root location Z
    scene.frame_set(1)
    root.location.z = 0.0
    root.keyframe_insert(data_path="location", index=2)

    scene.frame_set(60)
    root.location.z = 0.05
    root.keyframe_insert(data_path="location", index=2)

    scene.frame_set(120)
    root.location.z = 0.0
    root.keyframe_insert(data_path="location", index=2)

    # Add Cycles modifier
    add_cycles_modifier(root, "location", array_index=2)

    # Core Breathing (scale animation)
    core.animation_data_create()
    core_action = bpy.data.actions.new(name="Glyph_Idle_Core")
    core.animation_data.action = core_action

    # Set keyframes for scale
    for frame, scale_values in [
        (1, (1.0, 1.0, 0.9)),
        (60, (1.03, 1.03, 0.927)),
        (120, (1.0, 1.0, 0.9)),
    ]:
        scene.frame_set(frame)
        core.scale = scale_values
        core.keyframe_insert(data_path="scale")

    # Add Cycles modifier to scale curves
    add_cycles_modifier(core, "scale")

    # Ring Orbit (each ring rotates at different speed)
    rot_speeds = [0.3, 0.5, 0.7, 1.0]  # Different speeds per ring

    for i, ring in enumerate(rings):
        ring.animation_data_create()
        ring_action = bpy.data.actions.new(name=f"Glyph_Idle_Ring_{i+1:02d}")
        ring.animation_data.action = ring_action

        rot_speed = rot_speeds[i % len(rot_speeds)]
        initial_rot_z = ring.rotation_euler[2]

        # Set keyframes for rotation
        scene.frame_set(1)
        ring.rotation_euler[2] = initial_rot_z
        ring.keyframe_insert(data_path="rotation_euler", index=2)

        scene.frame_set(120)
        ring.rotation_euler[2] = initial_rot_z + 2 * math.pi * rot_speed
        ring.keyframe_insert(data_path="rotation_euler", index=2)

        # Add Cycles modifier
        add_cycles_modifier(ring, "rotation_euler", array_index=2)

    # Reset to frame 1
    scene.frame_set(1)

    print("✓ Idle animation created (breathing, float, ring orbit)")


def setup_listening_animation(root, core, rings, eyes, brow):
    """Create Listening animation state (user focused on Glyph input).

    Looped: 120 frames (can use 90 frame period for faster bob).
    Visual: Slightly more attentive, leans in, brightens.
    """
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 120

    bpy.ops.object.mode_set(mode="OBJECT")

    # Root: Faster bob + tilt toward camera
    root.animation_data_create()
    root_action = bpy.data.actions.new(name="Glyph_Listening_Root")
    root.animation_data.action = root_action

    # Faster bob (90 frame period)
    scene.frame_set(1)
    root.location.z = 0.0
    root.rotation_euler = Euler((math.radians(5), 0, 0), "XYZ")  # Tilt forward
    root.keyframe_insert(data_path="location", index=2)
    root.keyframe_insert(data_path="rotation_euler", index=0)

    scene.frame_set(45)
    root.location.z = 0.05
    root.keyframe_insert(data_path="location", index=2)

    scene.frame_set(90)
    root.location.z = 0.0
    root.keyframe_insert(data_path="location", index=2)

    scene.frame_set(120)
    root.location.z = 0.05
    root.keyframe_insert(data_path="location", index=2)

    # Add Cycles modifier
    add_cycles_modifier(root, "location", array_index=2)
    add_cycles_modifier(root, "rotation_euler", array_index=0)

    # Core: Increased breathing amplitude (+10%)
    core.animation_data_create()
    core_action = bpy.data.actions.new(name="Glyph_Listening_Core")
    core.animation_data.action = core_action

    for frame, scale_values in [
        (1, (1.0, 1.0, 0.9)),
        (60, (1.033, 1.033, 0.93)),  # +10% amplitude
        (120, (1.0, 1.0, 0.9)),
    ]:
        scene.frame_set(frame)
        core.scale = scale_values
        core.keyframe_insert(data_path="scale")

    add_cycles_modifier(core, "scale")

    # Rings: Speed up (rot_speed * 1.2)
    rot_speeds = [0.36, 0.6, 0.84, 1.2]  # 1.2x Idle speeds

    for i, ring in enumerate(rings):
        ring.animation_data_create()
        ring_action = bpy.data.actions.new(name=f"Glyph_Listening_Ring_{i+1:02d}")
        ring.animation_data.action = ring_action

        rot_speed = rot_speeds[i % len(rot_speeds)]
        initial_rot_z = ring.rotation_euler[2]

        scene.frame_set(1)
        ring.rotation_euler[2] = initial_rot_z
        ring.keyframe_insert(data_path="rotation_euler", index=2)

        scene.frame_set(120)
        ring.rotation_euler[2] = initial_rot_z + 2 * math.pi * rot_speed
        ring.keyframe_insert(data_path="rotation_euler", index=2)

        add_cycles_modifier(ring, "rotation_euler", array_index=2)

    scene.frame_set(1)
    print("✓ Listening animation created")


def setup_thinking_animation(root, core, rings):
    """Create Thinking animation state (LLM processing).

    Looped: 120 frames.
    Visual: Focused, tighter motion, faster rings, compressed breathing.
    """
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 120

    bpy.ops.object.mode_set(mode="OBJECT")

    # Root: Reduced bob amplitude
    root.animation_data_create()
    root_action = bpy.data.actions.new(name="Glyph_Thinking_Root")
    root.animation_data.action = root_action

    scene.frame_set(1)
    root.location.z = 0.0
    root.keyframe_insert(data_path="location", index=2)

    scene.frame_set(60)
    root.location.z = 0.03  # Reduced from 0.05
    root.keyframe_insert(data_path="location", index=2)

    scene.frame_set(120)
    root.location.z = 0.0
    root.keyframe_insert(data_path="location", index=2)

    add_cycles_modifier(root, "location", array_index=2)

    # Core: Quicker, compressed breathing
    core.animation_data_create()
    core_action = bpy.data.actions.new(name="Glyph_Thinking_Core")
    core.animation_data.action = core_action

    # Oscillate between compressed and slightly expanded
    for frame, scale_values in [
        (1, (0.98, 0.98, 0.88)),
        (30, (1.02, 1.02, 0.92)),
        (60, (0.98, 0.98, 0.88)),
        (90, (1.02, 1.02, 0.92)),
        (120, (0.98, 0.98, 0.88)),
    ]:
        scene.frame_set(frame)
        core.scale = scale_values
        core.keyframe_insert(data_path="scale")

    add_cycles_modifier(core, "scale")

    # Rings: Double speed + optional tilt oscillation
    rot_speeds = [0.6, 1.0, 1.4, 2.0]  # 2x Idle speeds

    for i, ring in enumerate(rings):
        ring.animation_data_create()
        ring_action = bpy.data.actions.new(name=f"Glyph_Thinking_Ring_{i+1:02d}")
        ring.animation_data.action = ring_action

        rot_speed = rot_speeds[i % len(rot_speeds)]
        initial_rot_z = ring.rotation_euler[2]

        scene.frame_set(1)
        ring.rotation_euler[2] = initial_rot_z
        ring.keyframe_insert(data_path="rotation_euler", index=2)

        scene.frame_set(120)
        ring.rotation_euler[2] = initial_rot_z + 2 * math.pi * rot_speed
        ring.keyframe_insert(data_path="rotation_euler", index=2)

        # Optional: Small tilt oscillation
        if i % 2 == 0:  # Every other ring
            scene.frame_set(1)
            ring.rotation_euler[0] += math.radians(1)
            ring.keyframe_insert(data_path="rotation_euler", index=0)

            scene.frame_set(60)
            ring.rotation_euler[0] -= math.radians(2)
            ring.keyframe_insert(data_path="rotation_euler", index=0)

            scene.frame_set(120)
            ring.rotation_euler[0] += math.radians(1)
            ring.keyframe_insert(data_path="rotation_euler", index=0)

        # Add Cycles modifiers for all rotation axes
        add_cycles_modifier(ring, "rotation_euler", array_index=0)
        add_cycles_modifier(ring, "rotation_euler", array_index=2)

    scene.frame_set(1)
    print("✓ Thinking animation created")


def setup_responding_animation(root, core, rings):
    """Create Responding animation state (one-shot, ~30 frames).

    Visual: Quick "aha" pulse, then settle.
    """
    scene = bpy.context.scene
    duration = 30
    scene.frame_start = 1
    scene.frame_end = duration

    bpy.ops.object.mode_set(mode="OBJECT")

    # Root: Upward nudge
    root.animation_data_create()
    root_action = bpy.data.actions.new(name="Glyph_Responding_Root")
    root.animation_data.action = root_action

    scene.frame_set(1)
    root.location.z = 0.0
    root.keyframe_insert(data_path="location", index=2)

    scene.frame_set(10)
    root.location.z = 0.02
    root.keyframe_insert(data_path="location", index=2)

    scene.frame_set(30)
    root.location.z = 0.0
    root.keyframe_insert(data_path="location", index=2)

    # Core: Pulse
    core.animation_data_create()
    core_action = bpy.data.actions.new(name="Glyph_Responding_Core")
    core.animation_data.action = core_action

    scene.frame_set(1)
    core.scale = (1.0, 1.0, 0.9)
    core.keyframe_insert(data_path="scale")

    scene.frame_set(15)
    core.scale = (1.07, 1.07, 0.963)
    core.keyframe_insert(data_path="scale")

    scene.frame_set(30)
    core.scale = (1.0, 1.0, 0.9)
    core.keyframe_insert(data_path="scale")

    # Rings: Brief alignment
    for i, ring in enumerate(rings):
        ring.animation_data_create()
        ring_action = bpy.data.actions.new(name=f"Glyph_Responding_Ring_{i+1:02d}")
        ring.animation_data.action = ring_action

        initial_rot_z = ring.rotation_euler[2]
        # Align to multiples of 45 degrees for brief order
        target_rot = math.floor(initial_rot_z / (math.pi / 4)) * (math.pi / 4)

        scene.frame_set(1)
        ring.rotation_euler[2] = initial_rot_z
        ring.keyframe_insert(data_path="rotation_euler", index=2)

        scene.frame_set(12)
        ring.rotation_euler[2] = target_rot + (i * math.pi / 8)
        ring.keyframe_insert(data_path="rotation_euler", index=2)

        scene.frame_set(30)
        ring.rotation_euler[2] = initial_rot_z + 0.1  # Slight drift
        ring.keyframe_insert(data_path="rotation_euler", index=2)

    scene.frame_set(1)
    print("✓ Responding animation created")


def setup_success_animation(root, core, rings):
    """Create Success animation state (one-shot, 40-45 frames).

    Visual: Celebration pulse, rings form checkmark-like shape.
    """
    scene = bpy.context.scene
    duration = 45
    scene.frame_start = 1
    scene.frame_end = duration

    bpy.ops.object.mode_set(mode="OBJECT")

    # Root: Stronger upward motion
    root.animation_data_create()
    root_action = bpy.data.actions.new(name="Glyph_Success_Root")
    root.animation_data.action = root_action

    scene.frame_set(1)
    root.location.z = 0.0
    root.keyframe_insert(data_path="location", index=2)

    scene.frame_set(20)
    root.location.z = 0.07
    root.keyframe_insert(data_path="location", index=2)

    scene.frame_set(35)
    root.location.z = 0.02  # Overshoot
    root.keyframe_insert(data_path="location", index=2)

    scene.frame_set(45)
    root.location.z = 0.0
    root.keyframe_insert(data_path="location", index=2)

    # Core: Bigger pulse
    core.animation_data_create()
    core_action = bpy.data.actions.new(name="Glyph_Success_Core")
    core.animation_data.action = core_action

    scene.frame_set(1)
    core.scale = (1.0, 1.0, 0.9)
    core.keyframe_insert(data_path="scale")

    scene.frame_set(20)
    core.scale = (1.12, 1.12, 1.008)
    core.keyframe_insert(data_path="scale")

    scene.frame_set(45)
    core.scale = (1.0, 1.0, 0.9)
    core.keyframe_insert(data_path="scale")

    # Rings: Form checkmark-like shape at peak
    for i, ring in enumerate(rings):
        ring.animation_data_create()
        ring_action = bpy.data.actions.new(name=f"Glyph_Success_Ring_{i+1:02d}")
        ring.animation_data.action = ring_action

        initial_rot_z = ring.rotation_euler[2]

        scene.frame_set(1)
        ring.rotation_euler[2] = initial_rot_z
        ring.keyframe_insert(data_path="rotation_euler", index=2)

        # At peak (frame 20), arrange for checkmark silhouette
        if i < 2:
            # First two rings form the checkmark base
            scene.frame_set(20)
            ring.rotation_euler[2] = math.pi / 4 + (i * math.pi / 6)
            ring.keyframe_insert(data_path="rotation_euler", index=2)
        else:
            # Other rings align
            scene.frame_set(20)
            ring.rotation_euler[2] = math.pi / 3 + (i * math.pi / 8)
            ring.keyframe_insert(data_path="rotation_euler", index=2)

        scene.frame_set(45)
        ring.rotation_euler[2] = initial_rot_z + 0.2
        ring.keyframe_insert(data_path="rotation_euler", index=2)

    scene.frame_set(1)
    print("✓ Success animation created")


def setup_error_animation(root, core, rings, brow):
    """Create Error animation state (one-shot, 30 frames).

    Visual: Subtle shake, momentary dip, brow lowers.
    """
    scene = bpy.context.scene
    duration = 30
    scene.frame_start = 1
    scene.frame_end = duration

    bpy.ops.object.mode_set(mode="OBJECT")

    # Root: Side-to-side shake
    root.animation_data_create()
    root_action = bpy.data.actions.new(name="Glyph_Error_Root")
    root.animation_data.action = root_action

    scene.frame_set(1)
    root.location.x = 0.0
    root.rotation_euler = Euler((0, 0, 0), "XYZ")
    root.keyframe_insert(data_path="location", index=0)
    root.keyframe_insert(data_path="rotation_euler", index=2)

    scene.frame_set(5)
    root.location.x = -0.01
    root.rotation_euler.z = math.radians(-2)
    root.keyframe_insert(data_path="location", index=0)
    root.keyframe_insert(data_path="rotation_euler", index=2)

    scene.frame_set(10)
    root.location.x = 0.01
    root.rotation_euler.z = math.radians(2)
    root.keyframe_insert(data_path="location", index=0)
    root.keyframe_insert(data_path="rotation_euler", index=2)

    scene.frame_set(15)
    root.location.x = -0.005
    root.rotation_euler.z = math.radians(-1)
    root.keyframe_insert(data_path="location", index=0)
    root.keyframe_insert(data_path="rotation_euler", index=2)

    scene.frame_set(30)
    root.location.x = 0.0
    root.rotation_euler.z = 0.0
    root.keyframe_insert(data_path="location", index=0)
    root.keyframe_insert(data_path="rotation_euler", index=2)

    # Core: Momentary size dip
    core.animation_data_create()
    core_action = bpy.data.actions.new(name="Glyph_Error_Core")
    core.animation_data.action = core_action

    scene.frame_set(1)
    core.scale = (1.0, 1.0, 0.9)
    core.keyframe_insert(data_path="scale")

    scene.frame_set(8)
    core.scale = (0.96, 0.96, 0.864)
    core.keyframe_insert(data_path="scale")

    scene.frame_set(12)
    core.scale = (1.0, 1.0, 0.9)
    core.keyframe_insert(data_path="scale")

    scene.frame_set(30)
    core.scale = (1.0, 1.0, 0.9)
    core.keyframe_insert(data_path="scale")

    # Rings: Tiny jitter
    for i, ring in enumerate(rings):
        ring.animation_data_create()
        ring_action = bpy.data.actions.new(name=f"Glyph_Error_Ring_{i+1:02d}")
        ring.animation_data.action = ring_action

        initial_rot_z = ring.rotation_euler[2]

        scene.frame_set(1)
        ring.rotation_euler[2] = initial_rot_z
        ring.keyframe_insert(data_path="rotation_euler", index=2)

        scene.frame_set(8)
        ring.rotation_euler[2] = initial_rot_z + math.radians(5)
        ring.keyframe_insert(data_path="rotation_euler", index=2)

        scene.frame_set(12)
        ring.rotation_euler[2] = initial_rot_z - math.radians(3)
        ring.keyframe_insert(data_path="rotation_euler", index=2)

        scene.frame_set(30)
        ring.rotation_euler[2] = initial_rot_z
        ring.keyframe_insert(data_path="rotation_euler", index=2)

    # Brow: Lower
    brow.animation_data_create()
    brow_action = bpy.data.actions.new(name="Glyph_Error_Brow")
    brow.animation_data.action = brow_action

    initial_brow_z = brow.location.z

    scene.frame_set(1)
    brow.location.z = initial_brow_z
    brow.keyframe_insert(data_path="location", index=2)

    scene.frame_set(10)
    brow.location.z = initial_brow_z - 0.02
    brow.keyframe_insert(data_path="location", index=2)

    scene.frame_set(30)
    brow.location.z = initial_brow_z
    brow.keyframe_insert(data_path="location", index=2)

    scene.frame_set(1)
    print("✓ Error animation created")


def setup_sleep_animation(root, core, rings, eyes):
    """Create Sleep animation state (looped, 120 frames).

    Visual: Very slow, low-amplitude, dimmed feel.
    """
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 120

    bpy.ops.object.mode_set(mode="OBJECT")

    # Root: Very slow, low-amplitude bob
    root.animation_data_create()
    root_action = bpy.data.actions.new(name="Glyph_Sleep_Root")
    root.animation_data.action = root_action

    scene.frame_set(1)
    root.location.z = 0.0
    root.keyframe_insert(data_path="location", index=2)

    scene.frame_set(60)
    root.location.z = 0.02  # Low amplitude
    root.keyframe_insert(data_path="location", index=2)

    scene.frame_set(120)
    root.location.z = 0.0
    root.keyframe_insert(data_path="location", index=2)

    add_cycles_modifier(root, "location", array_index=2)

    # Core: Slower, smaller breathing
    core.animation_data_create()
    core_action = bpy.data.actions.new(name="Glyph_Sleep_Core")
    core.animation_data.action = core_action

    for frame, scale_values in [
        (1, (1.0, 1.0, 0.9)),
        (60, (1.01, 1.01, 0.909)),  # Very small amplitude
        (120, (1.0, 1.0, 0.9)),
    ]:
        scene.frame_set(frame)
        core.scale = scale_values
        core.keyframe_insert(data_path="scale")

    add_cycles_modifier(core, "scale")

    # Rings: Minimal orbit speed (20-30% of Idle)
    rot_speeds = [0.06, 0.1, 0.14, 0.2]  # ~20% of Idle speeds

    for i, ring in enumerate(rings):
        ring.animation_data_create()
        ring_action = bpy.data.actions.new(name=f"Glyph_Sleep_Ring_{i+1:02d}")
        ring.animation_data.action = ring_action

        rot_speed = rot_speeds[i % len(rot_speeds)]
        initial_rot_z = ring.rotation_euler[2]

        scene.frame_set(1)
        ring.rotation_euler[2] = initial_rot_z
        ring.keyframe_insert(data_path="rotation_euler", index=2)

        scene.frame_set(120)
        ring.rotation_euler[2] = initial_rot_z + 2 * math.pi * rot_speed
        ring.keyframe_insert(data_path="rotation_euler", index=2)

        add_cycles_modifier(ring, "rotation_euler", array_index=2)

    # Eyes: Move closer together (slit-like)
    for eye in eyes:
        eye.animation_data_create()
        eye_action = bpy.data.actions.new(name=f"Glyph_Sleep_{eye.name}")
        eye.animation_data.action = eye_action

        initial_x = eye.location.x
        initial_scale = eye.scale.x

        scene.frame_set(1)
        eye.location.x = initial_x
        eye.scale.x = initial_scale
        eye.keyframe_insert(data_path="location", index=0)
        eye.keyframe_insert(data_path="scale", index=0)

        scene.frame_set(60)
        # Move slightly toward center and shrink
        eye.location.x = initial_x * 0.7
        eye.scale.x = initial_scale * 0.8
        eye.keyframe_insert(data_path="location", index=0)
        eye.keyframe_insert(data_path="scale", index=0)

        scene.frame_set(120)
        eye.location.x = initial_x
        eye.scale.x = initial_scale
        eye.keyframe_insert(data_path="location", index=0)
        eye.keyframe_insert(data_path="scale", index=0)

        add_cycles_modifier(eye, "location", array_index=0)
        add_cycles_modifier(eye, "scale", array_index=0)

    scene.frame_set(1)
    print("✓ Sleep animation created")


def create_all_animation_states(root, core, rings, eyes, brow):
    """Create all 7 animation states for Glyph."""
    print("\n=== Creating Animation States ===")
    setup_idle_animation(root, core, rings)
    setup_listening_animation(root, core, rings, eyes, brow)
    setup_thinking_animation(root, core, rings)
    setup_responding_animation(root, core, rings)
    setup_success_animation(root, core, rings)
    setup_error_animation(root, core, rings, brow)
    setup_sleep_animation(root, core, rings, eyes)
    print("\n✓ All animation states created!")


def prepare_for_export():
    """Prepare Glyph for GLB/GLTF export.

    Sets up export-friendly state:
    - Ensures all objects are in correct collections
    - Sets frame range to cover all animations
    - Provides export checklist
    """
    scene = bpy.context.scene

    # Set frame range to cover longest animation (120 frames)
    scene.frame_start = 1
    scene.frame_end = 120

    # Ensure root is selected for export
    root = bpy.data.objects.get("ol_glyph_root")
    if root:
        bpy.context.view_layer.objects.active = root
        root.select_set(True)

    print("\n=== Export Preparation ===")
    print("✓ Frame range set: 1-120")
    print("✓ Root object selected")
    print("\nExport Checklist:")
    print("  1. File > Export > glTF 2.0 (.glb/.gltf)")
    print("  2. Include > Animations: ✓")
    print("  3. Transform > +Y Up: ✓")
    print("  4. Geometry > Apply Modifiers: ✓ (recommended)")
    print("  5. Animation > Always Sample Animations: ✓ (recommended)")
    print("\nAll Actions will be exported:")

    action_count = sum(
        1 for action in bpy.data.actions if action.name.startswith("Glyph_")
    )
    print(f"  - {action_count} animation actions found")

    return root


def create_glyph(create_animation=True, setup_render=True, all_states=False):
    """Main function to create the complete Glyph model.

    Args:
        create_animation: If True, create Idle animation state (or all states if all_states=True)
        setup_render: If True, configure Eevee render settings
        all_states: If True, create all 7 animation states (Idle, Listening, Thinking, etc.)
    """
    # Clear default cube if it exists
    if "Cube" in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects["Cube"], do_unlink=True)

    glyph_collection = create_glyph_collection()
    core_obj = create_glyph_core(glyph_collection)
    rings = create_glyph_rings(glyph_collection)
    eyes = create_glyph_eyes(glyph_collection)
    brow = create_glyph_brow(glyph_collection)
    materials = create_glyph_materials()
    assign_materials(core_obj, rings, eyes, brow, materials)
    root = create_glyph_root(glyph_collection, core_obj, rings, eyes, brow)

    if setup_render:
        setup_render_settings()

    if create_animation:
        if all_states:
            create_all_animation_states(root, core_obj, rings, eyes, brow)
        else:
            setup_idle_animation(root, core_obj, rings)

    print("\n✓ Glyph model created successfully!")
    print(f"  - Core: {core_obj.name}")
    print(f"  - Rings: {len(rings)}")
    print(f"  - Eyes: {len(eyes)}")
    print(f"  - Brow: {brow.name}")
    print(f"  - Root: {root.name}")

    return {
        "root": root,
        "core": core_obj,
        "rings": rings,
        "eyes": eyes,
        "brow": brow,
        "materials": materials,
    }


if __name__ == "__main__":
    create_glyph()
