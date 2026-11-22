import time
import requests
from llms.Llm import Llm


class LlmOllama(Llm):
    def __init__(self, config):
        self.__config = config
        self.__model_id = self.__config.llm_id

        if not hasattr(self.__config, "seed"):
            setattr(self.__config, "seed", 99)

        if not hasattr(self.__config, "llm_id_coder"):
            setattr(self.__config, "llm_id_coder", self.__model_id)

        if not hasattr(self.__config, "temperature"):
            setattr(self.__config, "temperature", 0.7)

        # Default local Ollama server address
        if not hasattr(self.__config, "server_address"):
            setattr(self.__config, "server_address", "http://127.0.0.1:11434/api")

        self.base_url = self.__config.server_address
        self.generate_url = f"{self.base_url}/generate"
        self.chat_url = f"{self.base_url}/chat"

        self.__context = []

        self.unload_model()
        self.setup_model()

    def set_model_id(self, model_id):
        self.__model_id = model_id

    def setup_model(self):
        payload = {"model": self.__model_id}
        response = requests.post(self.generate_url, json=payload)
        if response.status_code == 200:
            print(f"######### Model {self.__model_id} successfully loaded in the ollama server.")
        else:
            print(f"Error: {response.status_code}, {response.text}")

    def unload_model(self):
        payload = {"model": self.__model_id, "keep_alive": 0}
        response = requests.post(self.generate_url, json=payload)
        if response.status_code == 200:
            print(f"######### Model {self.__model_id} successfully unloaded in the ollama server.")
        else:
            print(f"Error: {response.status_code}, {response.text}")

    def get_context(self):
        return self.__context

    def clear_context(self):
        self.__context = []

    def set_instruction(self, instruction):
        if instruction != "":
            self.__context.append({"role": "system", "content": instruction})

    def send_prompt_context(self, prompt):
        self.__context.append({"role": "user", "content": prompt})

        payload = {
            "model": self.__model_id,
            "messages": self.__context,
            "stream": False
        }

        response = requests.post(self.chat_url, json=payload)

        if response.status_code == 200:
            response_data = response.json()
            output = response_data.get("message", {}).get("content", "")
            if not output:
                output = response_data.get("response", "")
            self.__context.append({"role": "assistant", "content": output})
        else:
            print(f"Error: {response.status_code}, {response.text}")

        return output

    def get_last_response(self):
        return self.__context[-1]["content"]

    def send_single_prompt(self, prompt, coder=False):
        payload = {
            "model": self.__model_id if not coder else self.__config.llm_id_coder,
            "prompt": prompt,
            "options": {
                "seed": self.__config.seed,
                "temperature": self.__config.temperature
            },
            "stream": False
        }

        if "qwen2.5" in self.__model_id:
            payload["stop"] = "<|endoftext|>"

        for i in range(10):
            for j in range(10):
                try:
                    response = requests.post(self.generate_url, json=payload)
                    break
                except Exception as e:
                    print(
                        f"########################## Error when sending prompt request to Ollama server: \n {str(e)}\n Prompt:\n {prompt} \nTrying again in 5 seconds... trial #{j+1}"
                    )
                    time.sleep(5)

            if response.status_code == 200:
                response_data = response.json()
                output = response_data.get("response")
                break
            else:
                print(f"Error: \n{response.status_code}, {response.text}")
                print(f"########################## Trying again in 6 seconds... trial #{i+1}")
                time.sleep(6)
        return output
