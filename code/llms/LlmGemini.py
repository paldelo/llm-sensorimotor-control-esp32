import os
import time
import requests
from llms.Llm import Llm


class LlmGemini(Llm):
    """
    Connector for the Google Gemini REST API using the standard Llm interface.
    """

    def __init__(self, config):
        super().__init__(config)
        self.api_key = getattr(config, "gemini_api_key", "") or os.getenv("GEMINI_API_KEY", "")

        llm_id_config = getattr(config, "llm_id", ["gemini-1.5-flash"])
        self.model_name = llm_id_config[0] if isinstance(llm_id_config, list) else llm_id_config

        temp_config = getattr(config, "temperature", [0.7])
        self.temperature = float(temp_config[0] if isinstance(temp_config, list) else temp_config)

        self.system_instruction = "You are the sensorimotor controller of a differential-drive line-following robot."
        self.last_response = ""
        self.history = []

    def setup_model(self):
        pass

    def set_instruction(self, instruction):
        if instruction and instruction.strip() != "":
            self.system_instruction = instruction
        self.history = []

    def send_single_prompt(self, prompt, coder=False):
        return self._call_api(prompt, use_history=False)

    def send_prompt_context(self, prompt):
        return self._call_api(prompt, use_history=True)

    def _call_api(self, prompt, use_history=False):
        # Rate-limit delay between API requests
        time.sleep(15)

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}

        contents = []
        if use_history:
            contents.extend(self.history)

        contents.append({"role": "user", "parts": [{"text": prompt}]})

        data = {
            "systemInstruction": {"parts": [{"text": self.system_instruction}]},
            "contents": contents,
            "generationConfig": {"temperature": self.temperature},
        }

        attempts = 1
        max_attempts = 5
        while attempts <= max_attempts:
            try:
                response = requests.post(url, headers=headers, json=data, timeout=30)
                resp_json = response.json()

                if response.status_code == 200:
                    text_response = resp_json["candidates"][0]["content"]["parts"][0]["text"]
                    self.last_response = text_response

                    if use_history:
                        self.history.append({"role": "user", "parts": [{"text": prompt}]})
                        self.history.append({"role": "model", "parts": [{"text": text_response}]})

                    return text_response
                elif response.status_code == 429:
                    print("\n[LLM Warning] Quota exceeded (HTTP 429). Waiting 60 seconds...")
                    time.sleep(60)
                    attempts += 1
                else:
                    print(f"\n[LLM Warning] API error response: {resp_json}. Waiting 15 seconds...")
                    time.sleep(15)
                    attempts += 1
            except Exception as e:
                print(f"\n[LLM Warning] Connection error: {e}. Waiting 15 seconds...")
                time.sleep(15)
                attempts += 1

        return "Communication error."

    def get_last_response(self):
        return self.last_response
