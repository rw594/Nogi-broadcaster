# 阿里云 OSS 更新通道

## 紧急隔离状态

V1.25e 及更早客户端使用过的所有自动更新入口均已永久停用：

```text
latest.json
v2/latest.json
visual/latest.json
visual/v2/latest.json
GitHub releases/latest
GitHub main/latest.json
GitHub main/latest-v2.json
jsDelivr main/latest.json
jsDelivr main/latest-v2.json
```

这些入口必须继续返回 `versionCode: 1`、空 `downloadUrl` 和空 `downloadUrls`。不得把它们
重定向到新清单，也不得再次上传真实版本信息。GitHub Latest Release 固定为不含 ZIP 的
`v0.0.1` 安全占位版本。

仓库根目录的 `AUTO_UPDATE_DISABLED` 会阻止旧对象结构被发布。删除该文件并不能迁移旧客户端，
也不应作为恢复更新的手段。

## V1.3 新通道

V1.3 必须由用户手动安装一次。它使用与旧入口完全分离的新对象结构：

```text
channels/v13/public/latest.json
channels/v13/public/releases/v1.3/V1.3.zip
channels/v13/visual/latest.json
channels/v13/visual/releases/v1.3/r1/V1.3-visual-r1.zip
```

公开版的备用清单同样使用独立路径：

```text
https://raw.githubusercontent.com/rw594/Nogi-broadcaster/main/update-channels/v13/public/latest.json
```

公开包声明 `update_channel=nogi-v13-public`，视觉包声明
`update_channel=nogi-v13-visual`，并同时设置 `strict_update_channel=true`。严格通道客户端：

1. 只读取 `package-info.json` 中显式配置的新 URL；
2. 不回退 GitHub Latest API、旧 OSS、旧 Raw 或旧 jsDelivr；
3. 要求远端清单的 `channel` 与安装包完全一致；
4. 要求下载包的 `package-info.json`、版本码与 `nogi-install-root.json` 均匹配；
5. 只替换明确列出的插件托管文件，保留插件根目录中的其他用户文件。

## 发布公开版

构建 V1.3 包后，使用新通道参数执行 dry-run：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\publish_aliyun_mirror.ps1 `
  -BucketUri "oss://nogi-broadcaster-updates" `
  -PublicBaseUrl "https://nogi-broadcaster-updates.oss-cn-hangzhou.aliyuncs.com" `
  -ManifestPath "update-channels\v13\public\latest.json" `
  -ManifestObject "channels/v13/public/latest.json" `
  -ChannelRoot "channels/v13/public" `
  -DryRun
```

确认版本、哈希、大小和对象路径后去掉 `-DryRun`。脚本只有在 `ChannelRoot` 与
`ManifestObject` 精确匹配 V1.3 新通道时，才允许绕过旧通道发布锁。

## 发布视觉内测版

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\deploy_visual_private.ps1 `
  -BucketUri "oss://nogi-broadcaster-updates" `
  -PublicBaseUrl "https://nogi-broadcaster-updates.oss-cn-hangzhou.aliyuncs.com" `
  -Version "1.3" `
  -Revision 1 `
  -ManifestObject "channels/v13/visual/latest.json" `
  -ChannelRoot "channels/v13/visual"
```

旧入口和新入口的在线状态必须在每次发布后一起检查。任何旧入口出现大于 1 的版本码或非空下载地址，
都应视为发布事故并立即停止新通道发布。
