# satsentinel-cli

Factory provisioning CLI for SatSentinel ESP32-S3 units. Interactive TUI walks through
authentication, firmware caching, and full-stack flash in one session.

## Download

Latest release: [Fluxcon/satsentinel-flash-cli-tool/releases/latest](https://github.com/Fluxcon/satsentinel-flash-cli-tool/releases/latest)

| File | Platform |
|------|----------|
| `satsentinel-cli-linux.zip` | Linux x64 |
| `satsentinel-cli-macos.zip` | macOS arm64 |
| `satsentinel-cli-win64.zip` | Windows x64 |

### Linux

```bash
unzip satsentinel-cli-linux.zip
./satsentinel-cli
```

### macOS

```bash
unzip satsentinel-cli-macos.zip
xattr -d com.apple.quarantine satsentinel-cli
./satsentinel-cli
```

> The `xattr` command removes the Gatekeeper quarantine flag macOS applies to downloaded files. Only required on first run.

### Windows

Extract `satsentinel-cli-win64.zip` and run `satsentinel-cli.exe`. Windows may show a SmartScreen warning — click **More info → Run anyway**.

---

On first run you will be prompted for your API URL and API token. Both are saved to
`satsentinel-cli.cfg` alongside the binary. Subsequent runs skip straight to the
action menu.

## Interactive flow

```
┌  SatSentinel Flash  v1.0.0-alpha
│
◇  API URL
│  https://api.satsentinel.com
│
◆  Paste your API token
│  › 
│
◇  Authenticate
│  ✓ Connected to https://api.satsentinel.com
│
◆  What would you like to do?
│  ● Cache firmware
│  ○ Flash hardware
│  ○ Exit
```

After a successful flash you are offered **Flash another device** which reuses the
selected COM port and fetches fresh credentials from the API.

## Flags

All flags are optional. Any value provided skips the corresponding interactive prompt.

| Flag | Description |
|------|-------------|
| `--api URL` | Provisioning API URL. Saved on first use. Also: `SATSENTINEL_API_URL` env var. |
| `--auth TOKEN` | Pre-supply bearer token (saved, skips token prompt). |
| `--flash IMEI` | Skip action menu and flash this IMEI directly. |
| `--port PORT` | Serial port (skips interactive selection). |
| `--baud N` | Flash baud rate (default: 460800). |
| `--firmware-version TAG` | Pin firmware to a specific cached version. |
| `--cache` | Download and cache firmware only, no flash. |
| `--login` | Re-enter API token even if one is cached. |
| `--offline` | Flash using cached firmware. No network calls. Requires `--password`. |
| `--password PW` | AP password for NVS (offline mode only). |

### Fully non-interactive example

```bash
./satsentinel-cli --api https://api.example.com --auth <TOKEN> --flash 123456789012345 --port /dev/ttyUSB0
```

## Config

All settings are stored in a single `satsentinel-cli.cfg` INI file:

- **Pre-built binary**: `satsentinel-cli.cfg` in the same directory as the executable.
- **Dev (pip install -e)**: `~/.satsentinel/satsentinel-cli.cfg`

```ini
[satsentinel]
api_url = https://api.satsentinel.com
token = <your token>
```

Delete this file to fully reset (clears saved URL and token).

URL resolution priority: `--api` flag → `SATSENTINEL_API_URL` env var → `satsentinel-cli.cfg`.

## Offline mode

```bash
./satsentinel-cli --offline --password <AP_PASSWORD> <IMEI>
```

Requires firmware already cached (run **Cache firmware** from the action menu first).
Unit is NOT marked as provisioned in the backend.

## Dev setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
satsentinel-cli --help
```

The dev entry point (after `pip install -e .`) is `satsentinel-cli`; the distributed binary has the same name.

## Build standalone binary

```bash
pyinstaller satsentinel_flash.spec
./dist/satsentinel-cli --help
```

## Flash layout (ESP32-S3)

| Region | Address | Size |
|--------|---------|------|
| Bootloader | `0x0` | — |
| Partition table | `0x8000` | — |
| NVS (generated) | `0x9000` | `0x6000` (24 KB) |
| Firmware (`satsentinel.bin`) | `0x10000` | `0x1F0000` |
| OTA 1 slot | `0x200000` | `0x1F0000` |
| OTA data | `0x3F0000` | `0x2000` |

`ota_data_initial.bin` is flashed to `0x3F0000` on first flash to initialise OTA slot
tracking. Without it, rollback may not work correctly.

## NVS partition

Namespace `ap_cfg`, keys written at factory flash:

| Key | Type | Value |
|-----|------|-------|
| `imei` | string | 15-digit Iridium IMEI |
| `ap_password` | string | WiFi AP hotspot password |
| `provisioned` | u8 | `1` (hides first-install wizard on boot) |
| `debug` | u8 | `0` (WARN-only logging for production) |

AP SSID format: `SATS_<last 6 digits of IMEI>`.

Factory reset preserves `imei` and `ap_password` but erases `provisioned`, `debug`,
and all `system` / `wifi_sta` namespace keys.

## License

GPL-3.0-or-later; see [LICENSE](LICENSE). The release binaries bundle
[esptool](https://github.com/espressif/esptool) (GPL-2.0-or-later) and other
third-party packages under their own licenses.
`satsentinel_flash/_nvs_partition_gen.py` is vendored from ESP-IDF
(Apache-2.0, Espressif Systems) and keeps its original header.
