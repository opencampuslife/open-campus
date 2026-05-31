# Phase 2.7 QA 测试清单

## 前置
- [ ] Godot 编辑器打开项目无错误
- [ ] .sln 已自动生成
- [ ] C# 编译通过（编辑器底部 Build 输出无错误）
- [ ] `Main.tscn` 可运行

---

## 1. 启动验证

- [ ] 运行后 HUD 显示时间 `春季学期 · 第 1 天 · 07:00`
- [ ] HUD 四个指标条正常显示：效率 40 / 家长信任 50 / 合规 70 / 稳定 60
- [ ] HUD 资源条显示：AP 10/10 / 算力 100 / 预算 ¥10000
- [ ] F12 打开调试面板（游戏暂停）
- [ ] F11 打开坐标校准面板
- [ ] H 键打开 Dashboard
- [ ] E 键在 NPC/公告板附近触发交互

---

## 2. 调试面板 (F12)

### 时间控制
- [ ] "跳到 21:50" → HUD 时间变为 `21:50`
- [ ] "立即 EndDay" → SettlementReportPanel 弹出，游戏暂停
- [ ] 点击"继续" → 到达第 2 天 `07:00`

### 资源增删
- [ ] AP +5 → HUD AP 从 10 变为 15
- [ ] AP -5 → HUD AP 恢复
- [ ] 算力 +20 / -20 → HUD 算力变化
- [ ] 预算 +5000 / -5000 → HUD 预算变化

### 指标增删
- [ ] 效率 +10 → HUD 效率条从 40 变为 50
- [ ] 效率 -10 → HUD 效率条恢复
- [ ] 家长信任 +10 / -10 → HUD 家长信任变化
- [ ] 合规安全 +10 / -10 → HUD 合规变化
- [ ] 系统稳定 +10 / -10 → HUD 稳定变化
- [ ] 指标降到 <20 → HUD 指标条变红
- [ ] 指标降到 <40 → HUD 指标条变黄

### 技能 XP
- [ ] XP +50 (admissions) → Dashboard → 技能 Tab 显示等级变化
- [ ] XP +50 (compliance) → Dashboard → 技能 Tab 确认
- [ ] XP +50 (data_intelligence) → Dashboard → 技能 Tab 确认

### 任务控制
- [ ] "刷新每日任务" → HUD 显示每日委托标题
- [ ] 先接一个任务 → "完成首个活跃任务" → HUD 更新
- [ ] 再接一个任务 → "失败首个活跃任务" → HUD 更新

### 系统控制
- [ ] "解锁全部升级" → Dashboard → 升级 Tab 显示 4 个升级
- [ ] "全员信任 +3" → Dashboard → NPC Tab 信任值增加
- [ ] "打印系统状态" → 编辑器输出台显示状态摘要

---

## 3. 坐标校准 (F11)

- [ ] F11 打开校准面板
- [ ] 移动鼠标 → 面板实时显示屏幕坐标
- [ ] 导航到 TileMap 上各位置，依次 Snap

### 需要记录坐标的位置
| # | location_id     | 已记录 | 已写入 locations.json |
|---|-----------------|--------|----------------------|
| 1 | principal_office | [ ]   | [ ]                  |
| 2 | meeting_room     | [ ]   | [ ]                  |
| 3 | admission_office | [ ]   | [ ]                  |
| 4 | ai_hub           | [ ]   | [ ]                  |
| 5 | school_gate      | [ ]   | [ ]                  |
| 6 | academic_affairs | [ ]   | [ ]                  |
| 7 | teaching_building| [ ]   | [ ]                  |
| 8 | it_office        | [ ]   | [ ]                  |
| 9 | server_room      | [ ]   | [ ]                  |
|10 | logistics_area   | [ ]   | [ ]                  |
|11 | canteen          | [ ]   | [ ]                  |
|12 | compliance_office| [ ]   | [ ]                  |
|13 | parent_reception | [ ]   | [ ]                  |
|14 | dormitory        | [ ]   | [ ]                  |
|15 | classroom        | [ ]   | [ ]                  |

- [ ] 校准后 NPC 按 schedules.json 正确移动

---

## 4. 游戏交互

### 公告板
- [ ] 靠近公告板 Area2D 显示提示
- [ ] 按 E → QuestBoard 打开
- [ ] Daily/Risk/Active 三个 Tab 可切换
- [ ] 任务列表显示标题/优先级
- [ ] 点击任务 → QuestDetailPanel 显示详情
- [ ] 详情面板显示：类型、描述、截止时间、目标、奖励
- [ ] 接受任务 → 任务从 Available 变为 Active
- [ ] ESC 可关闭 QuestBoard

### NPC
- [ ] 靠近 NPC → 编辑器输出台显示 `Player near NPC: xxx`
- [ ] 按 E → NpcInteracted 信号触发
- [ ] 8 个 NPC 都可以靠近交互
- [ ] NPC 按 schedules.json 在不同时段移动

### Dashboard
- [ ] H 键打开 Dashboard
- [ ] 4 个 Tab 可切换：指标 / 技能 / NPC / 升级
- [ ] 指标 Tab 显示 4 项核心指标 + 12 项子指标
- [ ] 技能 Tab 显示 6 项技能等级/经验
- [ ] NPC Tab 显示 8 个 NPC 信任值
- [ ] 升级 Tab 显示已解锁升级
- [ ] H 键关闭 Dashboard

### SettlementReportPanel
- [ ] 21:50 EndDay → 结算面板弹出
- [ ] 面板显示：资源变化前/后
- [ ] 面板显示：4 项指标 Δ（箭头 + 颜色）
- [ ] 面板显示：任务完成/失败总结
- [ ] 面板显示：阈值后果（如触发）
- [ ] 面板显示：次日随机事件
- [ ] 点击"继续" → 面板关闭，游戏继续

---

## 5. 7 天循环验证

### Day 1
- [ ] 打开 QuestBoard → 主线 ch1 `招生季 AI 助手上线` 可见
- [ ] 每日委托显示 4 条
- [ ] 接主线 + 1-2 个每日
- [ ] NPC 校长/合规 支线可用
- [ ] F12 EndDay → 结算报告弹出

### Day 2
- [ ] 每日任务刷新
- [ ] NPC 招生/班主任/后勤/家长代表 支线可用
- [ ] 完成任务 → 指标、技能、资源变化
- [ ] Dashboard 反映变化

### Day 3
- [ ] 主线 ch2 `合规拦截器试运行` 解锁 (day≥3)
- [ ] NPC IT/学生代表/合规② 支线可用
- [ ] 全部 12 个每日委托可达

### Day 4-6
- [ ] 随机事件触发（用 F12 加速验证）
- [ ] RiskTab 显示高风险事件
- [ ] 把 compliance 降到 <40 → EndDay 触发 `audit_warning`
- [ ] 把 stability 降到 <20 → EndDay 触发 `system_outage`

### Day 6-7
- [ ] 主线 ch3 `系统稳定性审查` 解锁 (day≥6)
- [ ] 审计事件 `event_compliance_audit` 可触发
- [ ] Dashboard 显示 7 天累积变化

---

## 6. 边界与回归

- [ ] 空任务列表 → 没有报错
- [ ] 反复快速 EndDay → 状态不异常
- [ ] 结算报告中无任务时 → 显示"无变化"
- [ ] 低指标 (<20) → HUD 红色 + 阈值后果
- [ ] 中指标 (20-40) → HUD 黄色
- [ ] 已完成的任务不能再次接受
- [ ] 已失败的任务不能再次完成
- [ ] F12 开启时游戏暂停，关闭后恢复

---

## 7. 最终确认

| 条件 | 状态 |
|------|------|
| 无阻塞性 bug | [ ] PASS / [ ] FAIL |
| 所有 UI 面板层级不冲突 (10/80/90/95/100/200) | [ ] PASS / [ ] FAIL |
| NPC 坐标已校准到实际 TileMap | [ ] PASS / [ ] FAIL |
| 至少 20 个任务完成/失败路径被测试 | [ ] PASS / [ ] FAIL |
| 至少 3 个随机事件被触发并结算 | [ ] PASS / [ ] FAIL |
| 至少 2 个阈值后果被验证 | [ ] PASS / [ ] FAIL |
| 存档/自动存档不破坏游戏状态 | [ ] PASS / [ ] FAIL |
| F12/F11 调试面板稳定辅助测试 | [ ] PASS / [ ] FAIL |

---

**Phase 3 准入标准**（7 条全部通过方可进入 C++ GDExtension）：

- [ ] 1. 7 天切片完整跑通，无阻塞 bug
- [ ] 2. 任务 UI、结算 UI、Dashboard、HUD 无层级冲突
- [ ] 3. NPC 坐标已校准到实际 TileMap
- [ ] 4. 至少 20 个任务完成/失败路径被测试
- [ ] 5. 至少 3 个随机事件被触发并可结算
- [ ] 6. 至少 2 个阈值后果被验证
- [ ] 7. 存档/自动存档不破坏游戏状态
- [ ] 8. 调试面板可稳定辅助测试
