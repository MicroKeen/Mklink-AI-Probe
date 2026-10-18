# 0.3.5 正式发布验收

维护者在 2026-10-18 明确授权验收、合并和发布，并要求未解决项保留交接。

## 源码与回归

- PR43 检查头 8d422029cdd87188bfb0d7f612cc98afe32e128d；必需 CI 和共享前后端 CI 通过，无未解决讨论。
- PR43 合并后的正式源 2f474f60372efdf1218211d4235f05343eab840e，与检查头树一致。未修改分支保护；使用指定整合者已有的 PR 合并权限，独立必需 CI 规则无绕过者。
- Python 全量 4926 通过、2 可选跳过、1 旧 Skill 文本断言失败；运行期间该契约已按 V2.9.0 支持修正，随后相关 68 项全部通过。保留原全量失败报告，不宣称一次全绿。
- GUI 94 文件 / 985 项通过，TypeScript 与生产 Vite 构建通过。产品运行代码在这轮复测期间未变化。

## Windows、Skill 与实机

- 从干净最终 main 重新构建签名 NSIS。覆盖安装退出 0；提取/安装后 198 份 Python、40 份 Web、四个安装载荷核对一致。Windows-only PATH、无外部 Packs 下冻结 CLI、SVD、实际 stdio MCP、HTTP 资源和独立后台正常退出通过。
- 独立 Windows Site Agent 重新构建，基于实际包的 2 项资格测试通过。它不等于跨物理主机远程调试认证。
- 全局 Skill 2605 文件与正式归档一致，CLI/SVD/实际 stdio MCP通过，旧包备份保留在非系统盘。
- 当前 F103 是八通道测试固件：先核对 AXF 的 Flash 片段与板上代码匹配，再验证 RTT 八通道各约 110 行连续序号，8 路各 256 字节下行计数/hash一致；UART 115200 接收 109 条连续文本，256 字节下行计数/hash一致。未重编译或覆盖当前板上程序。
- 初版验收脚本过早发送，启动阶段被 409 拒绝；读取板端计数确认全零后，修正为等待 streaming 再发送。原失败日志保留；未修改产品代码或重放未知操作。
- 安装生产 Web 自动搜索解析并显示 CH0~7；SuperWatch 搜索入口精简、三变量曲线、点击名称列表后移开鼠标保持展开通过。默认不记录，显式记录生成 5034 行 / 549409 字节日志，停止后大小稳定。
- 冻结/Skill MCP 均复用安装版后台，V2.9.0 同版检查返回 up_to_date，F103 CPUID 为 31c21f41，随后 detach。未把同版检查算作再次固件升级。
- 本轮浏览器工具在本地文件选择器超时，未宣称最终包完成新的文件导入/PNG实测。原图回放、暂停、缩放、PNG、手动编译重载、MSH、双波特率二进制串口、五秒拔插和其他功能沿用相同运行代码的既有专项证据，见下列记录。

## 专项记录与未解决项

- [发布准备与原生回放](v035-release-preparation.md)、[手动重载](v035-superwatch-manual-reload.md)、[原图回放](v035-inline-replay.md)、[日志记录](v035-continuous-recording.md)。
- [串口续行](v035-serial-lines.md)、[串口即时显示/MSH](v035-serial-immediate.md)、[RTT 搜索及布局](v035-rtt-inspect-fit.md)、[下载型号同步](v035-download-target-sync.md)。
- [位域解析](v035-dwarf-bitfields.md)、[Pack 外设导入](v035-peripheral-import.md)。
- [五秒恢复](v035-transport-recovery.md)、[V2 RBL 更新](v035-v2-rbl-update.md)、[CDC 995 待排查](v035-cdc-995-disconnect.md)。

CDC 995 无人操作断链根因、UART 重配置首字节、客户旧版 MSH 丢 s / status6 现场、历史下载 2% unknown、30MHz 并行目标读错继续待排查。成功主动拔插不证明 995 根因修复；未知写入不得自动重放。

Mac/Linux 实体 USB/MSC、原生窗口和原地签名更新、跨物理主机 Agent、真实 Modbus、完整 RTOS Trace/YMODEM/全部 MCU/保护/供电组合未完整认证。原生 CI 包资格不替代上述实体矩阵；Windows 无 Authenticode，Mac 仅 ad-hoc 无 Developer ID 公证。维护者已明确这些未解决项保留交接，不扩大验收结论。

独有证据保存在构建根 artifacts/v035-release-acceptance、v035-official、v035-official-native。含联接的测试 run 目录保留人工处理，不强制清理。固件新资产独立记录见 v035-probe-firmware.md。


## 发布结果与正常退出

- [正式下载](https://github.com/MicroKeen/Mklink-AI-Probe/releases/tag/v0.3.5)：两个 GitHub 仓库各 17 个附件，匿名完整下载校验大小与 SHA-256 后才更新三个渠道索引。三个索引均回读为 0.3.5，五个平台的签名/大小/hash 和 Skill 源提交一致。
- macOS ARM/Intel 与 Linux 来自同源 [原生 CI 39116320413](https://github.com/MicroKeen/Mklink-AI-Probe/actions/runs/39116320413)，三个归档 CRC、GitHub artifact digest、内部清单全部核对；冻结 CLI/MCP/Web 与正常退出资格通过。五份更新签名均用现有公钥实际验签。
- Gitee 仅尝试镜像 Windows 和 Skill；Windows 超过 100 MB 被服务端明确拒绝，索引使用已验证 GitHub URL。Skill 为实际 Gitee 附件，安装后的更新器在进程内模拟 GitHub 不可达、访问真实 Gitee 索引并完整下载校验通过。
- 全局 Skill 的已验证 ZIP 与最终发布 ZIP 完全一致。AI 已运行进程需重启加载新 Skill；没有再次升级或回退下载器。
- 用户正常关闭最终原生窗口后，MKLink 进程、运行端点和监听端口均为 0；此前已停止测试采集、detach AI 并释放设备。
- 正式 Web 资源与本交接通过单独后续 PR 保存；不移动 v0.3.5 标签。新 V3/V4 固件的独立发布记录见 [固件发布](v035-probe-firmware.md)。

## 正式载荷

| 文件 | 字节 | SHA-256 |
| --- | ---: | --- |
| `Mklink-AI-Probe-v0.3.5-aarch64-apple-darwin.app.tar.gz` | 165057517 | `4e1731b76d5d950e88d6308e2ebf62e7df4f5a2d27856e61358e2879fcd428a4` |
| `Mklink-AI-Probe-v0.3.5-aarch64-apple-darwin.app.tar.gz.sig` | 452 | `f5bff8a54bb793341ce556a5dfb4d474cd122b7cb4255a1238448b3801ca8bd9` |
| `Mklink-AI-Probe-v0.3.5-aarch64-apple-darwin.dmg` | 165323369 | `50a430fc44191b61154c7c2db74a6a095f7c847d9f1e90d359a5ffdb68a26ca1` |
| `Mklink-AI-Probe-v0.3.5-Skill.zip` | 98711557 | `e148265e43e4f3e0cb56e7cf35ce51cb84f5d94a5090a70664a038a13d6bf457` |
| `Mklink-AI-Probe-v0.3.5-x64-Setup.exe` | 187223667 | `ebf07f2777f76f3c8a79a87793a86cb93c688d757d37ecf9e30b746a9d4e0c12` |
| `Mklink-AI-Probe-v0.3.5-x64-Setup.exe.sig` | 428 | `52c019fb68eae58a07ca9498b185fec95cc2e5fc042e5f61cd70858a56f1a6ee` |
| `Mklink-AI-Probe-v0.3.5-x86_64-apple-darwin.app.tar.gz` | 165493684 | `db3a2b84ce61dbcc47a6441a76adcb8b6a16bfd0841e32bd98964e0f00edfa77` |
| `Mklink-AI-Probe-v0.3.5-x86_64-apple-darwin.app.tar.gz.sig` | 452 | `dbcb9049e39bf79c8e208ebd55a8946a0855cfc4f3fd83950dad71488a27264d` |
| `Mklink-AI-Probe-v0.3.5-x86_64-apple-darwin.dmg` | 165726944 | `7525eb72a00ecd8970a8337e313e81ccec67f137d9580f41d210eabd3eed75e4` |
| `Mklink-AI-Probe-v0.3.5-x86_64-unknown-linux-gnu.AppImage` | 261646840 | `1edd2f30666f7a96bf86d03358ba37fc53f4684aeea729001cc8735a87498601` |
| `Mklink-AI-Probe-v0.3.5-x86_64-unknown-linux-gnu.AppImage.sig` | 456 | `0ae2846e93b7edf9e75c87a5b034c465593f6f1f864324dbdf161e1947b07b0a` |
| `Mklink-AI-Probe-v0.3.5-x86_64-unknown-linux-gnu.deb` | 183743888 | `f8478b28e9a564311a2ad013c4a6acb892f07a734b3c2494a4eb6775281186b8` |
| `Mklink-AI-Probe-v0.3.5-x86_64-unknown-linux-gnu.deb.sig` | 448 | `e117420b80605415919e19b2e2c489065fae21850681be1e1944258190637049` |
| `MKLink-Site-Agent-v0.3.5-windows-x86_64-portable.manifest.json` | 2391 | `fabdce5a7af760f687ee9870994406eaaa8b191e1b27de11edfe1dbb8af2212d` |
| `MKLink-Site-Agent-v0.3.5-windows-x86_64-portable.zip` | 66940594 | `86ee0c5f4bb702b15ae3dec4087df08b21e16f7ebe2e0eca54a3d7c55907509b` |
| `release-manifest.json` | 3587 | `07230c296187494adc11304d956e95b77bd7d0fd1ce266254106e49c155bd223` |
| `SHA256SUMS.txt` | 1779 | `238b0e161807d35604ff6a2a6ec0035101d4792c9bceba6e7612444cc057cb05` |
