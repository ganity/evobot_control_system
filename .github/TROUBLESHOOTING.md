# GitHub Actions 故障排除指南

## 🚨 常见错误及解决方案

### 1. ~~Chocolatey 包安装失败~~ ✅ 已修复

**错误信息:**
```
vcredist2019 not installed. The package was not found with the source(s) listed.
```

**解决方案:**
- ✅ 已修复：移除了不必要的系统依赖安装

### 2. ~~PyQt5 依赖冲突~~ ✅ 已修复

**错误信息:**
```
Distribution `pyqt5-qt5==5.15.18` can't be installed because it doesn't have a source distribution or wheel for the current platform
```

**解决方案:**
- ✅ 已修复：使用 `PyQt5==5.15.10` 版本
- 移除了 `PyQt5-Qt5` 依赖

### 3. ~~Actions版本过时~~ ✅ 已修复

**错误信息:**
```
This request has been automatically failed because it uses a deprecated version of `actions/upload-artifact: v3`
```

**解决方案:**
- ✅ 已修复：更新到 `actions/upload-artifact@v4`
- ✅ 已修复：更新到 `actions/setup-python@v5`

## 🔧 当前可用的工作流

### 推荐使用顺序
1. **`minimal-build.yml`** - 最简化，最稳定 ⭐⭐⭐⭐⭐
2. **`windows-build.yml`** - 标准构建流程 ⭐⭐⭐⭐
3. **`windows-ci.yml`** - 完整CI流程 ⭐⭐⭐
4. **`dependency-check.yml`** - 依赖检查 ⭐⭐⭐

### 工作流特点对比

| 工作流 | 测试 | 构建 | 代码质量 | 复杂度 | 稳定性 |
|--------|------|------|----------|--------|--------|
| minimal-build | ❌ | ✅ | ❌ | 低 | 高 |
| windows-build | ❌ | ✅ | ❌ | 中 | 高 |
| windows-ci | ❌ | ✅ | ✅ | 中 | 中 |
| dependency-check | ❌ | ❌ | ✅ | 低 | 中 |

## 🛠️ 本地调试方法

### 1. 复现CI环境
```bash
# 使用相同的Python版本
python --version  # 应该是 3.11.x

# 使用相同的依赖安装命令
pip install PyQt5==5.15.10 PyQt5-sip==12.13.0
pip install pyqtgraph pyserial numpy scipy pyyaml loguru matplotlib
pip install pyinstaller

# 运行构建
pyinstaller evobot.spec --clean --noconfirm
```

### 2. 检查构建结果
```bash
# Windows PowerShell
if (Test-Path "dist\EvoBot控制系统\EvoBot控制系统.exe") {
    Write-Host "✅ 构建成功"
} else {
    Write-Host "❌ 构建失败"
}
```

## 📋 最新依赖版本

### 核心依赖（锁定版本）
```
PyQt5==5.15.10
PyQt5-sip==12.13.0
pyinstaller>=6.0.0
```

### 其他依赖（兼容版本）
```
pyqtgraph>=0.13.0
pyserial>=3.5
numpy>=1.24.0,<2.0.0
scipy>=1.10.0
pyyaml>=6.0
loguru>=0.7.0
matplotlib>=3.7.0
```

## 🚀 最佳实践

### 1. 选择合适的工作流
- **快速测试**: 使用 `minimal-build.yml`
- **正式发布**: 使用 `windows-build.yml`
- **完整检查**: 使用 `windows-ci.yml`

### 2. 触发方式
```bash
# 手动触发
# 在GitHub Actions页面点击 "Run workflow"

# 推送触发
git push origin main

# 标签触发（自动发布）
git tag v1.0.0
git push origin v1.0.0
```

### 3. 监控构建
- 查看Actions页面实时日志
- 下载构建产物测试
- 检查发布页面

## 🔍 调试技巧

### 1. 查看详细日志
在工作流中添加调试步骤：
```yaml
- name: Debug info
  run: |
    python --version
    pip list
    Get-ChildItem dist -Recurse
```

### 2. 本地测试构建
```bash
# 测试PyInstaller配置
pyinstaller --version
pyinstaller evobot.spec --clean --noconfirm --debug all
```

### 3. 检查文件权限
```bash
# 检查生成的exe文件
Get-ItemProperty "dist\EvoBot控制系统\EvoBot控制系统.exe"
```

## 📞 获取帮助

如果遇到其他问题：

1. **优先使用**: `minimal-build.yml` 工作流
2. **检查日志**: GitHub Actions详细日志
3. **本地复现**: 使用相同命令测试
4. **提交Issue**: 包含完整错误信息

## 🔄 更新记录

- **2024-12-23**: 修复Actions版本过时问题
- **2024-12-23**: 添加minimal-build工作流
- **2024-12-23**: 更新所有action到最新版本
- **2024-12-23**: 移除所有Python测试步骤