"""
LLM integration layer.
 
This module is responsible for all communication
with the language model.
"""
 
from openai import OpenAI
 
from config import (
    MODEL_NAME,
    AZURE_ENDPOINT,
    API_KEY
)
 
from tools.tool import Tool
 
 
class LLMClient:
 
    def __init__(self):
        self.client = OpenAI(
            base_url=AZURE_ENDPOINT,
            api_key=API_KEY
        )
 
    def _tool_to_dict(self, tool: Tool):
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters
            }
        }
 
    def generate_response(self, messages, tools=None):
 
        kwargs = {
            "model": MODEL_NAME,
            "messages": messages
        }
 
        if tools:
            kwargs["tools"] = [
                self._tool_to_dict(tool)
                for tool in tools
            ]
 
        response = self.client.chat.completions.create(
            **kwargs
        )
 
        message = response.choices[0].message
 
        result = {
            "message": {
                "role": "assistant",
                "content": message.content
            }
        }
 
        if getattr(message, "tool_calls", None):
 
            result["message"]["tool_calls"] = []
 
            for tc in message.tool_calls:
 
                result["message"]["tool_calls"].append({
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                })
 
        return result