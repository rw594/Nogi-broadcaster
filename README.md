# Nogi-broadcaster

洛奇播报小助手是一个面向《洛奇》的本地语音提醒工具。它通过解析游戏网络事件中的状态、战斗时限、Boss 血量和特定机制信号，播放简短语音提示，减少玩家在战斗中反复盯 BUFF 栏和机制计时的负担。

当前项目主要围绕亚特服务器的实战数据调校，包含：

- 玩家 BUFF 剩余时间和结束提醒
- 魔法盾关闭与漏开提醒
- 关键敌人 DEBUFF 上齐与续期提醒
- Boss 血量机制提醒
- 布本安全屋、布三红球等机制提醒
- 图形化设置页与启动器
- 发布包构建脚本

## 使用发布包

普通用户建议直接下载 GitHub Releases 中的最新 zip 包，解压后运行：

```text
洛奇播报小助手 Vx.xx.exe
```

运行说明以发布包内的 `使用方法README.txt` 为准。

## 源码结构

```text
buffwatcher/                  核心逻辑、启动器、设置页
assets/                       图标与语音资源
docs/                         发布说明和设计文档
scripts/build_release.ps1     Windows 发布包构建脚本
buffwatcher.config.defaults.json
                              默认提醒配置
```

以下内容不会进入源码仓库：

- `logs/`
- `build/`
- `dist/`
- `release/`
- `scratch/`
- `buffwatcher.config.local.json`
- `vendor/*.exe`

## 开发环境

需要 Windows 与 Python 3.11。构建发布包还需要 PyInstaller：

```powershell
python -m pip install pyinstaller
```

运行设置页：

```powershell
python run_settings.py
```

运行后台：

```powershell
python run_standalone.py
```

构建发布包示例：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_release.ps1 `
  -ReleaseName "洛奇播报小助手 V1.20 乐曲重接静默" `
  -ReleaseConfigPath .\buffwatcher.config.defaults.json `
  -LocalConfigPath .\buffwatcher.config.local.json `
  -ReadmePath .\docs\release-readme-zh.txt
```

`vendor/mabicat.exe` 是运行时依赖的外部后端二进制，不提交到源码仓库。构建发布包时请在本机准备该文件，或使用 `-BackendPath` 指定路径。

## 更新清单

`latest.json` 用于后续客户端联网检查更新。建议将它随每个 GitHub Release 一起上传，客户端读取：

```text
https://github.com/rw594/Nogi-broadcaster/releases/latest/download/latest.json
```

仓库根目录也保留一份 `latest.json` 作为可读版本记录。每次发布新版本时，需要同步更新：

- `version`
- `versionCode`
- `releaseName`
- `downloadUrl`
- `sha256`
- `notes`

发布新版本前，应先请项目维护者手写一段面向用户的版本更新日志；除非维护者已经主动提供，否则不要自行直接生成最终发布说明。

## License

MIT License
