"""
Application entry point.

This module provides a simple command-line
interface(CLI) for interacting with the agent.
"""

from agent import Agent
from llm_client import LLMClient
from conversation_context import ConversationContext
from tools.tools import tools
from embedding_generator import EmbeddingGenerator


def main():
    # Initialize the conversation memory context
    context = ConversationContext()

    # Initialize the LLM Client for generating text and executing tools calls
    llm_client = LLMClient()

    # Instantiate the agent with required cognitive components and active tools
    agent = Agent(llm_client, context, tools=tools)

    print("Linux Wizzard started. Type 'exit' to quit.")


    #print(context.assemble_system_prompt())


    # Trigger the local database synchronization phase
    # This ensures that markdown docs are processed and embeddings.json is build/ verified
    generate = EmbeddingGenerator()
    generate.generate_embeddings()

    # Enter the main conversational REPL lool
    while True:
        try:
            user_input = input("\nYou: ")
        except (KeyboardInterrupt, EOFError):
            # Handle CTRL + C or terminal closure
            print("\nHappy to be helpfull!")
            break

        # Check for the exit command
        if user_input.strip().lower() == "exit":
            print("\nHappy to be helpfull!")
            break
        
        # Skip empty inputs 
        if not user_input.strip():
            continue
        
        # Give the message to the agent to triggewr the RAG& Completion Flow  
        response = agent.process_message(user_input)

        # Render the final system quidance in the console
        print(f"\nAI: {response}")


if __name__ == "__main__":
    main()
