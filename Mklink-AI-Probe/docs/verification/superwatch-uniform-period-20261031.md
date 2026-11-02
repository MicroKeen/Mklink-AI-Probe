# SuperWatch 统一输入周期下限

2026-10-31，按用户在指定固件会话中的最新要求，撤销动态下限、布局适用域缓存和额外提示方案。指定固件会话确认单个 4B 变量最快复测约 254–267k 组/秒，平均周期约 3.75–3.94 µs；向上取整采用统一 **4 µs（0.000004 s）** 输入下限。本次宿主修改未接触硬件，以上速率是固件会话提供的依据，不是本次重新测量。

## 结果

- Web、桌面源码与独立 viewer 的 SuperWatch 输入最小值均为 4 µs，步长仍为 1 µs，默认周期仍为 1 ms，上限 60 s。
- `/api/dash/superwatch/start` 和 `/interval`、manager 使用同一下限。非法启动请求在资源申请、停止其他采集和修改周期之前拒绝；非法修改不改变原周期。
- 旧偏好中低于 4 µs 的周期不再回放。打开页面仍只同步服务端的实际状态，不重配已有共享采集，也不把旧服务端报告的周期伪装成 4 µs。
- 不新增动态限制说明或提示面板；保留既有非法输入反馈。VOFA 的 0 值语义不变。
- 下限只是允许输入的产品边界，不承诺所有变量布局、JTAG/SWD 时钟都能达到该周期。低层 `capture_dump` 的显式 fastest、单次 period=0 和协议 1 µs 粒度均不改变，正周期不会静默转换成最快模式。

## 验证

使用 PowerShell 7 与 `scripts/build_workspace.ps1 -BuildRoot F:/MKLink-Build`：

- `test_rtt_superwatch_streaming.py`、`test_online_flash_probes.py`：263 passed。
- `WaveformViewer.test.ts`：122 passed，包含 4 µs 成功、低于下限不发送修改、旧偏好不回放和 VOFA 回归。
- `vue-tsc --noEmit` 与 `git diff --check` 通过。
- 实际 IAB 浏览器加载源码 Vue 页面及隔离模拟设备：默认 0.001、min=0.000004、step=0.000001；3 µs rangeUnderflow，4 µs 有效，上箭头到 5 µs，下箭头停在 4 µs。未启动真实采集。
- 首轮 GUI 测试有四项新增断言失败：模拟 DOM 的 stepUp 浮点字符串误差，以及空参数启动不带 body；修正为数值容差和无 body 检查后复跑通过。无生产代码规避。

截图保留于本机 F 盘 `artifacts/connection-clock-20261031/superwatch-minimum-4us.png`。Python 测试的临时目录包含测试链接，构建脚本保留而未强删。

本次仅源码修复，未重建 GUI 交付资源、安装包或 Skill。已安装 Windows 仍为 e29d7809，既有固定 SDK 候选不变。固件性能差异、Keil 复验和最终固件 hash 继续由指定会话完成。
