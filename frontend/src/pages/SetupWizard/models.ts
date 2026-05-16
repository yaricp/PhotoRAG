export interface Model {
    id: string
    name: string
    sizeMB: number
    required: boolean
    desc: string
}

export const MODELS: Model[] = [
    { id: 'clip',        name: 'CLIP ViT-B-32',          sizeMB: 330,  required: true,  desc: 'Required for photo tagging' },
    { id: 'embedding',   name: 'nomic-embed-text-v1.5',  sizeMB: 280,  required: true,  desc: 'Required for semantic search' },
    { id: 'vision',      name: 'Qwen2-VL-2B',            sizeMB: 6000, required: false, desc: 'Local image descriptions' },
    { id: 'translation', name: 'NLLB-200 Distilled',     sizeMB: 2500, required: false, desc: 'Auto-translation' },
    { id: 'ocr',         name: 'TrOCR-small',            sizeMB: 150,  required: false, desc: 'Text extraction from photos' },
    { id: 'chat',        name: 'Qwen2.5-Coder-3B',       sizeMB: 7000, required: false, desc: 'Local AI assistant' },
]

export function formatSizeMB(mb: number): string {
    if (mb >= 1000) return `${(mb / 1000).toFixed(1)} GB`
    return `${mb} MB`
}

export function totalSizeLabel(selectedIds: Set<string>): string {
    const total = MODELS
        .filter(m => selectedIds.has(m.id))
        .reduce((sum, m) => sum + m.sizeMB, 0)
    return formatSizeMB(total)
}
