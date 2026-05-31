extends RefCounted
class_name StudentRepresentativeSprites

## student_representative SpriteFrames 资源
## 由 NpcFactory 在运行时加载，构造完整动画集
##
## 实际文件位置（baseline/ 子目录）：
##   sprite_idle.png               → res://assets/npcs/student_representative/baseline/sprite_idle.png
##   student_representative_walk_down.png 等  → res://assets/npcs/student_representative/
##
## animation_spec.json 的 naming_convention 字段仅供参考；
## 实际 idle 文件名固定为 sprite_idle.png（在 baseline/ 子目录）。

const NPC_DIR := "res://assets/npcs/student_representative"
const SPEC_PATH := "res://assets/npcs/student_representative/animation_spec.json"

## idle PNG 实际路径（baseline/ 子目录，固定名称）
const _IDLE_PATH := "res://assets/npcs/student_representative/baseline/sprite_idle.png"


## 返回预构建的 SpriteFrames
static func get_sprite_frames() -> SpriteFrames:
	return NpcSpriteLoader.build_from_spec_with_idle(
		NPC_DIR, SPEC_PATH, _IDLE_PATH
	)


## 检查是否有 sprite_idle.png（baseline/ 下）
static func has_sprites() -> bool:
	return ResourceLoader.exists(_IDLE_PATH)


## 返回 idle AtlasTexture（用于直接引用单帧）
static func get_idle_frame() -> AtlasTexture:
	if ResourceLoader.exists(_IDLE_PATH):
		var tex: Texture2D = load(_IDLE_PATH)
		if tex != null:
			var region := AtlasTexture.new()
			region.atlas = tex
			var sz: Vector2 = tex.get_size()
			region.region = Rect2(0, 0, sz.x, sz.y)
			region.filter_clip = true
			return region
	return _empty_atlas()


static func _empty_atlas() -> AtlasTexture:
	var a := AtlasTexture.new()
	a.filter_clip = true
	return a
