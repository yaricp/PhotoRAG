import { useState, useEffect } from 'react'
import { getModelConfigs, updateModelConfig } from '@/api/client'
import type { AIModelConfig } from '@/types/api'
import { ServerIcon, CloudIcon } from '@heroicons/react/24/outline'

export function ModelsPage() {
    const [configs, setConfigs] = useState<AIModelConfig[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [saving, setSaving] = useState<string | null>(null)

    const fetchConfigs = async () => {
        try {
            const data = await getModelConfigs()
            setConfigs(data)
            setError(null)
        } catch (err: any) {
            setError(err.message || 'Failed to fetch models configurations')
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchConfigs()
    }, [])

    const handleSave = async (config: AIModelConfig) => {
        setSaving(config.type)
        try {
            const updated = await updateModelConfig(config.type, {
                mode: config.mode,
                model_name: config.model_name,
                url: config.url || undefined,
                api_key: config.api_key || undefined
            })
            setConfigs(prev => prev.map(c => c.type === updated.type ? updated : c))
        } catch (err: any) {
            setError(err.message || 'Failed to save configuration')
        } finally {
            setSaving(null)
        }
    }

    const handleChange = (type: string, field: keyof AIModelConfig, value: string) => {
        setConfigs(prev => prev.map(c => c.type === type ? { ...c, [field]: value } : c))
    }

    if (loading) return <div className="p-4 flex items-center justify-center h-full">
        <div className="text-gray-400">Loading AI models configuration...</div>
    </div>

    return (
        <div className="p-4 max-w-4xl mx-auto space-y-6">
            <div className="flex items-center gap-3 mb-6 border-b border-white/10 pb-4">
                <ServerIcon className="w-8 h-8 text-blue-400" />
                <h1 className="text-2xl font-bold text-white">AI Models Configuration</h1>
            </div>
            
            <p className="text-gray-400 text-sm mb-6">
                Configure your AI models here. Changes take effect immediately without restarting the server.
                Local models will be downloaded automatically when used for the first time.
            </p>

            {error && (
                <div className="bg-red-500/20 text-red-400 p-4 rounded-xl mb-6 border border-red-500/50">
                    {error}
                </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {configs.map(config => (
                    <div key={config.id} className="bg-[#1A1A1A] rounded-xl border border-white/5 p-6 space-y-4 hover:border-white/10 transition-colors">
                        <div className="flex items-center justify-between">
                            <h2 className="text-xl font-semibold capitalize text-white flex items-center gap-2">
                                {config.mode === 'local' ? (
                                    <ServerIcon className="w-5 h-5 text-blue-400" />
                                ) : (
                                    <CloudIcon className="w-5 h-5 text-purple-400" />
                                )}
                                {config.type}
                            </h2>
                            <span className={`px-2 py-1 text-xs rounded-full font-medium ${
                                config.mode === 'local' ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' : 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                            }`}>
                                {config.mode}
                            </span>
                        </div>

                        <div className="space-y-4 pt-2">
                            <div className="space-y-1">
                                <label className="text-sm font-medium text-gray-400">Processing Mode</label>
                                <select 
                                    className="w-full bg-[#252525] text-white rounded-lg p-2.5 border border-white/10 focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/50 outline-none transition-all"
                                    value={config.mode}
                                    onChange={(e) => handleChange(config.type, 'mode', e.target.value)}
                                >
                                    <option value="local">Local execution (GPU/CPU)</option>
                                    <option value="remote">Remote execution (API)</option>
                                </select>
                            </div>

                            <div className="space-y-1">
                                <label className="text-sm font-medium text-gray-400">Model Name / HuggingFace ID</label>
                                <input 
                                    className="w-full bg-[#252525] text-white rounded-lg p-2.5 border border-white/10 focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/50 outline-none transition-all"
                                    value={config.model_name}
                                    onChange={(e) => handleChange(config.type, 'model_name', e.target.value)}
                                    placeholder={config.mode === 'local' ? "e.g. Qwen/Qwen2-VL-2B-Instruct" : "e.g. gpt-4o-mini"}
                                />
                            </div>

                            {config.mode === 'remote' && (
                                <div className="space-y-4 bg-purple-500/5 p-4 rounded-lg border border-purple-500/10">
                                    <div className="space-y-1">
                                        <label className="text-sm font-medium text-purple-300/70">API Base URL (Optional)</label>
                                        <input 
                                            className="w-full bg-[#252525] text-white rounded-lg p-2.5 border border-white/10 focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/50 outline-none transition-all placeholder-gray-600"
                                            value={config.url || ''}
                                            onChange={(e) => handleChange(config.type, 'url', e.target.value)}
                                            placeholder="https://api.openai.com/v1"
                                        />
                                    </div>
                                    <div className="space-y-1">
                                        <label className="text-sm font-medium text-purple-300/70">API Key</label>
                                        <input 
                                            className="w-full bg-[#252525] text-white rounded-lg p-2.5 border border-white/10 focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/50 outline-none transition-all placeholder-gray-600"
                                            type="password"
                                            value={config.api_key || ''}
                                            onChange={(e) => handleChange(config.type, 'api_key', e.target.value)}
                                            placeholder="sk-..."
                                        />
                                    </div>
                                </div>
                            )}
                        </div>
                        
                        <div className="flex justify-end pt-4 mt-4 border-t border-white/5">
                            <button
                                onClick={() => handleSave(config)}
                                disabled={saving === config.type}
                                className="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-medium disabled:opacity-50 transition-colors flex items-center gap-2"
                            >
                                {saving === config.type ? (
                                    <>
                                        <svg className="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                        </svg>
                                        Saving...
                                    </>
                                ) : 'Save Configuration'}
                            </button>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    )
}