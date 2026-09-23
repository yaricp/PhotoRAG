"""Supported model provider matrix for packaged PhotoRAG installs."""

PACKAGED_PROVIDER_REQUIREMENTS = {
    "openai": "langchain-openai",
    "anthropic": "langchain-anthropic",
    "google_genai": "langchain-google-genai",
    "ollama": "langchain-ollama",
    "deepl": "requests",
    "libretranslate": "requests",
}

PACKAGED_PROVIDER_CAPABILITIES = {
    "openai": {"chat", "vision", "clip", "ocr", "translator", "embedding"},
    "anthropic": {"chat", "vision", "clip", "ocr", "translator"},
    "google_genai": {"chat", "vision", "clip", "ocr", "translator", "embedding"},
    "ollama": {"chat", "vision", "clip", "ocr", "translator", "embedding"},
    "deepl": {"translator"},
    "libretranslate": {"translator"},
}


def unsupported_provider_message(model_type: str, provider: str) -> str | None:
    capabilities = PACKAGED_PROVIDER_CAPABILITIES.get(provider)
    if capabilities is None:
        return (
            f"Provider '{provider}' is not supported by this packaged build. "
            "Choose a listed provider or install a build that includes this provider."
        )
    if model_type not in capabilities:
        return f"Provider '{provider}' does not support model type '{model_type}' in this packaged build."
    return None
