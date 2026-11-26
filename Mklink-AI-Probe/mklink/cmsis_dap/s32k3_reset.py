"""S32K3 functional reset on the previously identified application processor."""

def prepare(dp, evidence, profile):
    name = f"{profile.name}.FunctionalReset"
    evidence.update(command=name, ap6_idr=None, acknowledged_steps=0)
    # Check the entire MDM-AP ID again on the already admitted target's DP.
    idr = dp.read_ap(0x060000FC)
    evidence["ap6_idr"] = idr
    if idr != 0x001C0030:
        raise ValueError(f"Unexpected {profile.name} MDM-AP IDR {idr:#010x}; no reset issued")

    if profile.online_system_reset == "s32k3_functional":
        # The two RMs define SYSFUNCRST as a level. Preserve all unrelated
        # controls, including the debug requests for other cores.
        initial = dp.read_ap(0x06000004)
        if initial & 0x30:
            raise ValueError("MDM-AP already requests a system reset")
        values = (initial | 0x20, initial)
    else:
        values = (0x00400B00, 0x00400B20, 0x00400B00, 0x00400000)

    def functional_reset():
        # DFP ResetSystem -> FunctionalReset. Set reset-release/debug-request
        # controls, pulse SYSFUNCRST, then release debug requests.
        for step, value in enumerate(values, start=1):
            evidence["step"] = step
            dp.write_ap(0x06000004, value)
            dp.flush()
            evidence["acknowledged_steps"] = step

    return name, functional_reset
