import React from 'react'
import { useNavigate } from 'react-router-dom'
import { Badge } from '@/components/ui/Badge'
import { photoImageUrl } from '@/api/images'
import type { Photo, Job } from '@/types/api'
import './PhotoCard.css'

interface PhotoCardProps {
    photo: Photo
    job?: Job | null
    onArchive?: () => void
    onDelete?: () => void
}

export function PhotoCard({ photo, job, onArchive, onDelete }: PhotoCardProps) {
    const navigate = useNavigate()

    const filename =
        photo?.file_path?.split('/').pop() ?? photo?.file_path ?? 'Unknown file'

    const topTag = photo?.tags?.[0]

    const hasActions = onArchive !== undefined || onDelete !== undefined

    return (
        <article
            className="photo-card"
            onClick={() => navigate(`/photo/${photo.id}`)}
            role="article"
        >
            <div className="photo-card__image-wrap">
                <img
                    src={photoImageUrl(photo.file_path)}
                    alt={filename}
                    className="photo-card__image"
                />
            </div>

            <div className="photo-card__body">
                <p className="photo-card__name">{filename}</p>

                <div className="photo-card__badges">
                    {job && <Badge variant="processing">Processing…</Badge>}
                    {photo?.is_doc && <Badge variant="doc">Document</Badge>}
                    {topTag?.tag?.name && (
                        <Badge variant="default">{topTag.tag.name}</Badge>
                    )}
                </div>

                {typeof topTag?.confidence_score === 'number' && (
                    <div className="photo-card__confidence">
                        <div
                            className="photo-card__confidence-bar"
                            style={{
                                width: `${Math.round(
                                    (topTag.confidence_score || 0) * 100
                                )}%`,
                            }}
                        />
                    </div>
                )}

                {hasActions && (
                    <div className="photo-card__actions">
                        {onArchive && (
                            <button
                                className="photo-card__action-btn photo-card__action-btn--archive"
                                onClick={(e) => { e.stopPropagation(); onArchive() }}
                            >
                                Archive
                            </button>
                        )}
                        {onDelete && (
                            <button
                                className="photo-card__action-btn photo-card__action-btn--delete"
                                onClick={(e) => { e.stopPropagation(); onDelete() }}
                            >
                                Delete
                            </button>
                        )}
                    </div>
                )}
            </div>
        </article>
    )
}
