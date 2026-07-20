"""
Service Logs Tool Module.

Runs `journalctl -u <service> -n <lines>` locally (subprocess) and returns
the raw output so the LLM can spot errors/warnings. Read-only.
"""

import re
import subprocess
from .tool import Tool

_VALID_SERVICE_NAME = re.compile(r"^[a-zA-Z0-9_.@-]+$")
_MAX_LINES = 200
_DEFAULT_LINES = 50


def service_logs(service_name=None, lines=None, **kwargs):
    """
    Returns the last N log lines for a systemd service via journalctl.

    Args:
        service_name (str): Name of the systemd service (e.g. "nginx").
        lines (int): How many recent log lines to fetch (default 50, max 200).

    Returns:
        str: Raw log output, or a clear error message.
    """
    if service_name is None:
        service_name = kwargs.get("service_name")
    if lines is None:
        lines = kwargs.get("lines", _DEFAULT_LINES)

    if not service_name:
        return "Nu am primit numele serviciului. Ex: nginx, sshd, docker."

    if not _VALID_SERVICE_NAME.match(service_name):
        return (
            f"Numele de serviciu '{service_name}' conține caractere neobișnuite "
            "pentru un unit systemd — refuz să-l trimit ca să evit orice risc."
        )

    try:
        lines = int(lines)
    except (TypeError, ValueError):
        lines = _DEFAULT_LINES
    lines = max(1, min(lines, _MAX_LINES))

    try:
        result = subprocess.run(
            ["journalctl", "-u", service_name, "-n", str(lines), "--no-pager"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = (result.stdout or "") + (result.stderr or "")
        if not output.strip():
            output = f"(niciun log găsit pentru '{service_name}')"
        return output[:4000]

    except FileNotFoundError:
        return (
            "Comanda 'journalctl' nu există pe acest sistem. Probabil botul "
            "rulează local pe Windows/macOS, nu pe serverul Linux țintă — "
            "acest tool trebuie rulat pe (sau conectat la) mașina Linux reală."
        )
    except subprocess.TimeoutExpired:
        return f"Comanda 'journalctl -u {service_name}' a depășit timpul limită (10s)."
    except Exception as e:
        return f"Eroare la citirea logurilor pentru '{service_name}': {e}"


service_logs_tool = Tool(
    name="service_logs",
    description=(
        "Fetches the most recent journalctl log lines for a Linux systemd "
        "service, to help diagnose errors, warnings, or startup failures. "
        "Read-only."
    ),
    parameters={
        "type": "object",
        "properties": {
            "service_name": {
                "type": "string",
                "description": "The systemd service name, e.g. 'nginx', 'sshd', 'docker'."
            },
            "lines": {
                "type": "integer",
                "description": "How many recent log lines to fetch (default 50, max 200)."
            }
        },
        "required": ["service_name"]
    },
    callback=service_logs
)