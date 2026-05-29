# MetaCampus NPC 风格圣经 (NPC Style Bible)

> 版本：v1.0
> 日期：2026-05-28
> 作者：Narrative Designer
> 关联文档：art-style-guide.md v1.0, g2-acceptance.md, dialogues.json, npcs.json

---

## 一、世界观定位 (Worldview Positioning)

### 1.1 核心身份

MetaCampus 是一款 **校园 AI 运营模拟游戏**。玩家扮演校园 AI 管理员，在 2D cozy campus 场景中通过对话选择驱动校园运营指标变化。

| 维度 | 定义 |
|------|------|
| **空间** | 现代中国国际学校 / 教育科技校园 |
| **时间** | 近未来（AI 已深度融入校园运营） |
| **身份** | 校园 AI 管理员（非教师、非学生） |
| **玩法** | 对话选择 → 指标变化 → 任务完成 |
| **基调** | 温暖、专业、可信 |

### 1.2 NPC 角色定位

NPC 是 **校园运营场景中的交互对象**，不是可赠送物品/收集好感度的角色。每个 NPC 承载 1-3 个与校园运营相关的任务。

**现有 NPC 角色树**：

| npc_id | display_name | role | location | 颜色 |
|--------|-------------|------|----------|------|
| `parent_001` | 张同学家长 | 家长 | admission_office | #10b981 绿 |
| `teacher_admission_001` | 李招生老师 | 招生老师 | admission_office | #7c3aed 紫 |
| `teacher_class_001` | 王班主任 | 班主任 | academic_affairs | #7c3aed 紫 |
| `staff_logistics_001` | 陈后勤老师 | 后勤老师 | canteen | #f59e0b 橙 |
| `ai_assistant_001` | 小智AI助手 | AI助手 | ai_hub | #06b6d4 青 |

**角色扩展槽位**（未来可添加）：

| slot | role | suggested_location |
|------|------|-------------------|
| `student_*` | 学生 | school_gate / canteen |
| `parent_002` | 第二位家长 | admission_office |
| `teacher_*` | 学科老师 | academic_affairs |
| `admin_*` | 行政人员 | school_gate |
| `security_*` | 保安 | school_gate |

### 1.3 世界观禁止事项

| 禁止 | 说明 |
|------|------|
| 农场、牧场、矿洞 | MetaCampus 是教育科技校园，非乡村/田园 |
| 村庄模拟元素 | 不涉及村庄社区、市集交易 |
| Stardew Valley-like 元素 | 无作物种植、无钓鱼采集、无送礼好感动、无季节节日系统 |
| 奇幻/魔法元素 | 无魔法、无非科技超能力 |
| 战斗系统 | 无打斗、无HP、无敌人 |

---

## 二、角色视觉规范 (Character Visual Specification)

### 2.1 总体风格

- **2D cozy campus simulation style**：温暖、干净、可读性强
- **像素艺术**：低复杂度像素风，与 art-style-guide.md 一致
- **角色尺寸**：28×28 px（32×32 tile 内留 4px 阴影空间）
- **轮廓**：1px 深色描边，确保在俯视角地图上可辨识
- **颜色限制**：主色 + 1-2 辅助色，不超过 3 种颜色

### 2.2 角色颜色分配

| 角色类型 | 主色 | 色值 | 情感含义 |
|----------|------|------|----------|
| 家长 | 绿色 | #10b981 | 温和、信任、家庭感 |
| 教师 | 紫色 | #7c3aed | 学术、专业、权威 |
| 后勤 | 橙色 | #f59e0b | 热情、忙碌、效率 |
| AI 助手 | 青色 | #06b6d4 | 智能、未来、数据 |
| 学生 | 黄色 | #eab308 | 青春、活力、阳光 |
| 行政 | 蓝色 | #2563eb | 秩序、管理、冷静 |

### 2.3 角色体态与服装速查

| 角色 | 体态 | 服装 | 标识物 |
|------|------|------|--------|
| 家长 | 站立等候，轻微前倾 | 休闲装/正装 | 手提包 |
| 教师 | 站姿挺拔 | 教师制服 | 手持文件夹/平板 |
| 后勤 | 忙碌姿态，微侧身 | 工作服/马甲 | 工具包/对讲机 |
| AI 助手 | 悬浮/站立，略微发光 | 科技感服装 | 发光光环/徽章 |
| 学生 | 活泼站姿 | 校服 | 背包 |

### 2.4 Godot Sprite 可读性要求

| 要求 | 规范 |
|------|------|
| 导入模式 | 2D, Texture Filter: Nearest（像素风格） |
| 角色与背景对比度 | 主色与地面色差 ≥ 40% 亮度差 |
| 最小可辨识特征 | 角色在 28×28 范围内必须有可辨识的头部轮廓 |
| 方向性 | 四方向（上下左右），与玩家一致 |
| 动画帧 | MVP 阶段静态即可；完整版 3 帧/方向 |

---

## 三、表情规则 (Expression Rules)

### 3.1 四种表情定义

每个 NPC 必须配备 **4 种表情**，面部轮廓不变，仅眼、眉、嘴变化：

| 表情 | expression_id | 触发条件 | 眼 | 眉 | 嘴 |
|------|-------------|----------|----|----|-----|
| 普通 | `neutral` | 默认状态、无交互时 | 圆形或半圆 | 水平 | 直线或微弧 |
| 开心 | `happy` | 任务完成、指标上升 | 弯月形（上弧） | 弧形上挑 | 开口微笑弧 |
| 担心 | `worried` | 任务失败、指标下降 | 圆形稍大 | 八字眉（下斜） | 下弧或波浪 |
| 严肃 | `strict` | 合规警告、高风险对话 | 半眯眼 | 下压靠近眼 | 直线紧闭 |

### 3.2 表情设计原则

- **轮廓不变**：头部形状、发型、服装在四种表情间完全一致
- **仅变化五官**：只在眼、眉、嘴三个区域做像素级变化
- **变化量控制**：每种表情的五官偏移不超过 3px，确保切换自然
- **Godot 实现**：推荐使用 AnimatedSprite2D 或 SpriteFrames，4 帧对应 4 种表情

### 3.3 表情文件命名

```
assets/npcs/<npc_id>/
├── <npc_id>_neutral.png
├── <npc_id>_happy.png
├── <npc_id>_worried.png
├── <npc_id>_strict.png
└── <npc_id>_sprite.png          # 游戏内使用的行走/站立 sprite（可使用 neutral 替代）
```

---

## 四、命名规则 (Naming Conventions)

### 4.1 三要素命名体系

| 要素 | 格式 | 示例 | 约束 |
|------|------|------|------|
| **npc_id** | `snake_case` | `parent_001`, `teacher_class_001` | 全小写，下划线分隔，含角色类型前缀 + 序号 |
| **display_name** | 中文姓名 | `张同学家长`, `李招生老师` | 2-6 个中文字符，反映身份 |
| **location** | 英文场景标识 | `admission_office`, `canteen` | 必须与 locations.json 中 location_id 严格一致 |

### 4.2 npc_id 前缀规范

| 前缀 | 角色类型 | 示例 |
|------|----------|------|
| `parent_` | 家长 | `parent_001`, `parent_002` |
| `teacher_admission_` | 招生老师 | `teacher_admission_001` |
| `teacher_class_` | 班主任 | `teacher_class_001` |
| `teacher_` | 通用教师 | `teacher_math_001` |
| `staff_logistics_` | 后勤人员 | `staff_logistics_001` |
| `staff_` | 通用职员 | `staff_canteen_001` |
| `ai_assistant_` | AI 助手 | `ai_assistant_001` |
| `student_` | 学生 | `student_001` |
| `admin_` | 行政人员 | `admin_001` |
| `security_` | 保安 | `security_001` |

**编号规则**：
- 每个前缀从 `001` 开始递增
- 编号仅代表添加顺序，不代表重要性
- 已删除 NPC 的编号**不复用**

### 4.3 display_name 规范

- 必须使用中文姓名格式
- 家长：`X同学家长`（如 `张同学家长`）
- 教师：`X + 职务/学科 + 老师`（如 `李招生老师`、`王班主任`）
- 后勤：`X + 职务 + 老师`（如 `陈后勤老师`）
- AI 助手：可使用昵称（如 `小智AI助手`）
- 学生：`X同学`（如 `张同学`）
- 长度 2-6 个中文字符

### 4.4 location 规范

| location_id | 中文名 | 说明 |
|-------------|--------|------|
| `school_gate` | 校门 | 入口区域 |
| `admission_office` | 招生办 | 家长咨询、报名审核 |
| `academic_affairs` | 教务处 | 请假、成绩、考勤 |
| `canteen` | 食堂 | 订餐、报修 |
| `ai_hub` | AI 中枢 | 仪表盘、系统管理 |

**新增 location 时**：
1. 先在 `data/locations.json` 注册 `location_id`
2. NPC 的 `location` 字段必须引用已注册的 `location_id`
3. 命名格式：全小写 snake_case 英文

---

## 五、资产目录结构 (Asset Directory Structure)

### 5.1 NPC 资产根目录

```
assets/npcs/
├── _common/                       # 共享资源
│   ├── shadow.png                 # 通用阴影 (4px, 30% 透明度)
│   └── indicator_templates/       # 交互提示模板
│       ├── interact_default.png
│       ├── quest_active.png
│       └── quest_complete.png
│
├── parent_001/                    # 张同学家长
│   ├── portrait.png               # 对话头像 (64×64 或更大)
│   ├── parent_001_neutral.png     # 普通表情
│   ├── parent_001_happy.png      # 开心表情
│   ├── parent_001_worried.png    # 担心表情
│   ├── parent_001_strict.png     # 严肃表情
│   ├── parent_001_sprite.png     # 地图行走 sprite (28×28)
│   ├── parent_001_sprite_down.png  # 下方向 (可选，若不同于默认)
│   ├── parent_001_sprite_up.png    # 上方向 (可选)
│   ├── parent_001_sprite_left.png  # 左方向 (可选)
│   ├── parent_001_sprite_right.png # 右方向 (可选)
│   └── parent_001_prompt.md      # 角色 prompt 文件
│
├── teacher_admission_001/         # 李招生老师
│   ├── portrait.png
│   ├── teacher_admission_001_neutral.png
│   ├── teacher_admission_001_happy.png
│   ├── teacher_admission_001_worried.png
│   ├── teacher_admission_001_strict.png
│   ├── teacher_admission_001_sprite.png
│   └── teacher_admission_001_prompt.md
│
├── teacher_class_001/             # 王班主任
│   └── ... (同上)
│
├── staff_logistics_001/           # 陈后勤老师
│   └── ... (同上)
│
└── ai_assistant_001/              # 小智AI助手
    └── ... (同上)
```

### 5.2 文件命名总则

| 文件 | 命名格式 | 示例 |
|------|----------|------|
| 头像 | `portrait.png` | 固定名称，位于 `<npc_id>/` 下 |
| 表情 | `<npc_id>_<expression>.png` | `parent_001_neutral.png` |
| 地图 sprite | `<npc_id>_sprite.png` | `parent_001_sprite.png` |
| 方向 sprite | `<npc_id>_sprite_<direction>.png` | `parent_001_sprite_down.png` |
| Prompt 文件 | `<npc_id>_prompt.md` | `parent_001_prompt.md` |

### 5.3 Prompt 文件模板

每个 NPC 目录下的 `_prompt.md` 必须包含：

```markdown
# <display_name> - Character Prompt

## Identity
- npc_id: <npc_id>
- display_name: <display_name>
- role: <角色类型>
- location: <location>

## Personality
<2-3 句角色性格描述>

## Knowledge Domains
<该 NPC 涉及的知识领域>

## Quest Bindings
- <quest_id>: <一句话说明>

## Safety Boundaries
<该 NPC 特有的安全边界，如有>
```

### 5.4 Godot 场景目录对应

```
scenes/NPCs/
├── NPCBase.tscn                   # NPC 基础场景（可继承）
├── Parent001.tscn                 # 张同学家长实例
├── TeacherAdmission001.tscn       # 李招生老师实例
├── TeacherClass001.tscn           # 王班主任实例
├── StaffLogistics001.tscn         # 陈后勤老师实例
└── AIAssistant001.tscn            # 小智AI助手实例
```

场景命名规则：PascalCase，与 npc_id 对应（下划线转驼峰）。

---

## 六、JSON 数据规范 (JSON Data Specification)

### 6.1 NPC Profile 完整 Schema

每个 `data/npcs.json` 中的 NPC profile **必须**包含以下字段：

```json
{
  "npc_id": "string (必填, snake_case)",
  "name": "string (必填, 中文 display_name)",
  "role": "string (必填, 中文角色类型: 家长/招生老师/班主任/后勤老师/AI助手/学生)",
  "location": "string (必填, 英文 location_id, 必须存在于 locations.json)",
  "sprite": "string (必填, 对应 assets/npcs/<npc_id>/ 下的 sprite 文件名无扩展名)",
  "dialogue_id": "string (必填, 对应 dialogues.json 中的对话引用)",
  "quest_ids": ["string (必填, 至少 1 个, 关联的任务 ID 列表)"],
  "metric_effects": "object (必填, 该 NPC 交互默认的指标影响基线)",
  "indicator_tint": "string (必填, 角色颜色十六进制, 用于交互提示和 UI)"
}
```

### 6.2 metric_effects 字段规范

**每个 NPC profile 必须显式声明 `metric_effects`**。该字段定义与此 NPC 交互时默认的指标影响基线（具体对话选项可能覆盖此基线）。

格式：
```json
"metric_effects": {
  "school_efficiency": 0,
  "parent_trust": 0,
  "compliance_safety": 0,
  "system_stability": 0
}
```

**规则**：
- 四个指标键必须全部出现，值可以为 0
- 值范围 -100 到 +100
- 此字段是**基线声明**，实际效果由对话选项的 `metric_effects` 决定
- **即使是纯信息型 NPC（无指标变化），也必须包含此字段（全部为 0）**

### 6.3 quest_ids 字段规范

```json
"quest_ids": ["q_admission_001", "q_admission_002"]
```

**规则**：
- 必须为数组，至少包含 1 个有效 quest_id
- 每个 quest_id 必须存在于 `data/quests.json`
- 任务顺序按数组顺序排列（对话中依次触发）
- 不得包含不存在的 quest_id（会导致运行时错误）

### 6.4 数据一致性校验清单

新 NPC 上线前必须通过以下校验：

| # | 检查项 | 校验方式 |
|---|--------|----------|
| 1 | npc_id 存在于 npcs.json | 文件存在检查 |
| 2 | location 存在于 locations.json | 引用完整性 |
| 3 | quest_ids 全部存在于 quests.json | 引用完整性 |
| 4 | metric_effects 包含全部 4 个指标键 | 结构完整性 |
| 5 | 对话数据存在于 dialogues.json | 引用完整性 |
| 6 | sprite 文件存在于 assets/npcs/<npc_id>/ | 资产完整性 |
| 7 | 4 种表情文件存在 | 资产完整性 |
| 8 | indicator_tint 为有效 hex 颜色 | 格式验证 |

---

## 七、Persona 安全规则 (Persona Safety Rules)

### 7.1 三大禁止承诺

| 禁止 | 说明 | 示例 |
|------|------|------|
| **不得承诺录取** | 任何 NPC 不得暗示或担保录取结果 | "保证录取" / "包进" → 绝对禁止 |
| **不得绕过合规** | 不得暗示可以绕过学校规定或教育部门监管 | "特殊渠道" / "内部操作" → 绝对禁止 |
| **不得编造法规** | 不得编造不存在的教育政策、法规、招生条例 | 引用真实政策必须标注来源 |

### 7.2 对话安全边界

| 场景 | 安全回应 | 触发风险标记 |
|------|----------|-------------|
| 家长要求保证录取 | "不能承诺录取，请联系招生办确认" | 系统标记 T2 高风险对话 |
| 家长暗示找关系 | 转人工处理，不正面回应 | 合规安全指标下降 |
| 涉及学生隐私 | 拒绝查询，转合规审查 | 系统记录访问日志 |
| 教育政策咨询 | 引用已审核的知识库内容 | 标注"仅供参考" |

### 7.3 NPC 角色安全约束

| NPC 类型 | 额外安全约束 |
|----------|-------------|
| **AI 助手** | 不得模拟人类情感深度共情（保持 AI 身份），不得伪装成人类 |
| **教师** | 不得给出个人联系方式，不得私下承诺 |
| **后勤** | 不得透露学生个人信息，不得泄露校园安保细节 |
| **家长** | 作为 NPC 提出问题的合理边界：仅限校园服务相关 |

### 7.4 敏感词库（开发参考）

以下词汇应在对话系统中触发预警或拦截：

| 类别 | 示例词 |
|------|--------|
| 录取承诺 | 保证录取、包进、走后门、内部名额 |
| 隐私泄露 | 学号、身份证号、家庭住址、家长电话 |
| 违规操作 | 改分、代签、造假、绕过系统 |
| 歧视性用语 | 笨蛋、差生、问题学生 |

---

## 八、禁止事项 — Hard Rules

### 8.1 绝对禁止

| # | 禁止项 | 原因 | 检查方式 |
|---|--------|------|----------|
| 1 | **Stardew Valley-like 元素** | 世界观不符：校园非农场 | 设计审核 |
| 2 | **版权角色** | 法律风险：不得使用有版权保护的动漫/游戏/影视角色形象 | 资产审核 |
| 3 | **第三方参考资料** | 不引用外部 IP 角色作为设计参考 | Prompt 审核 |
| 4 | **真实人物形象** | 所有 NPC 均为像素风格原创角色 | 资产审核 |
| 5 | **承诺录取类对话选项** | 合规红线：游戏核心教育目标是"可信AI" | JSON 字段自动检查 |
| 6 | **绕过合规的对话路径** | 不得设计"先违规再补救"的正向奖励路径 | 对话树审核 |
| 7 | **未经审核的第三方素材** | 所有美术资源必须原创或使用开源许可 | 资产审核 |

### 8.2 设计禁区

| 禁区 | 替代方案 |
|------|----------|
| NPC 赠送礼物系统 | 对话选择驱动指标变化（已有） |
| 好感度数值化 | 用 parent_trust 指标替代 |
| 季节节日特殊对话 | 不做 Stardew-like 日历系统 |
| NPC 日程/作息表 | 不做动态 NPC 路径（MVP 阶段静态站位） |
| 浪漫/恋爱线 | 绝对不涉及 |

---

## 九、现有 NPC 审计 (Current NPC Audit)

### 9.1 覆盖状态

| npc_id | npcs.json | dialogues.json | quest_ids | metric_effects | 表情资产 |
|--------|-----------|---------------|-----------|---------------|----------|
| `parent_001` | ✅ | ✅ | ✅ (3 quests) | ❌ 缺失 | ❌ |
| `teacher_admission_001` | ✅ | ✅ | ✅ (1 quest) | ❌ 缺失 | ❌ |
| `teacher_class_001` | ✅ | ✅ | ✅ (1 quest) | ❌ 缺失 | ❌ |
| `staff_logistics_001` | ✅ | ✅ | ✅ (2 quests) | ❌ 缺失 | ❌ |
| `ai_assistant_001` | ✅ | ✅ | ✅ (2 quests) | ❌ 缺失 | ❌ |

### 9.2 待修复项

1. **所有 npcs.json 条目缺少 `metric_effects` 字段** — 必须补充
2. **dialogues.json 中存在未注册 NPC** — `canteen_staff`（食堂张阿姨）和 `academic_affairs`（教务处王主任）未出现在 npcs.json 中，需注册或清理
3. **所有 NPC 缺少表情资产** — 需按本文档第 3 章和第 5 章补充
4. **所有 NPC 缺少 prompt 文件** — 需按本文档第 5.3 节模板创建

### 9.3 修正后的 npcs.json 示例

```json
{
  "npc_id": "parent_001",
  "name": "张同学家长",
  "role": "家长",
  "location": "admission_office",
  "sprite": "parent_001_sprite",
  "dialogue_id": "dlg_admission_001",
  "quest_ids": ["q_admission_001", "q_admission_002", "q_material_reminder_001"],
  "metric_effects": {
    "school_efficiency": 0,
    "parent_trust": 0,
    "compliance_safety": 0,
    "system_stability": 0
  },
  "indicator_tint": "#10b981"
}
```

---

## 十、附录

### A. 新增 NPC 上架流程

```
1. 确定角色定位 → 2. 分配 npc_id → 3. 注册到 npcs.json → 4. 创建对话数据到 dialogues.json
→ 5. 创建 quest 到 quests.json → 6. 创建资产目录 → 7. 绘制 sprite + 4 表情 + portrait
→ 8. 编写 prompt.md → 9. 创建 Godot 场景 → 10. 跑数据一致性校验（第 6.4 节）
```

### B. 关联文档索引

| 文档 | 路径 | 相关章节 |
|------|------|----------|
| 美术规格指南 | `docs/art-style-guide.md` | 角色颜色、像素规格 |
| G2 验收清单 | `docs/g2-acceptance.md` | NPC 交互验收 |
| 演示路线 | `docs/demo-route.md` | NPC 出场顺序 |
| NPC 数据 | `data/npcs.json` | 角色数据 |
| 对话数据 | `data/dialogues.json` | 对话树 |
| 任务数据 | `data/quests.json` | 任务定义 |
| 位置数据 | `data/locations.json` | 场景定义 |

### C. 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-05-28 | 初始发布：世界观、视觉规范、表情规则、命名规则、资产目录、JSON 规范、安全规则、Hard Rules |

---

*本文档为 MetaCampus 2D 游戏的 NPC 设计与实现权威参考。所有 NPC 相关决策必须以本文档为准。*
*新增 NPC 或修改现有 NPC 数据时，必须同步更新本文档的审计章节。*

---

## 十一、视觉深化规范 — AI 生图用途 (Visual Deep Spec v1.1)

> 版本：v1.1 (追加于 2026-05-28)
> 用途：为 AI 图像/视频生成提供精确关键词和参数，补充第二章的像素风格基础规范。
> 与第二章的关系：本章为**深化版**，提供更精确的尺寸、比例、色板，用于 prompt 工程。第二章的 28×28 基础 sprite 规范仍适用于 MVP 阶段手工绘制的像素 sprite。

### 11.1 角色比例规范 (Character Proportions)

| 参数 | 规范 | 说明 |
|------|------|------|
| **整体身高** | 64px（sprite 全高） | 从头顶到脚底，不含阴影 |
| **头身比** | 1:4 | 头部约占整体身高的 1/4，即 16px |
| **头部尺寸** | 16×14 px | 宽 14px，高 16px（含发型则 16×18） |
| **躯干** | 20px | 肩到腰 |
| **腿部** | 28px | 腰到脚底 |
| **描边** | 1px 深色 | #1A1A2E 或深于主色的对比色 |
| **阴影** | 4px 底部柔边 | 20% 透明度椭圆，不随动画帧变化 |

```
比例示意（侧视图）：
  ┌── 头顶 (y=0)
  │   ■ 头部 16px (1/4)
  ├── 颈部 (y=16)
  │   │ 躯干 20px
  ├── 腰部 (y=36)
  │   │ 腿 28px
  └── 脚底 (y=64)
  ~~~ 阴影 4px (y=64~68)
```

### 11.2 立绘规格 (Portrait Specifications)

| 参数 | 规范 |
|------|------|
| **画布尺寸** | 256×256 px |
| **角色占比** | 占画布 70-80%，居中偏上 |
| **视角** | 正面 (front-facing) 或 3/4 侧视角 (three-quarter view) |
| **背景** | 透明 PNG，或纯色 #F5E6D3（暖白）作为占位背景 |
| **风格** | 现代像素插画 (modern pixel art)，非 8-bit 复古 |
| **线条** | 清晰 1-2px 轮廓线，内部色块分明 |
| **光影** | 柔和顶光 + 环境光，2-3 级明暗层次 |
| **导出格式** | PNG, 256×256, 72 DPI |

**正面 vs 3/4 视角分工**：
| 视角 | 用途 | NPC 分配 |
|------|------|----------|
| 正面 | 对话头像 (portrait.png) | 所有 NPC |
| 3/4 侧视 | 角色展示页 / 立绘大图 | 核心 NPC（校长、招生办主任、AI 助手） |

### 11.3 Sprite 行走动画规范 (Walk Sheet Specification)

| 参数 | 规范 |
|------|------|
| **单帧尺寸** | 64×64 px（含 4px 底部阴影空间） |
| **Sheet 尺寸** | 256×64 px（4 帧横向排列） |
| **帧数** | 4 帧 (walk cycle) |
| **帧排序** | 左→右：接触帧 → 过渡帧 → 交叉帧 → 过渡帧 |
| **帧间隔** | 150ms (≈6.67 fps) |
| **方向** | 四方向（上下左右），每个方向一个独立 sheet |
| **文件命名** | `<npc_id>_walk_<direction>.png`，如 `parent_001_walk_down.png` |

```
Walk Sheet 布局 (256×64 px)：
┌──────┬──────┬──────┬──────┐
│ 帧1  │ 帧2  │ 帧3  │ 帧4  │
│ 64×64│ 64×64│ 64×64│ 64×64│
│接触帧│过渡帧│交叉帧│过渡帧│
└──────┴──────┴──────┴──────┘
```

### 11.4 表情绘制规则 v1.1 (Expression Drawing Rules)

> 基于第三章的四种表情定义，补充像素级绘制规则。

**核心原则**：面部轮廓不变，仅眼、眉、嘴三个区域做像素级变化。

| 表情 | 眼 (Eyes) | 眉 (Eyebrows) | 嘴 (Mouth) |
|------|-----------|---------------|------------|
| `neutral` | 2×2 圆点，居中 | 水平 4×1 直线 | 3×1 水平直线 |
| `happy` | 2×2 上弧弯月 ^^ | 上挑 4×1 弧线 | 4×1 开口微笑弧 ⌣ |
| `worried` | 2×2 圆点（稍大） | 下斜 4×1 八字 / \ | 3×1 下弧 ⌢ |
| `strict` | 1×3 半眯竖线 | 下压 4×1 靠眼 | 2×1 紧闭直线 |

**像素变化约束**：
- 表情切换时眼眉嘴偏移量 ≤ 3px
- 面部轮廓、发型、耳朵在所有表情中完全一致
- 可选：开心时脸颊加 1px 淡粉色点（#F4C7A1 高光变体）

### 11.5 服装规范 (Clothing Specification)

> 每个 NPC 角色类型的精确服装描述，用于 AI 生图 prompt。

| 角色类型 | 服装 | 主色 | 辅色 | 细节 |
|----------|------|------|------|------|
| **招生办主任** (Admission Director) | 深蓝西装套装 | #2D4A6B | #F5E6D3 衬衫 | 深蓝西装外套 + 同色西裤，白色/暖白衬衫，深色领带，左胸佩戴校徽 |
| **合规专员** (Compliance Officer) | 灰色职业套装 | #6B7280 | #F5E6D3 衬衫 | 灰色西装外套 + 同色半身裙或西裤，浅色衬衫，黑框眼镜可选，手持文件夹 |
| **IT 运维** (IT Support) | 深灰 polo 衫 | #4B5563 | #374151 裤 | 深灰色 polo 衫，深色休闲裤，可选黑框眼镜，可选挂绳工牌 |
| **班主任** (Class Teacher) | 浅蓝衬衫 | #60A5FA | #1E3A5F 裤 | 浅蓝色长袖衬衫，卷袖至肘，深色西裤，手持平板或教案本 |
| **后勤主管** (Logistics Manager) | 卡其色工装 | #C4A77D | #5C4033 裤 | 卡其色工装夹克（多口袋），深棕色工装裤，腰间挂对讲机，手持工具夹 |
| **家长代表** (Parent Rep) | 商务休闲 | #3B82F6 外套 | #F5E6D3 内搭 | 深蓝休闲西装（不系扣），暖白内搭，深灰休闲裤，手提公文包或手提袋 |
| **学生代表** (Student Rep) | 校服 | #F5E6D3 衬衫 | #2D4A6B 外套 | 白色/暖白校服衬衫，深蓝西装外套（校徽），深灰校裤/格子裙，双肩背包 |
| **校长** (Principal) | 深灰西装 | #374151 | #F5E6D3 衬衫 | 深灰西装三件套（外套+马甲+西裤），白色衬衫，深红色领带，左胸金色校徽 |

### 11.6 色板 (Color Palette)

**11.6.1 主色板 (Primary Palette)**

| 色号 | 色名 | Hex | RGB | 用途 |
|------|------|-----|-----|------|
| 深蓝 | Deep Blue | `#2D4A6B` | 45, 74, 107 | 校服西装、招生办服装、UI 主色 |
| 暖白 | Warm White | `#F5E6D3` | 245, 230, 211 | 衬衫、背景占位、UI 底色 |
| 橙红 | Burnt Orange | `#E8734A` | 232, 115, 74 | 强调色、提示图标、指标警示 |
| 安全绿 | Sage Green | `#5BA87B` | 91, 168, 123 | 成功态、指标上升、合规安全 |
| 肤色 | Skin Tone | `#F4C7A1` | 244, 199, 161 | 所有 NPC 面部和手部肤色 |

**11.6.2 辅助色板 (Secondary Palette)**

| 色号 | Hex | 用途 |
|------|-----|------|
| 深灰 | `#374151` | 校长西装、IT 裤子 |
| 中灰 | `#6B7280` | 合规套装 |
| 浅蓝 | `#60A5FA` | 班主任衬衫 |
| 卡其 | `#C4A77D` | 后勤工装 |
| 深棕 | `#5C4033` | 后勤裤子 |
| 深蓝辅 | `#1E3A5F` | 班主任裤子、深色描边 |
| 校徽金 | `#D4A843` | 校长/招生办主任校徽 |
| 阴影 | `#1A1A2E` | 轮廓描边、阴影 |

**11.6.3 色板使用规则**

- 每个 NPC sprite 使用 ≤ 5 种颜色（含描边和阴影）
- 对话立绘可使用完整色板（≤ 16 色）
- 肤色 `#F4C7A1` 为全角色统一，禁止变体
- 所有颜色从色板选取，不得引入色板外颜色

### 11.7 禁止视觉元素 (Forbidden Visual Elements)

以下元素**绝对禁止**出现在任何 NPC 立绘、sprite、场景或概念图中：

| 类别 | 禁止元素 | 原因 |
|------|----------|------|
| **乡村/农业** | 农田、牧场、稻草人、农具、谷仓、木屋 | MetaCampus 是现代校园，非乡村 |
| **Stardew Valley** | 8-bit 复古像素风、农场帽、钓鱼竿、矿镐、史莱姆 | 必须与 Stardew Valley 形成明确视觉区分 |
| **法式乡村** | 普罗旺斯色调、薰衣草、铁艺装饰、乡村石墙 | 风格冲突 |
| **奇幻** | 魔法杖、翅膀、精灵耳、龙、魔法阵 | 非奇幻世界观 |
| **古风** | 汉服、武侠、古建筑、水墨渲染 | 现代教育科技世界观 |
| **低幼化** | Q 版大头（头身比 > 1:3）、婴儿肥、过于饱和的糖果色 | 保持专业可信的校园形象 |

**正向视觉关键词**（应出现在 prompt 中）：
- `modern campus`, `educational technology`, `clean architecture`
- `cozy 2D style` (非 8-bit), `warm lighting`, `professional attire`
- `contemporary Chinese international school`

### 11.8 版本历史补充

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.1 | 2026-05-28 | 追加视觉深化规范：角色比例 64px/1:4 头身比、立绘 256×256 规格、sprite 4 帧 walk sheet 150ms、服装色板详细规范、禁止视觉元素清单 |
