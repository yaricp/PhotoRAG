export const HELP_TOPICS = [
    { id: 'getting-started' },
    { id: 'gallery' },
    { id: 'search' },
    { id: 'photo-detail' },
    { id: 'photo-edit' },
    { id: 'documents' },
    { id: 'duplicates' },
    { id: 'garbage' },
    { id: 'chat' },
    { id: 'processing' },
    { id: 'folders' },
    { id: 'models' },
    { id: 'prompts' },
    { id: 'template-tags' },
    { id: 'template-categories' },
    { id: 'settings' },
    { id: 'agent-tools' },
    { id: 'uninstall' },
    { id: 'system-requirements' },
]

export const VALID_TOPIC_IDS = new Set(HELP_TOPICS.map(t => t.id))
