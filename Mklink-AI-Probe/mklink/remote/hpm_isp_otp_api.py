"""Bounded UART OTP operations, independent of JTAG and SD deployment."""
from __future__ import annotations

import asyncio
from typing import Literal
import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, model_validator

from .hpm_isp_otp_plans import OtpBinding, OtpPlans


class OtpReadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    part_number: StrictStr
    extended: StrictBool = False

    @model_validator(mode="after")
    def validate_target(self):
        if self.extended:
            from mklink.hpm_otp_profiles import family
            family(self.part_number)
        elif self.part_number not in ('HPM5301', 'HPM5301XEGX'):
            raise ValueError('Legacy OTP API requires HPM5301')
        return self
    model: Literal["V4"] = "V4"


class OtpPlanRequest(OtpReadRequest):
    word: StrictInt
    expected: StrictInt
    desired: StrictInt | StrictStr


class OtpProgramRequest(OtpReadRequest):
    plan_id: StrictStr
    confirm_irreversible: StrictBool


class OtpBatchChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    word: StrictInt
    expected: StrictInt
    desired: StrictInt | StrictStr


class OtpTargetIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chip_id: StrictInt = Field(ge=1, lt=0xFFFFFFFF)
    rom_version: StrictInt = Field(ge=1, lt=0xFFFFFFFF)
    soc_revision: StrictInt = Field(ge=1, lt=0xFFFFFFFF)


class OtpBatchPlanRequest(OtpReadRequest):
    target_identity: OtpTargetIdentity | None = None
    changes: list[OtpBatchChange] = Field(min_length=1, max_length=128)


def create_hpm_isp_otp_router(resource_manager, device_provider):
    router = APIRouter(prefix="/api/device/configuration/hpm-isp-otp", tags=["device"])
    plans = OtpPlans()

    @router.post("/read")
    async def read(request: Request, payload: OtpReadRequest):
        return await execute(request, payload, 'read')

    @router.post("/plan")
    async def plan(request: Request, payload: OtpPlanRequest):
        return await execute(request, payload, 'plan')

    @router.post("/program")
    async def program(request: Request, payload: OtpProgramRequest):
        if payload.confirm_irreversible is not True:
            raise HTTPException(422, 'Explicit irreversible OTP confirmation is required')
        return await execute(request, payload, 'program')

    @router.post("/batch-plan")
    async def batch_plan(request: Request, payload: OtpBatchPlanRequest):
        return await execute(request, payload, 'batch-plan')

    @router.post("/batch-program")
    async def batch_program(request: Request, payload: OtpProgramRequest):
        if payload.confirm_irreversible is not True:
            raise HTTPException(422, 'Explicit irreversible OTP confirmation is required')
        return await execute(request, payload, 'batch-program')

    async def execute(request, payload, action):
        from mklink import hpm_isp_otp
        from mklink import hpm_isp_otp_profile, hpm_otp_profiles
        transport = hpm_isp_otp_profile if payload.extended else hpm_isp_otp
        validate = hpm_otp_profiles.validate_change if payload.extended else hpm_isp_otp.validate_change
        if payload.extended and action in ('plan', 'program'):
            raise HTTPException(422, 'Extended OTP uses batch preview and programming')
        if action == 'batch-plan' and not payload.extended and len(payload.changes) > 11:
            raise HTTPException(422, 'Legacy OTP supports at most 11 words')
        from mklink.remote.resource_manager import ResourceError, ResourceGroup
        from mklink.runtime_api import settle

        runtime = getattr(request.app.state, "shared_runtime", None)
        port = None
        binding = None
        fixed = None
        if runtime is not None:
            from mklink.probes import select_probe
            runtime.require_identity()
            if runtime.uart_operations or any(s.scope == "uart" for s in runtime.sessions.values()):
                raise HTTPException(409, "Finish UART operations and detach UART clients before reading OTP")
            if runtime.current_operation is not None:
                runtime.current_operation["uart_exclusive"] = True
            port = select_probe(runtime.info["probe_id"])["port"]
            binding = OtpBinding(runtime.info['probe_id'], port.casefold(),
                                 request.app.state.mklink_state.get('device_generation', 0),
                                 payload.part_number, payload.extended)

        if action != 'read' and binding is None:
            raise HTTPException(409, 'Select a probe in the shared runtime before configuring UART OTP')
        try:
            if action in ('program', 'batch-program'):
                fixed = plans.consume(payload.plan_id, binding)
                if ('changes' in fixed) != (action == 'batch-program'):
                    raise ValueError('OTP plan type does not match the requested operation')
            else:
                plans.clear()
                if action == 'plan':
                    fixed = validate(payload.word, payload.expected, payload.desired)
                elif action == 'batch-plan':
                    fixed = {'changes': [validate(item.word, item.expected, item.desired)
                                         for item in payload.changes]}
                    words = [item['word'] for item in fixed['changes']]
                    if len(words) != len(set(words)):
                        raise ValueError('Duplicate OTP word in configuration')
                    fixed['changes'] = (hpm_otp_profiles.ordered_changes(fixed['changes']) if payload.extended
                                        else sorted(fixed['changes'], key=lambda item: item['word']))
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

        device = device_provider()
        bridge = getattr(device, "_bridge", None) if device and device.connected else None
        if bridge and port and str(device.port).casefold() != port.casefold():
            raise HTTPException(409, "OTP probe does not match the connected device")
        owner = f"user:isp-otp:{uuid.uuid4().hex}"

        def worker():
            from mklink.bridge import MKLinkSerialBridge
            from mklink.discovery import find_mklink_cdc_port
            active = bridge
            owned = False
            try:
                if active is None:
                    resolved = port or find_mklink_cdc_port()
                    if not resolved:
                        raise ConnectionError("MKLink CDC port was not found")
                    active = MKLinkSerialBridge(resolved)
                    owned = True
                    if not active.connect():
                        raise ConnectionError("Unable to connect to MKLink CDC port")
                if action == 'read':
                    return transport.read_snapshot(active, payload.part_number)
                if action == 'plan':
                    return hpm_isp_otp.plan_change(active, payload.part_number, **fixed)
                if action == 'batch-plan':
                    extra = {'target_identity': payload.target_identity.model_dump() if payload.target_identity else None} if payload.extended else {}
                    return transport.plan_changes(active, payload.part_number, fixed['changes'], **extra)
                if action == 'batch-program':
                    extra = {'target_identity': fixed.get('target_identity')} if payload.extended else {}
                    return transport.program_changes(active, payload.part_number, fixed['changes'], **extra)
                return hpm_isp_otp.program_change(active, payload.part_number, **fixed)
            finally:
                if owned:
                    active.close()

        try:
            resource_manager.acquire_many([
                ResourceGroup.MKLINK_BRIDGE, ResourceGroup.TARGET_DEBUG,
                ResourceGroup.MUX_RTT, ResourceGroup.MUX_WATCH,
                ResourceGroup.SERIAL_PORT, ResourceGroup.MODBUS_PORT,
            ], owner, preempt=False)
            # HTTP cancellation must not expose UART while the read is running.
            result = await settle(asyncio.create_task(asyncio.to_thread(worker)))
            if action in ('plan', 'batch-plan'):
                if request.app.state.mklink_state.get('device_generation', 0) != binding.generation:
                    raise ValueError('Target selection changed during OTP preview; read again')
                if result.get('qualified') is not True or result.get('write_supported') is not True:
                    return dict(result, plan_id=None, expires_in=0)
                return plans.remember(binding, result)
            return result
        except ResourceError as error:
            raise HTTPException(409, str(error)) from error
        except (ValueError, RuntimeError, OSError) as error:
            raise HTTPException(422, str(error)) from error
        finally:
            resource_manager.release(owner)

    return router
