import bpy


def apply_style():
    # 1. Apply Floor Material
    mat_floor = bpy.data.materials.get("laminate_floor_02")
    obj_floor = bpy.data.objects.get("ol_floor")
    if obj_floor and mat_floor:
        if not obj_floor.data.materials:
            obj_floor.data.materials.append(mat_floor)
        else:
            obj_floor.data.materials[0] = mat_floor

        if not obj_floor.data.uv_layers:
            bpy.context.view_layer.objects.active = obj_floor
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.uv.smart_project()
            bpy.ops.object.mode_set(mode="OBJECT")

    # 2. Tint Shelves (Deep Desaturated Green/Navy)
    target_color = (0.102, 0.169, 0.2, 1.0)  # Roughly #1A2B33

    mat_shelf = bpy.data.materials.get("Shelf_01")
    if mat_shelf and mat_shelf.use_nodes:
        nodes = mat_shelf.node_tree.nodes
        links = mat_shelf.node_tree.links

        bsdf = next((n for n in nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf:
            if bsdf.inputs["Base Color"].is_linked:
                link = bsdf.inputs["Base Color"].links[0]
                orig_socket = link.from_socket

                tint_node = nodes.get("OL_Tint")
                if not tint_node:
                    tint_node = nodes.new("ShaderNodeMix")
                    tint_node.name = "OL_Tint"
                    tint_node.data_type = "RGBA"
                    tint_node.blend_type = "MULTIPLY"
                    tint_node.inputs["Factor"].default_value = 0.9
                    tint_node.inputs["B"].default_value = target_color

                    links.new(orig_socket, tint_node.inputs["A"])
                    links.new(tint_node.outputs["Result"], bsdf.inputs["Base Color"])

                    tint_node.location = (bsdf.location.x - 200, bsdf.location.y)

    # 3. Lamp Emission (Warm Amber)
    emission_color = (1.0, 0.77, 0.56, 1.0)
    emission_strength = 15.0

    mat_lamp = bpy.data.materials.get("desk_lamp_arm_01_light")
    if mat_lamp and mat_lamp.use_nodes:
        nodes = mat_lamp.node_tree.nodes
        bsdf = next((n for n in nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf:
            bsdf.inputs["Emission Color"].default_value = emission_color
            bsdf.inputs["Emission Strength"].default_value = emission_strength

    # 4. Create/Get Wall Material
    mat_wall = bpy.data.materials.get("ol_mat_wall")
    if not mat_wall:
        mat_wall = bpy.data.materials.new("ol_mat_wall")
        mat_wall.use_nodes = True
        nodes = mat_wall.node_tree.nodes
        bsdf = nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (0.8, 0.8, 0.75, 1.0)  # Warm grey
            bsdf.inputs["Roughness"].default_value = 0.8

    # Apply to Walls
    obj_walls = bpy.data.objects.get("ol_walls")
    if obj_walls:
        if not obj_walls.data.materials:
            obj_walls.data.materials.append(mat_wall)
        else:
            obj_walls.data.materials[0] = mat_wall

    # Apply to Pillars
    for obj in bpy.data.objects:
        if obj.name.startswith("ol_pillar_"):
            if not obj.data.materials:
                obj.data.materials.append(mat_wall)
            else:
                obj.data.materials[0] = mat_wall

    # Apply to Ceiling
    obj_ceil = bpy.data.objects.get("ol_ceiling")
    if obj_ceil:
        if not obj_ceil.data.materials:
            obj_ceil.data.materials.append(mat_wall)
        else:
            obj_ceil.data.materials[0] = mat_wall


if __name__ == "__main__":
    apply_style()
