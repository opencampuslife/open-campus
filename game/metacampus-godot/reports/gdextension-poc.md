# GDExtension PoC 构建报告

## 1. Summary

成功搭建 MetaCampus Godot 项目的 GDExtension 编译链，产出一个最小可加载的 C++ 扩展（`MetaCampusNative` 节点类，含 `get_poc_message()` 方法返回 `"Native PoC OK"`），并通过 Godot 4.6.3 headless 模式验证：扩展加载无崩溃，ClassDB 中可正常实例化并调用方法。

## 2. Changed Files

### 新建文件

| 文件 | 用途 |
|------|------|
| `src/native/metacampus_native.h` | C++ 扩展类声明 (`MetaCampusNative : Node`) |
| `src/native/metacampus_native.cpp` | C++ 扩展类实现 (`get_poc_message()` 返回 "Native PoC OK") |
| `src/native/register_types.h` | 模块初始化/反初始化函数声明 |
| `src/native/register_types.cpp` | GDExtension 入口点 `metacampus_native_library_init` + `GDREGISTER_CLASS` |
| `SConstruct` | 项目级 SCons 构建脚本（先编译 godot-cpp 绑定库，再编译扩展） |
| `metacampus_native.gdextension` | GDExtension 配置文件（注册入口符号、平台库路径） |
| `bin/libmetacampus_native.macos.template_debug.framework/` | macOS arm64 构建产物（.framework bundle 含 .dylib + Info.plist） |

### 未修改文件

- `project.godot` — 未修改（不碰 GDScript 业务代码）
- 所有 `scripts/`、`scenes/`、`data/` — 未修改

## 3. 构建步骤

### 前置依赖

- **macOS arm64** (Apple Silicon)
- **Godot 4.6.3** (`~/Downloads/Godot.app/Contents/MacOS/Godot`)
- **Python 3** + **SCons 4.10+** (`pip3 install scons`)
- **clang** (系统自带)

### 构建命令

```bash
cd /path/to/metacampus-godot

# 编译 godot-cpp 绑定库 + 扩展（单条命令）
scons platform=macos arch=arm64 target=template_debug -j$(sysctl -n hw.logicalcpu)
```

### 产出路径

```
bin/libmetacampus_native.macos.template_debug.framework/
├── libmetacampus_native.macos.template_debug    # arm64 dylib (201 KB)
└── Resources/
    └── Info.plist
```

## 4. 验证结果

### Godot headless 加载测试

```bash
Godot --headless --path . --quit
# 输出: 无错误，TestHarness HTTP 正常启动
```

### ClassDB 运行时验证

通过临时 autoload 脚本调用 `ClassDB.class_exists("MetaCampusNative")` + `ClassDB.instantiate` → `get_poc_message()`：

```
[NativeProbe] PASS - MetaCampusNative loaded, message: Native PoC OK
```

⚠️ **注意**：GDExtension 类在 `_ready()` 阶段尚未注册到 ClassDB，需在 `_process()` 首帧或 `call_deferred()` 中访问。这是 Godot 4.x 的初始化时序导致的，不是扩展问题。

### 符号导出验证

```bash
nm bin/libmetacampus_native.macos.template_debug.framework/libmetacampus_native.macos.template_debug | grep metacampus_native_library_init
# 输出: 000000000000116c T _metacampus_native_library_init ✅
```

## 5. 关键路径与注意事项

| 项目 | 说明 |
|------|------|
| Godot 版本 | 4.6.3 stable, GL Compatibility |
| godot-cpp 版本 | master (v10 beta), API target 4.6 |
| 目标平台 | macOS arm64 (template_debug) |
| SCons 入口 | 项目根 `SConstruct` → 导入 `godot-cpp/SConstruct` → 编译扩展 |
| GDExtension 入口符号 | `metacampus_native_library_init` |
| 类初始化级别 | `MODULE_INITIALIZATION_LEVEL_SCENE` |
| .framework 结构 | 遵循 godot-cpp 测试项目约定（Resources/Info.plist 嵌套） |
| godot-cpp 仓库 | 本地 untracked 目录，非 git submodule（通过 symlink 或绝对路径引用） |

## 6. GDScript 使用示例

```gdscript
# 在 _process 首帧或 call_deferred 中使用
func _check_native():
    if ClassDB.class_exists("MetaCampusNative"):
        var inst = ClassDB.instantiate("MetaCampusNative")
        print(inst.get_poc_message())  # 输出: Native PoC OK
```
