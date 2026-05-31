extends CharacterBody2D
class_name Player

## 玩家角色控制器
## 支持四方向移动、碰撞检测、交互触发

signal interact_pressed
signal interact_released

@export var speed: float = 200.0  # 移动速度

var direction: Vector2 = Vector2.ZERO
var is_interacting: bool = false

# 节点引用
@onready var body_rect: ColorRect = $BodyRect
@onready var collision_shape: CollisionShape2D = $CollisionShape2D
@onready var interact_area: Area2D = $InteractArea
@onready var camera: Camera2D = $Camera2D

# 交互区域参考
var nearby_npc: Node2D = null
var nearby_interactable: Node2D = null

func _ready() -> void:
	# 设置碰撞层
	collision_layer = 1
	collision_mask = 2
	
	# 确保 Camera2D 正确设置
	if camera:
		camera.enabled = true
		camera.limit_left = 0
		camera.limit_top = 0
		camera.limit_right = 1280  # 40 tiles * 32
		camera.limit_bottom = 960   # 30 tiles * 32
	
	# 设置交互区域（NPC 是 Area2D，所以用 area_entered）
	if interact_area:
		interact_area.collision_mask = 1  # 检测 NPC（默认 layer 1）
		interact_area.area_entered.connect(_on_interact_area_area_entered)
		interact_area.area_exited.connect(_on_interact_area_area_exited)

func _physics_process(delta: float) -> void:
	# 获取输入方向
	direction = Vector2(
		Input.get_axis("move_left", "move_right"),
		Input.get_axis("move_up", "move_down")
	)
	
	# 归一化方向向量
	if direction.length() > 1:
		direction = direction.normalized()
	
	# 应用移动
	if direction != Vector2.ZERO:
		velocity = direction * speed
		# 根据方向更新精灵朝向
		_update_sprite_direction(direction)
	else:
		velocity = Vector2.ZERO
	
	# 碰撞检测移动
	move_and_slide()

func _process(_delta: float) -> void:
	# 处理交互输入
	if Input.is_action_just_pressed("interact"):
		interact_pressed.emit()
		_trigger_interact()
	elif Input.is_action_just_released("interact"):
		interact_released.emit()

func _update_sprite_direction(dir: Vector2) -> void:
	# ColorRect 不需要翻面，用颜色变化表示方向
	if body_rect:
		if dir.x > 0:
			body_rect.color = Color(0.14, 0.39, 0.92, 1)  # 蓝色-右
		elif dir.x < 0:
			body_rect.color = Color(0.92, 0.39, 0.14, 1)  # 橙色-左

func _on_interact_area_area_entered(area: Area2D) -> void:
	# 检测进入交互区域的 NPC 或可交互物体（NPC 是 Area2D）
	if area.has_method("interact"):
		nearby_npc = area
		nearby_interactable = area
		# 显示交互提示
		if area.has_method("show_interact_prompt"):
			area.show_interact_prompt()

func _on_interact_area_area_exited(area: Area2D) -> void:
	# 检测离开交互区域
	if area == nearby_npc:
		# 隐藏交互提示
		if area.has_method("hide_interact_prompt"):
			area.hide_interact_prompt()
		nearby_npc = null
		nearby_interactable = null

func _trigger_interact() -> void:
	# 触发交互
	if nearby_interactable and nearby_interactable.has_method("interact"):
		nearby_interactable.interact(self)

func set_enabled(enabled: bool) -> void:
	# 启用/禁用玩家控制
	set_physics_process(enabled)
	set_process(enabled)