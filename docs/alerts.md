# 提醒规则与音频

## 当前能力

`buffwatcher.alerting` 负责把标准化事件转换成提醒：

- `EventId 4`：buff 获得或刷新，读取 `ExtraData.SBT` 作为结束时间。
- 已经过期的 `EventId 4 + SBT` 会被视为过期快照并忽略，避免同一个已结束状态被重复复活和重复播报。
- SBT 时间启动时默认向后校准 12 秒；运行中如果收到同时包含 `SBT` 和 `DUR`/`SDUR`/`DURA`/`MCWPWD` 等持续时间字段、且结束点确实新出现或明显向后刷新的状态包，会自动学习当前机器与游戏 SBT 的实际偏移，并用动态校准值替代默认值。重复上报同一个 SBT 结束点的包不会参与学习，避免把已进行了一段时间的状态误当成新状态。由 SBT 推算的自然结束提醒会在校准后结束点前约 1 秒触发。
- `EventId 5`：buff 移除；只有配置了 `ended_alert: true` 的 buff 会播报结束提醒。结束提醒会先等待 `ended_grace_seconds`，同一 buff 在宽限时间内续上则取消播报。默认值是 1.5 秒；魔法盾单独配置为 0 秒，可在设置界面调为 0 到 10 秒。
- 死亡/清场抑制：收到玩家自身 `EventId 15` 时，取消刚刚排队和随后短窗口内的结束提醒；同时保留“0.5 秒内 5 个或更多已追踪 buff 同时移除”的兜底判断。
- `linked_ccids`：复合 buff 的关联组件，用来避免同一个 buff 播报多次。
- `stack_field`：叠层字段，例如生命的温度用 `MCSTCT`。
- `duration_seconds`：固定时长覆盖；生命的温度使用 60 秒固定时长，净化之浪使用 180 秒固定时长，避免这些状态的 SBT 在不同场景下偏短导致过早提醒。
- `stack_alert`：叠层达到指定层数时提醒。湛蓝内伤使用该规则，并且只有在危险提醒已经触发后、状态自然清除时，才按设置播放消除提示。
- `cooldown_alert`：状态结束后延迟指定秒数播报冷却完成。魔法阵和半神化使用这个规则；当前日志没有稳定的冷却完成专用事件 ID，因此按结束后计时实现。
- 独立机制预警：可用 boss/机制实体的统计字段锁定计时起点，再按固定节奏循环提醒。布四安全屋使用这个规则，只播放发生预警，不播放结束提醒。
- Boss 血量机制提醒：用最大血量 `StatId 30` 作为 boss 指纹，动态绑定本场实际实体，再追踪当前血量 `StatId 28`；当血量百分比向下跨过设置阈值时播报，每个阈值每场战斗只播一次。
- 魔法盾漏开提醒：战斗时限进行中，如果 `CCId 59` 保持关闭超过设置秒数，则播报“魔法盾忘开啦”；播报后仍未开启时每 5 秒重复一次，直到魔法盾开启或战斗时限结束。该提醒默认关闭。

当前这层使用 MicoPunch 的历史 raw 文件回放测试。实时 Npcap decoder 接好后，只需要把实时事件喂给同一个 `AlertEngine`。

## 当前测试版触发时间

现阶段所有提醒都先使用同一个测试音源：

```text
assets/audio/warn.wav
```

启用的 buff 都会在结束时提醒。额外的剩余时间触发点如下：

| Buff | CCId | 剩余时间提醒 | 结束提醒 |
| --- | ---: | --- | --- |
| 战争序曲 | 680 | 15 秒；若徒安之歌剩余时间不短于乐曲则抑制 | 是 |
| 活跃曲 | 192 | 15 秒；若徒安之歌剩余时间不短于乐曲则抑制 | 是 |
| 行进曲 | 193 | 15 秒；若徒安之歌剩余时间不短于乐曲则抑制 | 是 |
| 坚定意志 | 479 | 默认关闭；设置界面预填 30 秒 | 默认关闭 |
| 逆光剑 | 612 | 默认关闭；设置界面预填 30 秒 | 默认关闭 |
| 致命穿透 | 476 | 默认关闭；设置界面预填 30 秒 | 默认关闭 |
| 超越生命 | 478 | 默认关闭；设置界面预填 30 秒 | 默认关闭 |
| 负载转移 | 1123 | 30 秒 | 是 |
| 圣域之主 | 1061 | 10 秒 | 是 |
| 马纽斯秘药 | 835 | 无 | 是 |
| 魔攻水 | 1121 | 60 秒 | 是 |
| 物攻水 | 63 | 60 秒 | 是 |
| 法速水 | 62 | 60 秒 | 是 |
| 炼金水 | 1150 | 60 秒 | 是 |
| 净化之浪 | 645 | 10 秒；按 180 秒固定时长计算 | 是 |
| 活力之歌 | 800 | 30 秒 | 是 |
| 状态支援 | 515 | 30 秒 | 是 |
| 生命的温度 | 874 | 10 秒；按 60 秒固定时长计算 | 是 |
| 湛蓝内伤 | 1098 | 7 层危险提醒，可在设置中改 | 危险后自然清除时可提醒，默认开启 |

## 机制预警

| 项目 | 识别方式 | 默认提醒 |
| --- | --- | --- |
| 布四安全屋 | boss 实体 `StatId 28 = 3449779200` 且 `StatId 30 = 3449779200` 时开始计时；`StatId 28 <= 0` 或已追踪 boss 实体出现 `EventId 2` 时停止计时；安全屋按开始后 7 秒、之后每 63 秒发生，开场第一波不播 | 默认开启；从第二波开始，在发生前 7 秒播报“安全屋”，设置界面可调为 5 到 15 秒 |

## Boss 血量机制提醒

| Boss | 最大血量指纹 | 默认阈值 | 播报 |
| --- | --- | --- | --- |
| 枯木之佩塔克（布本1王） | `698517000`、`850368600` | 88%、73%、58%、38%、28%、18% | 注意机制 |
| 布隆塔纳斯（布本2王） | `1143352700` | 93%、78%、63%、53%、43%、23% | 注意机制 |
| 雷内恩的米耶尔（布本3王） | `1967880100` | 83%、63%、43%、33%、15% | 注意机制 |

该功能默认开启。设置界面中可按 boss 分别开关，并用逗号、空格或换行填写新的血量百分比阈值。
布本1王在 50% 左右会切换底层实体，但游戏内显示为同一条血条；工具会把两个阶段实体合并为一个逻辑 boss，并忽略新阶段实体刚出现时短暂上跳到满血的包。
如果战斗时限事件缺席，工具会用已识别到的布本 boss 血量刷新作为 boss 战进行中的兜底信号；该兜底也会供魔法盾漏开提醒判断是否处于 boss 战中。

## 结束与冷却提醒

| 项目 | CCId | 结束提醒 | 其他提醒 |
| --- | ---: | --- | --- |
| 魔法盾 | 59 | 默认开启，默认延迟 0 秒 | 无剩余提醒；漏开提醒默认关闭，首次提醒默认 5 秒 |

| 项目 | CCId | 结束提醒 | 冷却完成提醒 |
| --- | ---: | --- | --- |
| 魔法阵 | 10133 | 默认关闭 | 状态结束后 15 秒，默认开启 |
| 半神化 | 78 | 默认开启 | 默认关闭；设置界面可填 15 到 600 秒后手动开启 |

## 测试音频

占位音频在：

```text
assets/audio/warn.wav
assets/audio/critical.wav
assets/audio/ended.wav
assets/audio/xiaoyi/safehouse_warning.wav
```

播放测试：

```powershell
python -m buffwatcher.alerting test-sounds
```

如果只想验证命令不播放声音：

```powershell
python -m buffwatcher.alerting test-sounds --no-audio
```

## 查看启用的 buff

```powershell
python -m buffwatcher.alerting list-enabled
```

## 回放测试

也可以用测试版入口：

```powershell
.\scripts\run_test_plugin.ps1 -Mode list
.\scripts\run_test_plugin.ps1 -Mode sounds
.\scripts\run_test_plugin.ps1 -Mode replay -NoAudio -NoSleep -Drain
```

无声音回放最新 MicoPunch raw：

```powershell
python -m buffwatcher.alerting replay --histories "C:\Users\rw594\Desktop\MicoPunch\histories" --no-audio --no-sleep --drain
```

回放指定文件：

```powershell
python -m buffwatcher.alerting replay --file "C:\Users\rw594\Desktop\MicoPunch\histories\20260520-21-42-28-emergency-raw.ndjson.gz" --no-audio --no-sleep --drain
```

去掉 `--no-audio` 就会播放音频。`--drain` 会在文件结束后快进到未来提醒点，适合测试长 buff 的自定义剩余时间提醒。

## 实战运行

实战测试版入口：

```powershell
.\scripts\run_live_plugin.ps1
```

它会：

- 默认连接 `ws://127.0.0.1:18000/ws`，读取 MicoPunch 后端的实时事件流。
- 在启动后遇到第一个“目标 `Id` 等于 `AttackerId`”的已配置 buff 事件时自动学习玩家自身 `Id`。
- 后续只处理目标 `Id` 相同的 buff 事件。
- 使用系统时间推进倒计时，即使之后没有新事件，也能在到达剩余时间阈值时播放音频。

发布包内的独立启动器默认会启动工具包自带的 `mabicat.exe`，并使用自动端口。这样即使 MicoPunch 已经运行，也不会依赖 MicoPunch 界面的 WebSocket 事件分发。需要诊断时可以手动加 `--reuse-existing-backend` 复用 `ws://127.0.0.1:18000/ws`。

如果玩家在提醒器运行中退出角色并重新登录，自带后端可能停留在旧会话。独立启动器会在连续空闲重连后自动重启自带后端，并清除自动学习的 self id，让回到游戏后的事件重新识别角色。

推荐实战步骤：

1. 启动洛奇并进入角色。
2. 以管理员身份启动 MicoPunch。
3. 在本目录运行 `.\scripts\run_live_plugin.ps1`。
4. 优先开关一次魔法盾，看到 `learned self id`；也可以刷新或施放一个自己给自己的已配置 buff。
5. 进入实战测试。

常用参数：

```powershell
.\scripts\run_live_plugin.ps1 -NoAudio
.\scripts\run_live_plugin.ps1 -SelfId "4503599639695197"
.\scripts\run_live_plugin.ps1 -NoSelfFilter
.\scripts\run_live_plugin.ps1 -NoAudio -VerboseEvents
.\scripts\run_live_plugin.ps1 -Source file
```

如果运行后一直只看到 `active -`，先用 `-VerboseEvents` 看是否收到已配置 `CCId`。如果完全没有事件，确认 MicoPunch 已启动且后端端口是 `18000`；如果只收到队友事件，可以用 `-SelfId` 固定玩家自身 ID。

## 自定义提醒时间和声音

在 `buffwatcher.config.local.json` 里，每个启用 buff 可以使用：

```json
"alerts": [
  {
    "remaining_seconds": 45,
    "sound": "assets/audio/my_warn.wav",
    "message": "{name}"
  },
  {
    "remaining_seconds": 10,
    "sound": "assets/audio/my_critical.wav",
    "message": "{name} 快结束了"
  }
],
"ended_sound": "assets/audio/my_ended.wav",
"ended_message": "{name} 已结束"
```

可用占位符：

- `{name}`：buff 名称。
- `{remaining_seconds}`：触发时剩余秒数。
- `{stacks}`：当前层数，只有配置了 `stack_field` 的 buff 才有。
- `{max_stacks}`：最大层数。

没有写 `alerts` 时，会退回使用 `warn_seconds` 和 `critical_seconds`。
