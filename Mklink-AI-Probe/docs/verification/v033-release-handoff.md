# 0.3.3 正式发布交接

2026-10-11：维护者明确授权合并、签名、正式发布、更新本地 Skill、回原工作空间交接并清理临时工作树。PR [38](https://github.com/MicroKeen/Mklink-AI-Probe/pull/38) 已合入 main；不可变 `v0.3.3` 标签对应 `11616f8077c469c83f0b82de0de5b0f12098c960`。交接及正式 Web 资源通过后续 PR 整合，不移动版本标签。

## 维护入口和正式文件

- 原 `Mklink-AI-Probe` 工作空间为后续唯一上位机维护入口，从 `docs/ai/CURRENT_HANDOFF.md` 开始。
- [0.3.3 正式下载](https://github.com/MicroKeen/Mklink-AI-Probe/releases/tag/v0.3.3) 提供 Windows NSIS、两种 Mac DMG、Linux AppImage/DEB、五份更新签名、Skill 和 Site Agent，共 17 个附件。
- 原 Git 根 `.build/artifacts/v033-official/release/` 为完整正式归档；`archive-manifest.json` 记录复制后哈希。`qualification/` 保存正式冻结程序、原生包、签名、渠道、本地 Skill 以及此前安装候选真机证据。设备标识、截图、日志和本地路径只保留在忽略目录。
- 本机 Skill 已从 0.3.1 更新到正式 0.3.3，逐文件与发布 ZIP 核对，并验证离线 CLI、STM32F407VE SVD 目录及 MCP。旧 Skill 已备份；已运行的 AI 进程需重启才能加载新代码。

## 验证结果与边界

产品运行时代码与最终已安装 `77f56f20` 候选一致。后续为测试隔离、文档和构建版本元数据。GUI 全量 934 通过；Python 原运行因 E 盘满有一项环境失败，迁移 F 盘后重跑通过，合计 4747 通过 / 2 跳过，不能描述为一次全绿运行。PR38 精确头的三个合同检查通过后合并。

候选 77f56f20 已实际覆盖安装，安装载荷哈希匹配；最小 PATH 下 CLI/MCP/SVD 和 F103RC 连接、擦除、烧录、校验、复位、断开通过，113304 字节约 10.25 秒。AXF 5909 变量、124 结构体、115 枚举及实际搜索、调整区域高度通过。F103 校验约 0.30 秒，未测得显著性能提升。

正式源 11616f80 重新生成 Windows 更新签名 NSIS、Skill 和 Site Agent，验证内置 7059 FLM 目标、2224 blobs、4800 SVD 目标。正式提取载荷在 Windows-only PATH 下 CLI/MCP、35 项生产 Web 文件字节和 MIME、健康检查及正常退出通过；原生界面显示 0.3.3 / 11616f8077c4，三个 SuperWatch 区域及键盘调整高度通过。原生启动约 10.62 秒，没有 Python 子进程；正常关闭后本次进程及 8765/8766 均释放。

本轮正式 NSIS 的再次覆盖安装 UAC 被取消，因此不能声称 11616 正式安装器已重新实装；上述覆盖安装和 F103 硬件证据来自运行时代码相同的 77f56f20 候选。正式提取包验证单独记录，不冒充安装结果。

Apple Silicon/Linux 来自正式源 [CI 38069170299](https://github.com/MicroKeen/Mklink-AI-Probe/actions/runs/38069170299)。Intel 的该运行两次停于 DMG 最后打包步骤，不作为合格结果；精确同源的 [详细诊断构建 38071279659](https://github.com/MicroKeen/Mklink-AI-Probe/actions/runs/38071279659) 成功，实际 DMG 挂载/复制、更新 tar 可执行文件及权限一致、冻结 CLI/MCP、生产 Web 和正常退出均通过。该重跑仅增加 Tauri verbose 输出，没有改变产品源码；早先打包失败原因尚不能确定。

三个原生目标的 ZIP CRC、清单源提交、全部文件大小/SHA-256 和 qualification 已核对。Windows、两种 Mac tar、Linux AppImage/DEB 五份更新签名使用既有配置公钥实际验签。Mac 仍是 ad-hoc 签名，未做 Developer ID 公证。Mac/Linux 物理 USB/MSC 和原地升级仍按维护者先前决定由客户后验。

## 发布渠道

两个 GitHub 仓库各 17 个公开附件已匿名完整下载验证；版本索引最后写入。回读 MicroKeen/release、旧 GitHub/updates、Gitee/updates，均为 0.3.3，五个平台的 SHA-256、大小、签名及 Skill 源提交一致。保留既有更新公钥、应用 ID 和旧端点。

Gitee 上传返回 HTTP 400，按此前已明确采用的兼容策略，17 个缺失镜像文件使用已完整校验的 GitHub URL；已有镜像不覆盖。该渠道当前不是完整附件镜像，受 GitHub 网络可达性影响。实际名单和 HTTP 状态见 `gitee-fallback.json`。

## 后续问题与清理

原始 30MHz/1µs CDC 停采、首次启动后台离线、客户 F405 PROGRAM100% 后读线程退出尚未在客户同条件下复现。新增保护和原因链不等于现场根因闭环。客户受限 Python/AI/GD32、多 FLM 外置 Flash 实物验证仍待反馈；不把模拟验证替代实物结果，不重放未知烧录任务。共享后端的 USB 身份、唯一串口所有权及操作锁边界保持不变。

固件升级入口按型号选择最新索引版本，本次未另行烧录探针固件或改供电。既有固件高速并行读取限制仍按历史交接留待后续；需要固件改动另开会话，不扩大到本次应用发布。

原工作空间保留正式文件、必要回归证据、旧版本正式归档及共享依赖缓存。两个废弃 0.3.2 候选目录已清理约 1.86 GiB。临时 startup-cdc 工作树在本交接 PR 合入并确认无未保存变更后删除，仅解除指向原工作空间的已知目录联接，不能递归删除联接目标；实际结果见本地 `worktree-cleanup.json`。含联接的历史测试目录及仍被旧安装器占用的文件保留人工处理，不强删。长期跟进保持暂停。

## 正式载荷

| 文件 | 字节 | SHA-256 |
| --- | ---: | --- |
| `Mklink-AI-Probe-v0.3.3-aarch64-apple-darwin.app.tar.gz` | 164945081 | `4d1b9beb3f3f2164990b5464539a81c88012ced7fec50a78caf2a798870ec723` |
| `Mklink-AI-Probe-v0.3.3-aarch64-apple-darwin.app.tar.gz.sig` | 452 | `bb651d260c01fbefb768f92b0a6460ee26964de3804af6e252ea60b1626d9366` |
| `Mklink-AI-Probe-v0.3.3-aarch64-apple-darwin.dmg` | 165199999 | `f805f1147b2aab999061e6396394067ac16a69e6aefe3ed43acd54ac6ca20f4f` |
| `Mklink-AI-Probe-v0.3.3-Skill.zip` | 98682551 | `e1587c100f6f1a2df55d3e72b2e3b40eae10cb720261ce9c0b8e3b327b62b1bb` |
| `Mklink-AI-Probe-v0.3.3-x64-Setup.exe` | 176557369 | `90c9d57ec6fe7541b76b47d668f023f5f49a62701202045da50a4db19957c640` |
| `Mklink-AI-Probe-v0.3.3-x64-Setup.exe.sig` | 428 | `c7ed4a75f6c3d191090600a5f8d2f0c89888860766c1ab5c2c9203347cb7f3b1` |
| `Mklink-AI-Probe-v0.3.3-x86_64-apple-darwin.app.tar.gz` | 165369955 | `112026cf8b2786f1e6e191a26fc963b68c79d665e8c4d05d15a8ad75b7447642` |
| `Mklink-AI-Probe-v0.3.3-x86_64-apple-darwin.app.tar.gz.sig` | 452 | `26d061dcff2ef7431d718c617774e8aff7ca0b2a95f83ee8c2641ceeff60c370` |
| `Mklink-AI-Probe-v0.3.3-x86_64-apple-darwin.dmg` | 165588169 | `4d9eb7290286b9aaac1e158a4ac4433d9ba3ee6f3bbe76251bfeee342a081d55` |
| `Mklink-AI-Probe-v0.3.3-x86_64-unknown-linux-gnu.AppImage` | 261511672 | `bb5f1c06224864b0fa370f3a6d34aecbcffc3efe5375cd4ed329ff8a4100901c` |
| `Mklink-AI-Probe-v0.3.3-x86_64-unknown-linux-gnu.AppImage.sig` | 456 | `7fcfa93647316f74aeb46601452e5ff253cd0a55f85b5da88a54cd01d91cb715` |
| `Mklink-AI-Probe-v0.3.3-x86_64-unknown-linux-gnu.deb` | 183631306 | `19328afd99e58d71762a23be0b697adf41b4a2beb7b9b7465fab8f7f871fc409` |
| `Mklink-AI-Probe-v0.3.3-x86_64-unknown-linux-gnu.deb.sig` | 448 | `0e0662756e4358236eec59dad7c69f73b4e8e72f82c97b155e7382eded5ae8fa` |
| `MKLink-Site-Agent-v0.3.3-windows-x86_64-portable.manifest.json` | 2391 | `c2238e22cc6d54f60d849be845dfb253d0ae6fc265a8e6df8c3f873ed002e589` |
| `MKLink-Site-Agent-v0.3.3-windows-x86_64-portable.zip` | 66886811 | `3988ea157a4a06270759429b509d7718cff37a73b0c1c9efa623c0b21a4d4c9b` |
