"""
Conversation memory management.

This module is responsible for storing and retrieving
messages exchanged between the user and the AI assistant.
"""
from config import INPUT_TOKEN_PRICE_PER_MILLION, OUTPUT_TOKEN_PRICE_PER_MILLION
import json
import os
from utils import count_tokens


class ConversationContext:
    def __init__(self):
        self.total_input_tokens = 0
        self.total_output_tokens = 0


        system_message = self.assemble_system_prompt()


        sys_input = count_tokens(system_message["content"])
        system_message["input_tokens"] = sys_input
        system_message["output_tokens"] = 0


        self.total_input_tokens += sys_input
        self.messages = [system_message]


    def assemble_system_prompt(self):
        with open(
            "knowledge/prompts/identity.md", "r", encoding="utf-8"
        ) as f:
            prompt_content = f.read()
    

        # adaugam company facts in prompt content
        company_facts = json.load(open("knowledge/facts/registry.json", "r", encoding="utf-8"))
        for document in company_facts:
            if document["always_load"]:
                with open(f"knowledge/facts/{document['id']}.md", "r", encoding="utf-8") as f:
                    facts_content = f.read()
                    prompt_content += f"\n\n#{document['name']}\n"
                    prompt_content += "\n\n" + facts_content


        # adaugam procedures in prompt content
        procedures = json.load(open("knowledge/procedures/registry.json", "r", encoding="utf-8"))
        for document in procedures:
            if document["always_load"]:
                with open(f"knowledge/procedures/{document['id']}.md", "r", encoding="utf-8") as f:
                    procedures_content = f.read()
                    prompt_content += f"\n\n#{document['name']}\n"
                    prompt_content += "\n\n" + procedures_content


        return {
            "role": "system",
            "content": prompt_content
        }
    

    def add_message(self, message:dict, input_tokens:int = 0,output_tokens:int=0):
        msg_to_store = message.copy()

        msg_to_store["input_tokens"] = msg_to_store.get("input_tokens",input_tokens)
        msg_to_store["output_tokens"] = msg_to_store.get("output_tokens",output_tokens)

        self.total_input_tokens += msg_to_store["input_tokens"]
        self.total_output_tokens += msg_to_store["output_tokens"]
        
        self.messages.append(msg_to_store)

    def get_history(self):
        return self.messages
    
    def get_total_tokens_consumed(self):
        """Returnează stadiul curent al consumului total din sesiune."""
        return {
            "total_input": self.total_input_tokens,
            "total_output": self.total_output_tokens,
            "total_cost": self.total_input_tokens/1_000_000*INPUT_TOKEN_PRICE_PER_MILLION + self.total_output_tokens/1_000_000*OUTPUT_TOKEN_PRICE_PER_MILLION
        }
    