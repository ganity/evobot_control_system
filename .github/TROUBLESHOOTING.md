# GitHub Actions 故障排除指南

## 🚨 常见错误及解决方案

### 1. Chocolatey 包安装失败

**错误信息:**
```
vcredist2019 not installed. The package was not found with the source(s) listed.
```

**解决方案:**
- ✅ 已修复：移除了不必要的系统依赖安装
- 使用 `simple-windows.yml` 工作流，避免复杂的系统依赖

### 2. PyQt5 依赖冲突

**错误信息:**
```
Distribution `pyqt5-qt5==5.15.18` can't be installed because it doesn't have a source distribution or wheel for the current platform
```

**解决方案:**
- ✅ 已修复：使用 `PyQt5==5.15.10` 版本
- 移除了 `PyQt5-Qt5` 依赖
- 更新了 `requirements-windows.txt`

### 3. 机器人工具箱安装失败

**错误信息:**
```
ERROR: Could not find a version that satisfies the requirement roboticstoolbox-python
```

**解决方案:**
- ✅ 已修复：将机器人工具箱设为可选依赖
- 使用 `continue-on-error: true` 允许可选依赖失败
- 核心功能不依赖这些包

## 🔧 推荐的工作流使用

### 主要工作流
1. **`simple-windows.yml`** - 最稳定，推荐使用
2. **`windows-build.yml`** - 完整构建流程
3. **`windows-ci.yml`** - 全面测试（可能有兼容性问题）

### 选择建议
- **开发测试**: 使用 `simple-windows.yml`
- **正式发布**: 使用 `windows-build.yml`
- **完整CI**: 修复后使用 `windows-ci.yml`

## 🛠️ 本地调试方法

### 1. 复现CI环境
```bash
# 使用相同的Python版本
python --version  # 应该是 3.11.x

# 使用相同的依赖文件
pip install -r requirements-windows.txt

# 运行相同的测试
python -c "from PyQt5.QtWidgets import QApplication; print('OK')"
```

### 2. 检查依赖冲突
```bash
pip check
pip list | findstr PyQt
```

### 3. 测试构建
```bash
pip install pyinstaller
pyinstaller evobot.spec --clean --noconfirm
```

## 📋 依赖版本锁定

### 核心依赖（必须）
```
PyQt5==5.15.10
PyQt5-sip==12.13.0
pyqtgraph>=0.13.0
pyserial>=3.5
numpy>=1.24.0,<2.0.0
scipy>=1.10.0
pyyaml>=6.0
loguru>=0.7.0
matplotlib>=3.7.0
```

### 可选依赖（可失败）
```
roboticstoolbox-python>=1.1.0
spatialmath-python>=1.1.0
```

## 🔍 调试技巧

### 1. 查看详细错误
在GitHub Actions中添加：
```yaml
- name: Debug info
  run: |
    python --version
    pip list
    pip check
```

### 2. 测试特定模块
```yaml
- name: Test specific import
  run: |
    python -c "import PyQt5; print(PyQt5.__file__)"
```

### 3. 检查文件系统
```yaml
- name: Check files
  run: |
    Get-ChildItem -Recurse | Where-Object {$_.Name -like "*PyQt*"}
```

## 🚀 最佳实践

### 1. 依赖管理
- 锁定核心依赖版本
- 可选依赖使用 `continue-on-error`
- 定期更新依赖版本

### 2. 错误处理
- 使用 `continue-on-error: true` 处理非关键步骤
- 添加详细的错误信息输出
- 提供回退方案

### 3. 缓存策略
- 缓存pip依赖加速构建
- 使用合适的缓存键
- 定期清理缓存

## 📞 获取帮助

如果遇到其他问题：

1. **检查Actions日志**: 查看详细错误信息
2. **本地复现**: 使用相同环境测试
3. **提交Issue**: 包含完整错误日志
4. **查看文档**: 参考官方文档

## 🔄 更新记录

- **2024-12-23**: 修复Chocolatey依赖问题
- **2024-12-23**: 简化PyQt5依赖配置
- **2024-12-23**: 添加简化工作流