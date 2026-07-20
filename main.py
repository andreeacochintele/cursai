"""
Application entry point.

This module provides a simple command-line
interface(CLI) for interacting with the agent.
"""

import asyncio
from datetime import datetime

from logging_config import setup_logging
from agent import Agent
from llm_client import LLMClient
from conversation_context import ConversationContext
from tools.tools import tools
from embedding_generator import EmbeddingGenerator


def choose_session(context: ConversationContext) -> str:
    """
    Lets the user resume a previous conversation or start a new one.
    Returns the session_id that should be used for autosaving.
    """
    existing = ConversationContext.list_sessions()
    if existing:
        print("\nSesiuni salvate găsite:")
        for i, sid in enumerate(existing, 1):
            print(f"  {i}. {sid}")
        choice = input(
            "Introdu numărul unei sesiuni ca s-o continui, "
            "sau apasă Enter pentru o sesiune nouă: "
        ).strip()
        if choice.isdigit() and 1 <= int(choice) <= len(existing):
            session_id = existing[int(choice) - 1]
            if context.load_session(session_id):
                print(f"[Sesiune '{session_id}' încărcată — istoricul a fost restaurat.]")
                return session_id

    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"[Sesiune nouă: '{session_id}']")
    return session_id


def print_help():
    print(
        "\nComenzi disponibile:\n"
        "  exit              - închide programul (salvează automat)\n"
        "  /save             - salvează sesiunea curentă acum\n"
        "  /sessions         - listează sesiunile salvate\n"
        "  /export <fisier>  - exportă conversația într-un fișier .md lizibil\n"
        "  /history          - afișează pe scurt ultimele mesaje\n"
        "  /help             - afișează acest mesaj\n"
    )


async def main():
    setup_logging()

    # Initialize the LLM Client for generating text, executing tool calls,
    # and generating context summaries
    llm_client = LLMClient()

    # Initialize the conversation memory context, giving it the LLM client
    # so it can summarize older turns instead of just discarding them
    context = ConversationContext(llm_client=llm_client)

    # Instantiate the agent with required cognitive components and active tools
    agent = Agent(llm_client, context, tools=tools)

    print("Linux Wizzard started. Type 'exit' to quit, '/help' for commands.")

    # Trigger the local database synchronization phase
    # This ensures that markdown docs are processed and embeddings.json is build/ verified
    generate = EmbeddingGenerator()
    await generate.generate_embeddings()

    # Let the user resume a previous conversation or start fresh
    session_id = choose_session(context)

    # Enter the main conversational REPL loop
    while True:
        try:
            user_input = input("\nYou: ")
        except (KeyboardInterrupt, EOFError):
            # Handle CTRL + C or terminal closure
            context.save_session(session_id)
            print(f"\n[Sesiune salvată ca '{session_id}']")
            print("\nHappy to be helpfull!")
            break

        stripped = user_input.strip()

        # Check for the exit command
        if stripped.lower() == "exit":
            context.save_session(session_id)
            print(f"[Sesiune salvată ca '{session_id}']")
            print("\nHappy to be helpfull!")
            break

        # Skip empty inputs
        if not stripped:
            continue

        # --- Slash commands ---
        if stripped == "/help":
            print_help()
            continue

        if stripped == "/save":
            path = context.save_session(session_id)
            print(f"[Salvat în {path}]")
            continue

        if stripped == "/sessions":
            sessions = ConversationContext.list_sessions()
            if not sessions:
                print("[Nicio sesiune salvată încă]")
            else:
                print("[Sesiuni salvate]: " + ", ".join(sessions))
            continue

        if stripped.startswith("/export"):
            parts = stripped.split(maxsplit=1)
            filepath = parts[1] if len(parts) > 1 else f"{session_id}_export.md"
            path = context.export_history(filepath)
            print(f"[Conversație exportată în {path}]")
            continue

        if stripped == "/history":
            for msg in context.get_history():
                role = msg.get("role")
                if role not in ("user", "assistant"):
                    continue
                content = (msg.get("content") or "")[:120]
                print(f"  [{role}] {content}")
            continue

        # Give the message to the agent to trigger the RAG & Completion Flow
        response = await agent.process_message(user_input)

        # Render the final system guidance in the console
        print(f"\nAI: {response}")

        # Autosave after every turn so nothing is lost on a crash
        context.save_session(session_id)


if __name__ == "__main__":
    asyncio.run(main())