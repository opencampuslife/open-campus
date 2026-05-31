# Walk Sheet Generation Prompt — admissions_director (周明远)

> 版本：v1.0
> 日期：2026-05-28
> 作者：Narrative Designer
> 用途：AI 图像生成工具生成 walk sheet sprite sheet
> 输入参考：npc-style-bible.md §11.3, §11.5, art-style-guide.md

---

## 角色基础信息

| 字段 | 值 |
|------|------|
| **npc_id** | `admissions_director` |
| **display_name** | 周明远 |
| **role** | 招生办主任 |
| **location** | admission_office |
| **主色** | #2D4A6B 深蓝 |
| **indicator_tint** | #7c3aed 紫（教师角色）|

---

## 角色描述（Character Description）

**周明远**，约40-50岁男性。站姿挺拔，略微前倾表示专注。深色短发，面容严肃但不冷漠。身穿深蓝西装套装（外套+同色西裤），内搭白色衬衫，佩戴深色领带，左胸佩戴金色校徽（#D4A843），脚穿深色皮鞋。双手自然下垂或持文件夹。脚分开与肩同宽站立。

---

## 服装详细规格（Clothing Specification）

| 部位 | 颜色 | Hex | 说明 |
|------|------|-----|------|
| 西装外套 | 深蓝 | #2D4A6B | 主色调，正装西装 |
| 西裤 | 深蓝 | #2D4A6B | 同外套色 |
| 衬衫 | 暖白 | #F5E6D3 | 白色衬衫 |
| 领带 | 深色 | #1E3A5F | 深蓝色领带 |
| 校徽 | 金色 | #D4A843 | 左胸金色校徽 |
| 皮鞋 | 深色 | #374151 | 皮鞋 |
| 肤色 | 暖白 | #F4C7A1 | 面部和手部 |
| 描边/阴影 | 深色 | #1A1A2E | 1px轮廓线 |

---

## Walk Cycle 帧描述（4帧行走循环）

> **总尺寸**：256×64px（1行×4列，每帧64×64px）
> **帧率**：150ms/帧（约6.67fps）
> **背景**：透明PNG

### 帧1 — 接触帧（Contact Frame）
- 右脚前伸落地
- 左脚脚尖着地
- 身体重心略微偏右
- 手臂自然下垂

### 帧2 — 过渡帧（Transition Frame）
- 双脚即将交叉
- 身体重心从右向左转移
- 躯干微微前倾
- 手臂轻微摆动

### 帧3 — 交叉帧（Cross Frame）
- 双腿交错
- 左脚在前，右脚在后
- 身体重心居中或略偏左
- 手臂摆动幅度最大

### 帧4 — 过渡帧（Transition Frame）
- 双脚即将分开
- 身体重心从左向右转移
- 躯干恢复直立
- 手臂轻微摆动

---

## 生成视角与尺寸

| 参数 | 值 |
|------|------|
| **视角** | 正面俯视角（Top-down front view），身体略向前倾可见头顶 |
| **画布** | 256×64px |
| **单帧** | 64×64px |
| **角色占比** | 约占每帧高度80%（约52px），留4px底部阴影 |
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
- `professional attire`
- `business suit`
- `deep blue suit`
- `warm pixel art style`
- `contemporary Chinese international school`
- `top-down view`
- `pixel art walk cycle`

---

## 输出文件

| 文件 | 命名 | 尺寸 |
|------|------|------|
| 下方向 walk sheet | `admissions_director_walk_down.png` | 256×64px |
| 上方向 walk sheet | `admissions_director_walk_up.png` | 256×64px |
| 左方向 walk sheet | `admissions_director_walk_left.png` | 256×64px |
| 右方向 walk sheet | `admissions_director_walk_right.png` | 256×64px |

---

## 完整生成 Prompt 模板（用于 AI 生图）

```
Generate a 256x64 pixel art walk sheet sprite sheet for a Chinese male admission director NPC named 周明远 (Zhou Mingyuan), age 40-50, in a professional deep blue business suit with white shirt, dark blue tie, and gold school badge on left chest. Standing upright with slight forward lean. Top-down front view. 4-frame walk cycle: contact frame, transition frame, cross frame, transition frame. Modern pixel art style with clean 1px outlines, 2-3 level lighting. Transparent background PNG. Total canvas 256x64px (4 frames of 64x64 each, horizontally arranged). Skin tone #F4C7A1, suit #2D4A6B, shirt #F5E6D3, badge #D4A843. Max 5 colors. Top-down front view with slight perspective showing top of head.
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