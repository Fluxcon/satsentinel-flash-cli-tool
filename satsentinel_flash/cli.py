from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import click

from satsentinel_flash import __version__
from satsentinel_flash.auth import load_token, read_cfg, save_token, write_cfg
from satsentinel_flash.ui import ClackUI


# ── NVS extras helpers ────────────────────────────────────────────────────────

def _parse_extras(raw: tuple[str, ...]) -> list[tuple[str, str, int | str]]:
    """Parse --extra key=value flags into (key, nvs_encoding, value) tuples.

    Values prefixed with 0x are written as u32; all others as string.
    """
    result: list[tuple[str, str, int | str]] = []
    for item in raw:
        if "=" not in item:
            raise click.UsageError(f"--extra must be key=value, got: {item!r}")
        key, _, val = item.partition("=")
        key = key.strip()
        if not key:
            raise click.UsageError(f"--extra key cannot be empty: {item!r}")
        if val.lower().startswith("0x"):
            try:
                result.append((key, "u32", int(val, 16)))
            except ValueError:
                raise click.UsageError(f"--extra {key}: invalid hex value {val!r}")
        else:
            result.append((key, "string", val))
    return result


def _provision_extras(provision) -> list[tuple[str, str, int | str]]:
    """Convert known optional provision fields into NVS extras tuples."""
    extras: list[tuple[str, str, int | str]] = []
    if provision.hubadr is not None:
        extras.append(("hubadr", "u32", int(provision.hubadr)))
    return extras


# ── offline scripted path ─────────────────────────────────────────────────────

def _scripted_offline(
    ui: ClackUI,
    imei: str | None,
    ap_password: str,
    firmware_version: str | None,
    port: str | None,
    baud: int,
    extras: list[tuple[str, str, int | str]] = (),
) -> None:
    from satsentinel_flash.assets import cached_versions, get_cached_paths
    from satsentinel_flash.flash import FlashError, flash_device_threaded, list_serial_ports
    from satsentinel_flash.nvs import generate_nvs

    if not imei:
        raise SystemExit("--offline requires IMEI argument.")

    version = firmware_version
    if not version:
        versions = cached_versions()
        if not versions:
            raise SystemExit("No cached firmware. Run without --offline first.")
        version = versions[0]

    try:
        bootloader_path, partition_table_path, firmware_path, ota_data_path = get_cached_paths(version)
    except FileNotFoundError as exc:
        raise SystemExit(str(exc)) from exc

    with tempfile.TemporaryDirectory() as tmpdir:
        nvs_path = Path(tmpdir) / f"nvs_{imei}.bin"
        try:
            generate_nvs(imei, ap_password, nvs_path, extras=extras)
        except Exception as exc:
            ui.error(f"NVS generation failed: {exc}")
            sys.exit(1)

        ports = list_serial_ports()
        if not ports:
            raise SystemExit("No serial ports found.")
        selected_port = port or (ports[0].device if len(ports) == 1 else None)
        if not selected_port:
            choices = [f"{p.device}  {p.description}" for p in ports]
            selected_port = ui.select("Serial port", choices).split()[0]

        try:
            flash_device_threaded(
                ui=ui,
                port=selected_port,
                bootloader=bootloader_path,
                partition_table=partition_table_path,
                nvs_bin=nvs_path,
                firmware=firmware_path,
                ota_data=ota_data_path,
                baud=baud,
            )
        except FlashError as exc:
            ui.error(str(exc))
            sys.exit(1)

    ssid = f"SATS_{imei[-6:]}"
    ui.step("Flash complete (offline)", f"[bold #22c55e]✓[/] IMEI: {imei}  SSID: {ssid}")


# ── action: list firmware ─────────────────────────────────────────────────────

def _action_list_firmware(ui: ClackUI) -> None:
    from satsentinel_flash.assets import _ASSET_KEYS, _cache_root, cached_versions
    versions = cached_versions()
    if not versions:
        ui.note("No firmware cached. Use [bold]Cache firmware[/bold] to download.")
        return
    cache_root = _cache_root()
    ui.note(f"Cache: [dim]{cache_root}[/dim]")
    for v in versions:
        version_dir = cache_root / v
        files = [filename for _, filename in _ASSET_KEYS]
        present = [f for f in files if (version_dir / f).exists()]
        total_bytes = sum((version_dir / f).stat().st_size for f in present)
        size_mb = total_bytes / (1024 * 1024)
        complete = len(present) == len(files)
        status = "[bold #22c55e]complete[/]" if complete else f"[bold #ef4444]incomplete ({len(present)}/{len(files)} files)[/]"
        ui.step(f"v{v}", f"{status}  [dim]{size_mb:.1f} MB[/dim]")


# ── action: generate offline command ─────────────────────────────────────────

def _action_generate_command(ui: ClackUI) -> None:
    from rich.panel import Panel
    from satsentinel_flash.assets import cached_versions
    from satsentinel_flash.flash import list_serial_ports

    versions = cached_versions()
    if not versions:
        ui.error("No firmware cached. Run [bold]Cache firmware[/bold] first.")
        return

    imei = ui.text(
        "IMEI (15 digits)",
        validate=lambda v: None if (v.isdigit() and len(v) == 15) else "Must be exactly 15 digits",
    ).strip()

    password = ui.text("AP password").strip()

    if len(versions) == 1:
        version = versions[0]
        ui.step("Firmware version", version)
    else:
        version = ui.select("Firmware version", versions)

    ports = list_serial_ports()
    port_choice = ui.select(
        "Include serial port?",
        (["Omit (auto-detect at flash time)"] + [f"{p.device}  {p.description}" for p in ports])
        if ports else ["Omit (no ports detected)"],
    )
    selected_port = None if port_choice.startswith("Omit") else port_choice.split()[0]

    exe = "satsentinel-cli.exe" if sys.platform == "win32" else "./satsentinel-cli"
    parts = [exe, "--offline", f"--imei {imei}", f"--password {password}",
             f"--firmware-version {version}"]
    if selected_port:
        parts.append(f"--port {selected_port}")

    cmd = " ".join(parts)
    ui._console.print()
    ui._console.print(Panel(
        f"[bold white]{cmd}[/bold white]",
        title="[dim]offline flash command[/dim]",
        border_style="color(102)",
        padding=(0, 1),
    ))
    ui._console.print()


# ── action: clear cache ───────────────────────────────────────────────────────

def _action_clear_cache(ui: ClackUI) -> None:
    import shutil
    from satsentinel_flash.assets import _cache_root, cached_versions
    versions = cached_versions()
    if not versions:
        ui.note("No cached firmware to clear.")
        return
    choices = versions + ["All versions"]
    choice = ui.select("Which version to delete?", choices)
    if choice == "All versions":
        to_delete = versions
        label = "all cached versions"
    else:
        to_delete = [choice]
        label = choice
    confirm = ui.select(f"Delete {label}?", ["Yes, delete", "Cancel"])
    if confirm == "Cancel":
        ui.note("Cancelled.")
        return
    cache_root = _cache_root()
    for v in to_delete:
        shutil.rmtree(cache_root / v, ignore_errors=True)
    ui.step("Cache cleared", f"[bold #22c55e]✓[/] {label} removed")


# ── action: cache firmware ────────────────────────────────────────────────────

def _action_cache(ui: ClackUI, api_url: str, token: str) -> None:
    from satsentinel_flash.api import ApiError, get_latest_firmware
    from satsentinel_flash.assets import download_latest_firmware
    try:
        with ui.spin("Fetching latest firmware info…"):
            info = get_latest_firmware(token, api_url)
        ui.note(f"Firmware version [bold]{info.firmware_version}[/bold]")
        download_latest_firmware(info, ui)
        ui.step("Firmware cached", f"[bold #22c55e]✓[/] {info.firmware_version}")
    except ApiError as exc:
        ui.error(str(exc))
    except Exception as exc:
        ui.error(f"Download failed: {exc}")


# ── action: flash hardware ────────────────────────────────────────────────────

def _action_flash(
    ui: ClackUI,
    api_url: str,
    token: str,
    flash_imei: str | None,
    firmware_version: str | None,
    port: str | None,
    baud: int,
    extras: list[tuple[str, str, int | str]] = (),
) -> None:
    from satsentinel_flash.api import ApiError, get_provision
    from satsentinel_flash.assets import cached_versions, download_assets, get_cached_paths
    from satsentinel_flash.flash import FlashError, flash_device_threaded, list_serial_ports
    from satsentinel_flash.nvs import generate_nvs
    selected_port = port

    while True:
        # IMEI
        if flash_imei:
            imei = flash_imei.strip()
            flash_imei = None
            ui.step("IMEI", imei)
        else:
            imei = ui.text(
                "IMEI (15 digits)",
                validate=lambda v: None if (v.isdigit() and len(v) == 15) else "Must be exactly 15 digits",
            ).strip()

        # Port — prompt once, reuse on "Flash another"
        if not selected_port:
            ports = list_serial_ports()
            if not ports:
                ui.error("No serial ports found. Connect device and try again.")
                return
            if len(ports) == 1:
                selected_port = ports[0].device
                ui.step("Serial port", selected_port)
            else:
                choices = [f"{p.device}  {p.description}" for p in ports]
                selected_port = ui.select("Serial port", choices).split()[0]
        else:
            ui.step("Serial port", selected_port)

        # Fetch provision data
        provision = None
        try:
            with ui.spin(f"Fetching provisioning data for {imei}…"):
                provision = get_provision(imei, token, api_url)
        except ApiError as exc:
            if "401" in str(exc):
                ui.error("Token expired — run with --login to re-enter your token.")
            else:
                ui.error(str(exc))
            return

        # Download firmware assets
        try:
            download_assets(provision, ui)
        except ApiError as exc:
            ui.error(str(exc))
            return

        # Firmware version selection (if multiple cached)
        versions = cached_versions()
        if firmware_version:
            use_version = firmware_version
            ui.step("Firmware version", use_version)
        elif len(versions) > 1:
            use_version = ui.select("Firmware version", versions)
        else:
            use_version = provision.firmware_version
            ui.step("Firmware version", use_version)

        # Generate NVS + flash
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            nvs_path = Path(tmpdir) / f"nvs_{imei}.bin"
            try:
                with ui.spin("Generating NVS partition…"):
                    generate_nvs(
                        provision.imei,
                        provision.ap_password,
                        nvs_path,
                        extras=_provision_extras(provision) + list(extras),
                    )
            except Exception as exc:
                ui.error(f"NVS generation failed: {exc}")
                return

            try:
                bootloader, partition_table, firmware, ota_data = get_cached_paths(use_version)
            except FileNotFoundError as exc:
                ui.error(str(exc))
                return

            key_lines: list[str] = []
            try:
                key_lines = flash_device_threaded(
                    ui=ui,
                    port=selected_port,
                    bootloader=bootloader,
                    partition_table=partition_table,
                    nvs_bin=nvs_path,
                    firmware=firmware,
                    ota_data=ota_data,
                    baud=baud,
                )
            except Exception as exc:
                ui.error(f"Flash failed: {exc}")
                for line in key_lines:
                    ui.note(line)
                return

        ssid = f"SATS_{provision.imei[-6:]}"
        ui.step(
            "Flash complete",
            f"[bold #22c55e]✓[/]  IMEI: {provision.imei}   SSID: {ssid}",
        )

        action = ui.select("What next?", ["Flash another device", "Back to main menu"])
        if action == "Back to main menu":
            return
        # Loop — port stays, new IMEI prompted next iteration


# ── interactive loop ──────────────────────────────────────────────────────────

def _interactive_loop(
    ui: ClackUI,
    api_url: str | None,
    auth_token: str | None,
    cache_only: bool,
    firmware_version: str | None,
    port: str | None,
    baud: int,
    force_login: bool,
    flash_imei: str | None,
    extras: list[tuple[str, str, int | str]] = (),
) -> None:
    # ── Phase 1: API URL ──────────────────────────────────────────────────────
    resolved_url = api_url or os.environ.get("SATSENTINEL_API_URL")
    if not resolved_url:
        cfg = read_cfg()
        resolved_url = cfg.get("api_url")

    if resolved_url:
        ui.step("API URL", resolved_url)
    else:
        resolved_url = ui.text(
            "Provisioning API URL",
            placeholder="https://api.satsentinel.com",
            validate=lambda v: None if v.startswith("http") else "Must start with http",
        )
        try:
            write_cfg("api_url", resolved_url)
        except OSError as exc:
            ui.warn(f"Could not save API URL: {exc}")

    # ── Phase 2: Authentication ───────────────────────────────────────────────
    if auth_token:
        try:
            save_token(auth_token)
        except OSError as exc:
            ui.warn(f"Could not save token: {exc}")
        token = auth_token
        ui.step("Authenticate", f"[bold #22c55e]✓[/] Connected to {resolved_url}")
    elif not force_login and (cached_token := load_token()):
        token = cached_token
        ui.step("Authenticate", f"[bold #22c55e]✓[/] Connected to {resolved_url}")
    else:
        token = ui.text(
            "Paste your API token",
            silent=True,
            validate=lambda v: None if v.strip() else "Token cannot be empty",
        ).strip()
        try:
            save_token(token)
        except OSError as exc:
            ui.warn(f"Could not save token: {exc}")
        ui.step("Authenticate", f"[bold #22c55e]✓[/] Connected to {resolved_url}")

    # ── Phase 3: Action ───────────────────────────────────────────────────────
    if cache_only:
        _action_cache(ui, resolved_url, token)
        return

    if flash_imei:
        _action_flash(ui, resolved_url, token, flash_imei, firmware_version, port, baud, extras=extras)
        return

    while True:
        action = ui.select(
            "What would you like to do?",
            ["Flash hardware", "Cache firmware", "List firmware", "Clear cache", "Generate offline command", "Exit"],
        )
        if action == "Exit":
            break
        elif action == "Flash hardware":
            _action_flash(ui, resolved_url, token, None, firmware_version, port, baud, extras=extras)
        elif action == "Cache firmware":
            _action_cache(ui, resolved_url, token)
        elif action == "List firmware":
            _action_list_firmware(ui)
        elif action == "Clear cache":
            _action_clear_cache(ui)
        elif action == "Generate offline command":
            _action_generate_command(ui)


# ── Click entry point ─────────────────────────────────────────────────────────

@click.command()
@click.version_option(__version__, prog_name="satsentinel-cli")
@click.option("--api", "--api-url", "api_url", envvar="SATSENTINEL_API_URL",
              help="Provisioning API URL. Saved to config on first use.")
@click.option("--auth", "auth_token", metavar="TOKEN",
              help="Pre-fill bearer token (saved, skips login prompt).")
@click.option("--password", "ap_password", metavar="PASSWORD",
              help="AP password for NVS. Required with --offline.")
@click.option("--offline", "offline", is_flag=True,
              help="Flash using cached firmware. No network calls. Requires --password.")
@click.option("--cache", "cache_only", is_flag=True,
              help="Download and cache firmware only. No flash.")
@click.option("--firmware-version", metavar="VERSION",
              help="Firmware version tag to use.")
@click.option("--port", metavar="PORT", help="Serial port (skips interactive selection).")
@click.option("--baud", default=460800, show_default=True, help="Flash baud rate.")
@click.option("--login", "force_login", is_flag=True, help="Re-enter API token even if one is cached.")
@click.option("--imei", "flash_imei", metavar="IMEI",
              help="Skip action menu and flash this IMEI directly.")
@click.option("--extra", "raw_extras", metavar="KEY=VALUE", multiple=True,
              help="Extra NVS key-value pair written into ap_cfg. Values prefixed with 0x are stored as u32; all others as string. Can be specified multiple times.")
def cli(
    api_url: str | None,
    auth_token: str | None,
    ap_password: str | None,
    offline: bool,
    cache_only: bool,
    firmware_version: str | None,
    port: str | None,
    baud: int,
    force_login: bool,
    flash_imei: str | None,
    raw_extras: tuple[str, ...],
) -> None:
    """Provision a SatSentinel ESP32-S3 unit."""
    ui = ClackUI()
    ui.intro(f"SatSentinel Flash  [color(102)]v{__version__}[/]")

    extras = _parse_extras(raw_extras)

    # Offline scripted path
    if offline:
        if not ap_password:
            raise click.UsageError("--offline requires --password <AP_PASSWORD>.")
        _scripted_offline(ui, flash_imei, ap_password, firmware_version, port, baud, extras=extras)
        ui.outro("Done")
        return

    _interactive_loop(
        ui=ui,
        api_url=api_url,
        auth_token=auth_token,
        cache_only=cache_only,
        firmware_version=firmware_version,
        port=port,
        baud=baud,
        force_login=force_login,
        flash_imei=flash_imei,
        extras=extras,
    )
    ui.outro("Done")
