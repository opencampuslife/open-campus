# NPC Dialogue Stubs — 完成标记

**完成时间**: 2026-05-28 16:10 (Asia/Shanghai)

**产出物**:
- 8 个 NPC 对话包 (data/dialogues/<npc_id>_dialogues.json)
- 每个 NPC ≥ 2 个 dialogue entry
- 涉及合规风险的对话均含正确/错误分支
- metric_effects 全部在 ±10 ~ ±25 范围内

**对话包清单**:
| NPC ID | 名称 | 触发任务 | 条目数 |
|--------|------|---------|--------|
| admissions_director | 周明远 | q_admission_001, q_admission_002 | 2 |
| compliance_officer | 林澈 | q_admission_002 | 2 |
| homeroom_teacher | 陈芷 | q_leave_request_001 | 2 |
| it_operator | 许航 | q_dashboard_001, q_canary_release_001 | 2 |
| logistics_manager | 赵启山 | q_meal_count_001, q_repair_order_001 | 2 |
| parent_representative | 顾兰 | q_material_reminder_001, q_admission_002 | 2 |
| principal | 唐毓 | q_dashboard_001 | 2 |
| student_representative | 沈一诺 | q_leave_request_001 | 2 |

**验收确认**: ✅ JSON 格式验证通过 | ✅ metric_effects 范围验证通过 | ✅ 合规分支验证通过
