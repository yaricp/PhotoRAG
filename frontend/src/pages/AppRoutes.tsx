import React from 'react'
import { Routes, Route } from 'react-router-dom'
import { GalleryPage } from './GalleryPage'
import { SearchPage } from './SearchPage'
import { DocumentsPage } from './DocumentsPage'
import { ChatPage } from './ChatPage'
import { SettingsPage } from './SettingsPage'
import { PhotoDetailPage } from './PhotoDetailPage'
import { JobProcessingPage } from './JobProcessingPage'
import { FoldersPage } from './FoldersPage'
import { ModelsPage } from './ModelsPage'
import { DuplicatesPage } from './DuplicatesPage'
import { GarbageBadPhotoPage } from './GarbageBadPhotoPage'

export function AppRoutes() {
    return (
        <Routes>
            <Route path="/" element={<GalleryPage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/documents" element={<DocumentsPage />} />
            <Route path="/duplicates" element={<DuplicatesPage />} />
            <Route path="/garbage" element={<GarbageBadPhotoPage />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/photo/:id" element={<PhotoDetailPage />} />
            <Route path="/processing" element={<JobProcessingPage />} />
            <Route path="/folders" element={<FoldersPage />} />
            <Route path="/models" element={<ModelsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
        </Routes>
    )
}