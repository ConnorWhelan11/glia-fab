@tool
extends EditorScenePostImport


func _post_import(scene: Node) -> Object:
	# Optional helper: converts marker meshes into collider/trigger nodes at import time.
	# To use: select a GLB in the FileSystem dock -> Import -> Post Import Script.
	_process_marker_meshes(scene)
	return scene


func _process_marker_meshes(root: Node) -> void:
	var collider_meshes := _find_marker_meshes(root, ["COLLIDER_", "OL_COLLIDER_"])
	for mesh in collider_meshes:
		_convert_mesh_to_static_collider(mesh)

	var trigger_meshes := _find_marker_meshes(root, ["TRIGGER_", "OL_TRIGGER_"])
	for mesh in trigger_meshes:
		_convert_mesh_to_trigger(mesh)


func _find_marker_meshes(root: Node, prefixes: Array[String]) -> Array[MeshInstance3D]:
	var found: Array[MeshInstance3D] = []
	_walk(root, found, func(n: Node) -> bool:
		if not (n is MeshInstance3D):
			return false
		var upper := n.name.to_upper()
		for prefix in prefixes:
			if upper.begins_with(prefix.to_upper()):
				return true
		return false
	)
	return found


func _walk(root: Node, out: Array, predicate: Callable) -> void:
	if predicate.call(root):
		out.append(root)
	for child in root.get_children():
		_walk(child, out, predicate)


func _convert_mesh_to_static_collider(mesh_instance: MeshInstance3D) -> void:
	if mesh_instance.mesh == null:
		return
	var shape := mesh_instance.mesh.create_trimesh_shape()
	if shape == null:
		return

	var body := StaticBody3D.new()
	body.name = "StaticCollider_%s" % mesh_instance.name
	body.transform = mesh_instance.transform

	var collision := CollisionShape3D.new()
	collision.shape = shape
	body.add_child(collision)

	mesh_instance.get_parent().add_child(body)


func _convert_mesh_to_trigger(mesh_instance: MeshInstance3D) -> void:
	if mesh_instance.mesh == null:
		return
	var shape := mesh_instance.mesh.create_trimesh_shape()
	if shape == null:
		return

	var area := Area3D.new()
	area.name = "Trigger_%s" % mesh_instance.name
	area.transform = mesh_instance.transform

	var collision := CollisionShape3D.new()
	collision.shape = shape
	area.add_child(collision)

	mesh_instance.get_parent().add_child(area)

