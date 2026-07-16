"""Core agent orchestration.
The agent coordinates communication between
the conversation context and the language model."""
from embeddings_client import EmbeddingsClient
from utils import count_tokens

class Agent:
    def __init__(self, llm_client, context, tools=None):
        self.llm_client = llm_client
        self.context = context
        self.tools = {tool.name: tool for tool in tools} if tools else {}

    def _handle_tool_calls(self, tool_calls):
        results = []
        for tc in tool_calls:
            tool_name = tc["function"]["name"]
            arguments = tc["function"]["arguments"]
            tool_id = tc["id"]

            tool = self.tools.get(tool_name)
            if tool:
                result = tool.callback(**arguments)
            else:
                result = f"Tool '{tool_name}' not found"

            results.append({
                "role": "tool",
                "tool_call_id": tool_id,
                "content": str(result)
            })
        return results

    def _get_retrieved_context(self, user_message: str) -> str:
        """Caută în baza de date de vectori și returnează contextul sub formă de text."""
        client = EmbeddingsClient()
        results = client.semantic_search(user_message)

        retrieved_context = "# Retrieved Context \n"
        for result in results:
            retrieved_context += result["content"] + "\n\n"
        return retrieved_context

    def _track_llm_usage(self, response) -> tuple[int, int]:
        """Extrage în siguranță tokenii consumați din obiectul sau dicționarul de răspuns."""
        prompt = 0
        completion = 0
        
        if hasattr(response, "usage") and response.usage:
            prompt = response.usage.prompt_tokens
            completion = response.usage.completion_tokens
        elif isinstance(response, dict) and "usage" in response:
            prompt = response["usage"].get("prompt_tokens", 0)
            completion = response["usage"].get("completion_tokens", 0)
            
        return prompt, completion

    def _execute_tool_workflow(self, initial_message) -> tuple[dict, int, int]:
        """Rulează uneltele detectate și cere LLM-ului răspunsul final bazat pe rezultatele lor."""
        total_prompt = 0
        total_completion = 0
        
        # Adăugăm intenția inițială de a rula unelte în istoric
        self.context.add_message(initial_message)

        # Rulăm uneltele și salvăm rezultatele în istoric
        tool_results = self._handle_tool_calls(initial_message["tool_calls"])
        for result in tool_results:
            self.context.add_message(result)
        
        # Facem al doilea apel către LLM cu datele din unelte
        second_response = self.llm_client.generate_response(
            self.context.get_history()
        )
        
        # Adunăm consumul celui de-al doilea apel
        p, c = self._track_llm_usage(second_response)
        total_prompt += p
        total_completion += c
        
        return second_response["message"], total_prompt, total_completion

    def process_message(self, user_message: str) -> str:
        """Funcția principală care coordonează fluxul conversației."""
        # 1. Înregistrăm întrebarea utilizatorului
        self.context.add_message({"role": "user", "content": user_message})

        # 2. Obținem și adăugăm contextul RAG
        context_text = self._get_retrieved_context(user_message)
        self.context.add_message({"role": "system", "content": context_text})

        # Afișăm consumul utilizatorului (input + contextul adus)
        total_input_tokens = count_tokens(user_message) + count_tokens(context_text)
        print(f" [Consum Utilizator (Input + Context): {total_input_tokens} tokeni]")

        # 3. Primul apel LLM (poate returna text simplu sau cerere de unelte)
        response = self.llm_client.generate_response(
            self.context.get_history(),
            tools=list(self.tools.values())
        )

        # Monitorizăm consumul primului apel
        p_tokens, c_tokens = self._track_llm_usage(response)
        total_prompt = p_tokens
        total_completion = c_tokens

        message = response["message"]

        # 4. Verificăm dacă modelul vrea să apeleze unelte (Tools)
        if message.get("tool_calls"):
            message, tool_p, tool_c = self._execute_tool_workflow(message)
            total_prompt += tool_p
            total_completion += tool_c

        # 5. Salvăm răspunsul final în istoric
        self.context.add_message(message)

        # Fallback local de urgență dacă API-ul nu a returnat deloc consumul
        if total_prompt == 0:
            total_prompt = total_input_tokens
            total_completion = count_tokens(message.get("content", ""))

        # Afișăm consumul total acumulat
        self.context.add_message(
        message, 
        input_tokens=total_prompt, 
        output_tokens=total_completion
    )

    #  Obținem statisticile cumulative din istoric
        session_stats = self.context.get_total_tokens_consumed()

        print(f" [Mesaj curent - Prompt: {total_prompt} | Răspuns: {total_completion} tokeni]")
        print(f" [TOTAL CONVERSAȚIE - Input: {session_stats['total_input']} tokeni | Output: {session_stats['total_output']} tokeni | Cost: {session_stats['total_cost']}]")
        print("-" * 60)
        return message.get("content", "")
