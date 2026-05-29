extends Node

## NPC Persona Bridge — 连接 NPC persona 与 LLM Bridge
## 从 data/personas/<npc_id>.md 读取 persona 定义，生成 LLM system prompt
##
## 使用方式：
##   var prompt = NpcPersonaBridge.get_persona_prompt("principal")
##   # 发送到 LLM API


## Persona 文件目录
const PERSONA_DIR: String = "res://data/personas/"


## 获取指定 NPC 的 persona system prompt
## 返回完整的 LLM system prompt 字符串，文件不存在或读取失败返回空字符串
func get_persona_prompt(npc_id: String) -> String:
	var persona_text := _load_persona_md(npc_id)
	var profile := NpcRegistry.get_npc(npc_id)

	# 如果没有 persona 文件也没有 profile，返回空
	if persona_text.is_empty() and profile.is_empty():
		push_warning("[NpcPersonaBridge] 无 persona 数据和 profile: %s" % npc_id)
		return ""

	# 汇编 system prompt
	return _assemble_system_prompt(npc_id, profile, persona_text)


## 从 data/personas/<npc_id>.md 读取 persona 内容
func _load_persona_md(npc_id: String) -> String:
	var file_path := PERSONA_DIR + npc_id + ".md"
	if not FileAccess.file_exists(file_path):
		return ""

	var file := FileAccess.open(file_path, FileAccess.READ)
	if file == null:
		return ""

	var content := file.get_as_text()
	file.close()
	return content


## 汇编 system prompt（profile + persona 文件内容）
func _assemble_system_prompt(npc_id: String, profile: Dictionary, persona_text: String) -> String:
	var parts: Array[String] = []

	# 基本角色定义
	parts.append("你是 %s，一名 %s。" % [
		profile.get("display_name", npc_id),
		profile.get("role", "NPC")
	])

	# 性格
	var personality: Array = profile.get("personality", [])
	if not personality.is_empty():
		parts.append("性格特点：%s。" % ", ".join(personality))

	# 说话风格
	var voice_tone: String = profile.get("voice_tone", "")
	if not voice_tone.is_empty():
		parts.append("说话风格：%s" % voice_tone)

	# 核心冲突
	var core_conflict: String = profile.get("core_conflict", "")
	if not core_conflict.is_empty():
		parts.append("当前处境：%s" % core_conflict)

	# 与玩家的关系
	var player_rel: String = profile.get("player_relationship", "")
	if not player_rel.is_empty():
		parts.append("与玩家的关系：%s" % player_rel)

	# 禁止行为
	var forbidden: String = profile.get("forbidden_behavior", "")
	if not forbidden.is_empty():
		parts.append("禁止行为：%s" % forbidden)

	# 附加 persona 文件内容（如果有的话）
	if not persona_text.is_empty():
		parts.append("")
		parts.append("## 详细人格设定")
		parts.append(persona_text)

	# 全局规则
	parts.append("")
	parts.append("## 对话规则")
	parts.append("- 使用中文对话，保持角色一致性")
	parts.append("- 回复简洁，每次不超过 3 句话（除非玩家明确要求详细说明）")
	parts.append("- 涉及招生政策、合规问题时谨慎回答，不确定时引导玩家查阅官方文件")
	parts.append("- 记住与玩家的对话历史，保持连续性")

	return "\n\n".join(parts)


## 获取简化版 prompt（仅 profile，不含 persona 文件）
func get_short_prompt(npc_id: String) -> String:
	var profile := NpcRegistry.get_npc(npc_id)
	if profile.is_empty():
		return ""
	return _assemble_system_prompt(npc_id, profile, "")


## 批量获取所有 NPC 的 prompt（可用于预加载缓存）
func get_all_prompts() -> Dictionary:
	var result: Dictionary = {}
	for npc_id in NpcRegistry._npcs.keys():
		result[npc_id] = get_persona_prompt(npc_id)
	return result


## 检查指定 NPC 是否有 persona 文件
func has_persona_file(npc_id: String) -> bool:
	var file_path := PERSONA_DIR + npc_id + ".md"
	return FileAccess.file_exists(file_path)
