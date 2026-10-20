from __future__ import annotations

import io
from pathlib import Path

from satsentinel_flash import _nvs_partition_gen as _nvs

_PARTITION_SIZE = "0x6000"
_NAMESPACE = "ap_cfg"


def generate_nvs(
    imei: str,
    ap_password: str,
    output_path: Path,
    extras: list[tuple[str, str, int | str]] = (),
) -> Path:
    """Generate 24 KB NVS partition binary for factory flash.

    extras: sequence of (key, nvs_encoding, value) written into ap_cfg after
    the fixed keys. Encoding is any value accepted by nvs_partition_gen
    (e.g. "u32", "string"). Value must match the encoding type.
    """
    input_size = _nvs.check_size(_PARTITION_SIZE)
    buf = io.BytesIO()
    with _nvs.nvs_open(buf, input_size, version=_nvs.Page.VERSION2) as nvs:
        _nvs.write_entry(nvs, _NAMESPACE, "namespace", "", "")
        _nvs.write_entry(nvs, "imei", "data", "string", imei)
        _nvs.write_entry(nvs, "ap_password", "data", "string", ap_password)
        _nvs.write_entry(nvs, "provisioned", "data", "u8", "0")
        _nvs.write_entry(nvs, "debug", "data", "u8", "1")
        for key, encoding, value in extras:
            _nvs.write_entry(nvs, key, "data", encoding, value)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(buf.getvalue())
    return output_path
