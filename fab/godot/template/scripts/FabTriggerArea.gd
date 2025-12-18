extends Area3D

@export var trigger_name: String = ""


func _ready() -> void:
	body_entered.connect(_on_body_entered)


func _on_body_entered(body: Node) -> void:
	if body is CharacterBody3D:
		print("Trigger entered: %s" % trigger_name)

