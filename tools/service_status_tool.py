"""
Service Status Tool Module.

Runs `systemctl status <service>` locally (subprocess) and returns the raw
output so the LLM can interpret whether the service is active, failed, etc.
Read-only: never restarts, stops, or starts anything.
"""

import re
import subprocess
from .tool import Tool

# Systemd unit names: letters, digits, ':-_.\@' — keep it conservative.
_VALID_SERVICE_NAME = re.compile(r"^[a-zA-Z0-9_.@-]+$")


def service_status(service_name=None, **kwargs):
    """
    Returns the output of `systemctl status <service_name>`.

    Args:
        service_name (str): Name of the systemd service (e.g. "nginx", "sshd").

    Returns:
        str: Raw command output (stdout+stderr), or a clear error message.
    """
    if service_name is None:
        service_name = kwargs.get("service_name")

    if not service_name:
        return "Nu am primit numele serviciului. Ex: nginx, sshd, docker."

    if not _VALID_SERVICE_NAME.match(service_name):
        return (
            f"Numele de serviciu '{service_name}' conține caractere neobișnuite "
            "pentru un unit systemd — refuz să-l trimit ca să evit orice risc."
        )

    try:
        result = subprocess.run(
            ["systemctl", "status", service_name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = (result.stdout or "") + (result.stderr or "")
        if not output.strip():
            output = f"(fără output; cod de ieșire: {result.returncode})"
        # Keep it bounded so we don't blow the LLM's context window.
        return output[:3000]

    except FileNotFoundError:
        return (
            "Comanda 'systemctl' nu există pe acest sistem. Probabil botul "
            "rulează local pe Windows/macOS, nu pe serverul Linux țintă — "
            "acest tool trebuie rulat pe (sau conectat la) mașina Linux reală."
        )
    except subprocess.TimeoutExpired:
        return f"Comanda 'systemctl status {service_name}' a depășit timpul limită (10s)."
    except Exception as e:
        return f"Eroare la verificarea serviciului '{service_name}': {e}"


service_status_tool = Tool(
    name="service_status",
    description=(
        "Checks the current status of a Linux systemd service (active, "
        "inactive, failed) by running 'systemctl status'. Read-only — does "
        "not restart or modify the service."
    ),
    parameters={
        "type": "object",
        "properties": {
            "service_name": {
                "type": "string",
                "description": "The systemd service name, e.g. 'nginx', 'sshd', 'docker'."
            }
        },
        "required": ["service_name"]
    },
    callback=service_status
)