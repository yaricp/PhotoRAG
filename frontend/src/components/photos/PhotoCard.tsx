import React from 'react'
import { useNavigate } from 'react-router-dom'
import { Badge } from '@/components/ui/Badge'
import { photoImageUrl } from '@/api/images'
import type { Photo, Job } from '@/types/api'
import './PhotoCard.css'

interface PhotoCardProps {
    photo: Photo
    job?: Job | null
}

export function PhotoCard({ photo, job }: PhotoCardProps) {
    const navigate = useNavigate()

    const filename =
        photo?.file_path?.split('/').pop() ?? photo?.file_path ?? 'Unknown file'

    const topTag = photo?.tags?.[0]

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
            </div>
        </article>
    )
}