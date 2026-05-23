import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react'
import { SetupWizard } from '../index'
import { StepInstallDeps } from '../StepInstallDeps'
import { StepModelPicker } from '../StepModelPicker'
import { StepDownloading } from '../StepDownloading'
import { StepDone } from '../StepDone'

type ProgressCb = (data: { line: string; percent: number }) => void
type DownloadCb = (data: { modelId: string; percent: number; bytes: number }) => void

const progressListeners: ProgressCb[] = []
const downloadListeners: DownloadCb[] = []

const mockApi = {
    checkSetupNeeded: vi.fn().mockResolvedValue({ needed: true }),
    installDeps: vi.fn().mockResolvedValue(undefined),
    initDb: vi.fn().mockResolvedValue(undefined),
    downloadModel: vi.fn().mockResolvedValue(undefined),
    cancelDownload: vi.fn().mockResolvedValue(undefined),
    completeSetup: vi.fn().mockResolvedValue(undefined),
    onInstallDepsProgress: vi.fn().mockImplementation((cb: ProgressCb) => progressListeners.push(cb)),
    onDownloadModelProgress: vi.fn().mockImplementation((cb: DownloadCb) => downloadListeners.push(cb)),
}

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

    it('shows per-model progress bars', () => {
        render(<StepDownloading selectedModels={selectedModels} onDone={vi.fn()} />)

        act(() => {
            downloadListeners.forEach(cb => cb({ modelId: 'clip', percent: 75, bytes: 247_500_000 }))
        })

        const progressBars = screen.getAllByRole('progressbar')
        expect(progressBars.length).toBeGreaterThanOrEqual(2)
    })

    it('cancel download calls IPC', () => {
        render(<StepDownloading selectedModels={selectedModels} onDone={vi.fn()} />)
        fireEvent.click(screen.getByRole('button', { name: /cancel/i }))
        expect(mockApi.cancelDownload).toHaveBeenCalled()
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
