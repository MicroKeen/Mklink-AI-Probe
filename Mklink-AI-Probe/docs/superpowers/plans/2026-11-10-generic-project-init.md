# Optional generic project initialization implementation plan

> Execute inline with `superpowers:executing-plans`; verify behavior with `superpowers:test-driven-development`.

**Goal:** Let CMake/CLion and other projects save explicit target/artifact inputs, while direct flash remains usable without initialization.

**Architecture:** Keep offline Keil/IAR/HPM import and the existing `.mklink` schema. Add explicit generic inputs to `project-init`, report missing target information accurately, and let CLI flash consume one unambiguous saved firmware path. No hardware discovery during initialization.

**Tech Stack:** Python, argparse, pytest, existing shared runtime.

**Spec:** The user approved the preceding three-part proposal: optional initialization, generic explicit configuration, actionable missing-input errors. This document records its implementation details.

## Global constraints

- Continue `codex/v0.5.0-fixes`; preserve existing settings and all unrelated work.
- PowerShell 7 and UTF-8; tests through `scripts/build_workspace.ps1 -BuildRoot F:/MKLink-Build`.
- No new hardware operation, firmware change, installer, merge or publication.
- Explicit paths for initialization resolve relative to project root; missing build outputs may be configured before building.
- Do not guess a target from a directory name, ELF architecture or SW-DP ID.

## Review focus

- Ordinary CMake output layouts must not be mistaken for HPM SDK.
- Malformed existing JSON or invalid explicit inputs must cause failure without writes.
- Existing connection/RTT/toolchain settings survive initialization.
- Relative paths work when the CLI runs outside the project; competing saved images require explicit selection.
- Missing target and initialization failures must be visible to CLI/API callers.

## Task 1: Generic initialization and flash input resolution

**Files:** `mklink/cli.py`, `mklink/runtime_cli.py`, `mklink/device.py`, `mklink/remote/api.py`; tests in `_maintainer/testing/tests/test_generic_project_init.py`, `test_shared_flash_options.py`, `test_device_flash_verify.py`, `test_hpm_project_detect.py`.

**Interfaces:** Extend `_cli_project_init(project_root, *, target_part=None, firmware=None, elf=None) -> int`; return 0 on success, 1 on failure. CLI options `--target-part`, `--firmware`/`--hex`, `--elf`/`--axf`. Save canonical `device`, `hex_path`/`bin_path`, `axf_path`/`elf_path`. Explicit generic inputs do not require IDE detection. Flash accepts explicit image first, otherwise exactly one configured HEX/BIN image from the selected project.

- [x] Add failing tests for generic CLI initialization, validation/nonmutation, offline behavior, saved-image selection/ambiguity, truthful API status and target guidance.
- [x] Run focused tests and confirm the failures represent missing behavior.
- [x] Implement generic inputs, HPM detection guard, return codes and flash fallback/errors.
- [x] Run new tests and affected project/import/flash/runtime suites; inspect the diff.

## Task 2: Instructions, review and handoff

**Files:** `SKILL.md`, relevant `references/*.md`, `docs/verification/v050-project-init.md`, `docs/ai/project-memory.json`, generated `docs/ai/CURRENT_HANDOFF.md`.

- [x] Document direct flash and optional generic configuration; remove mandatory-init guidance.
- [x] Exercise the actual CLI offline with a CMake-shaped fixture through the build wrapper.
- [x] Review the scoped change with a fresh reviewer, address substantive findings, and run required checks.
- [ ] Record evidence and unverified hardware scope, render/validate memory, `git diff --check`, commit and push the existing branch; update its existing PR.

## Evidence and decisions

- Focused RED: 15 failures; first GREEN: 100 passes. Review follow-up RED: 4 failures. An additional failing regression pins existing IDE identity when updating paths explicitly.
- Actual offline CLI exit codes and saved paths verified. Detailed scope: [verification report](../../verification/v050-project-init.md).
- Explicit target migration is rejected for different stored targets or legacy profiles; this avoids inheriting incompatible target state. Users must verify existing configuration before changing chips.
- Scratch/evidence stays under the configured F: build root. Existing worktree and PR #79 are reused under standing repository authorization.

