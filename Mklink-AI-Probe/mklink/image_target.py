"""Resolve target identity from data that belongs to the selected ELF image."""
from __future__ import annotations

import hashlib
import json
import os
import re
import xml.etree.ElementTree as ET
from functools import lru_cache
from itertools import islice
from pathlib import Path

import yaml

from elftools.common.exceptions import DWARFError, ELFError
from elftools.elf.elffile import ELFFile

from mklink.iar_parser import _get_option_value
from mklink.keil_parser import _strip_namespaces
from mklink.profiles import TargetProfileError, load_mcu_profiles, model_key_index, normalize_model_id, resolve_attach_profile

# Only exact device tokens in a startup object, system source or device header
# are evidence. A core name, arbitrary path component or memory address is not.
_FILE = re.compile(r"(?:^|[^\w.-])(?P<prefix>startup[_-]|system[_-])?(?P<device>[a-z][a-z0-9_-]*\d[a-z0-9_-]*)\.(?:h|s|c|o|obj)(?=$|[^\w])", re.I)
_CORE = re.compile(r":Cortex-(?:[AMR]\d+\+?)(?:_(\d+))?$", re.I)
_GENERIC = re.compile(r"(?:CORTEX|ARMV|RISCV|CORE|CMSIS)|(?:XX|XXX)$", re.I)
_LIMIT = 8 * 1024 * 1024


def _text_file(path, limit=_LIMIT):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        return ""
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        return ""
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    return data.decode("utf-8-sig", errors="replace")


def _matches(image, base, value):
    if not isinstance(value, str) or not value or "$" in value:
        return False
    return Path(os.path.abspath(base / value.replace("\\", "/"))) == image


def _project_devices(project, image):
    if project.name.endswith(".cbuild-run.yml"):
        data = yaml.safe_load(_text_file(project)) or {}
        run = data.get("cbuild-run", {}) if isinstance(data, dict) else {}
        if isinstance(run, dict) and any(isinstance(o, dict) and o.get("type") == "elf"
                and _matches(image, project.parent, o.get("file")) for o in run.get("output") or []):
            yield run.get("device")
        return

    body = _text_file(project)
    if not body:
        return
    root = ET.fromstring(body)
    _strip_namespaces(root)
    if project.suffix.lower() == ".uvprojx":
        for options in root.findall(".//Target/TargetOption/TargetCommonOption"):
            folder = options.findtext("OutputDirectory")
            name = options.findtext("OutputName")
            if not name or not folder:
                continue
            if not Path(name).suffix and image.suffix.lower() in (".elf", ".axf"):
                name += image.suffix
            if _matches(image, project.parent, folder.rstrip("\\/") + "/" + name):
                yield options.findtext("Device")
    else:
        for config in root.findall("configuration"):
            groups = {s.findtext("name"): s.find("data") for s in config.findall("settings")}
            general, linker = groups.get("General"), groups.get("ILINK")
            if general is None or linker is None:
                continue
            folder = _get_option_value(general, "ExePath")
            name = _get_option_value(linker, "IlinkOutputFile")
            if not folder or not name:
                continue
            output = folder.replace("$PROJ_DIR$", ".").rstrip("\\/") + "/" + name
            if _matches(image, project.parent, output):
                menu = _get_option_value(general, "OGChipSelectEditMenu").split()
                if menu:
                    yield menu[0]


def _elf_sources(elf):
    meta = elf.get_section_by_name(".mklink.target")
    if meta is not None and meta.data_size <= 4096 and not meta["sh_flags"] & 2:
        doc = json.loads(meta.data().rstrip(b"\0"))
        if isinstance(doc, dict) and doc.get("schema_version") == 1:
            yield "elf-section", doc.get("device"), True
    attributes = elf.get_section_by_name(".ARM.attributes")
    if attributes is not None and hasattr(attributes, "iter_subsections"):
        for subsection in attributes.iter_subsections():
            for scope in subsection.iter_subsubsections():
                for attr in scope.iter_attributes():
                    if attr.tag == "TAG_CPU_NAME":
                        yield "elf-attribute", attr.value, False
    if not elf.has_dwarf_info(strict=True):
        return
    dwarf = elf.get_dwarf_info(follow_links=False)
    seen = set()
    for cu in dwarf.iter_CUs():
        name_attr = cu.get_top_DIE().attributes.get("DW_AT_name")
        line = dwarf.line_program_for_CU(cu)
        names = [name_attr.value] if name_attr else []
        if line is not None:
            names.extend(f.name for f in line["file_entry"])
        for raw in names:
            if not isinstance(raw, bytes) or raw in seen:
                continue
            seen.add(raw)
            name = raw.decode(errors="replace").replace("\\", "/").rsplit("/", 1)[-1]
            for match in _FILE.finditer(name):
                yield "dwarf", match["device"], False


@lru_cache(maxsize=1)
def _catalog_names():
    # These are the immutable resources shipped with this backend. Only load
    # names when an image supplies a device token, never enumerate hardware.
    from mklink.cmsis_dap.builtin_flm_bundle import load_builtin_flm_targets
    from mklink.cmsis_dap.builtin_pack_bundle import load_builtin_pack_records
    names = {record.part_number.upper(): record.part_number for record in load_builtin_pack_records()}
    names.update((record.part_number.upper(), record.part_number) for record in load_builtin_flm_targets())
    return names


def _device_mask(name, catalog_name):
    # Catalog spelling distinguishes literal X (e.g. XMC) from package 'x'.
    # CMSIS headers may also omit package and density with a trailing xx.
    spelling = catalog_name or name
    first_digit = re.search(r"\d", spelling)
    if not first_digit:
        return None
    tail = spelling[first_digit.end():]
    if catalog_name and "x" in tail:
        return spelling[:first_digit.end()] + tail.replace("x", "?")
    if name.lower().endswith("xx") and (not catalog_name or catalog_name.endswith(("xx", "XX"))):
        return re.sub("x+$", lambda m: "?" * len(m[0]), name, flags=re.I)
    if not catalog_name and re.fullmatch(r"STM32[A-Z]\d{3}X[A-Z0-9]", name, re.I):
        return name[:-2] + "?" + name[-1]
    return None


def resolve_image_target(path):
    """Return a JSON-ready identity and its evidence. Never access the target."""
    image = Path(path).absolute()
    evidence = set()
    issues = []
    family_masks = {}
    models = load_mcu_profiles()
    index = model_key_index(models)

    def add(source, value, explicit):
        if not isinstance(value, str) or len(value) > 200:
            return
        part = value.strip().split("::")[-1]
        core = _CORE.search(part)
        if core:
            part = part[:core.start()]
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", part, re.I) or not re.search(r"\d", part):
            return
        catalog = _catalog_names()
        declared = catalog.get(part.upper())
        if not declared and "_" in part:
            # e.g. nRF52840_xxAA.h vs the catalog's nRF52840xxAA
            declared = catalog.get(re.sub(r"_(?=xx)", "", part, flags=re.I).upper())
            if declared:
                part = declared
        mask = _device_mask(part, declared) if not explicit else None
        if mask and not declared and part.lower().endswith("xx"):
            prefix = mask.split("?")[0].upper()
            if len(prefix) < 4 or not any(name.startswith(prefix) for name in catalog):
                mask = None
        if _GENERIC.search(part) and not mask:
            return
        key = index.get(normalize_model_id(part))
        if key and "mux_attach" in models[key] and core and core[1] not in (None, "0"):
            issues.append(f"{source}: unsupported processor {value}")
            return
        if key:
            part = models[key]["name"]
        elif not explicit and not (declared or mask) and not re.fullmatch(r"(?:STM32[A-Z]\d{3}[A-Z0-9]*|HPM\d{4}[A-Z0-9]*|(?:GD|N|AT)32[A-Z]\d{3}[A-Z0-9]*)", part, re.I):
            return
        if mask and not key:
            family_masks[part.upper()] = mask.upper()
        evidence.add((source, part.upper()))

    def result():
        devices = sorted({device for _, device in evidence})
        concrete = set(devices) - family_masks.keys()
        if concrete:
            from mklink.cmsis_dap.builtin_flm_bundle import resolve_builtin_flm_parts
            aliases = resolve_builtin_flm_parts(sorted(concrete)) if family_masks else {}
            for family, mask in family_masks.items():
                pattern = re.escape(mask).replace(r"\?", "[A-Z0-9]") + "[A-Z0-9]{0,4}"
                if any(part.startswith(mask.split("?")[0]) and (re.fullmatch(pattern, part) or
                       aliases.get(part.lower(), "").upper() == family) for part in concrete):
                    devices.remove(family)
        elif len(devices) == 1 and devices[0] in family_masks and devices[0].endswith("XX"):
            devices = []  # A generic header alone cannot choose a package.
        status = "conflict" if len(devices) > 1 or issues else ("identified" if devices else "unknown")
        return {"status": status, "device": devices[0] if status == "identified" else None,
                "evidence": [{"source": src, "device": d} for src, d in sorted(evidence)],
                "issues": issues}

    try:
        stream = image.open("rb")
    except OSError:
        return result()
    with stream:
        if stream.read(4) != b"\x7fELF":
            return result()
        stream.seek(0)
        try:
            elf = ELFFile(stream)
            if elf["e_type"] not in ("ET_EXEC", "ET_DYN") or elf["e_machine"] not in ("EM_ARM", "EM_RISCV"):
                return result()
        except (ELFError, OSError, ValueError):
            return result()
        try:
            for source, value, explicit in _elf_sources(elf):
                add(source, value, explicit)
        except (DWARFError, ELFError, ValueError, KeyError, OSError, TypeError, IndexError):
            pass
        sidecar = image.with_name(image.name + ".mklink.json")
        if sidecar.is_file():
            try:
                doc = json.loads(_text_file(sidecar, 4096))
                stream.seek(0)
                digest = hashlib.sha256()
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
                if (isinstance(doc, dict) and type(doc.get("schema_version")) is int and doc["schema_version"] == 1
                        and isinstance(doc.get("sha256"), str) and doc["sha256"].lower() == digest.hexdigest()):
                    add(sidecar.name, doc.get("device"), True)
                else:
                    issues.append(f"{sidecar.name}: version or SHA-256 mismatch")
            except (ValueError, OSError):
                issues.append(f"{sidecar.name}: unreadable identity")
    map_path = image.with_suffix(".map")
    try:
        for match in _FILE.finditer(_text_file(map_path, 32 * 1024 * 1024)):
            # Link maps can contain many device headers from library listings.
            if match["prefix"]:
                add(map_path.name, match["device"], False)
    except OSError:
        pass
    for parent in islice(image.parents, 5):
        if parent == parent.parent:
            break
        for pattern in ("*.uvprojx", "*.ewp", "*.cbuild-run.yml"):
            for project in parent.glob(pattern):
                try:
                    for value in _project_devices(project, image):
                        add(project.name, value, True)
                except (ET.ParseError, yaml.YAMLError, ValueError, OSError, TypeError, RecursionError):
                    continue
    return result()


def image_binding(path, override=None):
    identity = resolve_image_target(path)
    if identity["status"] == "conflict" and not override:
        if identity["issues"] or any(resolve_attach_profile(e["device"]) for e in identity["evidence"]):
            raise TargetProfileError("image_target_conflict", str(identity["issues"] or identity["evidence"]))
    return identity, resolve_attach_profile(override or identity["device"])
