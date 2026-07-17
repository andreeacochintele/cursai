"""
Base Tool definition module.

This module defines the skeleton for all external tools (functions)
that the Agent can dynamically call to interact with the outside world.
"""

class Tool:
    """
    Represents a custom function wrapper that can be declared to the LLM.
    
    Attributes:
        name (str): The unique identifier of the tool (must match the LLM function name).
        description (str): Explains to the LLM when and why this tool should be used.
        parameters (dict): The JSON schema defining required inputs for the callback.
        callback : The actual Python function executed when the tool is called.
    """
    def __init__(
        self,
        name,
        description,
        parameters,
        callback
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.callback = callback
