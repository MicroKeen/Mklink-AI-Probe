"""S32K314 MDM-AP functional reset from Keil::S32K3xx_DFP@1.0.1."""

MODEL = "S32K314"
MEM_AP = 4


def prepare(dp, evidence):
    name = "S32K314.FunctionalReset"
    evidence.update(command=name, ap6_idr=None, acknowledged_steps=0)
    # Check the entire MDM-AP ID again on the already admitted target's DP.
    idr = dp.read_ap(0x060000FC)
    evidence["ap6_idr"] = idr
    if idr != 0x001C0030:
        raise ValueError(f"Unexpected S32K314 MDM-AP IDR {idr:#010x}; no reset issued")

    def functional_reset():
        # DFP ResetSystem -> FunctionalReset. Set reset-release/debug-request
        # controls, pulse SYSFUNCRST, then release debug requests.
        for step, value in enumerate((0x00400B00, 0x00400B20, 0x00400B00, 0x00400000), start=1):
            evidence["step"] = step
            dp.write_ap(0x06000004, value)
            dp.flush()
            evidence["acknowledged_steps"] = step

    return name, functional_reset
