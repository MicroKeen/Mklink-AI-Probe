"""Keep user captures out of the code/installation tree, across all clients."""
from pathlib import Path
import sys


def capture_directory(directory) -> Path:
    """Validate before creating files; never silently redirect a user's output."""
    path = Path(directory).expanduser().resolve()
    roots = [Path(__file__).resolve().parent.parent]
    if getattr(sys, 'frozen', False):
        roots.append(Path(sys.executable).resolve().parent)
    for parent in (path, *path.parents):
        if ((parent / 'SKILL.md').is_file() and (parent / 'mklink/__init__.py').is_file()) or (
                (parent / 'mklink-ai-probe.exe').is_file() and (parent / 'mklink-sidecar.exe').is_file()):
            roots.append(parent)
    if any(path.is_relative_to(root) for root in roots):
        raise ValueError(
            '工程日志不能保存在 Skill 或上位机安装目录；请选择用户工程的 .mklink/logs 目录。 '
            'Choose the target project .mklink/logs directory, outside the Skill/desktop installation.'
        )
    return path
