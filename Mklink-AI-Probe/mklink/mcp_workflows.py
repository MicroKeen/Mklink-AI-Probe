"""MCP entry points for existing guarded backend workflows."""
from typing import Literal

from pydantic import StrictBool, StrictInt


def register_workflow_tools(server, client):
    @server.tool()
    def probe_presence(interface: Literal['SWD', 'JTAG']) -> dict:
        """Read live target presence, not cached IDCODE; requires idle acquisition.

        Does not force interface switching. Negative codes mean busy/error/unknown,
        never target absence. A positive IDCODE does not identify an exact MCU.
        """
        return client().call('probe_presence', {'interface': interface})

    @server.tool()
    def probe_diagnostics(index: StrictInt = -1) -> dict:
        """Read probe diagnostics: -1 heap, -2 reset report, 0..31 stack watermarks.

        This is the downloader's own runtime, not target RAM. MEM_END ends thread
        enumeration; stack untouched bytes are a watermark estimate. Idle only.
        """
        return client().call('probe_diagnostics', {'index': index})

    @server.tool()
    def probe_control(setting: Literal['auto_scan', 'auto_follow_vref', 'beep'],
                      enabled: StrictBool, confirm_user: StrictBool = False) -> dict:
        """Change one explicit probe setting after user confirmation; idle only.

        Beep on remains on until explicitly disabled. Auto-scan changes discovery.
        Auto-follow-Vref can be disabled; enabling is blocked until firmware can
        validate the reference voltage. Use confirmed set_power_on for exact VCC.
        A setter ACK is not persistent-setting or physical measurement evidence.
        """
        return client().call('probe_control', dict(setting=setting, enabled=enabled, confirm_user=confirm_user))

    @server.tool()
    def set_power_on(voltage_mv: StrictInt, confirm_user: StrictBool = False,
                     confirm_5v: StrictBool = False) -> dict:
        """Set VCC to 1800/3300/5000 mV after per-operation user voltage approval.

        5000 mV also needs confirm_5v. Idle only, no automatic retry. ACK is not
        measured voltage; use get_power for telemetry when supported.
        """
        return client().call('set_power_on', dict(voltage_mv=voltage_mv,
                             confirm_user=confirm_user, confirm_5v=confirm_5v))

    @server.tool()
    def set_power_off(confirm_user: StrictBool = False) -> dict:
        """Turn VCC off only after this operation's user approval. Never auto-retry."""
        return client().call('set_power_off', {'confirm_user': confirm_user})

    @server.tool()
    def isp_link_probe(baud_rate: StrictInt = 115200, duration_ms: StrictInt = 10000,
                       strict: StrictBool = False) -> dict:
        """Diagnose HPM ROM UART link loss/reconnect for 1..120 seconds.

        Target must already be in ROM ISP at this baud. Requires idle probe and
        released independent UART clients. No flash/OTP/reset/VCC commands.
        Success proves observed reconnection only, not programming success.
        """
        return client().call('isp_link_probe', dict(baud_rate=baud_rate, duration_ms=duration_ms, strict=strict))

    @server.tool()
    def offline_download(action: Literal['status', 'preview', 'deploy', 'trigger'],
                         config: dict | None = None, request_id: str | None = None,
                         confirm: StrictBool = False) -> dict:
        """Use the GUI offline/ROM-UART-ISP pipeline on the bound downloader.

        See references/probe-workflows.md for payloads. preview/deploy use the same
        configuration as GUI; source_path refers to backend-local firmware/FLM.
        Deploy writes the probe disk, not target flash. Trigger runs the deployed
        script and can erase/program/reset the target; config contains only model,
        script_name and programming_protocol. Both require confirm and a stable
        request_id kept BEFORE submission. Trigger returns a job; poll job_status.
        Query original job after an uncertain reply, never blindly resubmit.
        """
        if action == 'status':
            if config is not None or request_id is not None or confirm:
                raise ValueError('status takes no configuration or confirmation')
            return client().call('offline_status')
        if not isinstance(config, dict):
            raise ValueError('config is required')
        if action == 'preview':
            return client().call('offline_preview', config)
        if confirm is not True or not isinstance(request_id, str) or not 1 <= len(request_id) <= 128:
            raise ValueError('Keep a stable request_id and confirm this deployment/trigger first')
        if action == 'deploy':
            return client().call('offline_deploy', dict(config=config, request_id=request_id, confirm=confirm))
        return client().start_job('offline_trigger', request_id=request_id, confirm=confirm, arguments=config)

    @server.tool()
    def hpm_otp(transport: Literal['jtag', 'isp'],
                action: Literal['read', 'plan', 'program', 'lock-plan', 'lock-program', 'batch-plan', 'batch-program'],
                arguments: dict) -> dict:
        """Use existing GUI HPM OTP guards; explicit irreversible approval for writes.

        JTAG supports HPM5301 user words 69..79 and lock groups 18/19. Read/plan
        first; program requires exact word/expected/desired and confirm_irreversible.
        ISP supports read/plan/program/batch-plan/batch-program. A successful plan
        returns an expiring, single-use plan_id bound to probe/generation/part.
        Program consumes that ID once, even on failure; never auto-retry OTP.
        Extended family profiles use extended=true and batch operations only.
        Stop acquisition first. See references/probe-workflows.md for arguments.
        """
        supported = {'jtag': {'read', 'plan', 'program', 'lock-plan', 'lock-program'},
                     'isp': {'read', 'plan', 'program', 'batch-plan', 'batch-program'}}
        if action not in supported[transport]:
            raise ValueError('This OTP action is unavailable on the selected transport')
        return client().call(f'hpm_otp_{transport}_{action.replace("-", "_")}', arguments)
