"""
Conversation memory management.

This module is responsible for storing and retrieving
messages exchanged between the user and the AI assistant.
"""
#from config import SYSTEM_PROMPT
import json
import os

DIRNAME = os.getcwd()

class ConversationContext:
    def __init__(self):
        self.messages = [
            self.assemble_system_prompt()
        ]

    def assemble_system_prompt(self):
        # knowlegde_dir = os.path.join(DIRNAME,"knowledge")
        # prompts_dir = os.path.join(knowlegde_dir,"prompts")
        # facts_dir = os.path.join(knowlegde_dir,"facts")
        # procedures_dir = os.path.join(knowlegde_dir,"procedures")

        # files = []
        # for file in os.listdir(prompts_dir):
        #     files.append(os.path.join(prompts_dir,file))
        # with open(f'{facts_dir}\\registry.json','r') as f:
        #     facts_registry = json.load(f)
        # with open(f'{procedures_dir}\\registry.json','r') as f:
        #     procedures_registry = json.load(f)

        # for object in facts_registry:
        #     if object["always_load"]:
        #         files.append(os.path.join(facts_registry, f'{object["id"]}.md'))                               
        # for object in procedures_registry:
        #     if object["always_load"]:
        #         files.append(os.path.join(procedures_registry, f'{object["id"]}.md'))

        # documentation_arr =[]        
        # for doc_files in files:
        #     with open(doc_files) as f:
        #         documentation_arr.append(f.read())
        # documentation = "\n\n###\n\n".join(documentation_arr)
        # print(documentation)
        with open(
            "knowledge/prompts/identity.md", "r", encoding="utf-8"
        ) as f:
            prompt_content = f.read()
        # print("SYSTEM PROMPT:", prompt_content)

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
    

    def add_message(self, message):
        self.messages.append(message)

    def get_history(self):
        return self.messages
