"""Construct a pyOCD session from the exact user-selected Pack device."""

from uuid import uuid4

from .errors import FlashError, FlashErrorCode
from .pyocd_runtime import import_pyocd_attr


def create_profile_pack_session(probe, options):
    """Board resolves a string in TARGET, with builtins taking priority over a DFP."""
    pack_targets = import_pyocd_attr("pyocd.target.pack.pack_target", "PackTargets")
    registry = import_pyocd_attr("pyocd.target", "TARGET")
    session_type = import_pyocd_attr("pyocd.core.session", "Session")
    model = options["target_override"]
    matches = []

    def match(device):
        if device.part_number.casefold() == model.casefold():
            matches.append(device)

    pack_targets.process_targets_from_pack(options["pack"], match)
    if len(matches) != 1:
        raise FlashError(FlashErrorCode.TARGET_NOT_SUPPORTED,
                         f"Selected Pack must contain exactly one device named {model}")
    target_type = pack_targets._generate_pack_target_class(matches[0])
    if target_type is None:
        raise FlashError(FlashErrorCode.TARGET_NOT_SUPPORTED, f"Cannot load {model} from selected Pack")

    # pyOCD resolves the board during Session construction, before USB open.
    # A private key allows simultaneous probes/Packs without replacing a public target.
    key = "mklink_pack_" + uuid4().hex
    registry[key] = target_type
    try:
        session = session_type(probe, options=dict(options, target_override=key, pack=None))
        if type(session.target) is not target_type:
            raise FlashError(FlashErrorCode.CONNECT_FAIL, f"Probe did not select {model} from the requested Pack")
        return session
    finally:
        registry.pop(key, None)
