import os

from langchain_core.language_models import BaseChatModel

from docspatch.utils.config import load


def get_llm(model_key: str = "model") -> BaseChatModel:
    """Return configured LangChain chat model. Tries Google → OpenAI → Anthropic."""
    config = load()
    model_name: str = config.get("defaults", {}).get(model_key, "gemini-2.0-flash")
    keys: dict = config.get("keys", {})

    if google_key := keys.get("google_api_key"):
        os.environ["GOOGLE_API_KEY"] = google_key
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(model=model_name)

    if openai_key := keys.get("openai_api_key"):
        os.environ["OPENAI_API_KEY"] = openai_key
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=model_name)

    if anthropic_key := keys.get("anthropic_api_key"):
        os.environ["ANTHROPIC_API_KEY"] = anthropic_key
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=model_name)  # type: ignore[call-arg]

    raise RuntimeError(
        "No API key configured.\n"
        "Add google_api_key, openai_api_key, or anthropic_api_key to ~/.docspatch/config.toml"
    )
