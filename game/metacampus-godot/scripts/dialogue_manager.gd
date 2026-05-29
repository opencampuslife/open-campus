extends CanvasLayer
class_name DialogueManager

## 对话管理器（扩展版）
## 管理对话框显示、对话数据加载、选项处理
## 支持 choices 分支，每个 choice 有 text/action/metric_effects
## action 触发后调用相应系统（quest_manager / metric_manager）

signal dialogue_started
signal dialogue_ended
signal choice_made(choice_data: Dictionary)

@export var dialogue_panel: Control = null
@export var name_label: Label = null
@export var text_label: Label = null
@export var choices_container: VBoxContainer = null
@export var prompt_label: Label = null

var is_dialogue_active: bool = false
var current_npc_id: String = ""
var current_npc_name: String = ""
var current_line_index: int = 0
var current_dialogue_data: Dictionary = {}
var player_ref: Node = null

# 对话数据（从 JSON 加载）
var dialogues_data: Dictionary = {}

func _ready() -> void:
	add_to_group("dialogue_manager")
	
	# 初始化 UI
	_setup_ui()
	_hide_dialogue()
	
	# 连接输入
	process_mode = Node.PROCESS_MODE_ALWAYS
	
	# 加载对话数据
	_load_dialogues()

func _load_dialogues() -> void:
	## 从 JSON 文件加载对话数据
	var json_loader = get_tree().get_first_node_in_group("json_loader")
	if not json_loader:
		push_warning("DialogueManager: JsonLoader not found in scene tree")
		return
	var data = json_loader.load_dialogues()
	var dialogues = data.get("dialogues", [])
	for dlg in dialogues:
		var npc_id = dlg.get("npc_id", "")
		if npc_id:
			dialogues_data[npc_id] = dlg

func _process(_delta: float) -> void:
	if is_dialogue_active:
		# ESC 关闭对话框
		if Input.is_action_just_pressed("ui_cancel"):
			close_dialogue()
		# 确认键/空格 继续对话或选择
		elif Input.is_action_just_pressed("ui_accept"):
			_advance_dialogue()

func _setup_ui() -> void:
	# 创建对话框 UI
	if not dialogue_panel:
		# 创建主面板
		dialogue_panel = Control.new()
		dialogue_panel.set_anchors_preset(Control.PRESET_BOTTOM_WIDE)
		dialogue_panel.offset_top = 500
		dialogue_panel.size_flags_vertical = Control.SIZE_SHRINK_END
		dialogue_panel.add_theme_stylebox_override("panel", StyleBoxFlat.new())
		add_child(dialogue_panel)
		
		# 名称标签
		name_label = Label.new()
		name_label.position = Vector2(20, 10)
		name_label.add_theme_font_size_override("font_size", 20)
		name_label.add_theme_color_override("font_color", Color("#10b981"))
		dialogue_panel.add_child(name_label)
		
		# 文本标签
		text_label = Label.new()
		text_label.position = Vector2(20, 50)
		text_label.size = Vector2(740, 120)
		text_label.autowrap_mode = TextServer.AUTOWRAP_WORD
		text_label.add_theme_font_size_override("font_size", 16)
		dialogue_panel.add_child(text_label)
		
		# 选项容器
		choices_container = VBoxContainer.new()
		choices_container.position = Vector2(20, 180)
		choices_container.add_theme_constant_override("separation", 8)
		dialogue_panel.add_child(choices_container)
		
		# 提示标签
		prompt_label = Label.new()
		prompt_label.anchor_right = 1.0
		prompt_label.anchor_bottom = 1.0
		prompt_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		prompt_label.vertical_alignment = VERTICAL_ALIGNMENT_BOTTOM
		prompt_label.offset_left = -150
		prompt_label.offset_top = -30
		prompt_label.offset_right = -20
		prompt_label.offset_bottom = -10
		prompt_label.text = "按 空格/Enter 继续  |  ESC 关闭"
		prompt_label.add_theme_color_override("font_color", Color("#888888"))
		prompt_label.add_theme_font_size_override("font_size", 12)
		dialogue_panel.add_child(prompt_label)
	
	# 应用样式
	_apply_dialogue_style()

func _apply_dialogue_style() -> void:
	# 设置对话框样式
	var style = StyleBoxFlat.new()
	style.bg_color = Color(0.1, 0.1, 0.15, 0.95)
	style.border_width_left = 2
	style.border_width_right = 2
	style.border_width_top = 2
	style.border_width_bottom = 2
	style.border_color = Color("#2563eb")
	style.corner_radius_top_left = 8
	style.corner_radius_top_right = 8
	style.corner_radius_bottom_left = 8
	style.corner_radius_bottom_right = 8
	style.content_margin_left = 20
	style.content_margin_right = 20
	style.content_margin_top = 20
	style.content_margin_bottom = 20
	
	dialogue_panel.add_theme_stylebox_override("panel", style)

func show_dialogue(npc_id: String, npc_name: String) -> void:
	# 显示对话
	if not dialogues_data.has(npc_id):
		push_warning("Dialogue not found for NPC: " + npc_id)
		return
	
	current_npc_id = npc_id
	current_npc_name = npc_name
	current_dialogue_data = dialogues_data[npc_id]
	# 跳过已完成的对话行（按 quest_id 判断）
	current_line_index = _find_first_available_line(current_dialogue_data)
	is_dialogue_active = true
	
	# 禁用玩家控制
	var player = get_tree().get_first_node_in_group("player")
	if player:
		player.set_enabled(false)
	
	AudioManager.play_dialog_open()
	dialogue_started.emit()
	
	# 如果没有可用的对话行，直接关闭
	if current_line_index < 0:
		close_dialogue()
		return
	
	_show_current_line()

func _find_first_available_line(dialogue_data: Dictionary) -> int:
	## 跳过 quest_id 已完成或已失败的对话行，返回第一个可显示的行索引
	## 返回 -1 表示没有可显示的行
	var lines = dialogue_data.get("lines", [])
	var quest_manager = get_tree().get_first_node_in_group("quest_manager")
	
	for i in range(lines.size()):
		var line = lines[i]
		var quest_id = line.get("quest_id", "")
		# 没有 quest_id 的行始终显示
		if quest_id == "":
			return i
		# 检查 quest 是否已完成/失败
		if quest_manager and quest_manager.has_method("get_quest_status"):
			var status = quest_manager.get_quest_status(quest_id)
			if status == "completed" or status == "failed":
				continue  # 跳过已终态的行
		return i
	
	return -1  # 所有行都已终态

func _show_current_line() -> void:
	if current_dialogue_data.is_empty() or current_line_index < 0:
		close_dialogue()
		return
	
	var lines = current_dialogue_data.get("lines", [])
	if current_line_index >= lines.size():
		close_dialogue()
		return
	
	var line_data = lines[current_line_index]
	
	# 显示说话者名字
	name_label.text = line_data.get("speaker", current_npc_name)
	
	# 显示对话文本
	text_label.text = line_data.get("text", "")
	
	# 启动关联任务
	var quest_id = line_data.get("quest_id", "")
	if quest_id:
		_start_quest_if_available(quest_id)
	
	# 显示选项
	_update_choices(line_data.get("choices", []))

func _start_quest_if_available(quest_id: String) -> void:
	## 如果任务处于 available 状态，启动它
	var quest_manager = get_tree().get_first_node_in_group("quest_manager")
	if quest_manager and quest_manager.has_method("start_quest"):
		var status = quest_manager.get_quest_status(quest_id)
		if status == "available" or status == "":
			quest_manager.start_quest(quest_id)

func _update_choices(choices: Array) -> void:
	# 清除旧选项
	for child in choices_container.get_children():
		child.queue_free()
	
	if choices.is_empty():
		# 无选项时显示继续提示
		prompt_label.text = "按 空格/Enter 继续  |  ESC 关闭"
	else:
		# 创建选项按钮
		prompt_label.text = "按 1-9 选择  |  ESC 关闭"
		
		for i in range(choices.size()):
			var choice = choices[i]
			var button = Button.new()
			button.text = "[%d] %s" % [i + 1, choice.get("text", "选项")]
			button.custom_minimum_size = Vector2(400, 40)
			button.pressed.connect(_on_choice_selected.bind(choice, i))
			choices_container.add_child(button)

func _on_choice_selected(choice: Dictionary, index: int) -> void:
	choice_made.emit(choice)
	
	# 应用指标效果
	var effects = choice.get("metric_effects", {})
	_apply_metric_effects(effects)
	
	# 处理任务完成/失败
	_handle_quest_action(choice)
	
	# 处理下一步
	var next_line = choice.get("next_line", -1)
	if next_line >= 0:
		current_line_index = next_line
		_show_current_line()
	else:
		close_dialogue()

func _handle_quest_action(choice: Dictionary) -> void:
	## 处理选择中的任务动作
	var quest_manager = get_tree().get_first_node_in_group("quest_manager")
	if not quest_manager:
		return
	
	# 完成任务
	var complete_quest = choice.get("complete_quest", "")
	if complete_quest and quest_manager.has_method("complete_quest"):
		quest_manager.complete_quest(complete_quest)
	
	# 完成任务2（用于连续完成多个任务）
	var complete_quest_2 = choice.get("complete_quest_2", "")
	if complete_quest_2 and quest_manager.has_method("complete_quest"):
		quest_manager.complete_quest(complete_quest_2)
	
	# 任务失败
	var fail_quest = choice.get("fail_quest", "")
	if fail_quest and quest_manager.has_method("fail_quest"):
		quest_manager.fail_quest(fail_quest)

func _advance_dialogue() -> void:
	# 继续对话（无选项时）
	var lines = current_dialogue_data.get("lines", [])
	if current_line_index < lines.size() - 1:
		current_line_index += 1
		_show_current_line()
	else:
		close_dialogue()

func _apply_metric_effects(effects: Dictionary) -> void:
	## 应用指标效果
	var metric_manager = get_tree().get_first_node_in_group("metric_manager")
	if metric_manager and metric_manager.has_method("apply_effects"):
		metric_manager.apply_effects(effects)

func close_dialogue() -> void:
	# 关闭对话框
	AudioManager.play_dialog_close()
	_hide_dialogue()
	is_dialogue_active = false
	
	# 恢复玩家控制
	var player = get_tree().get_first_node_in_group("player")
	if player:
		player.set_enabled(true)
	
	dialogue_ended.emit()

func _hide_dialogue() -> void:
	dialogue_panel.visible = false

func load_dialogues_from_file(path: String) -> bool:
	# 从 JSON 文件加载对话数据
	if not FileAccess.file_exists(path):
		push_warning("Dialogue file not found: " + path)
		return false
	
	var file = FileAccess.open(path, FileAccess.READ)
	if not file:
		return false
	
	var json_str = file.get_as_text()
	file.close()
	
	var json = JSON.new()
	if json.parse(json_str) != OK:
		push_error("Failed to parse dialogue JSON")
		return false
	
	# 转换为 npc_id -> dialogue 映射
	var data = json.data
	if data.has("dialogues"):
		for dlg in data["dialogues"]:
			var npc_id = dlg.get("npc_id", "")
			if npc_id:
				dialogues_data[npc_id] = dlg
	
	return true

func reload_dialogues() -> void:
	## 重新加载对话数据
	dialogues_data.clear()
	_load_dialogues()