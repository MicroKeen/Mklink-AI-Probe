"""Keep user captures out of the code/installation tree, across all clients."""
from pathlib import Path
import sys
import errno
import time


def open_log_file(path, mode, **kwargs):
    # Readers and sync clients may briefly deny sharing on Windows.
    for delay in (.04, .08, .16, .32, None):
        try:
            return path.open(mode, **kwargs)
        except PermissionError as exc:
            if delay is None or getattr(exc, 'winerror', None) not in (32, 33):
                raise
            time.sleep(delay)


def file_error(action, error, path=None):
    """Keep the native error and identify the operation and recovery step."""
    location = getattr(error, 'filename', None) or path
    win = getattr(error, 'winerror', None)
    if win in (32, 33):
        help_text = '文件正被占用。请关闭打开该文件的程序，或等同步结束后重试。'
    elif isinstance(error, FileExistsError):
        help_text = '同名文件已存在。已有文件受到保护，请保留或重命名它，再重试。'
    elif isinstance(error, PermissionError) or getattr(error, 'errno', None) == errno.EROFS:
        help_text = '访问被拒绝。请核对此路径的访问权限；保存或替换文件时还需检查只读属性。'
    elif isinstance(error, FileNotFoundError):
        help_text = '路径不存在。请确认工程目录可访问，并检查文件是否已移动。'
    elif getattr(error, 'errno', None) in (errno.ENOSPC, getattr(errno, 'EDQUOT', -1)) or win in (39, 112):
        help_text = '存储空间不足。请释放空间后重试。'
    else:
        help_text = '请查看下方详情，检查文件路径和存储设备。' if isinstance(error, OSError) else ''
    place = f'（{location}）' if location else ''
    return f'{action}失败{place}。{help_text} {error}'.strip()



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
