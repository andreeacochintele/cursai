"""
Service Logs Tool Module.

Fetches recent Windows Event Log entries related to a service, via
PowerShell's Get-WinEvent. This is the Windows analog of `journalctl -u`.
Read-only.
"""

import os
import re
import subprocess
from .tool import Tool

_VALID_SERVICE_NAME = re.compile(r"^[a-zA-Z0-9 _.-]+$")
_MAX_LINES = 100
_DEFAULT_LINES = 20


def service_logs(service_name=None, lines=None, **kwargs):
    """
    Returns recent Windows Event Log entries mentioning a service name,
    searched across the System and Application logs.

    Args:
        service_name (str): Windows service name, e.g. "Spooler".
        lines (int): How many recent matching events to fetch (default 20, max 100).

    Returns:
        str: Formatted event output, or a clear error message.
    """
    if service_name is None:
        service_name = kwargs.get("service_name")
    if lines is None:
        lines = kwargs.get("lines", _DEFAULT_LINES)

    if not service_name:
        return "I didn't receive a service name. Example: Spooler, wuauserv, W32Time."

    if not _VALID_SERVICE_NAME.match(service_name):
        return f"'{service_name}' has unusual characters for a service name — refusing to run it, to stay safe."

    try:
        lines = int(lines)
    except (TypeError, ValueError):
        lines = _DEFAULT_LINES
    lines = max(1, min(lines, _MAX_LINES))

    env = os.environ.copy()
    env["SVC_NAME"] = service_name
    env["SVC_LINES"] = str(lines)

    command = (
        "Get-WinEvent -LogName System,Application -MaxEvents 500 -ErrorAction SilentlyContinue | "
        "Where-Object { $_.Message -like ('*' + $env:SVC_NAME + '*') } | "
        "Select-Object -First ([int]$env:SVC_LINES) TimeCreated, LevelDisplayName, Message | "
        "Format-List"
    )

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            timeout=20,
            env=env,
        )
        output = (result.stdout or "") + (result.stderr or "")
        if not output.strip():
            output = f"(no matching events found for '{service_name}')"
        return output[:4000]

    except FileNotFoundError:
        return "The 'powershell' command isn't available on this system."
    except subprocess.TimeoutExpired:
        return f"Fetching logs for '{service_name}' timed out (20s)."
    except Exception as e:
        return f"Error fetching logs for '{service_name}': {e}"


service_logs_tool = Tool(
    name="service_logs",
    description=(
        "Fetches recent WINDOWS Event Log entries (System/Application logs) "
        "mentioning a given service, to help diagnose errors or warnings — "
        "the Windows analog of 'journalctl -u'. Read-only."
    ),
    parameters={
        "type": "object",
        "properties": {
            "service_name": {
                "type": "string",
                "description": "The Windows service name, e.g. 'Spooler', 'wuauserv'."
            },
            "lines": {
                "type": "integer",
                "description": "How many recent matching events to fetch (default 20, max 100)."
            }
        },
        "required": ["service_name"]
    },
    callback=service_logs
)