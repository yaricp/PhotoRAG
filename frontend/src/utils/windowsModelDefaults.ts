interface ModelConfigLike {
    type: string
    mode: 'local' | 'remote'
    model_name: string
    url?: string | null
    model_provider?: string | null
}

const WINDOWS_OPENAI_DEFAULT_MODELS: Record<string, string> = {
    vision: 'gpt-4o-mini',
    clip: 'gpt-4o-mini',
    ocr: 'gpt-4o-mini',
    translator: 'gpt-4o-mini',
    chat: 'gpt-4o-mini',
    embedding: 'text-embedding-3-small',
}

export function isWindowsAppPlatform(): boolean {
    return typeof window !== 'undefined' && window.electronAPI?.platform === 'win32'
}

export function applyWindowsRemoteModelDefaults<T extends ModelConfigLike>(configs: T[]): T[] {
    return configs.map(config => {
        const defaultModel = WINDOWS_OPENAI_DEFAULT_MODELS[config.type] ?? 'gpt-4o-mini'
        const shouldUseOpenAIDefaults = config.mode === 'local' || !config.model_provider || !config.model_name
        return {
            ...config,
            mode: 'remote',
            model_provider: shouldUseOpenAIDefaults ? 'openai' : config.model_provider,
            model_name: shouldUseOpenAIDefaults ? defaultModel : config.model_name,
            url: shouldUseOpenAIDefaults ? '' : config.url,
        }
    })
}
