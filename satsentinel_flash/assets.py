from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

import requests
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from satsentinel_flash.api import FirmwareInfo, ProvisionResponse

if TYPE_CHECKING:
    from satsentinel_flash.ui import ClackUI


def _cache_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "cache"
    return Path.home() / ".satsentinel" / "cache"

_ASSET_KEYS = [
    ("bootloader_url",        "bootloader.bin"),
    ("partition_table_url",   "partition-table.bin"),
    ("firmware_url",          "satsentinel.bin"),
    ("ota_data_initial_url",  "ota_data_initial.bin"),
]


def _download(url: str, dest: Path, ui: ClackUI) -> None:
    from satsentinel_flash.api import ApiError
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(url, stream=True, timeout=60) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            with Progress(
                TextColumn("[color(102)]│[/]  [bold blue]{task.description}"),
                BarColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
                console=ui._console,
                transient=False,
            ) as progress:
                task = progress.add_task(dest.name, total=total or None)
                with dest.open("wb") as f:
                    for chunk in resp.iter_content(chunk_size=65536):
                        f.write(chunk)
                        progress.advance(task, len(chunk))
    except requests.RequestException as e:
        raise ApiError(str(e)) from e
    except OSError as e:
        raise ApiError(f"Write failed: {e}") from e


def _download_set(
    version: str,
    urls: dict[str, str],
    ui: ClackUI,
) -> tuple[Path, Path, Path, Path]:
    version_dir = _cache_root() / version
    paths: dict[str, Path] = {}
    for key, filename in _ASSET_KEYS:
        dest = version_dir / filename
        if dest.exists():
            ui.note(f"Cached  {filename}")
        else:
            ui.note(f"Downloading {filename} …")
            _download(urls[key], dest, ui)
        paths[key] = dest
    return (
        paths["bootloader_url"],
        paths["partition_table_url"],
        paths["firmware_url"],
        paths["ota_data_initial_url"],
    )


def download_assets(provision: ProvisionResponse, ui: ClackUI) -> tuple[Path, Path, Path, Path]:
    return _download_set(
        provision.firmware_version,
        {k: getattr(provision, k) for k, _ in _ASSET_KEYS},
        ui,
    )


def download_latest_firmware(info: FirmwareInfo, ui: ClackUI) -> tuple[Path, Path, Path, Path]:
    return _download_set(
        info.firmware_version,
        {k: getattr(info, k) for k, _ in _ASSET_KEYS},
        ui,
    )


def cached_versions() -> list[str]:
    if not _cache_root().exists():
        return []
    dirs = [d for d in _cache_root().iterdir() if d.is_dir()]
    dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
    return [d.name for d in dirs]


def get_cached_paths(version: str) -> tuple[Path, Path, Path, Path]:
    version_dir = _cache_root() / version
    paths: dict[str, Path] = {}
    missing = []
    for key, filename in _ASSET_KEYS:
        dest = version_dir / filename
        if dest.exists():
            paths[key] = dest
        else:
            missing.append(filename)
    if missing:
        raise FileNotFoundError(
            f"Firmware {version!r} not fully cached (missing: {', '.join(missing)}). "
            "Run without --offline first to cache firmware."
        )
    return (
        paths["bootloader_url"],
        paths["partition_table_url"],
        paths["firmware_url"],
        paths["ota_data_initial_url"],
    )
