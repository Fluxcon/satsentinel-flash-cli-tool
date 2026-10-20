from __future__ import annotations

import configparser
import sys
from pathlib import Path


def cfg_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "satsentinel-cli.cfg"
    return Path.home() / ".satsentinel" / "satsentinel-cli.cfg"


def read_cfg() -> dict[str, str]:
    path = cfg_path()
    if not path.exists():
        return {}
    parser = configparser.ConfigParser()
    try:
        parser.read(path)
    except (configparser.Error, OSError):
        return {}
    return dict(parser["satsentinel"]) if "satsentinel" in parser else {}


def write_cfg(key: str, value: str) -> None:
    path = cfg_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        parser = configparser.ConfigParser()
        if path.exists():
            parser.read(path)
        if "satsentinel" not in parser:
            parser["satsentinel"] = {}
        parser["satsentinel"][key] = value
        with path.open("w") as f:
            parser.write(f)
        path.chmod(0o600)  # holds the API token
    except OSError as e:
        raise OSError(f"Cannot write config {path}: {e}") from e


def load_token() -> str | None:
    return read_cfg().get("token") or None


def save_token(token: str) -> None:
    write_cfg("token", token)
