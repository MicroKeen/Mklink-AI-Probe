# 0.3.6 正式发布验收

## 源码与回归

- 维护者明确授权 COS 香港公开下载、正式发布、保留 GitHub/Gitee 备用、撤下腾讯云测试版并通知 Dot；仅构建 Windows。
- PR50 检查头 e817ca1850bf5f3f46843a0fbac7bb1ce96efe95；三项 CI 通过。PR50/51 均合并，正式源 d000370b901a72e4f8ec8fe09cf8b837f2579f0c 与已检查树相同。未更改分支保护。
- 全 Python 5478 通过、2 可选跳过，4 个打包测试因外部 FLM 环境遗漏失败；补齐构建环境后，涉及的两个文件共 6 项通过。保留原始失败报告，不宣称首次全绿。
- 全 GUI 101 文件 / 1104 项通过，TypeScript 与生产 Vite 构建通过。最终固件/发布定点 20 项通过。

## 最终包资格

- 从干净最终 main 重新构建 NSIS，现有更新公钥独立验签通过。Windows 尚无 Authenticode。
- 真实原生旧版本从腾讯云 preview 索引下载最终 COS 安装包，覆盖安装后自动重启到 0.3.6；实装 3625 文件与提取包一致，210 Python / 41 Web 精确一致。
- Windows-only PATH、无主机 Packs/FLM 条件下，冻结 CLI、SVD、stdio MCP、常见 FLM、诊断导出、BIN/HEX 脱机校验预览通过。STM32F767xx 返回 20 个模糊候选，不要求特定型号说明。
- 安装版原生后端健康约 2.699 秒，无主机 Python 子进程；正常退出码 0，运行端点和监听端口释放。
- 完整 Skill 含 7059 目标、2224 FLM、4800 外设。真实 0.3.5 → 0.3.6 升级验证 2622 文件一致，用户文件保留，二次检查无更新，真实 MCP 模糊匹配通过。
- 最终独立 Windows Site Agent 两项实际包测试通过，不等于跨物理主机硬件矩阵认证。

## COS 下载

- 香港桶公有读、私有写，只放公开发行资源；未开额外加速或购买新套餐。自有下载域名将资源重定向到 HTTPS COS，更新索引保持不缓存。
- 七份正式文件在上海服务器关闭代理后完整下载，大小/SHA-256/Range 206 全部通过。安装包 76.511 秒 / 2.299 MiB/s，Skill 20.391 秒 / 4.620 MiB/s，Site Agent 34.552 秒 / 1.851 MiB/s；这是本次线路测量，不承诺用户固定速度。
- 本机原生更新与 Skill 更新也实际完成。此前本机无代理 COS DNS 解析失败记录保留，不将单线路成功解释为所有网络可达。

## 固件与实机边界

- 同版本修复识别使用固件构建时间；它是构建身份，不是设备上镜像的密码学哈希证明。未知修订允许明确重装，较新版本/构建阻止降级，成功回读需精确型号/版本/构建一致。
- 本轮四份指定固件已在 COS、GitHub、Gitee 完整下载验哈希；未再次刷下载器。
- H743 在线烧录/回读、RTT/Watch 等沿用同运行代码的发布准备记录，不将本轮打包验证算作新增硬件测试。UART 未接；V3 空 RTT 约 30 分钟掉线、30MHz 并行读错、N32 外置 Flash 和其他矩阵仍待处理。详见 [发布准备](v036-release-readiness-20261025.md)、[固件构建识别](v036-cos-firmware-revisions.md)。

## 发布载荷

| 文件 | 字节 | SHA-256 |
| --- | ---: | --- |
| `Mklink-AI-Probe-v0.3.6-Skill.zip` | 98783680 | `4fb046323d046aa854e7373594c5fe329de9435fa21f116afd76c3aa6979cf3f` |
| `Mklink-AI-Probe-v0.3.6-x64-Setup.exe` | 184426337 | `0cdd5ccb1d75e68aadb7a90e93a6c35e2750b40230167230349b0d335e25650e` |
| `Mklink-AI-Probe-v0.3.6-x64-Setup.exe.sig` | 428 | `98231aeefedbd4d2d09fd919179a6684b3f4dfa63b75acf1d4d69d492b0fb40c` |
| `MKLink-Site-Agent-v0.3.6-windows-x86_64-portable.manifest.json` | 2391 | `9cae914fb726eced14940cb0bbeed9111fc02149df659f3c44e72eebb2f9451c` |
| `MKLink-Site-Agent-v0.3.6-windows-x86_64-portable.zip` | 67063532 | `5dac1dac32cbb7a8dd0bae6f495d4f8a23dd079fb87e852a2ad2b4e59951bcb9` |
| `release-manifest.json` | 1275 | `f66d0c3922eec7c3442fce823d916127e1baa24d435cbef796a1a6dd4cdd1a8c` |
| `SHA256SUMS.txt` | 562 | `c9e235db70b3d9abdf0f6de2854d29ba5de645eb81698dedd41214df6e09e20e` |

## 正式发布与收尾

- [MicroKeen 正式发布](https://github.com/MicroKeen/Mklink-AI-Probe/releases/tag/v0.3.6)、[旧 GitHub 备用](https://github.com/Aladdin-Wang/Mklink-AI-Probe/releases/tag/v0.3.6)、[Gitee 备用](https://gitee.com/Aladdin-Wang/Mklink-AI-Probe/releases/tag/v0.3.6) 的不可变标签对象相同，均解析为正式源 d000370b901a72e4f8ec8fe09cf8b837f2579f0c。
- 两个 GitHub 仓库各七份附件均匿名完整下载验哈希；Gitee 明确拒绝超过 100 MB 的 Windows 安装包，保留实际完整 Skill 附件，安装包索引使用已验证 GitHub URL。模拟主源不可达后，安装后的 Skill 更新器访问真实 Gitee 索引并完整下载校验通过。
- 腾讯云 stable、MicroKeen release、旧 GitHub updates 和 Gitee updates 四个索引回读为 0.3.6，源提交、Windows 签名、Skill 大小及哈希一致；本次只有 Windows 平台项。两个固件索引在四个入口均回读一致，历史固件分支以快进方式更新。
- 腾讯云 preview 索引和旧测试包移至非公开可恢复归档，旧路径实际返回 404；旧 0.3.5 正式 Skill 仍为 200。没有删除 GitHub/Gitee 历史正式附件。
- 已在维护者指定的 Dot 网站会话发送正式资源、固件索引、测试版下线信息和网站更新要求，并核对消息已发送。通知完成不等于网站已部署；网站完成状态需以 Dot 回报和页面复核为准。
- 临时部署公钥已从服务器撤销，新 SSH 连接实际返回 Permission denied；其余 authorized_keys 行保留。
- 全局 Codex Skill 已按正式归档同步，2622 文件逐字节一致，旧内容备份保留；现有 AI MCP 进程需重启加载新代码。
- 根 README 与公开 Skill README 同步为无固定版本的功能/安装/更新说明，下载优先腾讯云，新增诊断入口和能力边界。该文档改动走后续 PR，不修改正式标签和发布包。
- 最终证据与正式资源保存在构建根 artifacts/v036-official 和 reports/v036-cos-20261025；含设备标识、路径和界面截图的本地证据不提交。
