extends RefCounted
class_name NpcSpriteLoader

## SpriteFrames 辅助工具 — 从 PNG sheet 切帧，构建 SpriteFrames 资源
##
## 路径约定：
##   NPC 资源根目录：res://assets/npcs/<npc_id>/
##   idle PNG 位置：  res://assets/npcs/<npc_id>/baseline/sprite_idle.png
##   walk sheets 位置：res://assets/npcs/<npc_id>/（由 animation_spec.json 的 naming_convention 决定）
##
## 用法示例：
##   # 通用：animation_spec.json 驱动
##   var frames = NpcSpriteLoader.build_from_spec(npc_dir, spec_path)
##
##   # 带显式 idle 路径（推荐，绕过 naming_convention 与实际文件名的偏差）
##   var frames = NpcSpriteLoader.build_from_spec_with_idle(
##       npc_dir, spec_path,
##       "res://assets/npcs/admissions_director/baseline/sprite_idle.png"
##   )


## 从单个 PNG sheet 提取帧并填充 SpriteFrames
## texture_path: PNG 文件路径（res://...）
## hframes/vframes: sheet 网格列数/行数
## anim_name: 动画名称（"idle" / "walk_down" / "walk_up" 等）
## frame_rate_ms: 帧间隔（ms）；0 表示静态
## frame_indices: 要使用的帧序号数组
static func build_sprite_frames(
	texture_path: String,
	hframes: int,
	vframes: int,
	anim_name: String,
	frame_rate_ms: int,
	frame_indices: Array
) -> SpriteFrames:
	var frames := SpriteFrames.new()

	if texture_path.is_empty() or not ResourceLoader.exists(texture_path):
		frames.add_animation("idle")
		return frames

	var tex := load(texture_path) as Texture2D
	if tex == null:
		push_warning("[NpcSpriteLoader] 无法加载纹理: %s" % texture_path)
		frames.add_animation("idle")
		return frames

	frames.add_animation(anim_name)
	frames.set_animation_loop(anim_name, frame_rate_ms > 0)
	if frame_rate_ms > 0:
		frames.set_animation_speed(anim_name, 1000.0 / float(frame_rate_ms))

	for idx in frame_indices:
		var region := _frame_region(tex, hframes, vframes, idx)
		frames.add_frame(anim_name, region)

	return frames


## 从 PNG 计算单帧 AtlasTexture（列优先网格）
## tex: 已加载的 Texture2D
## hframes/vframes: 网格列数/行数
## frame_idx: 帧序号（列优先）
static func _frame_region(tex: Texture2D, hframes: int, vframes: int, frame_idx: int) -> AtlasTexture:
	var atlas := AtlasTexture.new()
	atlas.atlas = tex

	var img_size: Vector2 = tex.get_size()
	var fw := img_size.x / float(hframes) if hframes > 0 else img_size.x
	var fh := img_size.y / float(vframes) if vframes > 0 else img_size.y

	var col := frame_idx % hframes if hframes > 0 else 0
	var row := frame_idx / hframes if hframes > 0 else 0

	atlas.region = Rect2(col * fw, row * fh, fw, fh)
	atlas.filter_clip = true
	return atlas


## 从 animation_spec.json 驱动构建 SpriteFrames（通用版）
## npc_dir: res://assets/npcs/<npc_id>/
## spec_path: animation_spec.json 完整路径
## NOTE: idle 查找依赖 naming_convention.idle_sprite，默认 fallback 到 sprite_idle.png
static func build_from_spec(npc_dir: String, spec_path: String) -> SpriteFrames:
	var frames := SpriteFrames.new()
	frames.add_animation("idle")
	frames.add_animation("walk_down")
	frames.add_animation("walk_up")
	frames.add_animation("walk_left")
	frames.add_animation("walk_right")
	frames.add_animation("talk")

	if not ResourceLoader.exists(spec_path):
		push_warning("[NpcSpriteLoader] animation_spec.json 不存在: %s" % spec_path)
		return frames

	var file := FileAccess.open(spec_path, FileAccess.READ)
	if file == null:
		push_warning("[NpcSpriteLoader] 无法读取 spec: %s" % spec_path)
		return frames

	var json := JSON.new()
	if json.parse(file.get_as_text()) != OK:
		push_warning("[NpcSpriteLoader] JSON 解析失败: %s" % spec_path)
		return frames

	var spec: Dictionary = json.get_data()
	if not spec is Dictionary:
		return frames

	var naming: Dictionary = spec.get("naming_convention", {})
	var anims: Dictionary = spec.get("animations", {})
	var frame_count: Dictionary = spec.get("frame_count", {})
	var per_dir: int = frame_count.get("per_direction", 4)

	# idle: 优先使用 naming_convention 中的名称，fallback 到 sprite_idle.png
	var idle_name: String = naming.get("idle_sprite", "sprite_idle.png")
	var idle_tex_path := npc_dir + "/" + idle_name
	if not ResourceLoader.exists(idle_tex_path):
		idle_tex_path = npc_dir + "/sprite_idle.png"  # 尝试不带子目录
	if not ResourceLoader.exists(idle_tex_path):
		idle_tex_path = npc_dir + "/baseline/sprite_idle.png"  # 尝试 baseline/

	_try_add_idle_frames(frames, idle_tex_path, anims)

	# walk sheets（按 naming_convention 的 walk_sheet 模板构建路径）
	var walk_sheet_tpl: String = naming.get("walk_sheet", "{npc_id}_walk_{direction}.png")
	var directions: Array = naming.get("directions", ["down", "up", "left", "right"])
	for d in directions:
		var sheet_name: String = walk_sheet_tpl.replace("{direction}", d)
		var sheet_path := npc_dir + "/" + sheet_name
		_try_add_walk_frames(frames, sheet_path, d, per_dir, anims)

	# talk（复用 idle 帧）
	_try_add_talk_frames(frames, anims)

	return frames


## 显式指定 idle_path 的构建版本（推荐）
## idle_path: idle PNG 的完整 res:// 路径（如 baseline/sprite_idle.png）
static func build_from_spec_with_idle(
	npc_dir: String,
	spec_path: String,
	idle_path: String
) -> SpriteFrames:
	var frames := SpriteFrames.new()
	frames.add_animation("idle")
	frames.add_animation("walk_down")
	frames.add_animation("walk_up")
	frames.add_animation("walk_left")
	frames.add_animation("walk_right")
	frames.add_animation("talk")

	# idle：使用传入的显式路径
	_try_add_idle_frames(frames, idle_path, {})

	# walk sheets
	if ResourceLoader.exists(spec_path):
		var file := FileAccess.open(spec_path, FileAccess.READ)
		if file != null:
			var json := JSON.new()
			if json.parse(file.get_as_text()) == OK:
				var spec: Dictionary = json.get_data()
				if spec is Dictionary:
					var naming: Dictionary = spec.get("naming_convention", {})
					var anims: Dictionary = spec.get("animations", {})
					var frame_count: Dictionary = spec.get("frame_count", {})
					var per_dir: int = frame_count.get("per_direction", 4)
					var walk_sheet_tpl: String = naming.get("walk_sheet", "{npc_id}_walk_{direction}.png")
					var directions: Array = naming.get("directions", ["down", "up", "left", "right"])
					for d in directions:
						var sheet_name: String = walk_sheet_tpl.replace("{direction}", d)
						var sheet_path := npc_dir + "/" + sheet_name
						_try_add_walk_frames(frames, sheet_path, d, per_dir, anims)

	# talk
	_try_add_talk_frames(frames, {})

	return frames


## 内部：向 frames 添加 idle 帧
static func _try_add_idle_frames(frames: SpriteFrames, idle_path: String, anims: Dictionary) -> void:
	if not ResourceLoader.exists(idle_path):
		return
	var tex: Texture2D = load(idle_path)
	if tex == null:
		return
	var sz: Vector2 = tex.get_size()
	# 自动推断帧数：64px/帧
	var h: int = max(1, int(sz.x / 64.0))
	var v: int = max(1, int(sz.y / 64.0))
	var idle_cfg: Dictionary = anims.get("idle", {})
	var idle_frames: Array = idle_cfg.get("frames", range(h * v))
	for idx in idle_frames:
		var region := _frame_region(tex, h, v, idx)
		frames.add_frame("idle", region)


## 内部：向 frames 添加某个方向的 walk 帧
static func _try_add_walk_frames(
	frames: SpriteFrames,
	sheet_path: String,
	direction: String,
	per_dir: int,
	anims: Dictionary
) -> void:
	var anim_name := "walk_" + direction

	if ResourceLoader.exists(sheet_path):
		var tex: Texture2D = load(sheet_path)
		if tex != null:
			var walk_cfg: Dictionary = anims.get("walk", {})
			var walk_frames: Array = walk_cfg.get("frames", range(per_dir))
			for idx in walk_frames:
				var region := _frame_region(tex, per_dir, 1, idx)
				frames.add_frame(anim_name, region)
			return

	# 降级：walk sheet 不存在时复用 idle 帧
	var idle_count: int = frames.get_frame_count("idle")
	for i in range(mini(per_dir, idle_count)):
		frames.add_frame(anim_name, frames.get_frame("idle", i))


## 内部：向 frames 添加 talk 帧（复用 idle）
static func _try_add_talk_frames(frames: SpriteFrames, anims: Dictionary) -> void:
	var talk_cfg: Dictionary = anims.get("talk", {})
	if talk_cfg.is_empty():
		return
	var talk_frames: Array = talk_cfg.get("frames", [0, 1])
	var idle_count: int = frames.get_frame_count("idle")
	if idle_count == 0:
		return
	for i in range(mini(talk_frames.size(), idle_count)):
		frames.add_frame("talk", frames.get_frame("idle", i))


## 检查 NPC 是否有 sprite 资源
## 检查顺序：baseline/sprite_idle.png → sprite_idle.png
static func has_sprite(npc_dir: String) -> bool:
	var candidates := [
		npc_dir + "/baseline/sprite_idle.png",
		npc_dir + "/sprite_idle.png",
	]
	for p in candidates:
		if ResourceLoader.exists(p):
			return true
	# 检查 walk sheet（含 baseline/ 前缀）
	var npc_id := npc_dir.get_file()
	var walk_candidates := [
		npc_dir + "/baseline/" + npc_id + "_walk_down.png",
		npc_dir + "/baseline/" + npc_id + "_walk_up.png",
	]
	for p in walk_candidates:
		if ResourceLoader.exists(p):
			return true
	return false
