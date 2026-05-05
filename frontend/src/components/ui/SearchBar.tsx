import React, { useState } from 'react'
import './SearchBar.css'

interface SearchBarProps {
    onSearch: (query: string) => void
    placeholder?: string
    defaultValue?: string
}

export function SearchBar({ onSearch, placeholder = 'Search...', defaultValue = '' }: SearchBarProps) {
    const [value, setValue] = useState(defaultValue)

    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === 'Enter' && value.trim()) {
            onSearch(value.trim())
        }
    }

    const handleClear = () => {
        setValue('')
    }

    return (
        <div className="search-bar">
            <input
                type="search"
                role="searchbox"
                className="search-bar__input"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={placeholder}
            />
            {value && (
                <button
                    className="search-bar__clear"
                    data-testid="search-clear"
                    onClick={handleClear}
                    aria-label="Clear search"
                >
                    ✕
                </button>
            )}
        </div>
    )
}