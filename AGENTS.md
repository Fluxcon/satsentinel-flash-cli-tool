# AGENTS.md

`satsentinel-cli` flashes SatSentinel ESP32-S3 boards: it fetches firmware and per-device provisioning from the SatSentinel API, generates an NVS partition, and writes everything with esptool.

## Dev setup

Needs Python 3.11+ (`python3 --version`).

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
satsentinel-cli --help        # all flags
pytest                        # no tests written yet
pyinstaller satsentinel_flash.spec && ./dist/satsentinel-cli --help
```

## Modules

- `cli.py`: Click entry point and interactive loop (API URL → token → action menu). `--offline` is a separate scripted path.
- `ui.py`: `ClackUI`, terminal rendering only.
- `auth.py`: owns the config file. `api.py`: backend calls. `assets.py`: firmware download and cache.
- `nvs.py`: builds the NVS partition. `flash.py`: runs esptool in a thread and streams its output.

## Gotchas

- **esptool is called as a library** (`esptool.main([...])`), never as a subprocess. It raises `SystemExit` on success and failure alike; check `.code`.
- **`_nvs_partition_gen.py` is vendored from ESP-IDF v5.1** with lines 16–26 patched to replace `distutils` (removed in Python 3.12). Keep the patch when updating the file.
- **UI output is pinned to `sys.__stdout__`** because `flash.py` redirects `sys.stdout` to capture esptool. Every UI write goes through `ClackUI._stdout`.
- **Prompt cursor math:** `text()` erases 3 lines; `select()` erases N+2. Changing either prompt's layout means changing these counts.
- **`prompt_toolkit`** is imported directly by `ui.py` but arrives only as a dependency of `questionary`.
- **Config file:** `satsentinel-cli.cfg` (INI, section `[satsentinel]`, keys `api_url`, `token`), next to the binary when frozen, else `~/.satsentinel/`. Written with mode 0600. `SATSENTINEL_API_URL` overrides the URL without saving it.
- **Auth is token-only.** Users get tokens from the web frontend; `--login` re-prompts.
- **Errors:** network and disk failures become `ApiError`; everything from esptool becomes `FlashError`. Config write failures are warnings, not fatal.

## NVS contents

Namespace `ap_cfg`. These are the factory values; after flashing, the firmware owns them.

| Key | Type | Value |
|---|---|---|
| `imei` | string | device IMEI |
| `ap_password` | string | Wi-Fi AP password from the server |
| `provisioned` | u8 | 0 (firmware sets 1 after the first-install wizard) |
| `debug` | u8 | 1 (boards must start in debug mode) |
| `hubadr` | u32 | kwehub only, when the API returns it |

All four fixed keys are required. Extras come from the provision response (`_provision_extras`) or from `--extra key=0xHEX` (u32) / `--extra key=value` (string). The API sends `hubadr` as a decimal string; parse it base 10.

AP SSID is `SATS_<last 6 digits of IMEI>`.

## Flash layout (ESP32-S3)

Changing an address can brick a board, so match the firmware's partition table exactly.

| Region | Address | Size |
|---|---|---|
| Bootloader | `0x0` | — |
| Partition table | `0x8000` | — |
| NVS (generated) | `0x9000` | `0x6000` |
| Firmware | `0x10000` | `0x1F0000` |
| OTA 1 | `0x200000` | `0x1F0000` |
| OTA data | `0x3F0000` | `0x2000` |

## Releases

Pushing a tag `satsentinel-cli-vX.Y.Z` runs `.github/workflows/build.yml`, which builds Linux, macOS (arm64) and Windows binaries. Files PyInstaller must bundle are listed under `datas` in `satsentinel_flash.spec`.
