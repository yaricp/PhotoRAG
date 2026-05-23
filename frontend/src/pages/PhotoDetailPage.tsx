import React, { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { getPhoto, deletePhoto, archivePhotos, updatePhotoFlags } from '@/api/client'
import { Spinner } from '@/components/ui/Spinner'
import { ConfirmModal } from '@/components/ui/ConfirmModal'
import type { Photo } from '@/types/api'
import { photoImageUrl } from '@/api/images'
import './PhotoDetailPage.css'

function Item({ label, value }: { label: string; value?: string | number | null }) {
    if (value === null || value === undefined || value === '') return null
    return (
        <div className="pd__item">
            <div className="pd__item-label">{label}</div>
            <div className="pd__item-value">{String(value)}</div>
        </div>
    )
}

function CollapsibleRow({ title, children }: { title: string; children: React.ReactNode }) {
    const [open, setOpen] = useState(false)
    return (
        <div className="pd__collapsible">
            <button className="pd__collapsible-toggle" onClick={() => setOpen(o => !o)}>
                <span className={`pd__chevron ${open ? 'pd__chevron--open' : ''}`}>▶</span>
                {title}
            </button>
            {open && <div className="pd__collapsible-body">{children}</div>}
        </div>
    )
}

type PendingAction = 'archive' | 'delete' | null

export function PhotoDetailPage() {
    const { t } = useTranslation()
    const { id } = useParams()
    const navigate = useNavigate()
    const [photo, setPhoto] = useState<Photo | null>(null)
    const [loading, setLoading] = useState(true)
    const [pending, setPending] = useState<PendingAction>(null)
    const [flagLoading, setFlagLoading] = useState(false)

    useEffect(() => {
        if (!id) return
        setLoading(true)
        getPhoto(Number(id))
            .then(setPhoto)
            .finally(() => setLoading(false))
    }, [id])

    async function handleToggleFlag(flag: 'is_doc' | 'is_trash', value: boolean) {
        if (!photo) return
        setFlagLoading(true)
        try {
            const updated = await updatePhotoFlags(photo.id, { [flag]: value })
            setPhoto(updated)
        } finally {
            setFlagLoading(false)
        }
    }

    async function handleArchive() {
        if (!photo) return
        await archivePhotos([photo.id])
        navigate(-1)
    }

    async function handleDelete() {
        if (!photo) return
        await deletePhoto(photo.id)
        navigate(-1)
    }

    if (loading) {
        return <div className="pd__center" data-testid="page-photo-detail"><Spinner size="lg" /></div>
    }

    if (!photo) {
        return <div className="pd__center" data-testid="page-photo-detail">{t('photoDetail.notFound')}</div>
    }

    const filename = photo.file_path.split('/').pop() ?? photo.file_path
    const geo = photo.geoposition
    const cam = photo.camera
    const tags = photo.tags_rel ?? []
    const categories = photo.categories_rel ?? []

    return (
        <div className="pd" data-testid="page-photo-detail">
            {/* HEADER */}
            <div className="pd__header">
                <button className="pd__back-btn" onClick={() => navigate(-1)}>{t('photoDetail.back')}</button>
                <Link className="pd__edit-btn" to={`/photo/${photo.id}/edit`}>{t('photoDetail.edit')}</Link>
            </div>

            {/* IMAGE */}
            <div className="pd__image-wrap">
                <img className="pd__image" src={photoImageUrl(photo.file_path)} alt={filename} />
            </div>

            {/* MAIN INFO */}
            <div className="pd__section">
                <div className="pd__filepath">{photo.file_path}</div>

                {photo.captured_at && (
                    <Item label={t('photoDetail.dateTaken')} value={photo.captured_at.replace('T', ' ').slice(0, 16)} />
                )}

                {geo && (
                    <div className="pd__geo">
                        {geo.address && <span className="pd__geo-address">{geo.address}</span>}
                        {geo.latitude != null && geo.longitude != null && (
                            <>
                                <span className="pd__geo-coords">
                                    {geo.latitude.toFixed(4)}°N {geo.longitude.toFixed(4)}°W
                                </span>
                                <a
                                    className="pd__map-link"
                                    href={`https://maps.google.com/?q=${geo.latitude},${geo.longitude}`}
                                    target="_blank"
                                    rel="noreferrer"
                                >
                                    Open in Google Maps ↗
                                </a>
                            </>
                        )}
                    </div>
                )}

                {cam && (
                    <Item label={t('photoDetail.camera')} value={`${cam.make ?? ''} ${cam.model ?? ''}`.trim()} />
                )}

                {photo.description && (
                    <div className="pd__description">
                        <div className="pd__desc-label">{t('photoDetail.description')}</div>
                        <div className="pd__desc-text">{photo.description}</div>
                    </div>
                )}

                {photo.translated_description && (
                    <div className="pd__description">
                        <div className="pd__desc-label">{t('photoDetail.translation')}</div>
                        <div className="pd__desc-text pd__desc-text--muted">{photo.translated_description}</div>
                    </div>
                )}

                {tags.length > 0 && (
                    <div className="pd__tags">
                        <div className="pd__desc-label">{t('photoDetail.tags')}</div>
                        <div className="pd__tag-list">
                            {tags.map(pt => (
                                <span key={pt.tag?.id} className="pd__tag">{pt.tag?.name}</span>
                            ))}
                        </div>
                    </div>
                )}

                {categories.length > 0 && (
                    <div className="pd__tags">
                        <div className="pd__desc-label">{t('photoDetail.categories')}</div>
                        <div className="pd__tag-list">
                            {categories.map(pc => (
                                <span key={pc.category?.id} className="pd__tag pd__tag--cat">{pc.category?.name}</span>
                            ))}
                        </div>
                    </div>
                )}
            </div>

            {/* FLAGS */}
            <div className="pd__section pd__flags">
                <label className={`pd__flag-label ${flagLoading ? 'pd__flag-label--disabled' : ''}`}>
                    <input
                        type="checkbox"
                        checked={!!photo.is_trash}
                        disabled={flagLoading}
                        onChange={e => handleToggleFlag('is_trash', e.target.checked)}
                    />
                    {t('photoDetail.trash')}
                </label>
                <label className={`pd__flag-label ${flagLoading ? 'pd__flag-label--disabled' : ''}`}>
                    <input
                        type="checkbox"
                        checked={!!photo.is_doc}
                        disabled={flagLoading}
                        onChange={e => handleToggleFlag('is_doc', e.target.checked)}
                    />
                    {t('photoDetail.document')}
                </label>
            </div>

            {/* DOCUMENT TEXT (collapsible, only when is_doc) */}
            {photo.is_doc && photo.ocr_text && (
                <div className="pd__section">
                    <CollapsibleRow title={t('photoDetail.documentText')}>
                        <div className="pd__ocr-text">{photo.ocr_text}</div>
                    </CollapsibleRow>
                </div>
            )}

            {/* ADDITIONAL DATA (collapsible) */}
            <div className="pd__section">
                <CollapsibleRow title={t('photoDetail.additionalData')}>
                    <div className="pd__grid">
                        <Item label={t('photoDetail.fileCreated')} value={photo.file_created_at?.replace('T', ' ').slice(0, 16)} />
                        <Item label={t('photoDetail.captured')} value={photo.captured_at?.replace('T', ' ').slice(0, 16)} />
                        <Item label={t('photoDetail.indexed')} value={photo.created_at?.replace('T', ' ').slice(0, 16)} />
                        <Item label={t('photoDetail.width')} value={photo.image_width} />
                        <Item label={t('photoDetail.height')} value={photo.image_height} />
                        <Item label={t('photoDetail.iso')} value={photo.iso} />
                        <Item label={t('photoDetail.aperture')} value={photo.aperture} />
                        <Item label={t('photoDetail.focalLength')} value={photo.focal_length} />
                        <Item label={t('photoDetail.shutterSpeed')} value={photo.shutter_speed} />
                        <Item label={t('photoDetail.offsetTime')} value={photo.offset_time} />
                    </div>
                </CollapsibleRow>
            </div>

            {/* ARCHIVE / DELETE */}
            <div className="pd__actions">
                <button className="pd__action-btn pd__action-btn--warning" onClick={() => setPending('archive')}>
                    {t('photoDetail.archive')}
                </button>
                <button className="pd__action-btn pd__action-btn--danger" onClick={() => setPending('delete')}>
                    {t('photoDetail.delete')}
                </button>
            </div>

            <ConfirmModal
                open={pending === 'archive'}
                title={t('photoDetail.archiveConfirmTitle')}
                message={t('photoDetail.archiveConfirmMessage')}
                confirmLabel={t('photoDetail.archive')}
                variant="warning"
                onConfirm={handleArchive}
                onClose={() => setPending(null)}
            />
            <ConfirmModal
                open={pending === 'delete'}
                title={t('photoDetail.deleteConfirmTitle')}
                message={t('photoDetail.deleteConfirmMessage')}
                confirmLabel={t('photoDetail.delete')}
                variant="danger"
                onConfirm={handleDelete}
                onClose={() => setPending(null)}
            />
        </div>
    )
}
