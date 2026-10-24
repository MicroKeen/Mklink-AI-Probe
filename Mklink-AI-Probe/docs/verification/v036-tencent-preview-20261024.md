# 0.3.6 腾讯云预览更新验收（2026-10-24）

用户授权在现有腾讯云服务器配置下载服务，并测试发布 Windows 和完整 Skill，
暂不正式发布；GitHub/Gitee 保留备用。实现与验收源码为
`5920c5c53fa373891e1fb44ccbb63948977857d3`，PR
[#50](https://github.com/MicroKeen/Mklink-AI-Probe/pull/50) 保持待审。

## 服务与发布边界

- 独立域名 `https://download.microkeenai.com` 使用独立 Nginx 虚拟主机与证书；
  原网站配置文件 SHA-256 复核未变，原网站正常响应。
- TLS 证书到期日为 2027-01-22。每日检查脚本复用现有 ACME 账户，剩余
  30 天时续期。本次仅执行新证书的跳过分支，未伪称已实测未来续签。
- 只有 `/mklink/preview/latest.json` 已启用，返回 `Cache-Control: no-store`。
  `/mklink/stable/latest.json`、目录列表、隐藏文件和不存在路径均返回 404。
- 不可变文件先在非公开目录上传并核对大小、SHA-256、签名，再移入版本目录；
  公网完整下载和 Range 校验通过后，原子切换预览索引。
- 本次临时 SSH 公钥经用户明确授权加入，禁用转发并设置 24 小时有效期。
  部署完成后已精确撤销，随后重新认证得到 Permission denied。其他公钥保留。
  签名私钥没有上传；没有创建永久云端登录权限。
- GitHub `main` 仍为 `303a2667c1983bda33e2d77a411f7d3c3a684270`，
  `release` 仍为 `1566581a2db75fe8aa6af35bf8437e48e551020a`，
  `firmware` 仍为 `927ee94232e05eea1cb0e1e6682e0d0fef660de4`；
  没有创建 `v0.3.6` 正式标签或修改 GitHub/Gitee 正式索引。

## 测试包

版本目录：`/mklink/releases/v0.3.6-preview-5920c5c53fa3/`。

| 文件 | 字节数 | SHA-256 |
| --- | ---: | --- |
| Mklink-AI-Probe-v0.3.6-preview-Setup.exe | 187357618 | b8b9e746586a2e8d8b637ca6967357a61f6725df7584da87cdd83156db589cc3 |
| Mklink-AI-Probe-v0.3.6-Skill.zip | 98769443 | 0e6bc039a2f75a3a4e06ea537aa15d3f5527b8ea66a1bf0620735345d95c9ae9 |

Windows NSIS 使用现有 Tauri 更新密钥签名；主签名和 trusted comment 签名均
已用现有公钥验证。该包明确选择 preview 更新源，不能作为 stable 安装包分发。
仅构建 Windows；本次没有构建 Linux/macOS 包。Windows Authenticode 状态
不因 Tauri 更新签名而改变。

完整 Skill 含 7059 个目标、2224 份 FLM 和 4800 个外设目标。维护文档、
测试和维护工具没有混入用户包。实际公网下载用时：安装包 8.17 秒（21.87 MiB/s），
Skill 3.93 秒（23.94 MiB/s）；这是本机本次测量，不代表所有用户速度。
两份包完整字节校验和 `bytes=1024-2047` 的 206 响应均通过。

## 验证结果

- 最终完整 Python：5412 passed、2 skipped、60 warnings，749.71 秒。
  GUI：99 文件、1090 项通过；生产构建完成。
- 更新源选择、缓存隔离/损坏缓存、三源回退与预览配置恢复：96 项通过。
  最新源码的 feedback-contract、shared-gui-contract、shared-runtime-contract
  三项 GitHub CI 均通过。
- 解包后的冻结程序校验 206 份 Python、41 份 Web 和所需静态模块一致；
  不依赖宿主 Python、Packs 或 FLM 目录运行 CLI/MCP/SVD/HTTP。
  通用 `STM32F767xx` 搜索能返回不同容量候选，不自动猜定容量或算法。
  离线 ELF、变量选择/公式/颜色、组合 HEX 几何和正常退出通过。
- 从正式 0.3.5 完整 Skill ZIP 建立隔离安装，使用旧版真实更新脚本从腾讯云
  升级到 0.3.6；2617 个文件与新 ZIP 逐一匹配，用户自有文件保留。
  新版本再次检查不重复更新；实际 stdio MCP 模糊搜索返回 20 个候选。
- 在验证进程内分别模拟腾讯云、腾讯云加 GitHub 不可达，实际读取 GitHub
  和 Gitee 正式索引；Gitee 完整 Skill 下载大小和 SHA-256 通过。
  两个备用源仍为正式 0.3.5，0.3.6 客户端不会降级。
- 原生升级使用真正的较低版本 `0.3.6-preview.0` 测试客户端，腾讯云索引
  和目标二进制版本均为 `0.3.6`，没有伪造更高索引版本。
  已实际下载并在界面显示“v0.3.6 已下载完成”，点击安装后触发 Windows UAC。
  UAC 随后消失，安装目录可执行文件哈希仍为旧包，安装程序和客户端均已退出；
  没有证据判定是用户取消或系统超时。用户随后明确要求重试；13:10 重试成功，
  安装目录程序自动启动，界面版本为 0.3.6、后台正常，启动更新检查后没有
  重复下载/安装提示或错误。实际安装的四份载荷与解包产物逐字节一致，206 份
  Python、41 份 Web、冻结 MCP/SVD/HTTP、离线功能及隔离后台正常退出均通过。
  主程序 SHA-256 为
  `181e0ec82fe4ddcd22288467f6e3747c473292dea8a87d67883cfdd7bfde0077`。
  已安装新版保持打开，未连接或写入硬件。

本轮更新改动没有操作硬件。原 V4/F103 全功能实测属于前次候选，证据和
30MHz 并行采集读错限制继续保留，不能把前次实测当作本包新增硬件证据。

## 失败与恢复记录

首轮全量测试有 5404 通过、2 跳过、4 个打包环境错误：测试复制工作区没有
设置维护者内置 FLM 路径。补上 FLM 与已验证 Packs 资源后，4 项独立重跑通过，
随后最终完整 5412 项通过。不能把这个环境配置错误描述为用户安装包缺失 FLM。

第一次签名构建期间审查发现缓存根 JSON 为 null/列表/数字时可能调用 `.get`
失败，主动终止了该次构建，补充类型保护和 4 项参数化测试，再从干净提交
完成最终全量测试和构建。原失败和主动中断日志保留，没有复用半成品。

## 本地证据与继续步骤

证据位于配置构建根的 `artifacts/v036-tencent-preview-20261024/`：
`build-report.json`、`latest.json`、`extracted-qualification.json`、
`download-verification.json`、`skill-upgrade-report.json`、`fallback-report.json`、
`installed-qualification.json`、`native-update-report.json`。
构建根 `reports/tencent-preview-*-20261024.log` 保存全量、构建、升级、
服务器复核及密钥撤销日志。测试链接目录按存储规则保留，未沿链接强删。

腾讯云预览更新的 Windows 和 Skill 真实升级验证已完成。无需重新上传、
重新签名或重新授权 SSH。正式发布仍需用户明确指示，不能推进 stable 或正式标签。
