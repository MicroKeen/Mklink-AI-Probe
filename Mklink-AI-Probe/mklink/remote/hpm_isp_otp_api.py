"""Bounded UART OTP reads, independent of JTAG and SD deployment."""
from __future__ import annotations

import asyncio
from typing import Literal
import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict


class OtpReadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    part_number: Literal["HPM5301", "HPM5301XEGX"]
    model: Literal["V4"] = "V4"


def create_hpm_isp_otp_router(resource_manager, device_provider):
    router = APIRouter(prefix="/api/device/configuration/hpm-isp-otp", tags=["device"])

    @router.post("/read")
    async def read(request: Request, payload: OtpReadRequest):
        from mklink.hpm_isp_otp import read_snapshot
        from mklink.remote.resource_manager import ResourceError, ResourceGroup
        from mklink.runtime_api import settle

        runtime = getattr(request.app.state, "shared_runtime", None)
        port = None
        if runtime is not None:
            from mklink.probes import select_probe
            runtime.require_identity()
            if runtime.uart_operations or any(s.scope == "uart" for s in runtime.sessions.values()):
                raise HTTPException(409, "Finish UART operations and detach UART clients before reading OTP")
            if runtime.current_operation is not None:
                runtime.current_operation["uart_exclusive"] = True
            port = select_probe(runtime.info["probe_id"])["port"]

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
                return read_snapshot(active, payload.part_number)
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
            return await settle(asyncio.create_task(asyncio.to_thread(worker)))
        except ResourceError as error:
            raise HTTPException(409, str(error)) from error
        except (ValueError, RuntimeError, OSError) as error:
            raise HTTPException(422, str(error)) from error
        finally:
            resource_manager.release(owner)

    return router
