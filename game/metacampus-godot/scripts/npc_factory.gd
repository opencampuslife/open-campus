extends Node

## NPC 工厂 — 根据 NPC profile 生成场景节点
##
## 使用方式：
##   var factory = NpcFactory.new()
##   var npc_node = factory.create_npc("principal")
##   add_child(npc_node)


## NPC sprite 资源脚本映射表（npc_id -> sprite builder class name）
const _SPRITE_SCRIPT_MAP: Dictionary = {
	"admissions_director": "AdmissionsDirectorSprites",
	"student_representative": "StudentRepresentativeSprites",
}

## NPC 资源根目录映射表（npc_id -> res://assets/npcs/<id>/baseline）
## 覆盖全部 8 个 NPC，确保 sprite 加载路径与 manifest 一致
## 注意：animation_spec.json 在 NPC root（不在 baseline/），_try_load_sprite_frames 会去掉 /baseline 后缀查找
const _NPC_ASSET_DIR: Dictionary = {
	"admissions_director":    "res://assets/npcs/admissions_director/baseline",
	"compliance_officer":     "res://assets/npcs/compliance_officer/baseline",
	"homeroom_teacher":       "res://assets/npcs/homeroom_teacher/baseline",
	"it_operator":            "res://assets/npcs/it_operator/baseline",
	"logistics_manager":     "res://assets/npcs/logistics_manager/baseline",
	"parent_representative":  "res://assets/npcs/parent_representative/baseline",
	"principal":              "res://assets/npcs/principal/baseline",
	"student_representative": "res://assets/npcs/student_representative/baseline",
}


## 根据 npc_id 从 NpcRegistry 读取 profile 并生成 Area2D 节点
## 返回 Node2D（实际为 Area2D/NPCController），失败返回 null
func create_npc(npc_id: String) -> NPCController:
	var profile: Dictionary = NpcRegistry.get_npc(npc_id)
	if profile.is_empty():
		push_warning("[NpcFactory] NPC 不存在: %s" % npc_id)
		return null

	var npc := _build_npc_node(profile)
	return npc


## 从 profile Dictionary 构建 NPC 节点
func _build_npc_node(profile: Dictionary) -> NPCController:
	var npc := NPCController.new()

	# 基础属性
	npc.npc_id = profile.get("npc_id", "")
	npc.npc_name = profile.get("display_name", "未命名 NPC")

	# 位置（默认 (0,0)，调用方自行设置）
	npc.position = Vector2.ZERO

	# 碰撞层
	npc.collision_layer = 4   # layer 3: npcs
	npc.collision_mask = 0    # NPC 自身不检测碰撞

	# 碰撞形状 — NPCController._ready() 已自动创建，这里不重复添加

	# --- 视觉层：优先使用 sprite，降级到 ColorRect ---
	_add_sprite_layer(npc, profile)

	# 名称标签
	var name_label := Label.new()
	name_label.text = npc.npc_name
	name_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	name_label.position = Vector2(-40, -55)
	name_label.add_theme_font_size_override("font_size", 12)
	npc.add_child(name_label)

	return npc


## 为 NPC 添加 sprite 层（AnimatedSprite2D），fallback 为 ColorRect
func _add_sprite_layer(npc: NPCController, profile: Dictionary) -> void:
	var npc_id: String = profile.get("npc_id", "")

	# 计算 npc_dir：优先用 profile.asset_root（manifest 格式），fallback 到硬编码短路径
	var npc_dir: String = profile.get("asset_root", "")
	if npc_dir.is_empty():
		npc_dir = _NPC_ASSET_DIR.get(npc_id, "")
	if npc_dir.is_empty():
		npc_dir = "res://assets/npcs/" + npc_id
	# 确保前缀为 res://
	if not npc_dir.begins_with("res://"):
		npc_dir = "res://" + npc_dir

	# 尝试加载 SpriteFrames
	var sprite_frames: SpriteFrames = _try_load_sprite_frames(npc_id, npc_dir)

	if sprite_frames != null and sprite_frames.get_animation_names().size() > 0:
		# --- 有 sprite：使用 AnimatedSprite2D ---
		var anim_sprite := AnimatedSprite2D.new()
		anim_sprite.sprite_frames = sprite_frames
		anim_sprite.centered = true
		# 锚点偏移：frame_size 64×64，anchor 在底部中心（32, 60）
		anim_sprite.offset = Vector2(-32, -60)
		anim_sprite.name = "AnimatedSprite2D"

		# 启动 idle 动画
		if sprite_frames.has_animation("idle"):
			anim_sprite.play("idle")
		else:
			var anims: Array = sprite_frames.get_animation_names()
			if anims.size() > 0:
				anim_sprite.play(anims[0])

		anim_sprite.animation_started.connect(_on_npc_animation_started)
		npc.add_child(anim_sprite)

		# 透明 BodyRect（供 NPCController.set_color 回退，但此时由 sprite 负责渲染）
		var body_rect := ColorRect.new()
		body_rect.custom_minimum_size = Vector2(24, 24)
		body_rect.offset_left = -12
		body_rect.offset_top = -12
		body_rect.offset_right = 12
		body_rect.offset_bottom = 12
		body_rect.color = Color(0, 0, 0, 0)  # 完全透明
		body_rect.name = "BodyRect"
		npc.add_child(body_rect)
		npc.body_rect = body_rect
	else:
		# --- 无 sprite：回退到 ColorRect（保持原有行为）---
		var body_rect := ColorRect.new()
		body_rect.custom_minimum_size = Vector2(24, 24)
		body_rect.offset_left = -12
		body_rect.offset_top = -12
		body_rect.offset_right = 12
		body_rect.offset_bottom = 12
		body_rect.color = _role_color(profile.get("role", ""))
		body_rect.name = "BodyRect"
		npc.add_child(body_rect)
		npc.body_rect = body_rect


## 尝试加载 NPC 的 SpriteFrames
## 优先级：专用 builder 类 > profile.asset_root + animation_spec.json + 显式 baseline/sprite_idle.png 路径
## npc_dir: 支持两种路径格式：
##   - 短路径：res://assets/npcs/<npc_id>（旧格式，兼容 2 个硬编码 NPC）
##   - 长路径：res://assets/npcs/<npc_id>/baseline（来自 profile.asset_root）
func _try_load_sprite_frames(npc_id: String, npc_dir: String) -> SpriteFrames:
	if npc_dir.is_empty():
		return null

	# 1. 优先用专用 builder 类（AdmissionsDirectorSprites / StudentRepresentativeSprites）
	var script_class_name: String = _SPRITE_SCRIPT_MAP.get(npc_id, "")
	if not script_class_name.is_empty():
		var builder_class = null
		match script_class_name:
			"AdmissionsDirectorSprites":
				builder_class = AdmissionsDirectorSprites
			"StudentRepresentativeSprites":
				builder_class = StudentRepresentativeSprites

		if builder_class != null and builder_class.has_sprites():
			return builder_class.get_sprite_frames()

	# 2. 降级：animation_spec.json + 显式 baseline/sprite_idle.png 路径
	# npc_dir 可能是 short 格式（res://assets/npcs/<id>）或 long 格式（res://assets/npcs/<id>/baseline）
	# animation_spec.json 在 NPC root（不在 baseline/），需要去掉可能的 /baseline 后缀
	var spec_dir: String = npc_dir
	if spec_dir.ends_with("/baseline"):
		spec_dir = spec_dir.substr(0, spec_dir.length() - len("/baseline"))

	var spec_path := spec_dir + "/animation_spec.json"

	# idle_path：优先用 npc_dir 本身（long 格式直接指向 baseline/），fallback 到显式路径
	var idle_path := npc_dir + "/sprite_idle.png"
	if not ResourceLoader.exists(idle_path):
		idle_path = spec_dir + "/baseline/sprite_idle.png"

	if ResourceLoader.exists(spec_path) or ResourceLoader.exists(idle_path):
		if ResourceLoader.exists(spec_path):
			var frames := NpcSpriteLoader.build_from_spec_with_idle(spec_dir, spec_path, idle_path)
			if frames.get_animation_names().size() > 0:
				return frames

	# 3. 最简降级：直接加载 idle_path
	return _build_fallback_frames(idle_path)


## 从单个 idle PNG 构建最简 SpriteFrames（最后一层降级）
func _build_fallback_frames(idle_path: String) -> SpriteFrames:
	var frames := SpriteFrames.new()
	frames.add_animation("idle")

	if not ResourceLoader.exists(idle_path):
		return frames

	var tex: Texture2D = load(idle_path)
	if tex == null:
		return frames

	var sz: Vector2 = tex.get_size()
	var h: int = max(1, int(sz.x / 64.0))
	var v: int = max(1, int(sz.y / 64.0))

	var temp_frames := NpcSpriteLoader.build_sprite_frames(
		idle_path, h, v, "_temp", 0, [0]
	)
	if temp_frames.get_frame_count("_temp") > 0:
		frames.add_frame("idle", temp_frames.get_frame("_temp", 0))
	return frames


## 根据角色返回视觉颜色（ColorRect fallback 用）
func _role_color(role: String) -> Color:
	var colors := {
		"校长": Color("#e74c3c"),
		"招生办主任": Color("#3498db"),
		"班主任": Color("#2ecc71"),
		"IT运维": Color("#9b59b6"),
		"后勤主管": Color("#f39c12"),
		"合规专员": Color("#1abc9c"),
		"家长代表": Color("#e67e22"),
		"学生代表": Color("#e91e63"),
	}
	return colors.get(role, Color("#10b981"))  # 默认绿色


## NPC 动画帧回调 — 用于触发脚步声音效
var _last_anim_name: String = ""

func _on_npc_animation_started() -> void:
	var sprite = get_node_or_null("AnimatedSprite2D") as AnimatedSprite2D
	if sprite == null:
		return
	var current_anim = sprite.animation
	var current_frame = sprite.frame
	# 每次 walk 方向变化时触发脚步声（第一帧）
	if current_anim.begins_with("walk") and current_frame == 0 and current_anim != _last_anim_name:
		_last_anim_name = current_anim
		AudioManager.play_npc_footstep()


## 批量创建 NPC — 返回 Dictionary[npc_id -> NPCController]
func create_all_npcs() -> Dictionary:
	var result: Dictionary = {}
	var all_profiles: Array = NpcRegistry.get_all_npcs()
	for profile in all_profiles:
		var npc_id: String = profile.get("npc_id", "")
		if npc_id.is_empty():
			continue
		var npc := _build_npc_node(profile)
		result[npc_id] = npc
	return result


## 按位置创建该位置的所有 NPC
func create_npcs_by_location(location: String) -> Array:
	var result: Array = []
	var profiles: Array = NpcRegistry.get_npcs_by_location(location)
	for profile in profiles:
		var npc := _build_npc_node(profile)
		result.append(npc)
	return result
