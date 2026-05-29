extends Area2D
class_name NPCController

## NPC 控制器 — G4: 任务状态指示器
##
## P3 新增：近程碰撞优化（距离门控）
## 详见 data/proximity_config.json

signal interacted(player: Player)

@export var npc_id: String = ""
@export var npc_name: String = "NPC"
@export var interaction_distance: float = 48.0

var is_interactable: bool = true
var interact_prompt: Label = null
var body_rect: ColorRect = null
var status_icon: Label = null
var _proximity_shape: CollisionShape2D = null

# 对话管理器 / 任务管理器引用
var dialogue_manager = null
var quest_manager = null
var _status_update_timer: float = 0.0

# ── P3 Proximity Optimization ─────────────────────────────────────────

# 硬线开关：true=跳过所有优化代码（紧急回滚用）
const OPTIMIZATION_BYPASS: bool = false

# 运行时配置（从 data/proximity_config.json 加载）
static var _p3_enabled: bool = false
static var _p3_radius: float = 200.0
static var _p3_interval_frames: int = 15
static var _p3_debug: bool = false

# 运行时状态
var _p3_player_ref: Node = null
var _p3_prox_active: bool = true        # NPC 当前是否在激活半径内
var _p3_prox_counter: int = 0
var _p3_initialized: bool = false       # 是否已完成初始化


func _ready() -> void:
	# ── 加载 P3 配置（首次调用触发静态加载）──
	if not _p3_initialized:
		_load_p3_config()
		_p3_initialized = true

	# 自动加载 NPC sprite
	_load_sprite()

	# 设置碰撞检测 — NPC 检测玩家（CharacterBody2D，layer 1）
	collision_mask = 1

	# ── CollisionShape2D ──
	# 不重复创建：检查是否已有 CollisionShape2D 子节点（NPCFactory 可能已添加）
	_proximity_shape = _find_existing_shape()
	if _proximity_shape == null:
		_proximity_shape = CollisionShape2D.new()
		_proximity_shape.shape = CircleShape2D.new()
		_proximity_shape.shape.radius = _p3_radius if _p3_enabled else 16.0
		add_child(_proximity_shape)
	
	# 配置了缩小形状时应用
	if _p3_enabled and not OPTIMIZATION_BYPASS:
		_proximity_shape.shape.radius = _p3_radius
	
	# P3 初始状态：如果是优化模式，所有 NPC 从 disabled 开始
	if _p3_enabled and not OPTIMIZATION_BYPASS:
		_proximity_shape.disabled = true
		_p3_prox_active = false
		if _p3_debug:
			print("[P3] NPC %s initialized with prox_disabled" % npc_id)
	else:
		_proximity_shape.disabled = false
		_p3_prox_active = true
	
	# 立即执行首次近程检查：玩家如果在附近，立刻启用形状
	if _p3_enabled and not OPTIMIZATION_BYPASS:
		_check_proximity_gate()
		# 首次检查后让计数器跳过交错延迟，后续仍正常交错
		_p3_prox_counter = _p3_interval_frames

	# 场景中的 BodyRect
	body_rect = $BodyRect as ColorRect
	if not body_rect:
		body_rect = ColorRect.new()
		body_rect.custom_minimum_size = Vector2(24, 24)
		body_rect.offset_left = -12
		body_rect.offset_top = -12
		body_rect.offset_right = 12
		body_rect.offset_bottom = 12
		body_rect.color = Color("#10b981")
		add_child(body_rect)
	
	# NPC 状态指示器 — G4
	status_icon = Label.new()
	status_icon.text = ""
	status_icon.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	status_icon.position = Vector2(-16, -60)
	status_icon.add_theme_font_size_override("font_size", 20)
	add_child(status_icon)
	
	interact_prompt = Label.new()
	interact_prompt.text = "按 E 交互"
	interact_prompt.visible = false
	interact_prompt.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	interact_prompt.vertical_alignment = VERTICAL_ALIGNMENT_BOTTOM
	interact_prompt.position = Vector2(-40, -40)
	interact_prompt.add_theme_font_size_override("font_size", 14)
	interact_prompt.add_theme_color_override("font_color", Color.WHITE)
	add_child(interact_prompt)
	
	body_entered.connect(_on_body_entered)
	body_exited.connect(_on_body_exited)


func _process(delta: float) -> void:
	# 更新交互提示位置
	if interact_prompt and interact_prompt.visible:
		interact_prompt.position = Vector2(-40, -50)
	
	# 每秒更新一次任务状态图标
	_status_update_timer += delta
	if _status_update_timer >= 1.0:
		_status_update_timer = 0.0
		_update_status_icon()
	
	# ── P3 Proximity Gate ──────────────────────────────────────────────
	if OPTIMIZATION_BYPASS or not _p3_enabled:
		return
	
	_p3_prox_counter += 1
	if _p3_prox_counter < _p3_interval_frames:
		return
	_p3_prox_counter = 0
	
	_check_proximity_gate()


# ── P3 Proximity Gating ───────────────────────────────────────────────

func _load_sprite() -> void:
	if npc_id == "":
		return
	var sprite_path := "res://assets/npcs/" + npc_id + "/sprite_idle.png"
	if not ResourceLoader.exists(sprite_path):
		push_warning("[NPC] Sprite not found: " + sprite_path)
		return
	var sprite = get_node_or_null("Sprite2D")
	if sprite == null:
		return
	sprite.texture = load(sprite_path)

func _load_p3_config() -> void:
	## 从 data/proximity_config.json 加载 P3 优化配置（仅加载一次）
	var file_path := "res://data/proximity_config.json"
	if not FileAccess.file_exists(file_path):
		# 配置文件不存在时使用默认值
		_p3_enabled = true
		_p3_radius = 200.0
		_p3_interval_frames = 15
		return
	
	var file := FileAccess.open(file_path, FileAccess.READ)
	if not file:
		_p3_enabled = true
		return
	
	var raw := file.get_as_text()
	file.close()
	
	var json := JSON.new()
	if json.parse(raw) != OK:
		_p3_enabled = true
		return
	
	var data = json.data
	var prox = data.get("proximity_optimization", {})
	
	_p3_enabled = bool(prox.get("enabled", true))
	_p3_radius = float(prox.get("activation_radius", 200.0))
	_p3_interval_frames = max(1, int(float(prox.get("check_interval_ms", 250)) / 16.0))
	_p3_debug = bool(prox.get("debug_log", false))
	
	if _p3_debug:
		print("[P3] Config loaded: enabled=%s radius=%.1f interval=%d frames" % [
			str(_p3_enabled), _p3_radius, _p3_interval_frames])


func _find_existing_shape() -> CollisionShape2D:
	## 检查子节点中是否已有 CollisionShape2D（NPCFactory 可能在 _ready 前已添加）
	for child in get_children():
		if child is CollisionShape2D:
			return child as CollisionShape2D
	return null


func _check_proximity_gate() -> void:
	## 距离门控：根据玩家距离启用/禁用碰撞形状
	if _p3_player_ref == null or not is_instance_valid(_p3_player_ref):
		_p3_player_ref = _find_player()
		if _p3_player_ref == null:
			return
	
	var dist_sq := global_position.distance_squared_to(_p3_player_ref.global_position)
	var threshold_sq := _p3_radius * _p3_radius
	
	if dist_sq > threshold_sq and _p3_prox_active:
		_proximity_shape.disabled = true
		_p3_prox_active = false
		# 如果之前显示了交互提示，远端 NPC 自动隐藏
		if interact_prompt and interact_prompt.visible:
			hide_interact_prompt()
		if _p3_debug:
			print("[P3] NPC %s → OUT (dist=%.1f > radius=%.1f)" % [npc_id, sqrt(dist_sq), _p3_radius])
		
	elif dist_sq <= threshold_sq and not _p3_prox_active:
		_proximity_shape.disabled = false
		_p3_prox_active = true
		if _p3_debug:
			print("[P3] NPC %s → IN (dist=%.1f <= radius=%.1f)" % [npc_id, sqrt(dist_sq), _p3_radius])


func _find_player() -> Node:
	## 查找当前场景中的玩家节点
	if Engine.is_editor_hint():
		return null
	return get_tree().get_first_node_in_group("player")


# ── Existing NPC logic (unchanged) ────────────────────────────────────

func _update_status_icon() -> void:
	if not status_icon or npc_id == "":
		return
	
	if not quest_manager:
		quest_manager = get_tree().get_first_node_in_group("quest_manager")
		if not quest_manager:
			return
	
	var quests = quest_manager.get_quests_for_npc(npc_id)
	if quests == null or quests.is_empty():
		status_icon.text = ""
		return
	
	var has_active = false
	var has_available = false
	var has_failed = false
	var all_done = true
	
	for quest in quests:
		var qid = quest.get("quest_id", "")
		var st = quest_manager.get_quest_status(qid)
		match st:
			"available": has_available = true
			"active": has_active = true
			"failed": has_failed = true
			_: pass
		if st != "completed":
			all_done = false
	
	if has_failed:
		status_icon.text = "⚠"
		status_icon.add_theme_color_override("font_color", Color("#ef4444"))
	elif has_active:
		status_icon.text = "?"
		status_icon.add_theme_color_override("font_color", Color("#2563eb"))
	elif has_available:
		status_icon.text = "!"
		status_icon.add_theme_color_override("font_color", Color("#f59e0b"))
	elif all_done:
		status_icon.text = "✓"
		status_icon.add_theme_color_override("font_color", Color("#10b981"))
	else:
		status_icon.text = ""

func _on_body_entered(body: Node) -> void:
	if body is Player:
		show_interact_prompt()

func _on_body_exited(body: Node) -> void:
	if body is Player:
		hide_interact_prompt()

func interact(player: Player) -> void:
	if not is_interactable:
		return
	
	interacted.emit(player)
	
	if dialogue_manager == null:
		dialogue_manager = get_tree().get_first_node_in_group("dialogue_manager")
	
	if dialogue_manager and dialogue_manager.has_method("show_dialogue"):
		dialogue_manager.show_dialogue(npc_id, npc_name)

func show_interact_prompt() -> void:
	if interact_prompt:
		interact_prompt.visible = true
		AudioManager.play_interact_prompt()
		var tween = create_tween()
		tween.tween_property(interact_prompt, "modulate:a", 1.0, 0.2)

func hide_interact_prompt() -> void:
	if interact_prompt:
		var tween = create_tween()
		tween.tween_property(interact_prompt, "modulate:a", 0.0, 0.2)
		await tween.finished
		interact_prompt.visible = false

func set_npc_id(id: String) -> void:
	npc_id = id

func set_npc_name(name: String) -> void:
	npc_name = name

func set_color(color: Color) -> void:
	if body_rect:
		body_rect.color = color