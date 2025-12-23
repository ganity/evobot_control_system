# GitHub Actions 工作流说明

本项目包含三个GitHub Actions工作流，专门针对Windows环境进行优化。

## 🔄 工作流概览

### 1. Windows Build & Test (`windows-build.yml`)
**主要工作流** - 用于构建和测试

**触发条件:**
- 推送到 `main` 分支
- 创建标签 (v*)
- Pull Request 到 `main` 分支

**功能:**
- ✅ 在Windows环境测试依赖安装
- ✅ 验证应用程序导入
- 🏗️ 构建Windows可执行文件
- 📦 创建发布包
- 🚀 自动发布到GitHub Releases

### 2. Windows CI (`windows-ci.yml`)
**完整CI流程** - 用于全面测试

**触发条件:**
- 推送到 `main` 或 `develop` 分支
- Pull Request
- 手动触发

**功能:**
- 🧪 多Python版本测试 (3.10, 3.11, 3.12)
- 📊 代码覆盖率报告
- 🔍 代码质量检查 (Black, Flake8, MyPy)
- 📦 构建测试

### 3. Dependency Check (`dependency-check.yml`)
**依赖检查** - 用于维护

**触发条件:**
- 每周一自动运行
- 手动触发

**功能:**
- 🔍 检查依赖冲突
- 🔒 安全审计
- 🧪 Windows兼容性测试

## 🎯 使用说明

### 开发流程
1. **开发**: 在功能分支开发
2. **测试**: 创建PR触发CI测试
3. **合并**: 合并到main分支
4. **发布**: 创建标签自动构建发布包

### 手动触发构建
```bash
# 创建标签触发发布
git tag v1.0.0
git push origin v1.0.0
```

### 查看构建结果
- 访问 Actions 页面查看构建状态
- 下载构建产物 (Artifacts)
- 查看发布页面获取最新版本

## 📋 构建产物

### Artifacts (临时文件)
- `EvoBot-Windows`: Windows可执行文件包
- `evobot-windows-build`: 完整构建目录
- `evobot-windows-release`: 发布压缩包

### Releases (正式发布)
- 标签推送时自动创建
- 包含 `EvoBot-Windows.zip` 发布包
- 适合最终用户下载

## 🔧 配置说明

### 环境变量
- `GITHUB_TOKEN`: 自动提供，用于发布
- `QT_QPA_PLATFORM=offscreen`: GUI测试环境

### 缓存策略
- pip依赖缓存: 加速构建
- 保留期: 30-90天

### 错误处理
- GUI测试失败不中断流程
- 可选依赖安装失败继续执行
- 详细错误日志输出

## 🚀 优化特性

### Windows专用优化
- 使用 `requirements-windows.txt`
- 自动修复PyQt5兼容性
- Windows路径处理
- 批处理脚本集成

### 构建优化
- 依赖缓存
- 并行任务
- 增量构建
- 智能触发条件

### 测试优化
- 多版本矩阵测试
- 虚拟显示环境
- 超时保护
- 错误容忍

## 📊 状态徽章

可以在README中添加状态徽章:

```markdown
![Windows Build](https://github.com/your-username/evobot-control-system/workflows/Windows%20Build%20&%20Test/badge.svg)
![Windows CI](https://github.com/your-username/evobot-control-system/workflows/Windows%20CI/badge.svg)
```

## 🔍 故障排除

### 常见问题
1. **PyQt5安装失败**: 检查Windows兼容性配置
2. **构建超时**: 增加timeout设置
3. **测试失败**: 检查虚拟显示配置

### 调试方法
1. 查看Actions日志
2. 下载失败的构建产物
3. 本地复现CI环境
4. 检查依赖版本冲突