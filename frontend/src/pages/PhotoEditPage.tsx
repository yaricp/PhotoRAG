import React, { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams, useNavigate } from 'react-router-dom'
import { getPhoto, updatePhoto, reindexPhoto, runPipelineForPhoto } from '@/api/client'
import type { LinkedTag, LinkedCategory } from '@/api/client'
import { Spinner } from '@/components/ui/Spinner'
import { TagPickerModal } from '@/components/photos/TagPickerModal'
import { CategoryPickerModal } from '@/components/photos/CategoryPickerModal'
import type { Photo } from '@/types/api'
import { photoImageUrl } from '@/api/images'
import './PhotoEditPage.css'

function tagToLinked(pt: { tag?: { id: number; name: string } | null; confidence_score?: number | null }): LinkedTag | null {
    if (!pt.tag) return null
    return { id: pt.tag.id, name: pt.tag.name, confidence_score: pt.confidence_score ?? 0 }
}

function catToLinked(pc: { category?: { id: number; name: string } | null; confidence_score?: number | null }): LinkedCategory | null {
    if (!pc.category) return null
    return { id: pc.category.id, name: pc.category.name, confidence_score: pc.confidence_score ?? 0 }
}

export function PhotoEditPage() {
    const { id } = useParams()
    const navigate = useNavigate()
    const [photo, setPhoto] = useState<Photo | null>(null)
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)
    const [saved, setSaved] = useState(false)
    const [reindexing, setReindexing] = useState(false)
    const [reindexed, setReindexed] = useState(false)
    const [pipelining, setPipelining] = useState(false)
    const [pipelined, setPipelined] = useState(false)

    const [description, setDescription] = useState('')
    const [translatedDescription, setTranslatedDescription] = useState('')
    const [ocrText, setOcrText] = useState('')

    const [linkedTags, setLinkedTags] = useState<LinkedTag[]>([])
    const [linkedCategories, setLinkedCategories] = useState<LinkedCategory[]>([])

    const [tagModalOpen, setTagModalOpen] = useState(false)
    const [catModalOpen, setCatModalOpen] = useState(false)

    useEffect(() => {
        if (!id) return
        setLoading(true)
        getPhoto(Number(id)).then(p => {
            setPhoto(p)
            setDescription(p.description ?? '')
            setTranslatedDescription(p.translated_description ?? '')
            setOcrText(p.ocr_text ?? '')
            setLinkedTags((p.tags_rel ?? []).map(tagToLinked).filter(Boolean) as LinkedTag[])
            setLinkedCategories((p.categories_rel ?? []).map(catToLinked).filter(Boolean) as LinkedCategory[])
        }).finally(() => setLoading(false))
    }, [id])

    async function handleRunPipeline() {
        if (!photo) return
        setPipelining(true)
        setPipelined(false)
        try {
            await runPipelineForPhoto(photo.id)
            setPipelined(true)
            setTimeout(() => setPipelined(false), 2500)
        } finally {
            setPipelining(false)
        }
    }

    async function handleReindex() {
        if (!photo) return
        setReindexing(true)
        setReindexed(false)
        try {
            await reindexPhoto(photo.id)
            setReindexed(true)
            setTimeout(() => setReindexed(false), 2500)
        } finally {
            setReindexing(false)
        }
    }

    async function handleSave() {
        if (!photo) return
        setSaving(true)
        setSaved(false)
        try {
            await updatePhoto(photo.id, {
                description: description || undefined,
                translated_description: translatedDescription || undefined,
                ocr_text: ocrText || undefined,
            })
            setSaved(true)
            setTimeout(() => setSaved(false), 2500)
        } finally {
            setSaving(false)
        }
    }

    const { t } = useTranslation()

    if (loading) return <div className="pe__center"><Spinner size="lg" /></div>
    if (!photo) return <div className="pe__center">{t('photoEdit.notFound')}</div>

    const filename = photo.file_path.split('/').pop() ?? photo.file_path

    return (
        <div className="pe">
            {/* HEADER */}
            <div className="pe__header">
                <button className="pe__back-btn" onClick={() => navigate(`/photo/${photo.id}`)}>
                    {t('photoEdit.backToPhoto')}
                </button>
            </div>

            {/* IMAGE */}
            <div className="pe__image-wrap">
                <img className="pe__image" src={photoImageUrl(photo.file_path)} alt={filename} />
            </div>

            {/* FIELDS */}
            <div className="pe__section">
                <label className="pe__label">{t('photoEdit.ocrText')}</label>
                <textarea
                    className="pe__textarea"
                    rows={4}
                    value={ocrText}
                    onChange={e => setOcrText(e.target.value)}
                />

                <label className="pe__label">{t('photoEdit.descriptionEn')}</label>
                <textarea
                    className="pe__textarea"
                    rows={5}
                    value={description}
                    onChange={e => setDescription(e.target.value)}
                />

                <label className="pe__label">{t('photoEdit.translation')}</label>
                <textarea
                    className="pe__textarea"
                    rows={5}
                    value={translatedDescription}
                    onChange={e => setTranslatedDescription(e.target.value)}
                />
            </div>

            {/* TAGS */}
            <div className="pe__section">
                <div className="pe__chips-row">
                    <div className="pe__chips-label">{t('photoDetail.tags')}</div>
                    <div className="pe__chips">
                        {linkedTags.map(lt => (
                            <span key={lt.id} className="pe__chip">{lt.name}</span>
                        ))}
                    </div>
                    <button className="pe__manage-btn" onClick={() => setTagModalOpen(true)}>
                        {t('photoEdit.manageTags')}
                    </button>
                </div>

                <div className="pe__chips-row">
                    <div className="pe__chips-label">{t('photoDetail.categories')}</div>
                    <div className="pe__chips">
                        {linkedCategories.map(lc => (
                            <span key={lc.id} className="pe__chip pe__chip--cat">{lc.name}</span>
                        ))}
                    </div>
                    <button className="pe__manage-btn" onClick={() => setCatModalOpen(true)}>
                        {t('photoEdit.manageCategories')}
                    </button>
                </div>
            </div>

            {/* SAVE / REINDEX */}
            <div className="pe__footer">
                <button className="pe__save-btn" onClick={handleSave} disabled={saving}>
                    {saving ? t('photoEdit.saving') : saved ? t('photoEdit.saved') : t('photoEdit.save')}
                </button>
                <button className="pe__reindex-btn" onClick={handleReindex} disabled={reindexing}>
                    {reindexing ? t('photoEdit.queuing') : reindexed ? t('photoEdit.queued') : t('photoEdit.reindexSearch')}
                </button>
                <button className="pe__pipeline-btn" onClick={handleRunPipeline} disabled={pipelining}>
                    {pipelining ? t('photoEdit.starting') : pipelined ? t('photoEdit.started') : t('photoEdit.runPipeline')}
                </button>
            </div>

            <TagPickerModal
                open={tagModalOpen}
                photoId={photo.id}
                linkedTags={linkedTags}
                onClose={() => setTagModalOpen(false)}
                onChanged={setLinkedTags}
            />
            <CategoryPickerModal
                open={catModalOpen}
                photoId={photo.id}
                linkedCategories={linkedCategories}
                onClose={() => setCatModalOpen(false)}
                onChanged={setLinkedCategories}
            />
        </div>
    )
}
