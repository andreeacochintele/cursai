"""
Disk Usage Tool Module.

Reports disk space usage via PowerShell Get-PSDrive — the Windows analog
of `df -h`. Read-only.
"""

import os
import re
import subprocess
from .tool import Tool

# A single drive letter, e.g. "C" or "C:" — deliberately narrow allowlist.
_VALID_DRIVE = re.compile(r"^[a-zA-Z]:?$")


def disk_usage(path=None, drive=None, **kwargs):
    """
    Returns disk usage for all local drives, or a single drive if specified.

    Args:
        path / drive (str, optional): A drive letter, e.g. "C" or "C:".
            If omitted, shows usage for all local filesystem drives.

    Returns:
        str: Formatted output, or a clear error message.
    """
    # Accept either "path" or "drive" as the parameter name for convenience.
    drive_letter = drive if drive is not None else path
    if drive_letter is None:
        drive_letter = kwargs.get("drive") or kwargs.get("path")

    env = os.environ.copy()

    if drive_letter:
        drive_letter = str(drive_letter).strip().rstrip(":")
        if not _VALID_DRIVE.match(drive_letter):
            return f"'{drive_letter}' doesn't look like a valid drive letter — refusing to run it, to stay safe."
        env["DRIVE_LETTER"] = drive_letter
        command = (
            "Get-PSDrive -Name $env:DRIVE_LETTER -PSProvider FileSystem -ErrorAction Stop | "
            "Select-Object Name, "
            "@{N='UsedGB';E={[math]::Round($_.Used/1GB,2)}}, "
            "@{N='FreeGB';E={[math]::Round($_.Free/1GB,2)}} | "
            "Format-Table -AutoSize"
        )
    else:
        command = (
            "Get-PSDrive -PSProvider FileSystem | "
            "Select-Object Name, "
            "@{N='UsedGB';E={[math]::Round($_.Used/1GB,2)}}, "
            "@{N='FreeGB';E={[math]::Round($_.Free/1GB,2)}} | "
            "Format-Table -AutoSize"
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
        return output[:2000]

    except FileNotFoundError:
        return "The 'powershell' command isn't available on this system."
    except subprocess.TimeoutExpired:
        return "Checking disk usage timed out (15s)."
    except Exception as e:
        return f"Error checking disk usage: {e}"


disk_usage_tool = Tool(
    name="disk_usage",
    description=(
        "Checks disk space usage (used/free GB) on the WINDOWS machine "
        "hosting this bot, via PowerShell Get-PSDrive — the Windows analog "
        "of 'df -h'. Optionally scoped to one drive letter. Read-only."
    ),
    parameters={
        "type": "object",
        "properties": {
            "drive": {
                "type": "string",
                "description": "Optional drive letter to check, e.g. 'C'. Omit to see all local drives."
            }
        },
        "required": []
    },
    callback=disk_usage
)