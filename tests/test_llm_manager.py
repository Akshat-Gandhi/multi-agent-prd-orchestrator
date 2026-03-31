from prd_planner.models.provider import DeterministicAdapter, LLMManager, OpenAIAdapter, OllamaAdapter


def test_llm_manager_defaults_to_ollama():
    manager = LLMManager(provider="ollama")
    adapter = manager.adapter_for(role="planner")
    assert isinstance(adapter, OllamaAdapter)


def test_llm_manager_can_switch_to_openai():
    manager = LLMManager(provider="openai", openai_api_key="test-key")
    adapter = manager.adapter_for(role="planner")
    assert isinstance(adapter, OpenAIAdapter)


def test_llm_manager_uses_deterministic_for_unknown_provider():
    manager = LLMManager(provider="something_else")
    adapter = manager.adapter_for(role="planner")
    assert isinstance(adapter, DeterministicAdapter)
