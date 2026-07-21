"""
Service Status Tool Module.

Checks a Windows service via PowerShell Get-Service. Read-only.
Note: runs against the Windows host, not a real Linux server — bot's
persona is Linux-focused but there's no Linux target in this setup yet.
"""

import os
import re
import subprocess
from .tool import Tool

# Windows service names: letters, digits, spaces, '_.-' — conservative allowlist.
_VALID_SERVICE_NAME = re.compile(r"^[a-zA-Z0-9 _.-]+$")


def service_status(service_name=None, **kwargs):
    """
    Returns the status of a Windows service (via PowerShell Get-Service).

    Args:
        service_name (str): Windows service name, e.g. "Spooler", "wuauserv".

    Returns:
        str: Formatted status output, or a clear error message.
    """
    if service_name is None:
        service_name = kwargs.get("service_name")

    if not service_name:
        return "I didn't receive a service name. Example: Spooler, wuauserv, W32Time."

    if not _VALID_SERVICE_NAME.match(service_name):
        return f"'{service_name}' has unusual characters for a service name — refusing to run it, to stay safe."

    # pass through env var, not string interpolation, so PowerShell treats it as data not code
    env = os.environ.copy()
    env["SVC_NAME"] = service_name

    command = (
        "Get-Service -Name $env:SVC_NAME -ErrorAction Stop | "
        "Format-List Name, DisplayName, Status, StartType"
    )

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            timeout=15,
            env=env,
        )
        output = (result.stdout or "") + (result.stderr or "")
        if not output.strip():
            output = f"(no output; exit code: {result.returncode})"
        return output[:3000]

    except FileNotFoundError:
        return "The 'powershell' command isn't available on this system."
    except subprocess.TimeoutExpired:
        return f"Checking service '{service_name}' timed out (15s)."
    except Exception as e:
        return f"Error checking service '{service_name}': {e}"


service_status_tool = Tool(
    name="service_status",
    description=(
        "Checks the current status of a WINDOWS service (running, stopped, "
        "startup type) via PowerShell Get-Service, on the machine hosting "
        "this bot. Read-only — does not restart or modify the service."
    ),
    parameters={
        "type": "object",
        "properties": {
            "service_name": {
                "type": "string",
                "description": "The Windows service name, e.g. 'Spooler', 'wuauserv', 'W32Time'."
            }
        },
        "required": ["service_name"]
    },
    callback=service_status
)