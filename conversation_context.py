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
    """
    Manages the conversation history, dynamically builds the system
    and keeps track of cumulative token consumption across the session.
    """


    def __init__(self):
        # Global token counters
        self.total_input_tokens = 0
        self.total_output_tokens = 0

        # Construct the inistial dynamic system prompt - Identity + Always-loaded procedures and facts
        system_message = self.assemble_system_prompt()

        # Calculate tokens for the initial system message and update global counters
        sys_input = count_tokens(system_message["content"])
        system_message["input_tokens"] = sys_input
        system_message["output_tokens"] = 0


        self.total_input_tokens += sys_input
        self.messages = [system_message]


    def assemble_system_prompt(self):
        """
        Loads the core identity file and appends any documents from
        the registry that have always_load
        """

        # Load the primary identity file
        with open(
            "knowledge/prompts/identity.md", "r", encoding="utf-8"
        ) as f:
            prompt_content = f.read()
    

        # Dynamically append essential company facts
        try: 
            company_facts = json.load(open("knowledge/facts/registry.json", "r", encoding="utf-8"))
            for document in company_facts:
                if document["always_load"]:
                    with open(f"knowledge/facts/{document['id']}.md", "r", encoding="utf-8") as f:
                        facts_content = f.read()
                        prompt_content += f"\n\n#{document['name']}\n"
                        prompt_content += "\n\n" + facts_content
        except FileNotFoundError:
            pass

        # Dinamically append essential procedures
        try:
            procedures = json.load(open("knowledge/procedures/registry.json", "r", encoding="utf-8"))
            for document in procedures:
                if document["always_load"]:
                    with open(f"knowledge/procedures/{document['id']}.md", "r", encoding="utf-8") as f:
                        procedures_content = f.read()
                        prompt_content += f"\n\n#{document['name']}\n"
                        prompt_content += "\n\n" + procedures_content
        except FileNotFoundError:
            pass

        return {
            "role": "system",
            "content": prompt_content
        }
    

    def add_message(self, message:dict, input_tokens:int = 0,output_tokens:int=0):
        """
        Appends a message to the memory stack and updates the global session counters
        """
        
        msg_to_store = message.copy()
        # Assign token values
        msg_to_store["input_tokens"] = msg_to_store.get("input_tokens",input_tokens)
        msg_to_store["output_tokens"] = msg_to_store.get("output_tokens",output_tokens)

        # Increment overall session counters
        self.total_input_tokens += msg_to_store["input_tokens"]
        self.total_output_tokens += msg_to_store["output_tokens"]
        
        self.messages.append(msg_to_store)

    def get_history(self):
        """
        Returnd the chronological list of messages.
        """
        return self.messages
    
    def get_total_tokens_consumed(self):
        """
        Return the total token stats
        """

        price_per_token_in = INPUT_TOKEN_PRICE_PER_MILLION/1_000_000
        price_per_token_out = OUTPUT_TOKEN_PRICE_PER_MILLION/1_000_000

        cost = (self.total_input_tokens*price_per_token_in) + (self.total_output_tokens*price_per_token_out)
        return {
            "total_input": self.total_input_tokens,
            "total_output": self.total_output_tokens,
            "grand_total": self.total_input_tokens + self.total_output_tokens,
            "total_cost": f"${cost:.6f}" # 6 decimals
        }
    