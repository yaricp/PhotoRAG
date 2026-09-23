export type ModelCapability = 'chat' | 'vision' | 'clip' | 'ocr' | 'translator' | 'embedding'

type ProviderId =
    | 'openai'
    | 'anthropic'
    | 'google_genai'
    | 'ollama'
    | 'deepl'
    | 'libretranslate'

interface ProviderOption {
    value: ProviderId
    label: string
    capabilities: ModelCapability[]
}

const ALL_CAPABILITIES: ModelCapability[] = ['chat', 'vision', 'clip', 'ocr', 'translator', 'embedding']
const VISION_LLM_CAPABILITIES: ModelCapability[] = ['chat', 'vision', 'clip', 'ocr', 'translator']

export const PACKAGED_PROVIDER_OPTIONS: ProviderOption[] = [
    { value: 'openai', label: 'OpenAI', capabilities: ALL_CAPABILITIES },
    { value: 'anthropic', label: 'Anthropic (Claude)', capabilities: VISION_LLM_CAPABILITIES },
    { value: 'google_genai', label: 'Google Gemini (AI Studio key)', capabilities: ALL_CAPABILITIES },
    { value: 'ollama', label: 'Local via Ollama', capabilities: ALL_CAPABILITIES },
    { value: 'deepl', label: 'DeepL', capabilities: ['translator'] },
    { value: 'libretranslate', label: 'LibreTranslate (self-hosted)', capabilities: ['translator'] },
]

export const MODEL_SUGGESTIONS: Record<string, Partial<Record<ModelCapability, string[]>>> = {
    openai: {
        chat:       ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo'],
        vision:     ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo'],
        ocr:        ['gpt-4o', 'gpt-4o-mini'],
        clip:       ['gpt-4o-mini', 'gpt-4o'],
        translator: ['gpt-4o-mini', 'gpt-4o'],
        embedding:  ['text-embedding-3-small', 'text-embedding-3-large', 'text-embedding-ada-002'],
    },
    anthropic: {
        chat:       ['claude-opus-4-5', 'claude-sonnet-4-5', 'claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022'],
        vision:     ['claude-opus-4-5', 'claude-sonnet-4-5', 'claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022'],
        ocr:        ['claude-3-5-haiku-20241022', 'claude-sonnet-4-5'],
        clip:       ['claude-3-5-haiku-20241022', 'claude-sonnet-4-5'],
        translator: ['claude-3-5-haiku-20241022', 'claude-sonnet-4-5'],
    },
    google_genai: {
        chat:       ['gemini-2.0-flash', 'gemini-2.0-flash-lite', 'gemini-1.5-flash-latest', 'gemini-1.5-pro-latest'],
        vision:     ['gemini-2.0-flash', 'gemini-1.5-flash-latest', 'gemini-1.5-pro-latest'],
        ocr:        ['gemini-2.0-flash', 'gemini-1.5-flash-latest'],
        clip:       ['gemini-2.0-flash', 'gemini-1.5-flash-latest'],
        translator: ['gemini-2.0-flash', 'gemini-1.5-flash-latest'],
        embedding:  ['models/text-embedding-004', 'models/embedding-001'],
    },
    ollama: {
        chat:       ['llama3.2', 'llama3.1', 'mistral', 'gemma3', 'phi4'],
        vision:     ['qwen2.5vl:3b', 'qwen2.5vl:7b', 'llava', 'llava-llama3'],
        ocr:        ['qwen2.5vl:3b', 'qwen2.5vl:7b', 'llava'],
        clip:       ['qwen2.5vl:3b', 'qwen2.5vl:7b', 'llava'],
        translator: ['gemma3:4b', 'llama3.2', 'mistral'],
        embedding:  ['nomic-embed-text', 'mxbai-embed-large'],
    },
}

export function getProviderOptions(modelType: string): ProviderOption[] {
    return PACKAGED_PROVIDER_OPTIONS.filter(provider =>
        provider.capabilities.includes(modelType as ModelCapability)
    )
}

export function getModelSuggestions(provider: string, modelType: string): string[] {
    return MODEL_SUGGESTIONS[provider]?.[modelType as ModelCapability] ?? []
}

export function providerRequiresApiKey(provider: string | undefined): boolean {
    return provider !== 'ollama'
}
