class LlmModelFactory:
    model = {}

    @staticmethod
    def get_llm_model(config):
        """
        Factory method to return an instance of the appropriate LLM connector
        based on the llm_type field defined in config.json.
        """
        llm_type = config.llm_type
        llm_id = config.llm_id

        print(f"Model {llm_id} was not instantiated yet. Creating a new instance.")
        if llm_type == "ollama":
            from llms.LlmOllama import LlmOllama
            LlmModelFactory.model[llm_id] = LlmOllama(config)
        elif llm_type == "gemini":
            from llms.LlmGemini import LlmGemini
            LlmModelFactory.model[llm_id] = LlmGemini(config)
        else:
            raise ValueError(f"LLM model type '{config.llm_type}' is not recognized.")

        return LlmModelFactory.model[llm_id]
