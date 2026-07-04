# Npcap 方案设计

## 目标

做一个独立提醒器，实时追踪指定洛奇 buff 的剩余时间，并在到达阈值时强提醒。

## 已验证线索

MicoPunch 的 raw 历史文件是 JSON lines gzip：

- `EventId == 4`：状态效果添加或刷新。
- `EventId == 5`：状态效果移除。
- `CCId`：状态效果 ID。
- `ExtraData.SBT`：状态效果结束时间。
- `ExtraData.SDUR` / `DURATION` / `DURA`：部分效果的持续时间。

`SBT` 初步换算：

```text
unix_end_ms = SBT - 62135596800000 - 8 * 60 * 60 * 1000
remaining_s = (unix_end_ms - At) / 1000
```

这里的 `At` 来自 raw 事件自身，单位是毫秒。

## 开发阶段

### 1. 离线识别阶段

用 `buffwatcher.analyze` 从 MicoPunch 历史 raw 文件中统计所有 `CCId`：

- 出现次数
- 移除次数
- 观察到的剩余时间范围
- 持续时间字段
- `ExtraData` 键集合

这一步的目的，是把每个重要 buff 的 `CCId` 找出来。

### 2. 映射表阶段

建立配置：

```json
{
  "buffs": [
    {
      "name": "行进曲",
      "ccid": 123,
      "enabled": true,
      "warn_seconds": 60,
      "critical_seconds": 15
    }
  ]
}
```

实际 `ccid` 需要通过实验确认。

### 3. 实时事件源阶段

有两个可选方向：

1. 复用 MicoPunch 输出：如果能找到实时 NDJSON、WebSocket、IPC 或本地端口，直接订阅它的事件流。
2. 自己实现 Npcap 解析：抓洛奇连接，解析包结构，输出和 MicoPunch raw 类似的事件。

当前实战测试版先实现了方向 1：连接 MicoPunch 后端 `mabicat.exe` 暴露的本地 WebSocket `ws://127.0.0.1:18000/ws`，并把实时事件送入 `AlertEngine`。
历史文件监听模式仍保留为备用，但 MicoPunch 的 `histories` 文件通常只在关闭或结算时写入，不适合实时提醒。

方向 1 成本最低，但依赖 MicoPunch 的后端进程、端口和事件结构。
方向 2 最独立，但协议解析成本最高。

### 4. 提醒阶段

提醒逻辑只依赖标准化事件：

- 收到 `EventId 4` 且 `CCId` 在配置中：刷新该 buff 的结束时间。
- 收到 `EventId 5` 且 `CCId` 在配置中：标记该 buff 已移除。
- 当前时间进入 `warn_seconds`：普通语音。
- 当前时间进入 `critical_seconds`：重复语音 + 强视觉。
- buff 消失或过期：播报已断。

## 风险点

- `CCId` 可能随版本变化，需要可配置。
- 不同服务器、频道或网络路径可能影响抓包过滤条件。
- 游戏协议更新后，实时 decoder 可能需要维护。
- `SBT` 的时区偏移目前按 `+8` 验证，需要用更多样本确认。
