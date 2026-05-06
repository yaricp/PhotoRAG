import React, { useState } from 'react'
import './FolderSelector.css'

type Props = {
    onSelect: (path: string) => void
}

export function FolderSelector({ onSelect }: Props) {
    const [path, setPath] = useState('')

    const handlePick = async () => {
        const selected = await window.electronAPI.openFolder()

        if (!selected) return

        setPath(selected)
        onSelect(selected)
    }

    return (
        <div className="folder-selector">
            <button onClick={handlePick}>
                📁 Choose folder
            </button>

            <div className="folder-selector__preview">
                {path || 'No folder selected'}
            </div>
        </div>
    )
}