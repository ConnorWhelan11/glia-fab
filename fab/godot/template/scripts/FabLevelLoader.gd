extends Node3D

@export var level_path: String = "res://assets/level.glb"
@export var player_scene: PackedScene = preload("res://scenes/Player.tscn")
@export var show_collider_meshes: bool = false
@export var show_trigger_meshes: bool = false


func _ready() -> void:
	var resource := load(level_path)
	if resource == null:
		push_error("FabLevelLoader: failed to load level: %s" % level_path)
		return
	if not (resource is PackedScene):
		push_error("FabLevelLoader: level is not a PackedScene: %s" % level_path)
		return

	var level_instance := (resource as PackedScene).instantiate()
	add_child(level_instance)

	_apply_fab_conventions(level_instance)


func _apply_fab_conventions(root: Node) -> void:
	var spawn := _find_first_spawn(root)
	_spawn_player(spawn)

	var collider_meshes := _find_marker_meshes(root, ["COLLIDER_", "OL_COLLIDER_"])
	for mesh in collider_meshes:
		_convert_mesh_to_static_collider(mesh)

	var trigger_meshes := _find_marker_meshes(root, ["TRIGGER_", "OL_TRIGGER_"])
	for mesh in trigger_meshes:
		_convert_mesh_to_trigger(mesh)

	var interact_nodes := _find_marker_nodes(root, ["INTERACT_", "OL_INTERACT_"])
	for node in interact_nodes:
		node.set_meta("fab_interact", true)


func _spawn_player(spawn_node: Node3D) -> void:
	var player := player_scene.instantiate()
	add_child(player)

	var t := Transform3D.IDENTITY
	if spawn_node != null:
		t = spawn_node.global_transform
	player.global_transform = t


func _find_first_spawn(root: Node) -> Node3D:
	var candidates := _find_marker_nodes(root, ["SPAWN_PLAYER", "OL_SPAWN_PLAYER"])
	if candidates.is_empty():
		return null
	var node := candidates[0]
	if node is Node3D:
		return node as Node3D
	return null


func _find_marker_nodes(root: Node, tokens: Array[String]) -> Array[Node]:
	var found: Array[Node] = []
	_walk(root, found, func(n: Node) -> bool:
		var upper := n.name.to_upper()
		for token in tokens:
			var t := token.to_upper()
			if upper == t or upper.begins_with(t + "_"):
				return true
		return false
	)
	return found


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
	body.global_transform = mesh_instance.global_transform

	var collision := CollisionShape3D.new()
	collision.shape = shape
	body.add_child(collision)

	mesh_instance.get_parent().add_child(body)
	mesh_instance.visible = show_collider_meshes


func _convert_mesh_to_trigger(mesh_instance: MeshInstance3D) -> void:
	if mesh_instance.mesh == null:
		return

	var shape := mesh_instance.mesh.create_trimesh_shape()
	if shape == null:
		return

	var area := Area3D.new()
	area.name = "Trigger_%s" % mesh_instance.name
	area.global_transform = mesh_instance.global_transform

	var collision := CollisionShape3D.new()
	collision.shape = shape
	area.add_child(collision)

	var trigger_script := load("res://scripts/FabTriggerArea.gd")
	if trigger_script != null:
		area.set_script(trigger_script)
		area.set("trigger_name", mesh_instance.name)

	mesh_instance.get_parent().add_child(area)
	mesh_instance.visible = show_trigger_meshes

