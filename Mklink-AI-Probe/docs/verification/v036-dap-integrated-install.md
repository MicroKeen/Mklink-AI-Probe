# 0.3.6 DAP 恢复整合与 Windows 覆盖安装

2026-10-24，用户授权整合后重新打包并覆盖安装。组合源码为
`dde3ad0188f4d715977d06d34ba231b1d9d78d31`，在 `codex/tencent-update-preview`
合入 PR #51 的完整头 `7aca04805c06421ad23cdbd1943482f1a1f80cd9`。
保留本分支连接诊断、启动优化及新交接，未合并 main 或发布正式更新。

## 内容与边界

- 新 CDC 连接核对同一探针的 Windows DAP 独占所有权后，发送 HostStatus 清除遗留占用。
  活动 IDE 持有句柄时跳过，不按空闲时间抢占，不发目标暂停、复位或内存命令。
- 启动界面只显示 30/60/90/100 进度条，取消勾选列表及正常阶段文字。
  两个并行前置任务完成后到90%，工作区绘制后到100%，延迟不虚增。
- 后台管理页诊断导出、完整 FLM/Packs、腾讯云 preview 和 GitHub/Gitee 备用保留。
- DAP 实物证据仍以 [原修复报告](v036-dap-orphan-recovery.md) 为准；本轮未打开目标设备、
  重测 SES、烧写或升级固件。V2/V3、完整 SES 矩阵尚未验证，不继承 V4 实物结论。

## 验证

- 整合后353项 DAP/bridge/MUX/runtime/诊断/启动定点通过，完整GUI 1099项通过。
- Python全套首轮5444通过、2跳过、4项准备错误：隔离Site Agent源码未获得本地FLM路径。
  配置已验证的 `MKLINK_BUILTIN_FLM_ROOT` 后原4项全部通过（含重新构建独立包），
  累计5448项通过、2跳过。没有修改产品或测试来绕过资源校验。
- PR #51 精确头的 feedback/shared-runtime/shared-gui 三项远端检查全部成功。
- 维护者 builder 经受管理构建入口生成 Windows NSIS；TypeScript/Vite、Rust编译成功。
  构建资源验证7059目标、2224 FLM blobs、4800外设目标；未构建Linux/macOS。
- 解包及实装210份Python源码、41份Web资源与组合源码一致；安装目录含完整
  `_internal` 的3624份文件与候选逐字节一致，新增 `dap_recovery.py` 已随包。
- 无宿主Python和外部Pack环境下，实际stdio MCP、常用FLM、泛型号搜索、离线SVD、
  健康、被动探针枚举、断开状态诊断ZIP、全部Web文件HTTP字节一致、后台正常退出通过。
- 覆盖安装exit 0。原生窗口后台健康、未连接；后台管理导出入口可用。
  实际安装Web加载显示100%进度后进入工作区，后台管理正常，控制台错误为空。
- 原生测试进程启动至健康3.227秒，原生初始化至首屏绘制3.100秒；仅一次检查，
  不作为前后性能比较。正常关闭exit 0，后台端点和监听端口释放，无宿主Python子进程。

## 产物

- `Mklink-AI-Probe-v0.3.6-dap-dde3ad01-Setup.exe`
- 大小：184418196字节。
- SHA-256：`09db218458f0fc8bcfabacad11d58b2efda6297ecd4c68c690886b7cdc80a77b`。
- 构建根证据：`artifacts/v036-dap-integrated-20261024`；Python报告在 `reports/v036-dap-integrated-*.xml`。
- 本地未签名preview包，无 `.sig`，未替换腾讯云在线包或正式GitHub/Gitee附件、索引、标签。
  Windows仍无Authenticode签名。当前安装已覆盖此前86f9a75d勾选版。
- 运行目录 `run-20261024-211729-cf8b36d1`、`run-20261024-211940-3ef91009`、
  `run-20261024-212904-ccd42c1a` 含测试链接，构建入口已保留，未强制删除。
