# MKLink 能力入口矩阵（源码自动盘点）

由 `_maintainer/testing/frontend_capability_matrix.py` 从实际注册表、CLI parser 和 OpenAPI 生成。
这是接入与路由契约清单，不是逐项真机通过证明。场景证据见 [验证报告](v050-capability-validation.md)。

生成的 `inventory.json` 同时保留 MCP 参数 schema 和 CLI 参数/choices，便于检查同一命令下的动作分支。命名布局的 HTTP 存储端点归为 protocol，对应的页面操作为 layout.save、layout.search、layout.load。映射列是业务能力对应关系，包装工具的参数必须按原入口转换，不能原样互换。

共享调用 155；灵活面板直接操作 234；MCP 工具 59；CLI 命令节点（含分组、别名及 remote 子命令）124；HTTP 操作 294。

`panel`：能力面板选择后执行，原校验/确认/任务边界不变。`agent-cli`：灵活面板 Agent 请求交给当前会话，使用原 CLI 并回复结果，尚不是可绑定的直接按钮。
`original-ui`：文件上传、下载、流及兼容业务入口仍在原页面，通过 gui_control 导航/原控件使用；未宣称均已成为独立子面板。`protocol`：认证、会话、代理、静态资源和控制协议，不作为任意 URL 代理开放。

## 灵活面板直接操作

| 名称 | 方法与原入口 | 验证层级 |
| --- | --- | --- |
| `breakpoints` | `POST /api/device/breakpoints` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `capture_dump` | `POST /api/device/dump-memory/capture` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `capture_peripherals` | `POST /api/device/peripherals/capture` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `config_read` | `GET /api/config` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `config_save` | `PUT /api/config` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `config_status` | `GET /api/config/status` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `configuration_description` | `GET /api/device/configuration` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `configuration_script` | `OFFLINE ` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `core_registers` | `GET /api/device/core-registers` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `dash_conflict_check` | `GET /api/dash/conflict-check` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `debug_speed` | `GET /api/device/debug-speed` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `device_connect` | `POST /api/device/connect` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `device_disconnect` | `POST /api/device/disconnect` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `device_reboot` | `POST /api/device/reboot` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `device_status` | `GET /api/device/status` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `diagnostic_events` | `POST /api/runtime/diagnostics/events` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `discover_probes` | `GET /api/ports/discover` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `dump_memory` | `POST /api/device/dump-memory` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `fault_snapshot` | `POST /api/device/fault-snapshot` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `flash_algorithm_remove` | `DELETE /api/online-flash/algorithms/{algorithm_id}` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `flash_algorithms` | `GET /api/online-flash/algorithms` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `flash_image_inspect` | `POST /api/online-flash/images/inspect-path` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `flash_image_preview` | `GET /api/online-flash/images/{image_id}/preview` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `flash_image_source_status` | `GET /api/online-flash/images/source-status` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `flash_job` | `GET /api/online-flash/jobs/{job_id}` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `flash_job_start` | `POST /api/online-flash/jobs` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `flash_job_stop` | `POST /api/online-flash/jobs/{job_id}/stop` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `flash_jobs` | `GET /api/online-flash/jobs/active` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `flash_memory_read` | `POST /api/online-flash/memory/read` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `flash_probes` | `GET /api/online-flash/probes` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `flash_target_algorithms` | `GET /api/online-flash/targets/{part_number}/algorithms` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `flash_target_memory_map` | `GET /api/online-flash/targets/{part_number}/memory-map` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `flash_targets` | `GET /api/online-flash/targets` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `flush_memory` | `POST /api/device/flush-memory` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `gui_action` | `POST /api/runtime/control/gui-action` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `gui_frontend_call` | `POST /api/runtime/frontend/call` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `gui_frontend_capabilities` | `GET /api/runtime/capabilities` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `gui_frontend_intent` | `GET /api/runtime/frontend/intent` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `gui_frontend_intents` | `GET /api/runtime/frontend/intents` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `gui_frontend_layout` | `GET /api/runtime/frontend/layout` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `gui_frontend_pages` | `GET /api/runtime/frontend/pages` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `gui_frontend_read` | `GET /api/runtime/frontend/read` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `gui_frontend_receipt` | `GET /api/runtime/frontend/receipt` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `gui_frontend_reply` | `POST /api/runtime/frontend/reply` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `gui_frontend_save_layout` | `PUT /api/runtime/frontend/layout` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `gui_present` | `POST /api/runtime/control/present` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `gui_snapshot` | `POST /api/runtime/control/gui-snapshot` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `gui_windows` | `GET /api/runtime/control/windows` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `halt` | `POST /api/device/halt` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `hardfault` | `GET /api/device/hardfault-detail` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `hardfault_check` | `GET /api/device/hardfault` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `hardfault_decode` | `POST /api/device/hardfault-detail` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `health` | `GET /api/health` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `hpm_debug` | `POST /api/device/hpm-debug` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `hpm_otp_isp_batch_plan` | `POST /api/device/configuration/hpm-isp-otp/batch-plan` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `hpm_otp_isp_batch_program` | `POST /api/device/configuration/hpm-isp-otp/batch-program` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `hpm_otp_isp_plan` | `POST /api/device/configuration/hpm-isp-otp/plan` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `hpm_otp_isp_program` | `POST /api/device/configuration/hpm-isp-otp/program` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `hpm_otp_isp_read` | `POST /api/device/configuration/hpm-isp-otp/read` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `hpm_otp_jtag_lock_plan` | `POST /api/device/configuration/hpm-user-otp/lock-plan` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `hpm_otp_jtag_lock_program` | `POST /api/device/configuration/hpm-user-otp/lock-program` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `hpm_otp_jtag_plan` | `POST /api/device/configuration/hpm-user-otp/plan` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `hpm_otp_jtag_program` | `POST /api/device/configuration/hpm-user-otp/program` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `hpm_otp_jtag_read` | `POST /api/device/configuration/hpm-user-otp/read` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `inspect_mcu` | `POST /api/mcu-detect` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `isp_link_probe` | `POST /api/probe/isp-link-probe` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `job_start` | `POST /api/runtime/jobs/` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `job_status` | `GET /api/runtime/jobs/{job_id}` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `jobs` | `GET /api/runtime/jobs/` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `list_peripherals` | `GET /api/dash/superwatch/peripherals` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `measure_dump_memory` | `POST /api/device/dump-memory/measure` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `memory_map` | `GET /api/device/memory-map` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `microkeen` | `GET /api/microkeen` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `modbus_history` | `POST /api/dash/modbus/history` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `modbus_loop_start` | `POST /api/dash/modbus/loop/start` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `modbus_loop_stop` | `POST /api/dash/modbus/loop/stop` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `modbus_probe` | `POST /api/dash/modbus/probe` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `modbus_read` | `POST /api/dash/modbus/read` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `modbus_start` | `POST /api/dash/modbus/start` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `modbus_status` | `GET /api/dash/modbus/status` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `modbus_stop` | `POST /api/dash/modbus/stop` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `modbus_transaction` | `POST /api/dash/modbus/transaction` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `modbus_write` | `POST /api/dash/modbus/write` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `offline_algorithms` | `GET /api/offline-download/algorithms` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `offline_deploy` | `POST /api/offline-download/deploy` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `offline_preview` | `POST /api/offline-download/preview` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `offline_security` | `GET /api/offline-download/security` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `offline_status` | `GET /api/offline-download/status` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `pack_cancel` | `POST /api/online-flash/packs/cancel` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `pack_index_update` | `POST /api/online-flash/packs/index/update` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `pack_install` | `POST /api/online-flash/packs/install` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `pack_remove` | `DELETE /api/online-flash/packs/{pack_id}/{version}` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `pack_status` | `GET /api/online-flash/packs/status` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `peripheral_targets` | `GET /api/dash/superwatch/peripherals/targets` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `ports` | `GET /api/ports` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `power_read` | `POST /api/probe/power-read` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `probe_control` | `POST /api/probe/probe-control` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `probe_diagnostics` | `POST /api/probe/probe-diagnostics` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `probe_firmware_check` | `GET /api/probe/firmware-check` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `probe_firmware_upgrade` | `POST /api/probe/firmware-upgrade` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `probe_idcode` | `POST /api/probe/idcode` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `probe_presence` | `POST /api/probe/probe-presence` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `probe_version` | `POST /api/probe/version` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `profiles` | `GET /api/profiles` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `project` | `GET /api/project` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `project_browse` | `GET /api/project-root/browse` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `project_history` | `GET /api/project-history` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `project_history_remove` | `DELETE /api/project-history` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `project_history_save` | `POST /api/project-history` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `project_init` | `POST /api/project-init` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `project_root` | `GET /api/project-root` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `read_configuration` | `POST /api/device/configuration/read` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `read_memory` | `POST /api/device/read-memory` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `read_memory_regions` | `POST /api/device/read-memory-regions` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `read_peripherals` | `POST /api/device/peripherals/read` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `read_register` | `POST /api/device/read-register` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `read_variable` | `POST /api/device/read-variable` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `register_snapshot` | `POST /api/device/register-snapshot` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `resources` | `GET /api/resources/status` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `resources_release` | `POST /api/resources/release` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `resources_release_all` | `POST /api/resources/release-all` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `resources_release_serial` | `POST /api/resources/release-serial` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `resume` | `POST /api/device/resume` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `rtt_config` | `GET /api/rtt-config` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `rtt_config_save` | `PUT /api/rtt-config` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `rtt_encoding` | `POST /api/dash/rtt/encoding` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `rtt_find` | `POST /api/rtt-find` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `rtt_history` | `GET /api/dash/rtt/history` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `rtt_inspect` | `POST /api/device/rtt-control-block` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `rtt_pause` | `POST /api/dash/rtt/pause` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `rtt_read_channel` | `GET /api/dash/rtt/channels/read` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `rtt_recording_export` | `POST /api/dash/rtt/traffic-recording/export` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `rtt_recording_start` | `POST /api/dash/rtt/traffic-recording/start` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `rtt_recording_status` | `GET /api/dash/rtt/traffic-recording/status` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `rtt_recording_stop` | `POST /api/dash/rtt/traffic-recording/stop` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `rtt_resume` | `POST /api/dash/rtt/resume` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `rtt_start` | `POST /api/dash/rtt/start` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `rtt_status` | `GET /api/dash/rtt/status` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `rtt_stop` | `POST /api/dash/rtt/stop` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `rtt_write` | `POST /api/dash/rtt/write` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `runtime_detach_client` | `POST /api/runtime/control/detach-client` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `runtime_release_device` | `POST /api/runtime/control/release-device` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `runtime_status` | `GET /api/runtime/control/status` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `runtime_stop_acquisition` | `POST /api/runtime/control/stop-acquisition` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `runtime_stop_backend` | `POST /api/runtime/control/stop-backend` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `runtime_volume` | `GET /api/runtime/control/volume` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `security_status` | `GET /api/online-flash/targets/{part_number}/security` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `select_peripherals` | `POST /api/dash/superwatch/peripherals/select` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `select_probe` | `POST /api/runtime/select` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `serial_broadcast` | `POST /api/dash/serial/broadcast` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `serial_exchange` | `POST /api/dash/serial/exchange` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `serial_history` | `POST /api/dash/serial/history` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `serial_recording_start` | `POST /api/dash/serial/recording/start` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `serial_recording_stop` | `POST /api/dash/serial/recording/stop` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `serial_send` | `POST /api/dash/serial/send` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `serial_send_file` | `POST /api/dash/serial/file` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `serial_sequence_start` | `POST /api/dash/serial/sequence/start` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `serial_sequence_stop` | `POST /api/dash/serial/sequence/stop` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `serial_start` | `POST /api/dash/serial/start` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `serial_status` | `GET /api/dash/serial/status` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `serial_stop` | `POST /api/dash/serial/stop` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `serial_ymodem_cancel` | `POST /api/dash/serial/ymodem/cancel` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `serial_ymodem_start` | `POST /api/dash/serial/ymodem/file` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `serial_ymodem_status` | `GET /api/dash/serial/ymodem/status` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `serial_ymodem_trace` | `GET /api/dash/serial/ymodem/trace` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `set_debug_speed` | `POST /api/device/debug-speed` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `set_power_off` | `POST /api/probe/set-power-off` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `set_power_on` | `POST /api/probe/set-power-on` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `set_probe_alias` | `POST /api/runtime/alias` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `set_sleep_debug` | `POST /api/device/sleep-debug` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `site_agent_status` | `GET /api/site-agent/status` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `step` | `POST /api/device/step` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `superwatch_add` | `POST /api/dash/superwatch/add` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `superwatch_inspect` | `GET /api/dash/superwatch/inspect` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `superwatch_interval` | `POST /api/dash/superwatch/interval` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `superwatch_items` | `GET /api/dash/superwatch/items` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `superwatch_pause` | `POST /api/dash/superwatch/pause` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `superwatch_pins` | `GET /api/dash/superwatch/pins` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `superwatch_pins_save` | `PUT /api/dash/superwatch/pins` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `superwatch_profile` | `GET /api/dash/superwatch/profile` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `superwatch_profile_save` | `PUT /api/dash/superwatch/profile` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `superwatch_recording_export` | `POST /api/dash/superwatch/recording/export` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `superwatch_recording_start` | `POST /api/dash/superwatch/recording/start` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `superwatch_recording_status` | `GET /api/dash/superwatch/recording/status` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `superwatch_recording_stop` | `POST /api/dash/superwatch/recording/stop` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `superwatch_remove` | `POST /api/dash/superwatch/remove` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `superwatch_resume` | `POST /api/dash/superwatch/resume` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `superwatch_save_pins` | `PUT /api/dash/superwatch/pins` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `superwatch_save_workspace` | `PUT /api/dash/superwatch/workspace` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `superwatch_snapshot` | `GET /api/dash/superwatch/array-snapshot` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `superwatch_snapshot_clear` | `POST /api/dash/superwatch/array-snapshot/clear` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `superwatch_snapshot_select` | `POST /api/dash/superwatch/array-snapshot/select` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `superwatch_start` | `POST /api/dash/superwatch/start` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `superwatch_status` | `GET /api/dash/superwatch/status` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `superwatch_stop` | `POST /api/dash/superwatch/stop` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `superwatch_values` | `GET /api/dash/superwatch/latest` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `superwatch_workspace` | `GET /api/dash/superwatch/workspace` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `superwatch_workspace_save` | `PUT /api/dash/superwatch/workspace` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `superwatch_write` | `POST /api/dash/superwatch/write` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `symbol_apply_c_layout` | `POST /api/symbols/c-layout` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `symbol_catalog` | `GET /api/symbols/catalog` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `symbol_reload_sources` | `POST /api/symbols/reload-sources` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `symbol_reparse` | `POST /api/symbols/reparse` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `symbol_search` | `GET /api/symbols/search` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `symbol_status` | `GET /api/symbols/status` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `symbol_typeinfo` | `GET /api/symbols/typeinfo` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `symbols_browse` | `GET /api/symbols/browse` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `symbols_load` | `POST /api/device/parse-axf` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `symbols_resolve` | `GET /api/symbols/resolve` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `systemview_analyze_events` | `OFFLINE ` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `systemview_capture_history` | `GET /api/dash/systemview/history/cursor` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `systemview_decode` | `OFFLINE ` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `systemview_history` | `GET /api/dash/systemview/history` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `systemview_logs` | `GET /api/dash/systemview/logs` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `systemview_pause` | `POST /api/dash/systemview/pause` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `systemview_recording_start` | `POST /api/dash/systemview/recording/start` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `systemview_recording_stop` | `POST /api/dash/systemview/recording/stop` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `systemview_resume` | `POST /api/dash/systemview/resume` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `systemview_start` | `POST /api/dash/systemview/start` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `systemview_status` | `GET /api/dash/systemview/status` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `systemview_stop` | `POST /api/dash/systemview/stop` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `uart_baudrates` | `POST /api/runtime/uart-baudrates` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `uart_ports` | `GET /api/ports/uart` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `vofa_history` | `GET /api/dash/vofa/history` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `vofa_interval` | `POST /api/dash/vofa/interval` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `vofa_pause` | `POST /api/dash/vofa/pause` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `vofa_resume` | `POST /api/dash/vofa/resume` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `vofa_start` | `POST /api/dash/vofa/start` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `vofa_status` | `GET /api/dash/vofa/status` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `vofa_stop` | `POST /api/dash/vofa/stop` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `watch` | `POST /api/device/watch` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `watch_runtime_stats` | `POST /api/device/dump-memory/runtime-stats` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `write_memory` | `POST /api/device/write-memory` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |
| `write_variable` | `POST /api/device/write-variable` | 路由/契约 + 非对象参数拒绝；实际业务见场景报告 |

## MCP 工具映射

| 入口 | 模式 | 对应能力 |
| --- | --- | --- |
| `capture_peripherals` | panel | capture_peripherals |
| `configuration_description` | panel | configuration_description |
| `configuration_script` | panel | configuration_script |
| `connect` | panel | device_connect |
| `detach` | panel | runtime_detach_client |
| `device_status` | panel | device_status |
| `disconnect` | panel | device_disconnect |
| `discover_probes` | panel | discover_probes |
| `dump_memory` | panel | dump_memory |
| `flush_memory` | panel | flush_memory |
| `get_power` | panel | power_read |
| `gui_call` | panel | gui_frontend_capabilities |
| `gui_control` | panel | gui_windows gui_action gui_snapshot |
| `gui_open` | panel | gui_windows gui_present |
| `hpm_debug` | panel | hpm_debug |
| `hpm_otp` | panel | hpm_otp_jtag_read hpm_otp_jtag_plan hpm_otp_jtag_program hpm_otp_jtag_lock_plan hpm_otp_jtag_lock_program hpm_otp_isp_read hpm_otp_isp_plan hpm_otp_isp_program hpm_otp_isp_batch_plan hpm_otp_isp_batch_program |
| `inspect_mcu` | panel | inspect_mcu |
| `isp_link_probe` | panel | isp_link_probe |
| `job_status` | panel | job_status |
| `list_peripherals` | panel | list_peripherals |
| `measure_dump_memory` | panel | measure_dump_memory |
| `offline_download` | panel | offline_status offline_preview offline_deploy job_start |
| `peripheral_targets` | panel | peripheral_targets |
| `ping` | panel | health gui_frontend_capabilities |
| `probe_control` | panel | probe_control |
| `probe_diagnostics` | panel | probe_diagnostics |
| `probe_firmware` | panel | probe_firmware_check probe_firmware_upgrade |
| `probe_presence` | panel | probe_presence |
| `read_configuration` | panel | read_configuration |
| `read_memory` | panel | read_memory |
| `read_memory_regions` | panel | read_memory_regions |
| `read_register` | panel | read_register |
| `read_variable` | panel | read_variable |
| `reboot_probe` | panel | device_reboot |
| `rtt_history` | panel | rtt_history |
| `rtt_read_channel` | panel | rtt_read_channel |
| `rtt_start` | panel | rtt_start |
| `rtt_stop` | panel | rtt_stop |
| `rtt_write` | panel | rtt_write |
| `rtt_write_hex` | panel | rtt_write |
| `runtime_control` | panel | runtime_status runtime_stop_acquisition runtime_release_device runtime_stop_backend |
| `runtime_status` | panel | runtime_status |
| `search_symbols` | panel | symbol_search |
| `security_lock` | panel | job_start |
| `security_status` | panel | security_status |
| `security_unlock` | panel | job_start |
| `select_peripherals` | panel | select_peripherals |
| `set_debug_speed` | panel | set_debug_speed |
| `set_power_off` | panel | set_power_off |
| `set_power_on` | panel | set_power_on |
| `set_probe_alias` | panel | set_probe_alias |
| `set_sleep_debug` | panel | set_sleep_debug |
| `start_job` | panel | job_start |
| `superwatch` | panel | superwatch_status superwatch_items superwatch_values superwatch_snapshot superwatch_snapshot_select superwatch_snapshot_clear superwatch_add superwatch_remove superwatch_start superwatch_stop superwatch_pause superwatch_resume superwatch_interval superwatch_write superwatch_recording_start superwatch_recording_stop superwatch_recording_status superwatch_recording_export superwatch_profile superwatch_profile_save superwatch_workspace superwatch_workspace_save superwatch_pins superwatch_pins_save |
| `systemview` | panel | systemview_status systemview_history systemview_start systemview_stop systemview_pause systemview_resume |
| `systemview_analyze_events` | panel | systemview_analyze_events |
| `systemview_decode` | panel | systemview_decode |
| `write_memory` | panel | write_memory |
| `write_variable` | panel | write_variable |

## CLI 命令映射

| 入口 | 模式 | 对应能力 |
| --- | --- | --- |
| `autostart` | agent-cli | 沿用原入口；见上方模式说明 |
| `break` | panel | breakpoints |
| `configuration` | panel | configuration_description read_configuration configuration_script |
| `copy-flm` | agent-cli | 沿用原入口；见上方模式说明 |
| `debug-speed` | panel | debug_speed set_debug_speed |
| `desktop-proxy` | agent-cli | 沿用原入口；见上方模式说明 |
| `device-status` | panel | device_status |
| `dump` | panel | capture_dump |
| `dump-benchmark` | panel | measure_dump_memory |
| `dump-memory` | panel | dump_memory |
| `erase` | panel | job_start |
| `flash` | panel | flash_image_inspect flash_job_start flash_job |
| `flush-memory` | panel | flush_memory |
| `gui` | panel | gui_windows gui_present gui_action |
| `halt` | panel | halt |
| `hardfault` | panel | hardfault_check hardfault_decode fault_snapshot |
| `iar-parse` | agent-cli | 沿用原入口；见上方模式说明 |
| `keil-parse` | agent-cli | 沿用原入口；见上方模式说明 |
| `mcp` | agent-cli | 沿用原入口；见上方模式说明 |
| `mcp-config` | agent-cli | 沿用原入口；见上方模式说明 |
| `mcu-detect` | panel | inspect_mcu |
| `memmap` | panel | memory_map |
| `modbus` | group | 沿用原入口；见上方模式说明 |
| `modbus dashboard` | panel | modbus_start modbus_history modbus_transaction |
| `modbus diag` | panel | modbus_probe |
| `modbus monitor` | panel | modbus_start modbus_history |
| `modbus pointmap` | group | 沿用原入口；见上方模式说明 |
| `modbus pointmap detect` | agent-cli | 沿用原入口；见上方模式说明 |
| `modbus pointmap generate` | agent-cli | 沿用原入口；见上方模式说明 |
| `modbus poll` | panel | modbus_loop_start modbus_loop_stop |
| `modbus read` | panel | modbus_transaction |
| `modbus scan` | panel | modbus_probe |
| `modbus write` | panel | modbus_transaction |
| `peripherals` | panel | peripheral_targets select_peripherals list_peripherals capture_peripherals |
| `power-read` | panel | power_read |
| `probes` | group | discover_probes |
| `probes alias` | panel | set_probe_alias |
| `probes list` | panel | discover_probes |
| `project-info` | panel | project |
| `project-init` | panel | project_init |
| `read-flash` | panel | read_memory |
| `read-ram` | panel | read_memory |
| `read-reg` | panel | read_register |
| `read-variable` | panel | read_variable |
| `reload-symbols` | panel | symbol_reload_sources |
| `remote` | agent-cli | 沿用原入口；见上方模式说明 |
| `remote call` | agent-cli | 沿用原入口；见上方模式说明 |
| `remote capabilities` | agent-cli | 沿用原入口；见上方模式说明 |
| `remote connect` | agent-cli | 沿用原入口；见上方模式说明 |
| `remote flash` | agent-cli | 沿用原入口；见上方模式说明 |
| `remote health` | agent-cli | 沿用原入口；见上方模式说明 |
| `remote ports` | agent-cli | 沿用原入口；见上方模式说明 |
| `remote reconnect` | agent-cli | 沿用原入口；见上方模式说明 |
| `remote rtt` | agent-cli | 沿用原入口；见上方模式说明 |
| `remote sites` | group | 沿用原入口；见上方模式说明 |
| `remote sites add` | agent-cli | 沿用原入口；见上方模式说明 |
| `remote sites list` | agent-cli | 沿用原入口；见上方模式说明 |
| `remote sites remove` | agent-cli | 沿用原入口；见上方模式说明 |
| `remote sites switch` | agent-cli | 沿用原入口；见上方模式说明 |
| `remote sites use` | agent-cli | 沿用原入口；见上方模式说明 |
| `remote status` | agent-cli | 沿用原入口；见上方模式说明 |
| `remote stcp` | group | 沿用原入口；见上方模式说明 |
| `remote stcp visitor` | agent-cli | 沿用原入口；见上方模式说明 |
| `remote stop-agent` | agent-cli | 沿用原入口；见上方模式说明 |
| `remote upload` | agent-cli | 沿用原入口；见上方模式说明 |
| `remote-mcp` | agent-cli | 沿用原入口；见上方模式说明 |
| `reset` | panel | job_start |
| `resource` | group | resources resources_release_all resources_release_serial |
| `resource release-all` | panel | resources resources_release_all resources_release_serial |
| `resource release-serial` | panel | resources resources_release_all resources_release_serial |
| `resource status` | panel | resources resources_release_all resources_release_serial |
| `resources` | group | resources resources_release_all resources_release_serial |
| `resources release-all` | panel | resources resources_release_all resources_release_serial |
| `resources release-serial` | panel | resources resources_release_all resources_release_serial |
| `resources status` | panel | resources resources_release_all resources_release_serial |
| `resume` | panel | resume |
| `rtt` | panel | rtt_start rtt_history rtt_stop |
| `rtt-find` | panel | rtt_find |
| `rtt-integrate` | agent-cli | 沿用原入口；见上方模式说明 |
| `runtime` | group | 沿用原入口；见上方模式说明 |
| `runtime call` | panel | gui_frontend_capabilities |
| `runtime control` | panel | runtime_status runtime_stop_acquisition runtime_release_device runtime_stop_backend |
| `runtime firmware` | panel | probe_firmware_check probe_firmware_upgrade |
| `runtime jobs` | panel | jobs job_status |
| `runtime serve` | agent-cli | 沿用原入口；见上方模式说明 |
| `runtime start` | agent-cli | 沿用原入口；见上方模式说明 |
| `runtime status` | panel | runtime_status |
| `runtime stop` | agent-cli | 沿用原入口；见上方模式说明 |
| `s3-workbench` | agent-cli | 沿用原入口；见上方模式说明 |
| `security` | group | security_status job_start |
| `security lock` | panel | security_status job_start |
| `security unlock` | panel | security_status job_start |
| `serial` | group | 沿用原入口；见上方模式说明 |
| `serial dashboard` | panel | serial_status serial_start serial_history serial_send serial_stop |
| `serial list` | panel | uart_ports |
| `serial log` | panel | serial_recording_start serial_recording_stop |
| `serial monitor` | panel | serial_start serial_history |
| `serial open` | panel | serial_start |
| `serial profile` | group | 沿用原入口；见上方模式说明 |
| `serial profile detect` | agent-cli | 沿用原入口；见上方模式说明 |
| `serial profile generate` | agent-cli | 沿用原入口；见上方模式说明 |
| `serial profile show` | agent-cli | 沿用原入口；见上方模式说明 |
| `serial send` | panel | serial_send |
| `step` | panel | step |
| `superwatch` | panel | superwatch_start superwatch_values superwatch_stop |
| `symbols` | panel | symbol_search |
| `systemview` | panel | systemview_start systemview_history systemview_stop |
| `systemview-analyze` | panel | systemview_analyze_events |
| `systemview-integrate` | agent-cli | 沿用原入口；见上方模式说明 |
| `systemview-report` | agent-cli | 沿用原入口；见上方模式说明 |
| `typeinfo` | panel | symbol_typeinfo |
| `version` | panel | probe_version |
| `vofa` | panel | vofa_start vofa_history vofa_stop |
| `watch` | panel | watch |
| `web-entry` | group | 沿用原入口；见上方模式说明 |
| `web-entry handle` | agent-cli | 沿用原入口；见上方模式说明 |
| `web-entry html` | agent-cli | 沿用原入口；见上方模式说明 |
| `web-entry install` | agent-cli | 沿用原入口；见上方模式说明 |
| `web-entry start` | agent-cli | 沿用原入口；见上方模式说明 |
| `web-entry status` | agent-cli | 沿用原入口；见上方模式说明 |
| `web-entry stop` | agent-cli | 沿用原入口；见上方模式说明 |
| `web-entry uninstall` | agent-cli | 沿用原入口；见上方模式说明 |
| `write-ram` | panel | write_memory |
| `write-variable` | panel | write_variable |

## HTTP 入口审计

| 入口 | 模式 | 对应能力 |
| --- | --- | --- |
| `DELETE /_runtime/remote-windows/{key}/api/{path}` | protocol | 沿用原入口；见上方模式说明 |
| `DELETE /api/online-flash/algorithms/{algorithm_id}` | panel | flash_algorithm_remove |
| `DELETE /api/online-flash/packs/{pack_id}/{version}` | panel | pack_remove |
| `DELETE /api/project-history` | panel | project_history_remove |
| `GET /` | protocol | 沿用原入口；见上方模式说明 |
| `GET /_runtime/open` | protocol | 沿用原入口；见上方模式说明 |
| `GET /_runtime/remote-service` | protocol | 沿用原入口；见上方模式说明 |
| `GET /_runtime/remote-service/addresses` | protocol | 沿用原入口；见上方模式说明 |
| `GET /_runtime/remote-windows/{key}` | protocol | 沿用原入口；见上方模式说明 |
| `GET /_runtime/remote-windows/{key}/api/{path}` | protocol | 沿用原入口；见上方模式说明 |
| `GET /_runtime/status` | protocol | 沿用原入口；见上方模式说明 |
| `GET /api/config` | panel | config_read |
| `GET /api/config/status` | panel | config_status |
| `GET /api/dash/conflict-check` | panel | dash_conflict_check |
| `GET /api/dash/modbus/status` | panel | modbus_status |
| `GET /api/dash/modbus/stream` | original-ui | 沿用原入口；见上方模式说明 |
| `GET /api/dash/rtt/channels/read` | panel | rtt_read_channel |
| `GET /api/dash/rtt/history` | panel | rtt_history |
| `GET /api/dash/rtt/status` | panel | rtt_status |
| `GET /api/dash/rtt/stream` | original-ui | 沿用原入口；见上方模式说明 |
| `GET /api/dash/serial/status` | panel | serial_status |
| `GET /api/dash/serial/stream` | original-ui | 沿用原入口；见上方模式说明 |
| `GET /api/dash/serial/ymodem/status` | panel | serial_ymodem_status |
| `GET /api/dash/serial/ymodem/trace` | panel | serial_ymodem_trace |
| `GET /api/dash/superwatch/array-snapshot` | panel | superwatch_snapshot |
| `GET /api/dash/superwatch/inspect` | panel | superwatch_inspect |
| `GET /api/dash/superwatch/items` | panel | superwatch_items |
| `GET /api/dash/superwatch/latest` | panel | superwatch_values |
| `GET /api/dash/superwatch/peripherals` | panel | list_peripherals |
| `GET /api/dash/superwatch/peripherals/targets` | panel | peripheral_targets |
| `GET /api/dash/superwatch/pins` | panel | superwatch_pins |
| `GET /api/dash/superwatch/profile` | panel | superwatch_profile |
| `GET /api/dash/superwatch/recording/status` | panel | superwatch_recording_status |
| `GET /api/dash/superwatch/status` | panel | superwatch_status |
| `GET /api/dash/superwatch/stream` | original-ui | 沿用原入口；见上方模式说明 |
| `GET /api/dash/superwatch/workspace` | panel | superwatch_workspace |
| `GET /api/dash/systemview/history` | panel | systemview_history |
| `GET /api/dash/systemview/history/cursor` | panel | systemview_capture_history |
| `GET /api/dash/systemview/logs` | panel | systemview_logs |
| `GET /api/dash/systemview/logs/download` | original-ui | 沿用原入口；见上方模式说明 |
| `GET /api/dash/systemview/status` | panel | systemview_status |
| `GET /api/dash/systemview/stream` | original-ui | 沿用原入口；见上方模式说明 |
| `GET /api/dash/vofa/history` | panel | vofa_history |
| `GET /api/dash/vofa/status` | panel | vofa_status |
| `GET /api/dash/vofa/stream` | original-ui | 沿用原入口；见上方模式说明 |
| `GET /api/dash/{kind}/traffic-recording/status` | panel | rtt_recording_status |
| `GET /api/device/configuration` | panel | configuration_description |
| `GET /api/device/core-registers` | panel | core_registers |
| `GET /api/device/debug-speed` | panel | debug_speed |
| `GET /api/device/hardfault` | panel | hardfault_check |
| `GET /api/device/hardfault-detail` | panel | hardfault |
| `GET /api/device/memory-map` | panel | memory_map |
| `GET /api/device/status` | panel | device_status |
| `GET /api/diagnostics/export` | original-ui | 沿用原入口；见上方模式说明 |
| `GET /api/health` | panel | health |
| `GET /api/microkeen` | panel | microkeen |
| `GET /api/offline-download/algorithms` | panel | offline_algorithms |
| `GET /api/offline-download/security` | panel | offline_security |
| `GET /api/offline-download/status` | panel | offline_status |
| `GET /api/online-flash/algorithms` | panel | flash_algorithms |
| `GET /api/online-flash/images/source-status` | panel | flash_image_source_status |
| `GET /api/online-flash/images/{image_id}/preview` | panel | flash_image_preview |
| `GET /api/online-flash/jobs/active` | panel | flash_jobs |
| `GET /api/online-flash/jobs/{job_id}` | panel | flash_jobs flash_job |
| `GET /api/online-flash/jobs/{job_id}/events` | original-ui | 沿用原入口；见上方模式说明 |
| `GET /api/online-flash/packs/status` | panel | pack_status |
| `GET /api/online-flash/probes` | panel | flash_probes |
| `GET /api/online-flash/targets` | panel | flash_targets |
| `GET /api/online-flash/targets/{part_number}/algorithms` | panel | flash_target_algorithms |
| `GET /api/online-flash/targets/{part_number}/memory-map` | panel | flash_target_memory_map |
| `GET /api/online-flash/targets/{part_number}/security` | panel | security_status |
| `GET /api/ports` | panel | ports |
| `GET /api/ports/discover` | panel | discover_probes |
| `GET /api/ports/uart` | panel | uart_ports |
| `GET /api/probe/firmware-check` | panel | probe_firmware_check |
| `GET /api/probe/firmware-download` | original-ui | 沿用原入口；见上方模式说明 |
| `GET /api/profiles` | panel | profiles |
| `GET /api/project` | panel | project |
| `GET /api/project-history` | panel | project_history |
| `GET /api/project-root` | panel | project_root |
| `GET /api/project-root/browse` | panel | project_browse |
| `GET /api/resources/status` | panel | resources |
| `GET /api/rtt-config` | panel | rtt_config |
| `GET /api/runtime/capabilities` | panel | gui_frontend_capabilities |
| `GET /api/runtime/control/gui-files/{token}` | protocol | 沿用原入口；见上方模式说明 |
| `GET /api/runtime/control/status` | panel | runtime_status |
| `GET /api/runtime/control/volume` | panel | runtime_volume |
| `GET /api/runtime/control/windows` | panel | gui_windows |
| `GET /api/runtime/frontend/intent` | panel | gui_frontend_intent |
| `GET /api/runtime/frontend/intents` | panel | gui_frontend_intents |
| `GET /api/runtime/frontend/layout` | panel | gui_frontend_layout |
| `GET /api/runtime/frontend/layouts` | protocol | 沿用原入口；见上方模式说明 |
| `GET /api/runtime/frontend/layouts/item` | protocol | 沿用原入口；见上方模式说明 |
| `GET /api/runtime/frontend/pages` | panel | gui_frontend_pages |
| `GET /api/runtime/frontend/read` | panel | gui_frontend_read |
| `GET /api/runtime/frontend/receipt` | panel | gui_frontend_receipt |
| `GET /api/runtime/jobs/` | panel | jobs |
| `GET /api/runtime/jobs/{job_id}` | panel | job_status |
| `GET /api/site-agent/status` | panel | site_agent_status |
| `GET /api/symbols/browse` | panel | symbols_browse |
| `GET /api/symbols/catalog` | panel | symbol_catalog |
| `GET /api/symbols/resolve` | panel | symbols_resolve |
| `GET /api/symbols/search` | panel | symbol_search |
| `GET /api/symbols/status` | panel | symbol_status |
| `GET /api/symbols/typeinfo` | panel | symbol_typeinfo |
| `GET /assets/{file_path}` | protocol | 沿用原入口；见上方模式说明 |
| `GET /{full_path}` | protocol | 沿用原入口；见上方模式说明 |
| `PATCH /_runtime/remote-windows/{key}/api/{path}` | protocol | 沿用原入口；见上方模式说明 |
| `POST /_runtime/attach` | protocol | 沿用原入口；见上方模式说明 |
| `POST /_runtime/call` | protocol | 沿用原入口；见上方模式说明 |
| `POST /_runtime/detach` | protocol | 沿用原入口；见上方模式说明 |
| `POST /_runtime/gui-link` | protocol | 沿用原入口；见上方模式说明 |
| `POST /_runtime/heartbeat` | protocol | 沿用原入口；见上方模式说明 |
| `POST /_runtime/login` | protocol | 沿用原入口；见上方模式说明 |
| `POST /_runtime/remote-service` | protocol | 沿用原入口；见上方模式说明 |
| `POST /_runtime/remote-service/stop` | protocol | 沿用原入口；见上方模式说明 |
| `POST /_runtime/remote-service/token` | protocol | 沿用原入口；见上方模式说明 |
| `POST /_runtime/remote-windows` | protocol | 沿用原入口；见上方模式说明 |
| `POST /_runtime/remote-windows/{key}/api/{path}` | protocol | 沿用原入口；见上方模式说明 |
| `POST /_runtime/remote-windows/{key}/close` | protocol | 沿用原入口；见上方模式说明 |
| `POST /_runtime/remote-windows/{key}/open` | protocol | 沿用原入口；见上方模式说明 |
| `POST /_runtime/stop` | protocol | 沿用原入口；见上方模式说明 |
| `POST /api/browser-session/heartbeat` | protocol | 沿用原入口；见上方模式说明 |
| `POST /api/browser-session/release` | protocol | 沿用原入口；见上方模式说明 |
| `POST /api/dash/modbus/history` | panel | modbus_history |
| `POST /api/dash/modbus/loop/start` | panel | modbus_loop_start |
| `POST /api/dash/modbus/loop/stop` | panel | modbus_loop_stop |
| `POST /api/dash/modbus/probe` | panel | modbus_probe |
| `POST /api/dash/modbus/read` | panel | modbus_read |
| `POST /api/dash/modbus/start` | panel | modbus_start |
| `POST /api/dash/modbus/stop` | panel | modbus_stop |
| `POST /api/dash/modbus/transaction` | panel | modbus_transaction |
| `POST /api/dash/modbus/write` | panel | modbus_write |
| `POST /api/dash/rtt/encoding` | panel | rtt_encoding |
| `POST /api/dash/rtt/pause` | panel | rtt_pause |
| `POST /api/dash/rtt/resume` | panel | rtt_resume |
| `POST /api/dash/rtt/start` | panel | rtt_start |
| `POST /api/dash/rtt/stop` | panel | rtt_stop |
| `POST /api/dash/rtt/traffic-recording/export` | panel | rtt_recording_export |
| `POST /api/dash/rtt/write` | panel | rtt_write |
| `POST /api/dash/serial/broadcast` | panel | serial_broadcast |
| `POST /api/dash/serial/exchange` | panel | serial_exchange |
| `POST /api/dash/serial/file` | panel | serial_send_file |
| `POST /api/dash/serial/file/upload` | original-ui | 沿用原入口；见上方模式说明 |
| `POST /api/dash/serial/history` | panel | serial_history |
| `POST /api/dash/serial/recording/start` | panel | serial_recording_start |
| `POST /api/dash/serial/recording/stop` | panel | serial_recording_stop |
| `POST /api/dash/serial/send` | panel | serial_send |
| `POST /api/dash/serial/sequence/start` | panel | serial_sequence_start |
| `POST /api/dash/serial/sequence/stop` | panel | serial_sequence_stop |
| `POST /api/dash/serial/start` | panel | serial_start |
| `POST /api/dash/serial/stop` | panel | serial_stop |
| `POST /api/dash/serial/ymodem/cancel` | panel | serial_ymodem_cancel |
| `POST /api/dash/serial/ymodem/file` | panel | serial_ymodem_start |
| `POST /api/dash/serial/ymodem/start` | original-ui | 沿用原入口；见上方模式说明 |
| `POST /api/dash/superwatch/add` | panel | superwatch_add |
| `POST /api/dash/superwatch/array-snapshot/clear` | panel | superwatch_snapshot_clear |
| `POST /api/dash/superwatch/array-snapshot/select` | panel | superwatch_snapshot_select |
| `POST /api/dash/superwatch/interval` | panel | superwatch_interval |
| `POST /api/dash/superwatch/pause` | panel | superwatch_pause |
| `POST /api/dash/superwatch/peripherals/select` | panel | select_peripherals |
| `POST /api/dash/superwatch/recording/export` | panel | superwatch_recording_export |
| `POST /api/dash/superwatch/recording/start` | panel | superwatch_recording_start |
| `POST /api/dash/superwatch/recording/stop` | panel | superwatch_recording_stop |
| `POST /api/dash/superwatch/remove` | panel | superwatch_remove |
| `POST /api/dash/superwatch/resume` | panel | superwatch_resume |
| `POST /api/dash/superwatch/start` | panel | superwatch_start |
| `POST /api/dash/superwatch/stop` | panel | superwatch_stop |
| `POST /api/dash/superwatch/write` | panel | superwatch_write |
| `POST /api/dash/systemview/pause` | panel | systemview_pause |
| `POST /api/dash/systemview/recording/start` | panel | systemview_recording_start |
| `POST /api/dash/systemview/recording/stop` | panel | systemview_recording_stop |
| `POST /api/dash/systemview/resume` | panel | systemview_resume |
| `POST /api/dash/systemview/start` | panel | systemview_start |
| `POST /api/dash/systemview/stop` | panel | systemview_stop |
| `POST /api/dash/vofa/interval` | panel | vofa_interval |
| `POST /api/dash/vofa/pause` | panel | vofa_pause |
| `POST /api/dash/vofa/resume` | panel | vofa_resume |
| `POST /api/dash/vofa/start` | panel | vofa_start |
| `POST /api/dash/vofa/stop` | panel | vofa_stop |
| `POST /api/dash/{kind}/traffic-recording/start` | panel | rtt_recording_start |
| `POST /api/dash/{kind}/traffic-recording/stop` | panel | rtt_recording_stop |
| `POST /api/desktop/shutdown` | protocol | 沿用原入口；见上方模式说明 |
| `POST /api/device/breakpoints` | panel | breakpoints |
| `POST /api/device/configuration/hpm-isp-otp/batch-plan` | panel | hpm_otp_isp_batch_plan |
| `POST /api/device/configuration/hpm-isp-otp/batch-program` | panel | hpm_otp_isp_batch_program |
| `POST /api/device/configuration/hpm-isp-otp/plan` | panel | hpm_otp_isp_plan |
| `POST /api/device/configuration/hpm-isp-otp/program` | panel | hpm_otp_isp_program |
| `POST /api/device/configuration/hpm-isp-otp/read` | panel | hpm_otp_isp_read |
| `POST /api/device/configuration/hpm-user-otp/{action}` | panel | hpm_otp_jtag_read hpm_otp_jtag_plan hpm_otp_jtag_program hpm_otp_jtag_lock_plan hpm_otp_jtag_lock_program |
| `POST /api/device/configuration/read` | panel | read_configuration |
| `POST /api/device/connect` | panel | device_connect |
| `POST /api/device/debug-speed` | panel | set_debug_speed |
| `POST /api/device/disconnect` | panel | device_disconnect |
| `POST /api/device/dump-memory` | panel | dump_memory |
| `POST /api/device/dump-memory/capture` | panel | capture_dump |
| `POST /api/device/dump-memory/measure` | panel | measure_dump_memory |
| `POST /api/device/dump-memory/runtime-stats` | panel | watch_runtime_stats |
| `POST /api/device/erase` | original-ui | 沿用原入口；见上方模式说明 |
| `POST /api/device/erase-sector` | original-ui | 沿用原入口；见上方模式说明 |
| `POST /api/device/fault-snapshot` | panel | fault_snapshot |
| `POST /api/device/flash` | original-ui | 沿用原入口；见上方模式说明 |
| `POST /api/device/flush-memory` | panel | flush_memory |
| `POST /api/device/halt` | panel | halt |
| `POST /api/device/hardfault-detail` | panel | hardfault_decode |
| `POST /api/device/hpm-debug` | panel | hpm_debug |
| `POST /api/device/parse-axf` | panel | symbols_load |
| `POST /api/device/peripherals/capture` | panel | capture_peripherals |
| `POST /api/device/peripherals/read` | panel | read_peripherals |
| `POST /api/device/power` | original-ui | 沿用原入口；见上方模式说明 |
| `POST /api/device/read-memory` | panel | read_memory |
| `POST /api/device/read-memory-regions` | panel | read_memory_regions |
| `POST /api/device/read-register` | panel | read_register |
| `POST /api/device/read-variable` | panel | read_variable |
| `POST /api/device/reboot` | panel | device_reboot |
| `POST /api/device/register-snapshot` | panel | register_snapshot |
| `POST /api/device/reset` | original-ui | 沿用原入口；见上方模式说明 |
| `POST /api/device/resume` | panel | resume |
| `POST /api/device/rtt-control-block` | panel | rtt_inspect |
| `POST /api/device/security` | original-ui | 沿用原入口；见上方模式说明 |
| `POST /api/device/sleep-debug` | panel | set_sleep_debug |
| `POST /api/device/step` | panel | step |
| `POST /api/device/watch` | panel | watch |
| `POST /api/device/write-memory` | panel | write_memory |
| `POST /api/device/write-variable` | panel | write_variable |
| `POST /api/files/map` | original-ui | 沿用原入口；见上方模式说明 |
| `POST /api/files/svd` | original-ui | 沿用原入口；见上方模式说明 |
| `POST /api/files/symbol` | original-ui | 沿用原入口；见上方模式说明 |
| `POST /api/mcu-detect` | panel | inspect_mcu |
| `POST /api/offline-download/algorithm` | original-ui | 沿用原入口；见上方模式说明 |
| `POST /api/offline-download/deploy` | panel | offline_deploy |
| `POST /api/offline-download/preview` | panel | offline_preview |
| `POST /api/offline-download/trigger` | original-ui | 沿用原入口；见上方模式说明 |
| `POST /api/offline-download/trigger-job` | original-ui | 沿用原入口；见上方模式说明 |
| `POST /api/online-flash/algorithms` | original-ui | 沿用原入口；见上方模式说明 |
| `POST /api/online-flash/images/inspect` | original-ui | 沿用原入口；见上方模式说明 |
| `POST /api/online-flash/images/inspect-path` | panel | flash_image_inspect |
| `POST /api/online-flash/jobs` | panel | flash_job_start |
| `POST /api/online-flash/jobs/{job_id}/stop` | panel | flash_job_stop |
| `POST /api/online-flash/memory/read` | panel | flash_memory_read |
| `POST /api/online-flash/memory/read-stream` | original-ui | 沿用原入口；见上方模式说明 |
| `POST /api/online-flash/packs/cancel` | panel | pack_cancel |
| `POST /api/online-flash/packs/import` | original-ui | 沿用原入口；见上方模式说明 |
| `POST /api/online-flash/packs/index/update` | panel | pack_index_update |
| `POST /api/online-flash/packs/install` | panel | pack_install |
| `POST /api/probe/firmware-upgrade` | panel | probe_firmware_upgrade |
| `POST /api/probe/idcode` | panel | probe_idcode |
| `POST /api/probe/isp-link-probe` | panel | isp_link_probe |
| `POST /api/probe/power-read` | panel | power_read |
| `POST /api/probe/probe-control` | panel | probe_control |
| `POST /api/probe/probe-diagnostics` | panel | probe_diagnostics |
| `POST /api/probe/probe-presence` | panel | probe_presence |
| `POST /api/probe/set-power-off` | panel | set_power_off |
| `POST /api/probe/set-power-on` | panel | set_power_on |
| `POST /api/probe/version` | panel | probe_version |
| `POST /api/project-history` | panel | project_history_save |
| `POST /api/project-init` | panel | project_init |
| `POST /api/resources/release` | panel | resources_release |
| `POST /api/resources/release-all` | panel | resources_release_all |
| `POST /api/resources/release-serial` | panel | resources_release_serial |
| `POST /api/rtt-find` | panel | rtt_find |
| `POST /api/runtime/alias` | panel | set_probe_alias |
| `POST /api/runtime/capabilities/call` | protocol | 沿用原入口；见上方模式说明 |
| `POST /api/runtime/control/detach-client` | panel | runtime_detach_client |
| `POST /api/runtime/control/gui-action` | panel | gui_action |
| `POST /api/runtime/control/gui-snapshot` | panel | gui_snapshot |
| `POST /api/runtime/control/present` | panel | gui_present |
| `POST /api/runtime/control/release-device` | panel | runtime_release_device |
| `POST /api/runtime/control/stop-acquisition` | panel | runtime_stop_acquisition |
| `POST /api/runtime/control/stop-backend` | panel | runtime_stop_backend |
| `POST /api/runtime/control/view` | protocol | 沿用原入口；见上方模式说明 |
| `POST /api/runtime/diagnostics/events` | panel | diagnostic_events |
| `POST /api/runtime/frontend/call` | panel | gui_frontend_call |
| `POST /api/runtime/frontend/exchange` | protocol | 沿用原入口；见上方模式说明 |
| `POST /api/runtime/frontend/intent` | protocol | 沿用原入口；见上方模式说明 |
| `POST /api/runtime/frontend/layouts` | protocol | 沿用原入口；见上方模式说明 |
| `POST /api/runtime/frontend/replay-file` | protocol | 沿用原入口；见上方模式说明 |
| `POST /api/runtime/frontend/reply` | panel | gui_frontend_reply |
| `POST /api/runtime/host-update/prepare` | protocol | 沿用原入口；见上方模式说明 |
| `POST /api/runtime/host-update/release` | protocol | 沿用原入口；见上方模式说明 |
| `POST /api/runtime/host-update/renew` | protocol | 沿用原入口；见上方模式说明 |
| `POST /api/runtime/jobs/` | panel | job_start |
| `POST /api/runtime/select` | panel | select_probe |
| `POST /api/runtime/uart-baudrates` | panel | uart_baudrates |
| `POST /api/symbols/c-layout` | panel | symbol_apply_c_layout |
| `POST /api/symbols/reload-sources` | panel | symbol_reload_sources |
| `POST /api/symbols/reparse` | panel | symbol_reparse |
| `PUT /_runtime/remote-windows/{key}/api/{path}` | protocol | 沿用原入口；见上方模式说明 |
| `PUT /api/config` | panel | config_save |
| `PUT /api/dash/superwatch/pins` | panel | superwatch_pins_save superwatch_save_pins |
| `PUT /api/dash/superwatch/profile` | panel | superwatch_profile_save |
| `PUT /api/dash/superwatch/workspace` | panel | superwatch_workspace_save superwatch_save_workspace |
| `PUT /api/rtt-config` | panel | rtt_config_save |
| `PUT /api/runtime/frontend/layout` | panel | gui_frontend_save_layout |
