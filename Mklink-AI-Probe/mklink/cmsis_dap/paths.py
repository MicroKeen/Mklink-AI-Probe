"""Stable filesystem locations for CMSIS-Pack catalog data."""

from dataclasses import dataclass, field
import os
from pathlib import Path
import platform


def _default_root() -> Path:
    configured = os.environ.get("MKLINK_PYOCD_HOME")
    if configured:
        return Path(configured)

    legacy = Path.home() / "AppData" / "Local" / "MKLink" / "pyocd"
    if platform.system() == "Windows":
        local = os.environ.get("LOCALAPPDATA")
        return Path(local) / "MKLink" / "pyocd" if local else legacy

    from mklink.web_entry import platform_data_dir
    native = platform_data_dir().parent / "pyocd"
    # Keep an established, writable catalog on upgrade. An unrelated AppData
    # directory (or an empty snapshot directory) does not select the old path.
    try:
        if not native.exists() and os.access(legacy, os.W_OK | os.X_OK):
            markers = ("state.json", "index/index.json", "index/aliases.json", "custom-flm/registry.json")
            if any((legacy / entry).is_file() for entry in markers):
                return legacy
    except OSError:
        pass  # An inaccessible legacy directory must not block the local service.
    return native


@dataclass(frozen=True)
class PackPaths:
    """Paths used by the local CMSIS-Pack cache."""

    root: Path = field(default_factory=_default_root)

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", Path(self.root))

    @property
    def index_dir(self) -> Path:
        return self.root / "index"

    @property
    def index_file(self) -> Path:
        return self.index_dir / "index.json"

    @property
    def aliases_file(self) -> Path:
        return self.index_dir / "aliases.json"

    @property
    def data_dir(self) -> Path:
        return self.root / "data"

    @property
    def staging_dir(self) -> Path:
        return self.root / "staging"

    @property
    def state_file(self) -> Path:
        return self.root / "state.json"
