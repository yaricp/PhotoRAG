import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react'
import { SetupWizard } from '../index'
import { StepInstallDeps } from '../StepInstallDeps'
import { StepModelPicker } from '../StepModelPicker'
import { StepModelConfig } from '../StepModelConfig'
import { StepDownloading } from '../StepDownloading'
import { StepInitDb } from '../StepInitDb'
import { StepDone } from '../StepDone'
import i18n from '@/i18n'

type ProgressCb = (data: { line: string; percent: number }) => void
type DownloadCb = (data: { modelId: string; bytes: number; done: boolean }) => void

const progressListeners: ProgressCb[] = []
const downloadListeners: DownloadCb[] = []

const mockApi = {
    checkSetupNeeded: vi.fn().mockResolvedValue({ needed: true }),
    installDeps: vi.fn().mockResolvedValue(undefined),
    initDb: vi.fn().mockResolvedValue(undefined),
    downloadModel: vi.fn().mockResolvedValue(undefined),
    cancelDownload: vi.fn().mockResolvedValue(undefined),
    completeSetup: vi.fn().mockResolvedValue(undefined),
    getModelStatuses: vi.fn().mockResolvedValue({}),
    getModelConfigs: vi.fn().mockResolvedValue([]),
    saveModelConfigs: vi.fn().mockResolvedValue(undefined),
    onInstallDepsProgress: vi.fn().mockImplementation((cb: ProgressCb) => progressListeners.push(cb)),
    onDownloadModelProgress: vi.fn().mockImplementation((cb: DownloadCb) => downloadListeners.push(cb)),
}

afterEach(() => { i18n.changeLanguage('en') })

beforeEach(() => {
    progressListeners.length = 0
    downloadListeners.length = 0
    vi.clearAllMocks()
    // Re-establish implementations after clearAllMocks resets them
    mockApi.installDeps.mockResolvedValue(undefined)
    mockApi.initDb.mockResolvedValue(undefined)
    mockApi.downloadModel.mockResolvedValue(undefined)
    mockApi.cancelDownload.mockResolvedValue(undefined)
    mockApi.completeSetup.mockResolvedValue(undefined)
    mockApi.getModelStatuses.mockResolvedValue({})
    mockApi.getModelConfigs.mockResolvedValue([])
    mockApi.saveModelConfigs.mockResolvedValue(undefined)
    mockApi.onInstallDepsProgress.mockImplementation((cb: ProgressCb) => progressListeners.push(cb))
    mockApi.onDownloadModelProgress.mockImplementation((cb: DownloadCb) => downloadListeners.push(cb))
    Object.defineProperty(window, 'electronAPI', {
        value: mockApi,
        writable: true,
        configurable: true,
    })
})

describe('SetupWizard', () => {
    it('starts at language step', () => {
        render(<SetupWizard onComplete={vi.fn()} />)
        expect(screen.getByText(/choose your language/i)).toBeInTheDocument()
    })

    it('advances to welcome step after language continue', async () => {
        render(<SetupWizard onComplete={vi.fn()} />)
        await act(async () => {
            fireEvent.click(screen.getByRole('button', { name: /continue/i }))
        })
        expect(screen.getByText(/welcome to photorag/i)).toBeInTheDocument()
    })

    it('advances to install-deps from welcome step', async () => {
        render(<SetupWizard onComplete={vi.fn()} />)
        await act(async () => {
            fireEvent.click(screen.getByRole('button', { name: /continue/i }))
        })
        fireEvent.click(screen.getByRole('button', { name: /get started/i }))
        expect(screen.getByText(/install dependencies/i)).toBeInTheDocument()
    })
})

describe('StepInstallDeps', () => {
    it('calls installDeps IPC on Install click', () => {
        render(<StepInstallDeps onDone={vi.fn()} />)
        fireEvent.click(screen.getByRole('button', { name: /install/i }))
        expect(mockApi.installDeps).toHaveBeenCalled()
    })

    it('progress bar updates on progress event', () => {
        render(<StepInstallDeps onDone={vi.fn()} />)
        fireEvent.click(screen.getByRole('button', { name: /install/i }))

        act(() => {
            progressListeners.forEach(cb => cb({ percent: 50, line: 'Installing numpy...' }))
        })

        expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '50')
    })
})

describe('StepModelPicker', () => {
    const defaultSelected = new Set(['clip', 'embedding'])
    const renderPicker = (
        selected = defaultSelected,
        onChange = vi.fn(),
        onContinue = vi.fn()
    ) => render(<StepModelPicker selected={selected} onChange={onChange} onContinue={onContinue} />)

    it('renders all 6 models and Skip all optional checkbox', () => {
        renderPicker()
        expect(screen.getByLabelText(/CLIP ViT-B-32/i)).toBeInTheDocument()
        expect(screen.getByLabelText(/nomic-embed/i)).toBeInTheDocument()
        expect(screen.getByLabelText(/Qwen2-VL/i)).toBeInTheDocument()
        expect(screen.getByLabelText(/NLLB-200/i)).toBeInTheDocument()
        expect(screen.getByLabelText(/TrOCR/i)).toBeInTheDocument()
        expect(screen.getByLabelText(/Qwen2\.5-Coder/i)).toBeInTheDocument()
        expect(screen.getByLabelText(/skip all optional/i)).toBeInTheDocument()
    })

    it('calculates total size for CLIP + embedding as ~610 MB', () => {
        renderPicker()
        expect(screen.getByText(/610 MB/i)).toBeInTheDocument()
    })

    it('required models (clip, embedding) are always checked and disabled', () => {
        renderPicker()
        const clipCheckbox = screen.getByLabelText(/CLIP ViT-B-32/i) as HTMLInputElement
        const embCheckbox = screen.getByLabelText(/nomic-embed/i) as HTMLInputElement
        expect(clipCheckbox).toBeDisabled()
        expect(embCheckbox).toBeDisabled()
        expect(clipCheckbox.checked).toBe(true)
        expect(embCheckbox.checked).toBe(true)
    })
})

describe('StepDownloading', () => {
    const selectedModels = new Set(['clip', 'embedding'])

    it('shows per-model progress bars', async () => {
        render(<StepDownloading selectedModels={selectedModels} onDone={vi.fn()} />)
        await waitFor(() => expect(mockApi.getModelStatuses).toHaveBeenCalled())

        act(() => {
            downloadListeners.forEach(cb => cb({ modelId: 'clip', bytes: 247_500_000, done: false }))
        })

        const progressBars = screen.getAllByRole('progressbar')
        expect(progressBars.length).toBeGreaterThanOrEqual(2)
    })

    it('cancel download calls IPC', async () => {
        // Keep download pending so the cancel button stays visible
        mockApi.downloadModel.mockReturnValue(new Promise(() => {}))
        render(<StepDownloading selectedModels={selectedModels} onDone={vi.fn()} />)
        await waitFor(() => expect(mockApi.getModelStatuses).toHaveBeenCalled())
        await waitFor(() => expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument())
        fireEvent.click(screen.getByRole('button', { name: /cancel/i }))
        expect(mockApi.cancelDownload).toHaveBeenCalled()
    })

    it('shows static model size before any progress event', async () => {
        render(<StepDownloading selectedModels={new Set(['clip'])} onDone={vi.fn()} />)
        await waitFor(() => expect(mockApi.getModelStatuses).toHaveBeenCalled())
        // CLIP is 330 MB in models.ts — should show immediately, not 0 MB
        expect(screen.getByText(/330 MB/i)).toBeInTheDocument()
    })

    it('computes percent from bytes against known model size', async () => {
        render(<StepDownloading selectedModels={new Set(['clip'])} onDone={vi.fn()} />)
        await waitFor(() => expect(mockApi.getModelStatuses).toHaveBeenCalled())

        act(() => {
            // 165 MB out of 330 MB = 50%
            downloadListeners.forEach(cb => cb({ modelId: 'clip', bytes: 165 * 1_048_576, done: false }))
        })

        const bar = screen.getByRole('progressbar', { name: /CLIP/i })
        expect(bar).toHaveAttribute('aria-valuenow', '50')
    })

    it('reaches 100% on done event', async () => {
        render(<StepDownloading selectedModels={new Set(['clip'])} onDone={vi.fn()} />)
        await waitFor(() => expect(mockApi.getModelStatuses).toHaveBeenCalled())

        act(() => {
            downloadListeners.forEach(cb => cb({ modelId: 'clip', bytes: 330 * 1_048_576, done: true }))
        })

        const bar = screen.getByRole('progressbar', { name: /CLIP/i })
        expect(bar).toHaveAttribute('aria-valuenow', '100')
    })

    it('starts at 0% before any progress event', async () => {
        render(<StepDownloading selectedModels={new Set(['clip'])} onDone={vi.fn()} />)
        await waitFor(() => expect(mockApi.getModelStatuses).toHaveBeenCalled())

        const bar = screen.getByRole('progressbar', { name: /CLIP/i })
        expect(bar).toHaveAttribute('aria-valuenow', '0')
    })

    it('launches all downloads in parallel (not sequentially)', async () => {
        let resolveClip!: () => void
        let resolveEmbedding!: () => void
        mockApi.downloadModel.mockImplementation(({ modelId }: { modelId: string }) => {
            if (modelId === 'clip') return new Promise<void>(res => { resolveClip = res })
            if (modelId === 'embedding') return new Promise<void>(res => { resolveEmbedding = res })
            return Promise.resolve()
        })

        render(<StepDownloading selectedModels={selectedModels} onDone={vi.fn()} />)

        // Both download calls should be initiated before either resolves
        await waitFor(() => expect(mockApi.downloadModel).toHaveBeenCalledTimes(2))
        expect(mockApi.downloadModel).toHaveBeenCalledWith({ modelId: 'clip' })
        expect(mockApi.downloadModel).toHaveBeenCalledWith({ modelId: 'embedding' })

        resolveClip()
        resolveEmbedding()
    })

    it('skips already-ready models and shows them at 100%', async () => {
        mockApi.getModelStatuses.mockResolvedValue({ clip: 'ready' })

        render(<StepDownloading selectedModels={selectedModels} onDone={vi.fn()} />)
        await waitFor(() => expect(mockApi.getModelStatuses).toHaveBeenCalled())

        // clip should not be downloaded
        await waitFor(() => expect(mockApi.downloadModel).not.toHaveBeenCalledWith({ modelId: 'clip' }))
        // clip should show 100%
        await waitFor(() => {
            const bar = screen.getByRole('progressbar', { name: /CLIP/i })
            expect(bar).toHaveAttribute('aria-valuenow', '100')
        })
        // embedding should still be downloaded
        await waitFor(() => expect(mockApi.downloadModel).toHaveBeenCalledWith({ modelId: 'embedding' }))
    })

    it('calls onDone immediately when all selected models are already ready', async () => {
        mockApi.getModelStatuses.mockResolvedValue({ clip: 'ready', embedding: 'ready' })
        const onDone = vi.fn()

        render(<StepDownloading selectedModels={selectedModels} onDone={onDone} />)

        await waitFor(() => expect(onDone).toHaveBeenCalled())
        expect(mockApi.downloadModel).not.toHaveBeenCalled()
    })

    it('shows Back button when onBack provided', async () => {
        mockApi.downloadModel.mockReturnValue(new Promise(() => {}))
        render(<StepDownloading selectedModels={selectedModels} onDone={vi.fn()} onBack={vi.fn()} />)
        await waitFor(() => expect(mockApi.getModelStatuses).toHaveBeenCalled())
        await waitFor(() => expect(screen.getByRole('button', { name: /back/i })).toBeInTheDocument())
    })

    it('Back button calls cancelDownload and onBack', async () => {
        mockApi.downloadModel.mockReturnValue(new Promise(() => {}))
        const onBack = vi.fn()
        render(<StepDownloading selectedModels={selectedModels} onDone={vi.fn()} onBack={onBack} />)
        await waitFor(() => expect(mockApi.getModelStatuses).toHaveBeenCalled())
        await waitFor(() => screen.getByRole('button', { name: /back/i }))

        fireEvent.click(screen.getByRole('button', { name: /back/i }))

        expect(mockApi.cancelDownload).toHaveBeenCalled()
        expect(onBack).toHaveBeenCalled()
    })

    it('hides Back button after all downloads complete', async () => {
        const onDone = vi.fn()
        render(<StepDownloading selectedModels={new Set(['clip'])} onDone={onDone} onBack={vi.fn()} />)
        await waitFor(() => expect(mockApi.getModelStatuses).toHaveBeenCalled())

        act(() => {
            downloadListeners.forEach(cb => cb({ modelId: 'clip', bytes: 330 * 1_048_576, done: true }))
        })
        await waitFor(() => expect(onDone).toHaveBeenCalled())

        expect(screen.queryByRole('button', { name: /back/i })).not.toBeInTheDocument()
    })
})

describe('StepDone', () => {
    it('shows launch button and calls completeSetup then onComplete', async () => {
        const onComplete = vi.fn()
        render(<StepDone onComplete={onComplete} />)
        expect(screen.getByRole('button', { name: /launch/i })).toBeInTheDocument()
        fireEvent.click(screen.getByRole('button', { name: /launch/i }))
        expect(mockApi.completeSetup).toHaveBeenCalled()
        await waitFor(() => expect(onComplete).toHaveBeenCalled())
    })
})

describe('i18n — Russian titles', () => {
    it('StepInstallDeps renders Russian title', () => {
        i18n.changeLanguage('ru')
        render(<StepInstallDeps onDone={vi.fn()} />)
        expect(screen.getByRole('heading', { name: 'Установка зависимостей' })).toBeInTheDocument()
    })

    it('StepModelPicker renders Russian title', () => {
        i18n.changeLanguage('ru')
        render(<StepModelPicker selected={new Set(['clip', 'embedding'])} onChange={vi.fn()} onContinue={vi.fn()} />)
        expect(screen.getByRole('heading', { name: 'Выбор моделей для загрузки' })).toBeInTheDocument()
    })

    it('StepDownloading renders Russian title', () => {
        i18n.changeLanguage('ru')
        render(<StepDownloading selectedModels={new Set(['clip'])} onDone={vi.fn()} />)
        expect(screen.getByRole('heading', { name: 'Загрузка моделей' })).toBeInTheDocument()
    })

    it('StepInitDb renders Russian title', () => {
        i18n.changeLanguage('ru')
        render(<StepInitDb onDone={vi.fn()} />)
        expect(screen.getByRole('heading', { name: 'Инициализация базы данных' })).toBeInTheDocument()
    })

    it('StepDone renders Russian title', () => {
        i18n.changeLanguage('ru')
        render(<StepDone onComplete={vi.fn()} />)
        expect(screen.getByRole('heading', { name: 'Установка завершена!' })).toBeInTheDocument()
    })
})

describe('StepModelConfig i18n', () => {
    it('renders Russian title', async () => {
        i18n.changeLanguage('ru')
        render(<StepModelConfig onDone={vi.fn()} />)
        await waitFor(() =>
            expect(screen.getByRole('heading', { name: /Настройка моделей ИИ/i })).toBeInTheDocument()
        )
    })

    it('renders Russian Continue button', async () => {
        i18n.changeLanguage('ru')
        render(<StepModelConfig onDone={vi.fn()} />)
        await waitFor(() =>
            expect(screen.getByRole('button', { name: /Продолжить/i })).toBeInTheDocument()
        )
    })

    it('renders Spanish title', async () => {
        i18n.changeLanguage('es')
        render(<StepModelConfig onDone={vi.fn()} />)
        await waitFor(() =>
            expect(screen.getByRole('heading', { name: /Configurar modelos de IA/i })).toBeInTheDocument()
        )
    })
})
