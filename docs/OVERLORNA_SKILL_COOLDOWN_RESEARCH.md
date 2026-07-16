# OverLorna 技能冷却状态研究

研究对象：`OverLorna 2.0.45.10 release` 与 `2.0.46-dev3`。仅做单文件静态拆包与反编译，
没有启动 OverLorna。

## 结论

这两个版本没有现成的“技能冷却监控/HUD”。它们能从封包识别技能准备、就绪、使用、完成、
取消、开始和停止，但运行时只维护“角色当前是否正在使用技能”这一布尔值，并未维护每个技能的
冷却开始、剩余秒数或可用状态。

`OverLorna.Shared.Mabinogi.Network.Op` 确实定义了 `ResetCooldown = 27047`，但
`OverLorna.Monitor.SessionManager` 没有分派这个 opcode，`SessionHandler` 也没有对应处理器。
所以这只是协议表中存在的名字，不代表 OverLorna 使用它监控冷却。

OverLorna 的“Condition Countdown”是 BUFF/DEBUFF 到期提醒：它使用 condition 的
`ExpireTime` 驱动 Toast，与技能冷却不是同一套状态。程序集内也有进程内存扫描工具类，但在
应用与监控程序集里没有调用者；技能冷却逻辑没有走内存读取。

## 可以复用的信号

最可靠的通用起点是服务端回给客户端的 `SkillUse`：OverLorna 的协议号为 `27016`，包中含
角色 ID 与 Skill ID。它能证明服务器接受了本次技能使用，比按键、动画或本地施法开始更适合作为
冷却起点。现有 mabicat 日志中的 `EventId 10/11/12/13` 呈现与
Prepare/Ready/Use/Complete 一致的固定顺序，其中 `EventId=12` 是首要待验证的 SkillUse 映射。

但 SkillUse 只可靠地说明“冷却从这里开始”，不能单独证明“现在已经冷却完成”。如果技能冷却
固定，或者只有少量已知装备档位，可以按 SkillUse 的服务器时间加配置时长计算，并在收到新的
SkillUse、换角色、换频道、死亡或专用重置信号时修正。

## 已排除的候选

- `SkillPrepare/SkillReady/SkillComplete/SkillCancel` 描述一次施法流程，不是技能冷却完成。
- 归档 raw 中的 `Op=0x69a8` 带 Skill ID 与时间，但三例 `SkillId=50161` 都与同一实体的
  `EventId=13` 同毫秒出现，属于施法完成相关信号。
- `Op=0x69a9` 带 Skill ID 与一个 byte，但会在 SkillUse 后约 0--10 秒出现，并可同毫秒批量列出
  多个技能；战争序曲样本也只间隔约 1.7--9.4 秒，显然不是这些技能的自然冷却完成。
- 已检查的归档日志没有出现旧协议表所列的 `0x69a7 / 27047`。即使未来观察到 ResetCooldown，
  它也更适合作为“提前清空计时器”的校正信号，而不是日常冷却状态来源。

## 推荐实测

先选一个冷却短、界面读秒明确、没有装备减冷却的技能，连续做以下对照：

1. 单独施放一次，记录自身 `EventId 10--13`、原始 `Op/Msg`、CCId 和服务器时间。
2. 在游戏 UI 刚变为可用的瞬间再次施放，检查第二次成功的 SkillUse 与第一次之间的间隔。
3. 冷却中故意再按一次，确认失败尝试是否缺少 SkillUse；若缺少，就能证明该信号只在服务器接受后出现。
4. 分别测试普通装备、减冷却装备、死亡/复活、换频道，以及会重置冷却的效果。
5. 至少重复 20 次，统计“SkillUse 计时到 UI 可用”的平均值、中位数、P95 与最大偏差。

通过后可在视觉分支增加通用技能冷却 HUD：服务器确认使用后显示灰/暗色图标和倒计时，计时结束
恢复亮色或隐藏。对能产生明确自身 CC 的技能，优先使用 CC 开始信号；其他技能使用
`SkillUse + 已知冷却时长 + ResetCooldown 校正` 的混合方案，并在日志中标注计时来源与可信度。
