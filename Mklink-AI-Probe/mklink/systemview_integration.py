"""
MKLink Serial Bridge — SystemView 源码集成工具。

镜像 ``rtt_integration.py`` 的做法，把打包的 SEGGER SystemView 目标端源码
（核心层 + RT-Thread 适配层）集成进 Keil/IAR 工程，并加 ``USE_SYSTEMVIEW`` 宏。
SystemView 跑在 RTT 通道 1 之上，故**先要求 RTT 已集成**（复用 check_rtt_in_project）。

与 RTT 的关键差异：
  * SystemView 的初始化由 RT-Thread 自动完成——``SEGGER_SYSVIEW_RTThread.c`` 里
    的 ``rt_trace_init`` 用 ``INIT_COMPONENT_EXPORT`` 在 INIT_COMPONENT 阶段自动
    调用（已被本仓库打包副本用 ``#ifdef USE_SYSTEMVIEW`` 守卫并追加 ``Start()``）。
    因此 main.c 只需 ``#include "SEGGER_SYSVIEW.h"``，**无需手写 Init 调用**。
  * 所有 SystemView 文件放进工程内单一 ``segger_systemview/`` 目录，并把该目录
    加入 Keil IncludePath（SystemView 头文件互相 include）。

零外部依赖（仅 stdlib）。内部依赖: mklink.rtt_integration（复用备份 / Keil 注册 /
RTT 检查等助手）。
"""

from __future__ import annotations

import os
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

# 打包的 SystemView 源（mklink/systemview_sources/）
_SV_SRC_FILES = [
    "SEGGER_SYSVIEW.c",
    "SEGGER_SYSVIEW_RTThread.c",
    "SEGGER_SYSVIEW_Config_RTThread.c",
]
_SV_INC_FILES = [
    "SEGGER.h",
    "SEGGER_SYSVIEW.h",
    "SEGGER_SYSVIEW_Int.h",
    "SEGGER_SYSVIEW_Conf.h",
    "SEGGER_SYSVIEW_ConfDefaults.h",
    "SEGGER_SYSVIEW_RTThread.h",
]
_ALL_SV_FILES = _SV_SRC_FILES + _SV_INC_FILES


def _is_relative_to(path: Path, root: Path) -> bool:
    path_text = os.path.normcase(str(path.resolve()))
    root_text = os.path.normcase(str(root.resolve()))
    try:
        return os.path.commonpath([path_text, root_text]) == root_text
    except ValueError:
        return False


def _resolve_project_subdir(project_root: Path, path: str, label: str) -> Path:
    raw = Path(path)
    resolved = raw.resolve() if raw.is_absolute() else (project_root / raw).resolve()
    if not _is_relative_to(resolved, project_root):
        raise ValueError(f"{label} must stay inside project_root: {path}")
    return resolved


def _original_from_backup(backup: Path) -> Path | None:
    marker = ".bak."
    if marker not in backup.name:
        return None
    return backup.with_name(backup.name.rsplit(marker, 1)[0])


def get_bundled_systemview_dir() -> Path:
    """返回技能打包的 systemview_sources/ 目录路径。"""
    return Path(__file__).parent / "systemview_sources"


def check_systemview_sources_bundled() -> bool:
    """验证 systemview_sources/ 下所有必需文件存在。"""
    d = get_bundled_systemview_dir()
    return all((d / f).exists() for f in _ALL_SV_FILES)


def check_systemview_in_project(sv_dir: str) -> dict:
    """检查项目中是否已有 SystemView 源文件。"""
    d = Path(sv_dir)
    found = [f for f in _ALL_SV_FILES if (d / f).exists()]
    missing = [f for f in _ALL_SV_FILES if f not in found]
    return {
        "integrated": len(missing) == 0,
        "found": found,
        "missing": missing,
    }


def integrate_systemview_sources(sv_dir: str) -> dict:
    """把打包的 SystemView 文件（.c + .h）复制到工程内单一目录，不覆盖已有文件。"""
    bundled = get_bundled_systemview_dir()
    if not check_systemview_sources_bundled():
        return {
            "success": False, "copied": [], "skipped": [], "errors": [],
        }
    dst = Path(sv_dir)
    dst.mkdir(parents=True, exist_ok=True)
    copied, skipped, errors = [], [], []
    for fname in _ALL_SV_FILES:
        target = dst / fname
        if target.exists():
            skipped.append(str(target))
            continue
        try:
            shutil.copy2(bundled / fname, target)
            copied.append(str(target))
        except OSError as e:
            errors.append(f"复制 {fname} 失败: {e}")
    return {"success": len(errors) == 0, "copied": copied, "skipped": skipped,
            "errors": errors}


def _add_include_path_to_keil(uvprojx_path: str, rel_dir: str) -> dict:
    """把 rel_dir 追加到 Keil .uvprojx 的 VariousControls/IncludePath。"""
    uvprojx = Path(uvprojx_path)
    tree = ET.parse(str(uvprojx))
    root = tree.getroot()
    inc_el = root.find(".//VariousControls/IncludePath")
    if inc_el is None:
        return {"success": False, "errors": ["未找到 VariousControls/IncludePath 节点"]}
    current = (inc_el.text or "").strip()
    # 用反斜杠 + 分号，匹配 Keil 风格；已存在则跳过
    token = rel_dir.replace("/", "\\")
    if token in current.split(";"):
        return {"success": True, "added": False, "errors": []}
    inc_el.text = f"{current};{token}" if current else token
    tree.write(str(uvprojx), encoding="utf-8", xml_declaration=True)
    return {"success": True, "added": True, "errors": []}


def add_systemview_to_keil_project(uvprojx_path: str, sv_dir: str) -> dict:
    """在 Keil 工程注册 SystemView .c 文件到 SEGGER_SYSVIEW 组，并加 IncludePath。"""
    from mklink.rtt_integration import _register_keil_files, _backup_file

    backup = _backup_file(Path(uvprojx_path))
    abs_sv = str(Path(sv_dir).resolve())
    entries = [(group, f"{abs_sv}\\{fname}")
               for group, fname in [("SEGGER_SYSVIEW", f) for f in _SV_SRC_FILES]]
    reg = _register_keil_files(uvprojx_path, entries)
    # 把 SystemView 目录加入 IncludePath（头文件互相 include）
    rel = str(Path(sv_dir).resolve().relative_to(Path(uvprojx_path).resolve().parent.parent))
    inc = _add_include_path_to_keil(uvprojx_path, "..\\" + rel.replace("/", "\\"))
    return {
        "success": reg["success"] and inc["success"],
        "backup_path": str(backup),
        "register": reg,
        "include_path": inc,
        "errors": reg.get("errors", []) + inc.get("errors", []),
    }


def add_systemview_init_to_main(main_c_path: str) -> dict:
    """在 main.c 注入 SystemView 头文件（USE_SYSTEMVIEW 守卫）。

    SystemView 的初始化由 RT-Thread 的 INIT_COMPONENT_EXPORT(rt_trace_init) 自动
    完成，故这里只加 include，不写 Init 调用。
    """
    from mklink.rtt_integration import _backup_file

    main_path = Path(main_c_path)
    if not main_path.exists():
        return {"success": False, "backup_path": "", "errors": [f"main.c 不存在: {main_c_path}"]}
    try:
        content = main_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = main_path.read_text(encoding="gbk")

    if "SEGGER_SYSVIEW.h" in content:
        return {"success": True, "backup_path": "", "added": False,
                "errors": ["SEGGER_SYSVIEW.h 已包含，跳过"]}

    backup = _backup_file(main_path)
    block = (
        "#ifdef USE_SYSTEMVIEW\n"
        '#include "SEGGER_SYSVIEW.h"\n'
        "#endif\n"
    )
    # 优先插在 SEGGER_RTT.h include 之后；否则插在最后一个 #include 之后
    lines = content.split("\n")
    insert_at = 0
    for i, line in enumerate(lines):
        if "SEGGER_RTT.h" in line:
            # 找到其后最近的 #endif（USE_RTT 守卫结束）
            for j in range(i + 1, min(i + 6, len(lines))):
                if lines[j].strip().startswith("#endif"):
                    insert_at = j + 1
                    break
            break
        if line.strip().startswith("#include"):
            insert_at = i + 1
    lines.insert(insert_at, block.rstrip("\n"))
    new_content = "\n".join(lines)
    try:
        main_path.write_text(new_content, encoding="utf-8")
    except UnicodeDecodeError:
        main_path.write_text(new_content, encoding="gbk")
    return {"success": True, "backup_path": str(backup), "added": True, "errors": []}


def add_systemview_macro_to_defines(
    project_root: str,
    uvprojx_path: str | None = None,
    ewp_path: str | None = None,
) -> dict:
    """在工程 Define 中追加 USE_SYSTEMVIEW 宏。"""
    from mklink.iar_parser import find_ewp
    from mklink.keil_parser import find_uvprojx

    root = Path(project_root).resolve()
    if uvprojx_path is None:
        uvprojx_path = find_uvprojx(root)
    if uvprojx_path is None and ewp_path is None:
        ewp_path = find_ewp(root)
    if uvprojx_path:
        return _add_macro_to_keil(uvprojx_path, "USE_SYSTEMVIEW")
    if ewp_path:
        return _add_macro_to_iar(ewp_path, "USE_SYSTEMVIEW")
    return {"success": False, "macro_added": False,
            "errors": ["未找到 Keil 或 IAR 工程文件，无法添加 USE_SYSTEMVIEW 宏"]}


def _add_macro_to_keil(uvprojx_path: str, macro: str) -> dict:
    uvprojx = Path(uvprojx_path)
    tree = ET.parse(str(uvprojx))
    root = tree.getroot()
    define_el = root.find(".//VariousControls/Define")
    if define_el is None:
        return {"success": False, "macro_added": False, "errors": ["未找到 VariousControls/Define 节点"]}
    defines = [d.strip() for d in (define_el.text or "").split(",") if d.strip()]
    if macro in defines:
        return {"success": True, "macro_added": False, "errors": [f"{macro} 已存在"]}
    defines.append(macro)
    define_el.text = ", ".join(defines)
    tree.write(str(uvprojx), encoding="utf-8", xml_declaration=True)
    return {"success": True, "macro_added": True, "ide_type": "Keil", "errors": []}


def _add_macro_to_iar(ewp_path: str, macro: str) -> dict:
    ewp = Path(ewp_path)
    tree = ET.parse(str(ewp))
    root = tree.getroot()
    for config in root.findall("configuration"):
        for settings in config.findall("settings"):
            sname = settings.find("name")
            if sname is not None and sname.text == "ICCARM":
                for data in settings.findall("data"):
                    for option in data.findall("option"):
                        name_el = option.find("name")
                        if name_el is not None and name_el.text == "CCDefines":
                            for state in option.findall("state"):
                                if state.text and state.text.strip() == macro:
                                    return {"success": True, "macro_added": False,
                                            "ide_type": "IAR", "errors": [f"{macro} 已存在"]}
                            ET.SubElement(option, "state").text = macro
                            tree.write(str(ewp), encoding="utf-8", xml_declaration=True)
                            return {"success": True, "macro_added": True,
                                    "ide_type": "IAR", "errors": []}
    return {"success": False, "macro_added": False, "errors": ["未找到 ICCARM/CCDefines 节点"]}


def full_systemview_integrate(
    project_root: str,
    uvprojx_path: str | None = None,
    sv_dir: str = "segger_systemview",
    main_c_path: str | None = None,
    require_rtt: bool = True,
) -> dict:
    """完整 SystemView 集成流程（带回滚）。

    步骤：
      0. 校验 RTT 已集成（SystemView 跑在 RTT 通道 1 上）
      1. 复制 SystemView 源到 ``<project_root>/sv_dir``
      2. 注册 .c 到 Keil SEGGER_SYSVIEW 组 + 加 IncludePath
      3. main.c 加 ``#include "SEGGER_SYSVIEW.h"``（USE_SYSTEMVIEW 守卫）
      4. 工程 Define 加 ``USE_SYSTEMVIEW``

    任何步骤失败自动回滚已做的修改。
    """
    from mklink.rtt_integration import check_rtt_in_project, _find_main_c
    from mklink.keil_parser import find_uvprojx

    root = Path(project_root).resolve()
    backups: list[Path] = []
    copied_paths: list[Path] = []
    sv_abs: Path | None = None
    sv_dir_existed = False
    results: dict = {"copy": None, "keil": None, "main": None, "macro": None,
                     "success": False, "errors": []}

    def _rollback():
        for b in reversed(backups):
            try:
                original = _original_from_backup(b)
                if b.exists() and original is not None:
                    shutil.copy2(b, original)
                    b.unlink()
            except OSError as e:
                results["errors"].append(f"回滚 {b} 失败: {e}")
        for p in reversed(copied_paths):
            try:
                if p.exists():
                    p.unlink()
            except OSError as e:
                results["errors"].append(f"回滚 {p} 失败: {e}")
        if sv_abs is not None and not sv_dir_existed:
            try:
                sv_abs.rmdir()
            except OSError:
                pass

    try:
        sv_abs = _resolve_project_subdir(
            root, sv_dir, "SystemView source directory",
        )
    except ValueError as e:
        results["errors"].append(str(e))
        return results
    sv_dir_existed = sv_abs.exists()

    # 0. RTT 前置校验
    if require_rtt:
        from mklink.rtt_integration import check_rtt_in_project as _chk
        rtt_state = _chk(str(root / "src"),
                         str(root / "libraries" / "HAL_Drivers" / "config"))
        if not rtt_state["integrated"]:
            # 退一步：全工程搜 SEGGER_RTT.c
            found = list(root.rglob("SEGGER_RTT.c"))
            if not found:
                results["errors"].append(
                    "RTT 未集成——SystemView 跑在 RTT 通道 1 上，请先运行 "
                    "`python -m mklink rtt-integrate --project-root .`")
                return results

    # 1. 复制源
    copy_res = integrate_systemview_sources(str(sv_abs))
    results["copy"] = copy_res
    if not copy_res["success"]:
        results["errors"].extend(copy_res.get("errors", []))
        return results
    copied_paths = [Path(p) for p in copy_res.get("copied", [])]

    # 找 Keil 工程
    if uvprojx_path is None:
        uvprojx_path = find_uvprojx(root)
    if not uvprojx_path:
        results["errors"].append("未找到 Keil .uvprojx（IAR 全自动集成暂未实现）")
        _rollback()
        return results

    # 2. 注册到 Keil + IncludePath
    keil_res = add_systemview_to_keil_project(uvprojx_path, str(sv_abs))
    results["keil"] = keil_res
    if keil_res.get("backup_path"):
        backups.append(Path(keil_res["backup_path"]))
    if not keil_res["success"]:
        results["errors"].extend(keil_res.get("errors", []))
        _rollback()
        return results

    # 3. main.c
    if main_c_path is None:
        main_c = _find_main_c(root)
        main_c_path = str(main_c) if main_c else None
    if main_c_path and Path(main_c_path).exists():
        main_res = add_systemview_init_to_main(main_c_path)
        results["main"] = main_res
        if main_res.get("backup_path"):
            backups.append(Path(main_res["backup_path"]))
        if not main_res["success"]:
            results["errors"].extend(main_res.get("errors", []))
            _rollback()
            return results
    else:
        results["errors"].append(f"main.c 未找到（跳过 include 注入）")
        _rollback()
        return results

    # 4. 宏
    macro_res = add_systemview_macro_to_defines(project_root, uvprojx_path=uvprojx_path)
    results["macro"] = macro_res
    if not macro_res["success"]:
        results["errors"].extend(macro_res.get("errors", []))
        _rollback()
        return results

    results["success"] = True
    return results


def generate_systemview_usage_example() -> str:
    """返回 SystemView 集成后的使用说明。"""
    return """\
// SystemView 已集成（USE_SYSTEMVIEW 宏控制）。RT-Thread 启动时自动初始化并
// 开始把跟踪事件写入 RTT 通道 1——无需手写任何 Init 调用。
// 额外 RTT 通道在 SystemView 初始化后配置（INIT_APP 或 main）；启用
// SEGGER_RTT_SECTION 时 SystemView 初始化会重置 RTT 控制块。不要随后重复 Init。
// 若普通 RTT 已占用通道 1，请把 SystemView 改为独立通道，并匹配上下行通道容量。
// 集成命令不覆盖工程已有文件；旧适配器需要审查后单独更新。
//
// PC 端采集：
//   python -m mklink systemview --duration 10         # 控制台解码事件
//   mklink gui → Dashboard → 'RTOS Trace' Tab          # 可视化时间轴
//   MCP: systemview_start / systemview_read            # Agent 调用
//
// 发布固件时移除 USE_SYSTEMVIEW 宏即可关闭（移除后 SEGGER_SYSVIEW_RTThread.c
// 的 rt_trace_init 不注册任何钩子、不跟踪）。
//
// 配置（segger_systemview/SEGGER_SYSVIEW_Conf.h + Config_RTThread.c）：
//   通道 = 1（SEGGER_SYSVIEW_RTT_CHANNEL，与 mklink 读取一致）
//   缓冲 = 16384 字节（SEGGER_SYSVIEW_RTT_BUFFER_SIZE，欠读会溢出，可调大）
//   CPU 频率 = SystemCoreClock；RAM base = 0x20000000；时间戳 = DWT CYCCNT
"""
