# Walk Sheet Generation Prompt — student_representative (林澈)

> 版本：v1.00
> 日期：2026-05-28
> 作者：Narrative Designer
> 用途：AI 图像生成工具生成 walk sheet sprite sheet
> 输入参考：npc-style-bible.md §11.3, §11.5, art-style-guide.md

---

## 角色基础信息

| 字段 | 值 |
|------|------|
| **npc_id** | `student_representative` |
| **display_name** | 林澈 |
| **role** | 学生代表 |
| **location** | academic_affairs |
| **主色** | #F5E6D3 暖白（衬衫）+ #2D4A6B 深蓝（外套）|
| **indicator_tint** | #eab308 黄（学生角色）|

---

## 角色描述（Character Description）

**林澈**，约16-18岁学生代表。站姿活泼，重心略偏一侧彰显青春气息。深色短发，面容阳光自信。身穿白色校服衬衫，外套深蓝西装外套（校徽，#D4A843金色），下着深灰校裤。背负双肩背包（#2D4A6B深蓝色），肩带使肩部略微后仰。脚穿白色运动鞋或黑色皮鞋。

---

## 服装详细规格（Clothing Specification）

| 部位 | 颜色 | Hex | 说明 |
|------|------|-----|------|
| 校服衬衫 | 暖白 | #F5E6D3 | 白色校服衬衫 |
| 西装外套 | 深蓝 | #2D4A6B | 深蓝西装外套 |
| 校裤 | 中灰 | #6B7280 | 深灰校裤 |
| 校徽 | 金色 | #D4A843 | 外套左胸金色校徽 |
| 双肩背包 | 深蓝 | #2D4A6B | 双肩背包 |
| 运动鞋 | 白色 | #F5E6D3 | 白色运动鞋 |
| 肤色 | 暖白 | #F4C7A1 | 面部和手部 |
| 描边/阴影 | 深色 | #1A1A2E | 1px轮廓线 |

---

## Walk Cycle 帧描述（4帧行走循环）

> **总尺寸**：256×64px（1行×4列，每帧64×64px）
> **帧率**：150ms/帧（约6.67fps）
> **背景**：透明PNG

### 帧1 — 接触帧（Contact Frame）
- 右脚前伸落地（步伐稍大，活泼感）
- 左脚脚尖着地
- 身体重心略微偏右
- 背包随步伐轻微晃动
- 手臂自然摆动

### 帧2 — 过渡帧（Transition Frame）
- 双脚即将交叉
- 身体重心从右向左转移
- 躯干微微前倾（学生步伐轻快）
- 手臂摆动幅度增加
- 背包肩带略微上扬

### 帧3 — 交叉帧（Cross Frame）
- 双腿交错
- 左脚在前，右脚在后
- 身体重心居中
- 手臂摆动幅度最大（步伐更轻盈）
- 背包轻微后摆

### 帧4 — 过渡帧（Transition Frame）
- 双脚即将分开
- 身体重心从左向右转移
- 躯干恢复活泼站姿
- 手臂轻微摆动
- 背包恢复原位

---

## 生成视角与尺寸

| 参数 | 值 |
|------|------|
| **视角** | 正面俯视角（Top-down front view），身体略向前倾可见头顶 |
| **画布** | 256×64px |
| **单帧** | 64×64px |
| **角色占比** | 约占每帧高度75-80%（约48-52px），留4px底部阴影；学生身形较矮但背包占用额外空间 |
| **背景** | 透明 PNG |
| **风格** | 现代像素艺术（Modern Pixel Art），非8-bit复古 |
| **线条** | 清晰1px轮廓线，内部色块分明 |
| **光影** | 柔和顶光+环境光，2-3级明暗层次 |

---

## 禁止视觉元素（Forbidden Elements）

- ❌ 农场/农田元素
- ❌ 8-bit复古像素风
- ❌ 魔法/奇幻元素
- ❌ 古风/汉服
- ❌ Q版大头（头身比>1:3）
- ❌ 过于饱和的糖果色
- ❌ 真实学生照片/版权角色

---

## 正向视觉关键词（Positive Keywords）

- `modern campus`
- `educational technology`
- `clean architecture`
- `student uniform`
- `school uniform`
- `backpack`
- `youthful posture`
- `warm pixel art style`
- `contemporary Chinese international school`
- `top-down view`
- `pixel art walk cycle`

---

## 输出文件

| 文件 | 命名 | 尺寸 |
|------|------|------|
| 下方向 walk sheet | `student_representative_walk_down.png` | 256×64px |
| 上方向 walk sheet | `student_representative_walk_up.png` | 256×64px |
| 左方向 walk sheet | `student_representative_walk_left.png` | 256×64px |
| 右方向 walk sheet | `student_representative_walk_right.png` | 256×64px |

---

## 完整生成 Prompt 模板（用于 AI 生图）

```
Generate a 256x64 pixel art walk sheet sprite sheet for a Chinese student representative NPC named 林澈 (Lin Che), age 16-18, wearing a white school uniform shirt, deep blue school jacket with gold school badge on left chest, gray school pants, and carrying a deep blue backpack. Standing with a lively, youthful posture with slight weight shift. Top-down front view. 4-frame walk cycle: contact frame, transition frame, cross frame, transition frame. Modern pixel art style with clean 1px outlines, 2-3 level lighting. Transparent background PNG. Total canvas 256x64px (4 frames of 64x64 each, horizontally arranged). Skin tone #F4C7A1, shirt #F5E6D3, jacket #2D4A6B, backpack #2D4A6B, badge #D4A843. Max 5 colors. Top-down front view with slight perspective showing top of head.
```

---

## Godot 集成说明

| 参数 | 值 |
|------|------|
| 导入模式 | 2D |
| Texture Filter | Nearest |
| hframes | 4 |
| vframes | 1 |
| 帧率 | 150ms |

---

## 与 admissions_director 差异说明

| 差异点 | admissions_director | student_representative |
|--------|---------------------|-----------------------|
| 年龄感 | 40-50岁，挺拔严肃 | 16-18岁，活泼青春 |
| 服装主色 | 深蓝西装套装 | 白衬衫+深蓝外套 |
| 特殊配件 | 领带+校徽 | 双肩背包+校徽 |
| 步伐感 | 稳重，步伐均匀 | 轻快，步伐稍大 |
| 背包 | 无 | 有，肩带使肩后仰 |
| 站姿 | 双脚分开与肩同宽 | 重心略偏，活泼感 |