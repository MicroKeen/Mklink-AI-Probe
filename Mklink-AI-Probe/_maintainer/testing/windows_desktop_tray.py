"""Exercise a single test-owned desktop's tray through its Win32 window and menu."""

import ctypes
import json
import sys
import time
from urllib.request import ProxyHandler, build_opener

import win32con
import win32gui
import win32process


def wait_for(read, message):
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        result = read()
        if result:
            return result
        time.sleep(0.1)
    raise RuntimeError(message)


def owned_window(pid, class_name):
    matches = []

    def visit(hwnd, _):
        if win32process.GetWindowThreadProcessId(hwnd)[1] == pid and win32gui.GetClassName(hwnd) == class_name:
            matches.append(hwnd)

    win32gui.EnumWindows(visit, None)
    return matches[0] if len(matches) == 1 else None


def verify(pid, main, port, instance):
    assert win32process.GetWindowThreadProcessId(main)[1] == pid
    tray = wait_for(lambda: owned_window(pid, 'tray_icon_app'), 'Missing notification icon')
    # The tray-icon crate registers this Shell_NotifyIcon callback message.
    tray_callback = 6002
    win32gui.PostMessage(main, win32con.WM_CLOSE, 0, 0)
    wait_for(lambda: not win32gui.IsWindowVisible(main), 'Main window did not hide')
    assert win32gui.IsWindow(main)
    with build_opener(ProxyHandler({})).open(f'http://127.0.0.1:{port}/api/health', timeout=3) as res:
        assert json.load(res)['desktop_instance_id'] == instance
    win32gui.PostMessage(tray, tray_callback, 0, win32con.WM_LBUTTONUP)
    wait_for(lambda: win32gui.IsWindowVisible(main), 'Tray did not restore the same window')
    win32gui.PostMessage(tray, tray_callback, 0, win32con.WM_RBUTTONUP)
    popup = wait_for(lambda: owned_window(pid, '#32768'), 'Tray menu did not open')
    menu = win32gui.SendMessage(popup, 0x01E1, 0, 0)  # MN_GETHMENU
    assert menu
    for index in range(win32gui.GetMenuItemCount(menu)):
        label = ctypes.create_unicode_buffer(100)
        ctypes.windll.user32.GetMenuStringW(ctypes.c_void_p(menu), index, label, len(label), win32con.MF_BYPOSITION)
        if label.value.replace('&', '') == 'Exit':
            command = win32gui.GetMenuItemID(menu, index)
            win32gui.PostMessage(tray, win32con.WM_CANCELMODE, 0, 0)
            win32gui.PostMessage(tray, win32con.WM_COMMAND, command, 0)
            return
    raise RuntimeError('Tray menu lacks the explicit Exit command')


if __name__ == '__main__':
    verify(int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4])
