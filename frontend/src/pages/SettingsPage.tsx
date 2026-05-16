import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getSettings, updateSetting } from '@/api/client'
import './SettingsPage.css'

const isElectron = typeof window !== 'undefined' && !!window.electronAPI?.uninstall

const LANGUAGES = [
    { value: 'en', label: 'English' },
    { value: 'ru', label: 'Русский' },
]

export function SettingsPage() {
    const navigate = useNavigate()
    const [defaultFolder, setDefaultFolder] = useState('')
    const [language, setLanguage] = useState('en')
    const [saving, setSaving] = useState(false)
    const [saved, setSaved] = useState(false)
    const [uninstalling, setUninstalling] = useState(false)

    useEffect(() => {
        getSettings().then(s => {
            setDefaultFolder(s['default_folder'] ?? '')
            setLanguage(s['default_language'] ?? 'en')
        }).catch(() => {
            // fallback to localStorage if API not available
            const stored = localStorage.getItem('settings')
            if (stored) {
                const s = JSON.parse(stored)
                setDefaultFolder(s.default_folder ?? '')
                setLanguage(s.default_language ?? 'en')
            }
        })
    }, [])

    async function handleSave() {
        setSaving(true)
        setSaved(false)
        try {
            await updateSetting('default_folder', defaultFolder)
            await updateSetting('default_language', language)
            setSaved(true)
            setTimeout(() => setSaved(false), 2500)
        } finally {
            setSaving(false)
        }
    }

    async function handleUninstall() {
        if (!window.electronAPI?.uninstall) return
        setUninstalling(true)
        try {
            await window.electronAPI.uninstall()
        } finally {
            setUninstalling(false)
        }
    }

    return (
        <div className="settings-page">
            <h1 className="settings-page__title">Settings</h1>

            <div className="settings-section">
                <p className="settings-section__heading">General</p>

                <div className="settings-row">
                    <label className="settings-row__label" htmlFor="default-language">
                        Default language
                    </label>
                    <select
                        id="default-language"
                        className="settings-select"
                        value={language}
                        onChange={e => setLanguage(e.target.value)}
                    >
                        {LANGUAGES.map(l => (
                            <option key={l.value} value={l.value}>{l.label}</option>
                        ))}
                    </select>
                </div>

                <div className="settings-row">
                    <label className="settings-row__label" htmlFor="default-folder">
                        Default folder
                    </label>
                    <input
                        id="default-folder"
                        type="text"
                        className="settings-input"
                        value={defaultFolder}
                        onChange={e => setDefaultFolder(e.target.value)}
                        placeholder="/Users/you/Photos"
                    />
                    <span className="settings-row__hint">
                        Used by agent tools (create folder, move photos, archive). Falls back to home directory if empty.
                    </span>
                </div>
            </div>

            <div className="settings-footer">
                <button
                    className="settings-save-btn"
                    onClick={handleSave}
                    disabled={saving}
                >
                    {saving ? 'Saving…' : 'Save'}
                </button>
                {saved && <span className="settings-saved">Saved</span>}
            </div>

            <div className="settings-section">
                <p className="settings-section__heading">CLIP Vocabulary</p>
                <div className="settings-nav-cards">
                    <button className="settings-nav-card" onClick={() => navigate('/template-tags')}>
                        <span className="settings-nav-card__title">Template Tags</span>
                        <span className="settings-nav-card__desc">Manage the tag vocabulary used by CLIP detection</span>
                    </button>
                    <button className="settings-nav-card" onClick={() => navigate('/template-categories')}>
                        <span className="settings-nav-card__title">Template Categories</span>
                        <span className="settings-nav-card__desc">Manage the category list used by CLIP classification</span>
                    </button>
                </div>
            </div>

            {isElectron && (
                <div className="settings-section settings-section--danger">
                    <p className="settings-section__heading">Danger Zone</p>
                    <div className="settings-danger-row">
                        <div className="settings-danger-info">
                            <span className="settings-danger-title">Uninstall PhotoDescriber2</span>
                            <span className="settings-danger-desc">
                                Removes the app, database, AI models, and all settings.
                                Your original photos are not affected.
                            </span>
                        </div>
                        <button
                            className="settings-uninstall-btn"
                            onClick={handleUninstall}
                            disabled={uninstalling}
                        >
                            {uninstalling ? 'Uninstalling…' : 'Uninstall'}
                        </button>
                    </div>
                </div>
            )}
        </div>
    )
}
