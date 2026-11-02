# RT-Thread SystemView 模板兼容修复

产品提交 `76307f05`，共用 `codex/v0.4.2-fixes` 分支；仅修改宿主随附模板和使用说明。
指定固件会话在 H7 实测中发现问题并修正自己的测试工程，本会话据此修复以后集成时复制的模板。
未改动其工程、不可变宿主候选 `4be6ab66-verified`、固件、全局 Skill 或已安装软件。

## 原因与行为

- RT-Thread 的固定长任务名可能没有 NUL。原模板直接把字段交给 SystemView，可能把后续对象字段编码为名称，造成 TASK_INFO 解析丢弃。现在在临界区有界复制并补 NUL，随后同步编码；`RT_NAME_MAX=0` 的字符串指针模式单独处理。
- 原模板依赖 `RT_VERSION >= 5` 判断线程布局，但部分 5.1 内核仅定义 `RT_VERSION_MAJOR`；5.0 虽有 `parent`，却没有新调度字段。现在名称与链表使用公共对象头，优先级按 `RT_SCHED_PRIV` 是否存在选择。
- 创建钩子区分旧 4.0 单回调和新 hooklist 节点接口。没有该可选接口时保留任务列表与任务切换，不调用不存在的 setter，不接管全局 object-attach 钩子。调度器仍使用单回调槽，已有回调需要显式组合。
- 使用说明明确：启用 `SEGGER_RTT_SECTION` 时，SystemView 核心初始化会调用 `SEGGER_RTT_Init()`。额外 RTT 通道应在 SystemView 后配置，不能反复初始化清除描述符。普通 RTT 占 CH1 时，可将 SV 设为 CH2，并扩大上下行描述符数量。未修改 SEGGER 核心初始化语义。
- 记录 `target_initializing=true` / `user:api:connect-init` 的 409 时序：目标初始化尚持有资源时，后续命令须等待其释放。此项是操作指导，不是运行时自动重试修改，也不能算固件丢包。

集成命令继续不覆盖工程已有文件。更新 Skill 不会自动修复此前复制的适配器，须审查后合并，保留目标自己的时间戳、内存和通道配置。

## 验证与边界

新增 C 行为回归直接复制并编译实际模板：4.0、4.1、5.0、5.1 布局；旧回调、无创建钩子、hooklist；固定数组和指针名称，共七组。断言完整八字符名称、短名称、任务 ID/优先级/栈信息、空闲任务排除、调度与创建回调。

修复前复现满长任务名污染，以及新版字段和接口编译失败；修复后七组通过。结合解析器、任务名、CLI 和用户 Skill 边界检查，共 **104 项通过**。Windows MinGW GCC 执行 C 夹具；ARM GCC 使用现场 H7 工程真实 RT-Thread 5.1 头文件，hooklist 开/关两次 `-fsyntax-only` 通过。编译环境的 include 路径补齐后通过；未修改现场工程。夹具不是所有 RT-Thread 版本的完整构建或硬件验证，未宣称 AC5、SMP 或全部 RTOS 配置已验收。

官方接口依据：[4.0.4 rtthread.h](https://github.com/RT-Thread/rt-thread/blob/v4.0.4/include/rtthread.h)、[4.1.1 rtdef.h](https://github.com/RT-Thread/rt-thread/blob/v4.1.1/include/rtdef.h)、[5.0.2 rtdef.h](https://github.com/RT-Thread/rt-thread/blob/v5.0.2/include/rtdef.h)、[5.1.0 rtdef.h](https://github.com/RT-Thread/rt-thread/blob/v5.1.0/include/rtdef.h)。分支回移可能改变接口，不能只看版本号推断能力。

测试经 `scripts/build_workspace.ps1`、`F:/MKLink-Build` 执行，日志 `run-20261031-002437-3b6252ea.log`。含链接的测试临时目录由包装脚本保留，没有强删。本轮不构建安装包、不覆盖安装、不正式发布。
