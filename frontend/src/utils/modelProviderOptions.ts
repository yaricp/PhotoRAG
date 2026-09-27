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
        chat:       ['qwen3-vl:2b-instruct', 'gemma3:4b', 'gemma3:12b'],
        vision:     ['qwen3-vl:2b-instruct', 'qwen3-vl:4b-instruct', 'qwen3-vl:8b-instruct', 'qwen2.5vl:3b'],
        ocr:        ['qwen3-vl:2b-instruct', 'qwen3-vl:4b-instruct', 'qwen3-vl:8b-instruct', 'qwen2.5vl:3b'],
        clip:       ['qwen3-vl:2b-instruct', 'qwen3-vl:4b-instruct', 'qwen3-vl:8b-instruct', 'qwen2.5vl:3b'],
        translator: ['qwen3-vl:2b-instruct', 'gemma3:4b', 'gemma3:12b'],
        embedding:  ['nomic-embed-text', 'mxbai-embed-large'],
    },
}

export const LOCAL_MODEL_NAMES: Record<ModelCapability, string> = {
    vision: 'Qwen/Qwen2-VL-2B-Instruct',
    clip: 'ViT-B-32',
    ocr: 'easyocr',
    embedding: 'nomic-ai/nomic-embed-text-v1.5',
    translator: 'facebook/nllb-200-distilled-600M',
    chat: 'Qwen/Qwen2.5-Coder-3B-Instruct',
}

export function changeProcessingMode<T extends { type: string; mode: 'local' | 'remote'; model_name: string; model_provider?: string; url?: string; api_key?: string }>(config: T, choice: string): T {
    if (choice === 'ollama') return {
        ...config, mode: 'remote', model_provider: 'ollama',
        model_name: '',
        url: 'http://localhost:11434', api_key: '',
    }
    if (choice === 'local') return {
        ...config, mode: 'local', model_provider: undefined,
        model_name: LOCAL_MODEL_NAMES[config.type as ModelCapability] ?? config.model_name,
        url: '', api_key: '',
    }
    return {
        ...config, mode: 'remote', model_provider: 'openai',
        model_name: getModelSuggestions('openai', config.type)[0] ?? '', url: '', api_key: '',
    }
}

export function changeProvider<T extends { type: string; model_name: string; model_provider?: string; url?: string; api_key?: string }>(config: T, provider: string): T {
    return {
        ...config,
        model_provider: provider || undefined,
        model_name: provider === 'ollama' ? '' : getModelSuggestions(provider, config.type)[0] ?? '',
        url: provider === 'ollama' ? 'http://localhost:11434' : '',
        api_key: '',
    }
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

export function isLocalOllamaUrl(value?: string | null): boolean {
    try {
        const url = new URL(value?.trim() || 'http://localhost:11434')
        return url.protocol === 'http:' && ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)
    } catch {
        return false
    }
}
