"""
Tools Registry Module.

This module aggregates and exports all the active tools available to the Agent.
To equip the Wizzard of OS with new magical capabilities, import them here
and append them to the 'tools' list.
"""
from .tool import Tool
from .lucky_number_tool import lucky_number_tool
from .service_status_tool import service_status_tool
from .service_logs_tool import service_logs_tool
from .disk_usage_tool import disk_usage_tool

tools: list[Tool] = [
    lucky_number_tool,
    service_logs_tool,
    service_status_tool,
    disk_usage_tool
]
