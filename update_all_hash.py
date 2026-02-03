#!/usr/bin/env python3
"""
Upsert RetroAchievements hash lists for all systems into `all_hash/`.

Uses the exact curl shape requested:
  https://retroachievements.org/API/API_GetGameList.php?i=<SYSTEM_ID>&h=1&f=1&y=<API_KEY>&f=1

Rate-limited to ~1 request/second to avoid API rate limiting.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


ROOT_DIR = Path(__file__).resolve().parent
SYSTEMS_PATH = ROOT_DIR / "data" / "all_system_id.json"
ALL_HASH_DIR = ROOT_DIR / "all_hash"


@dataclass(frozen=True)
class SystemInfo:
    id: int
    name: str
    icon_url: str
    active: bool
    is_game_system: bool


def _load_app_constants(path: Path) -> dict[str, str]:
    """
    Load KEY=VALUE lines from APP_CONSTANTS (if present).
    """
    if not path.exists():
        return {}

    out: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _sanitize_slug(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "unknown"


def _icon_basename(icon_url: str) -> str:
    # e.g. https://.../system/gbc.png -> gbc
    name = icon_url.rsplit("/", 1)[-1]
    if "." in name:
        name = name.rsplit(".", 1)[0]
    return name


def _system_file_stem(system: SystemInfo) -> str:
    """
    Produce a stable stem used by existing files where possible.
    """
    icon = _icon_basename(system.icon_url)

    # Preserve your existing naming conventions for commonly-used systems.
    # (Icon basenames differ from folder naming in a few cases.)
    alias = {
        "nes": "fc",
        "snes": "sfc",
        "2600": "atari",
        "ngp": "neogeo",
        "arc": "arcade",
    }
    return _sanitize_slug(alias.get(icon, icon))


def _load_systems() -> list[SystemInfo]:
    data = json.loads(SYSTEMS_PATH.read_text(encoding="utf-8"))
    systems: list[SystemInfo] = []
    for item in data:
        systems.append(
            SystemInfo(
                id=int(item["ID"]),
                name=str(item.get("Name", "")),
                icon_url=str(item.get("IconURL", "")),
                active=bool(item.get("Active", False)),
                is_game_system=bool(item.get("IsGameSystem", False)),
            )
        )
    return systems


def _curl_game_list(system_id: int, api_key: str, timeout_s: int) -> str:
    url = (
        "https://retroachievements.org/API/API_GetGameList.php"
        f"?i={system_id}&h=1&f=1&y={api_key}&f=1"
    )
    # Use curl exactly (as requested), and follow redirects.
    proc = subprocess.run(
        ["curl", "--location", url],
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"curl failed (exit {proc.returncode})")
    return proc.stdout


def _iter_target_systems(
    systems: Iterable[SystemInfo], include_inactive: bool
) -> list[SystemInfo]:
    out: list[SystemInfo] = []
    for s in systems:
        if not s.is_game_system:
            continue
        if (not include_inactive) and (not s.active):
            continue
        out.append(s)
    return sorted(out, key=lambda x: x.id)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Upsert `all_hash/all-*.json` for all RetroAchievements systems."
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="RetroAchievements API key (overrides APP_CONSTANTS / env).",
    )
    parser.add_argument(
        "--include-inactive",
        action="store_true",
        help="Also fetch systems marked Active=false in `all_system_id.json`.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=1.05,
        help="Delay between curl calls (default: 1.05).",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=60,
        help="Per-request timeout for curl (default: 60).",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Retries per system on failure (default: 3).",
    )
    args = parser.parse_args()

    constants = _load_app_constants(ROOT_DIR / "APP_CONSTANTS")
    api_key = (
        args.api_key
        or os.environ.get("RA_API_KEY")
        or constants.get("RA_API_KEY")
        or ""
    ).strip()
    if not api_key:
        print(
            "Missing API key. Provide one of:\n"
            "- `--api-key YOUR_KEY`\n"
            "- env var `RA_API_KEY`\n"
            "- file `APP_CONSTANTS` with `RA_API_KEY=...`",
            file=sys.stderr,
        )
        return 2

    ALL_HASH_DIR.mkdir(parents=True, exist_ok=True)
    systems = _iter_target_systems(_load_systems(), include_inactive=args.include_inactive)
    total = len(systems)
    if total == 0:
        print("No systems found to update.", file=sys.stderr)
        return 1

    started = time.time()
    for idx, sysinfo in enumerate(systems, start=1):
        stem = _system_file_stem(sysinfo)
        out_path = ALL_HASH_DIR / f"all-{stem}.json"

        # Progress line
        print(f"[{idx:>3}/{total}] system {sysinfo.id:>3} -> {out_path.name} ({sysinfo.name})")

        last_err: Exception | None = None
        for attempt in range(1, args.retries + 1):
            try:
                body = _curl_game_list(sysinfo.id, api_key=api_key, timeout_s=args.timeout_seconds)
                # Validate it's JSON; keep pretty output for easier diffs/readability.
                parsed: Any = json.loads(body)
                out_path.write_text(json.dumps(parsed, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
                last_err = None
                break
            except Exception as e:  # noqa: BLE001 - simple CLI script
                last_err = e
                if attempt < args.retries:
                    time.sleep(min(5.0, args.sleep_seconds * attempt))
                continue

        if last_err is not None:
            print(
                f"  ERROR: failed system {sysinfo.id} after {args.retries} attempts: {last_err}",
                file=sys.stderr,
            )

        # Always sleep between systems to respect rate limits.
        if idx < total:
            time.sleep(args.sleep_seconds)

    elapsed = time.time() - started
    print(f"Done. Updated {total} systems in {elapsed:.1f}s.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

