from __future__ import annotations

import requests
from dataclasses import dataclass


class ApiError(Exception):
    pass


@dataclass
class ProvisionResponse:
    imei: str
    ap_password: str
    firmware_version: str
    firmware_url: str
    bootloader_url: str
    partition_table_url: str
    ota_data_initial_url: str
    hubadr: str | None = None


def _check(resp: requests.Response) -> dict:
    try:
        body = resp.json()
    except Exception:
        body = None

    if not resp.ok:
        msg = (body.get("error") or body.get("message") or resp.text[:200]) if isinstance(body, dict) else resp.text[:200]
        raise ApiError(f"HTTP {resp.status_code}: {msg}")

    if isinstance(body, dict) and "error" in body:
        raise ApiError(body["error"])

    return body


def _req(method: str, url: str, **kwargs) -> requests.Response:
    try:
        return requests.request(method, url, **kwargs)
    except requests.RequestException as e:
        raise ApiError(str(e)) from e


def get_provision(imei: str, token: str, api_url: str) -> ProvisionResponse:
    url = f"{api_url.rstrip('/')}/api/devices/{imei}/provision"
    data = _check(_req("GET", url, headers={"Authorization": f"Bearer {token}"}, timeout=30))
    return ProvisionResponse(
        imei=data["imei"],
        ap_password=data["ap_password"],
        firmware_version=data["version"],
        firmware_url=data["firmware_url"],
        bootloader_url=data["bootloader_url"],
        partition_table_url=data["partition_table_url"],
        ota_data_initial_url=data["ota_data_initial_url"],
        hubadr=data.get("hubadr"),
    )


@dataclass
class FirmwareInfo:
    firmware_version: str
    firmware_url: str
    bootloader_url: str
    partition_table_url: str
    ota_data_initial_url: str


def get_latest_firmware(token: str, api_url: str) -> FirmwareInfo:
    url = f"{api_url.rstrip('/')}/api/firmware"
    data = _check(_req("GET", url, headers={"Authorization": f"Bearer {token}"}, timeout=30))
    return FirmwareInfo(
        firmware_version=data["version"],
        firmware_url=data["firmware_url"],
        bootloader_url=data["bootloader_url"],
        partition_table_url=data["partition_table_url"],
        ota_data_initial_url=data["ota_data_initial_url"],
    )


