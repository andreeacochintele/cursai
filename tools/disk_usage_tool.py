"""
Disk Usage Tool Module.

Runs `df -h [path]` locally (subprocess) and returns the raw output.
Read-only — useful for spotting full disks that cause services to crash.
"""

import re
import subprocess
from .tool import Tool

# Loose but safe: allow typical POSIX path characters only.
_VALID_PATH = re.compile(r"^[a-zA-Z0-9_./-]+$")


def disk_usage(path=None, **kwargs):
    """
    Returns `df -h` output, optionally scoped to a specific mount/path.

    Args:
        path (str, optional): Path or mount point to check (e.g. "/var").
            If omitted, shows usage for all mounted filesystems.

    Returns:
        str: Raw command output, or a clear error message.
    """
    if path is None:
        path = kwargs.get("path")

    command = ["df", "-h"]
    if path:
        if not _VALID_PATH.match(path):
            return f"Calea '{path}' conține caractere neobișnuite — refuz să o trimit."
        command.append(path)

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = (result.stdout or "") + (result.stderr or "")
        if not output.strip():
            output = f"(fără output; cod de ieșire: {result.returncode})"
        return output[:2000]

    except FileNotFoundError:
        return (
            "Comanda 'df' nu există pe acest sistem. Probabil botul rulează "
            "local pe Windows, nu pe serverul Linux țintă — acest tool "
            "trebuie rulat pe (sau conectat la) mașina Linux reală."
        )
    except subprocess.TimeoutExpired:
        return "Comanda 'df -h' a depășit timpul limită (10s)."
    except Exception as e:
        return f"Eroare la verificarea spațiului pe disc: {e}"


disk_usage_tool = Tool(
    name="disk_usage",
    description=(
        "Checks disk space usage on the Linux server (like 'df -h'). "
        "Optionally scoped to a specific path or mount point. Read-only."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Optional path or mount point to check, e.g. '/var'. Omit to see all filesystems."
            }
        },
        "required": []
    },
    callback=disk_usage
)