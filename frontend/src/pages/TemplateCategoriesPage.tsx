import { useState, useEffect, useCallback } from 'react'
import {
    getTemplateCategories, createTemplateCategory, updateTemplateCategory, deleteTemplateCategory,
} from '@/api/client'
import type { TemplateCategory } from '@/api/client'
import { Spinner } from '@/components/ui/Spinner'
import './TemplateVocabPage.css'

const EMPTY_FORM = { name: '', clip_prompt: '' }
const PAGE_SIZE = 50

export function TemplateCategoriesPage() {
    const [items, setItems] = useState<TemplateCategory[]>([])
    const [total, setTotal] = useState(0)
    const [page, setPage] = useState(0)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    const [showAdd, setShowAdd] = useState(false)
    const [addForm, setAddForm] = useState(EMPTY_FORM)
    const [adding, setAdding] = useState(false)

    const [editingId, setEditingId] = useState<number | null>(null)
    const [editForm, setEditForm] = useState(EMPTY_FORM)
    const [saving, setSaving] = useState(false)

    const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

    const load = useCallback(async (p: number) => {
        setLoading(true)
        setError(null)
        try {
            const data = await getTemplateCategories(p * PAGE_SIZE, PAGE_SIZE)
            setItems(data.items)
            setTotal(data.total)
        } catch (e: any) {
            setError(e.message ?? 'Failed to load template categories')
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => { load(page) }, [page, load])

    async function handleCreate() {
        if (!addForm.name.trim() || !addForm.clip_prompt.trim()) return
        setAdding(true)
        setError(null)
        try {
            await createTemplateCategory(addForm.name.trim(), addForm.clip_prompt.trim())
            setAddForm(EMPTY_FORM)
            setShowAdd(false)
            const newTotal = total + 1
            const newLastPage = Math.max(0, Math.ceil(newTotal / PAGE_SIZE) - 1)
            if (page === newLastPage) {
                load(page)
            } else {
                setPage(newLastPage)
            }
        } catch (e: any) {
            setError(e.message ?? 'Failed to create category')
        } finally {
            setAdding(false)
        }
    }

    function startEdit(item: TemplateCategory) {
        setEditingId(item.id)
        setEditForm({ name: item.name, clip_prompt: item.clip_prompt })
    }

    async function handleSave() {
        if (editingId == null) return
        if (!editForm.name.trim() || !editForm.clip_prompt.trim()) return
        setSaving(true)
        setError(null)
        try {
            const updated = await updateTemplateCategory(editingId, editForm.name.trim(), editForm.clip_prompt.trim())
            setItems(prev => prev.map(it => it.id === updated.id ? updated : it))
            setEditingId(null)
        } catch (e: any) {
            setError(e.message ?? 'Failed to update category')
        } finally {
            setSaving(false)
        }
    }

    async function handleDelete(id: number) {
        setError(null)
        try {
            await deleteTemplateCategory(id)
            const newTotal = total - 1
            const newLastPage = Math.max(0, Math.ceil(newTotal / PAGE_SIZE) - 1)
            const targetPage = Math.min(page, newLastPage)
            if (targetPage === page) {
                load(page)
            } else {
                setPage(targetPage)
            }
        } catch (e: any) {
            setError(e.message ?? 'Failed to delete category')
        }
    }

    return (
        <div className="vocab-page">
            <div className="vocab-page__header">
                <div className="vocab-page__titles">
                    <h1 className="vocab-page__title">
                        Template Categories
                        <span className="vocab-count">{total}</span>
                    </h1>
                    <p className="vocab-page__desc">
                        Categories that CLIP assigns to photos. Each entry has a name (shown in UI) and a CLIP prompt (fed to the model).
                        Changes trigger an automatic embedding recompute in the background.
                    </p>
                </div>
                <button className="vocab-page__add-btn" onClick={() => { setShowAdd(true); setEditingId(null) }}>
                    + Add Category
                </button>
            </div>

            {error && <div className="vocab-page__error">{error}</div>}

            {showAdd && (
                <div className="vocab-add-form">
                    <div className="vocab-field">
                        <label className="vocab-field__label">Name</label>
                        <input
                            className="vocab-field__input"
                            placeholder="e.g. food"
                            value={addForm.name}
                            onChange={e => setAddForm(f => ({ ...f, name: e.target.value }))}
                            autoFocus
                        />
                    </div>
                    <div className="vocab-field">
                        <label className="vocab-field__label">CLIP prompt</label>
                        <input
                            className="vocab-field__input"
                            placeholder="e.g. a photo of food"
                            value={addForm.clip_prompt}
                            onChange={e => setAddForm(f => ({ ...f, clip_prompt: e.target.value }))}
                            onKeyDown={e => e.key === 'Enter' && handleCreate()}
                        />
                    </div>
                    <div className="vocab-add-form__actions">
                        <button className="vocab-btn vocab-btn--ghost" onClick={() => { setShowAdd(false); setAddForm(EMPTY_FORM) }}>
                            Cancel
                        </button>
                        <button
                            className="vocab-btn vocab-btn--primary"
                            onClick={handleCreate}
                            disabled={adding || !addForm.name.trim() || !addForm.clip_prompt.trim()}
                        >
                            {adding ? 'Adding…' : 'Add'}
                        </button>
                    </div>
                </div>
            )}

            <div className="vocab-table">
                <div className="vocab-table__head">
                    <span className="vocab-table__head-cell">Name</span>
                    <span className="vocab-table__head-cell">CLIP prompt</span>
                    <span className="vocab-table__head-cell" />
                </div>
                <div className="vocab-table__body">
                    {loading ? (
                        <div className="vocab-empty"><Spinner size="md" /></div>
                    ) : items.length === 0 ? (
                        <div className="vocab-empty">No categories yet. Click "Add Category" to create the first one.</div>
                    ) : items.map(item => (
                        editingId === item.id ? (
                            <div key={item.id} className="vocab-row vocab-row--editing">
                                <div className="vocab-row__edit-grid">
                                    <div className="vocab-field">
                                        <label className="vocab-field__label">Name</label>
                                        <input
                                            className="vocab-field__input"
                                            value={editForm.name}
                                            onChange={e => setEditForm(f => ({ ...f, name: e.target.value }))}
                                            autoFocus
                                        />
                                    </div>
                                    <div className="vocab-field">
                                        <label className="vocab-field__label">CLIP prompt</label>
                                        <input
                                            className="vocab-field__input"
                                            value={editForm.clip_prompt}
                                            onChange={e => setEditForm(f => ({ ...f, clip_prompt: e.target.value }))}
                                            onKeyDown={e => e.key === 'Enter' && handleSave()}
                                        />
                                    </div>
                                </div>
                                <div className="vocab-row__edit-actions">
                                    <button className="vocab-btn vocab-btn--ghost" onClick={() => setEditingId(null)}>Cancel</button>
                                    <button
                                        className="vocab-btn vocab-btn--primary"
                                        onClick={handleSave}
                                        disabled={saving}
                                    >
                                        {saving ? 'Saving…' : 'Save'}
                                    </button>
                                </div>
                            </div>
                        ) : (
                            <div key={item.id} className="vocab-row">
                                <span className="vocab-row__cell">{item.name}</span>
                                <span className="vocab-row__cell vocab-row__cell--dim">{item.clip_prompt}</span>
                                <div className="vocab-row__actions">
                                    <button className="vocab-btn--icon" onClick={() => startEdit(item)}>Edit</button>
                                    <button className="vocab-btn vocab-btn--danger" onClick={() => handleDelete(item.id)}>Delete</button>
                                </div>
                            </div>
                        )
                    ))}
                </div>
            </div>

            {totalPages > 1 && (
                <div className="vocab-pagination">
                    <button
                        className="vocab-btn vocab-btn--ghost"
                        onClick={() => setPage(p => Math.max(0, p - 1))}
                        disabled={page === 0}
                    >
                        ← Prev
                    </button>
                    <span className="vocab-pagination__info">
                        Page {page + 1} of {totalPages}
                    </span>
                    <button
                        className="vocab-btn vocab-btn--ghost"
                        onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
                        disabled={page + 1 >= totalPages}
                    >
                        Next →
                    </button>
                </div>
            )}
        </div>
    )
}
