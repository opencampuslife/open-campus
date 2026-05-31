extends Node

var _music_volume: float = 0.8
var _sfx_volume: float = 0.9

func _ready():
	pass

func play_music(path: String, loop: bool = true):
	pass

func stop_music():
	pass

func play_sfx(path: String):
	pass

func play_interact_prompt():
	pass

func play_dialog_open():
	pass

func play_dialog_close():
	pass

func play_ui_click():
	pass

func play_quest_start():
	pass

func play_quest_complete():
	pass

func play_quest_fail():
	pass

func play_npc_footstep():
	pass

func set_music_volume(v: float):
	_music_volume = clamp(v, 0.0, 1.0)

func set_sfx_volume(v: float):
	_sfx_volume = clamp(v, 0.0, 1.0)

func get_music_volume() -> float:
	return _music_volume

func get_sfx_volume() -> float:
	return _sfx_volume