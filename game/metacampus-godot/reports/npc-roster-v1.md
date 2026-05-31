# MetaCampus MVP NPC Roster v1

> 8 个叙事 NPC 角色卡，覆盖全部 8 个 MVP 任务（T1–T8）

## 概览表

| # | NPC ID | 姓名 | 角色 | 位置 | 性格关键词 | 主要冲突 | 主指标 | 绑定任务 |
|---|--------|------|------|------|-----------|----------|--------|----------|
| 1 | `admissions_director` | 周明远 | 招生办主任 | admission_office | 严谨务实、耐心细致 | 效率与公平：名额有限，咨询量远超预期 | school_efficiency | T1 |
| 2 | `compliance_officer` | 林澈 | 合规专员 | compliance_office | 敏锐警觉、法条至上 | 智能与合规：AI越强越容易越界 | compliance_safety | T2 |
| 3 | `it_operator` | 许航 | IT运维 | server_room | 技术宅、有强迫症 | 创新与稳定：每次发布都可能影响全校 | system_stability | T7, T8 |
| 4 | `homeroom_teacher` | 陈芷 | 班主任 | teacher_office | 温柔干练、高度共情 | 理想与现实：想关心每个学生却被事务淹没 | school_efficiency | T4 |
| 5 | `logistics_manager` | 赵启山 | 后勤主管 | logistics_department | 粗中有细、雷厉风行 | 省钱与办好：预算有限但需求无穷 | school_efficiency | T5, T6 |
| 6 | `parent_representative` | 顾兰 | 家长代表 | reception_area | 热心积极、心思细腻 | 集体与个体：每个家庭需求各不相同 | parent_trust | T3 |
| 7 | `student_representative` | 沈一诺 | 学生代表 | classroom | 阳光开朗、有责任感 | 朋友与代表：同学期望和学校规则之间 | parent_trust | T4 |
| 8 | `principal` | 唐毓 | 校长 | principal_office | 大局观强、果敢决断 | 决策与责任：每一步要对三方负责 | school_efficiency | T7 |

## 任务覆盖矩阵

| 任务 | Quest ID | 主要 NPC | 辅助 NPC |
|------|----------|----------|----------|
| T1 家长招生咨询 | `q_admission_001` | 周明远 | — |
| T2 拦截高风险问题 | `q_admission_002` | 林澈 | — |
| T3 材料催办 | `q_material_reminder_001` | 顾兰 | — |
| T4 请假处理 | `q_leave_request_001` | 陈芷 | 沈一诺 |
| T5 订餐统计 | `q_meal_count_001` | 赵启山 | — |
| T6 报修工单 | `q_repair_order_001` | 赵启山 | — |
| T7 运营驾驶舱 | `q_dashboard_001` | 许航 | 唐毓 |
| T8 Canary发布 | `q_canary_release_001` | 许航 | — |

## 指标分布

| 指标 | 主负责 NPC | 次要 NPC |
|------|-----------|----------|
| school_efficiency | 周明远、陈芷、赵启山、唐毓 | 顾兰、沈一诺 |
| parent_trust | 顾兰、沈一诺 | 周明远、陈芷、唐毓 |
| compliance_safety | 林澈 | 许航、赵启山 |
| system_stability | 许航 | — |

## 角色关系图

```
唐毓 (校长)
  ├── 周明远 (招生办主任) ← 汇报招生数据
  ├── 林澈 (合规专员) ← 汇报合规风险
  ├── 许航 (IT运维) ← 部署运营驾驶舱
  ├── 陈芷 (班主任) ← 汇报班级情况
  └── 赵启山 (后勤主管) ← 汇报后勤数据

顾兰 (家长代表) → 周明远 ← 对接招生咨询
                  → 陈芷 ← 对接班级事务

沈一诺 (学生代表) → 陈芷 ← 反馈学生诉求
                  → 赵启山 ← 反馈后勤意见
```

## 文件清单

| 文件 | 路径 |
|------|------|
| NPC 1 | `data/npcs/npc_admissions_director.json` |
| NPC 2 | `data/npcs/npc_compliance_officer.json` |
| NPC 3 | `data/npcs/npc_it_operator.json` |
| NPC 4 | `data/npcs/npc_homeroom_teacher.json` |
| NPC 5 | `data/npcs/npc_logistics_manager.json` |
| NPC 6 | `data/npcs/npc_parent_representative.json` |
| NPC 7 | `data/npcs/npc_student_representative.json` |
| NPC 8 | `data/npcs/npc_principal.json` |

---

*版本: v1 | 日期: 2026-05-28 | 作者: Narrative Designer*
