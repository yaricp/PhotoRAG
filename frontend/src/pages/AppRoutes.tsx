import React from 'react'
import { Routes, Route } from 'react-router-dom'
import { GalleryPage } from './GalleryPage'
import { SearchPage } from './SearchPage'
import { DocumentsPage } from './DocumentsPage'
import { ChatPage } from './ChatPage'
import { SettingsPage } from './SettingsPage'
import { PhotoDetailPage } from './PhotoDetailPage'

export function AppRoutes() {
    return (
        <Routes>
            <Route path="/" element={<GalleryPage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/documents" element={<DocumentsPage />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/photo/:id" element={<PhotoDetailPage />} />
        </Routes>
    )
}