import React, { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { getPhoto } from '@/api/client'
import { Spinner } from '@/components/ui/Spinner'
import type { Photo } from '@/types/api'
import './PhotoDetailPage.css'

function Item({ label, value }: { label: string; value?: any }) {
    if (value === null || value === undefined || value === '') return null

    return (
        <div className="photo-detail__item">
            <div className="photo-detail__label">{label}</div>
            <div className="photo-detail__value">{String(value)}</div>
        </div>
    )
}

export function PhotoDetailPage() {
    const { id } = useParams()
    const [photo, setPhoto] = useState<Photo | null>(null)
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        if (!id) return

        setLoading(true)

        getPhoto(Number(id))
            .then(setPhoto)
            .finally(() => setLoading(false))
    }, [id])

    if (loading) {
        return (
            <div className="photo-detail__center">
                <Spinner size="lg" />
            </div>
        )
    }

    if (!photo) {
        return (
            <div className="photo-detail__center">
                Photo not found
            </div>
        )
    }

    return (
        <div className="photo-detail">

            {/* IMAGE */}
            <div className="photo-detail__image-wrap">
                <img
                    className="photo-detail__image"
                    src={photo.file_path}
                    alt="photo"
                />
            </div>

            {/* MAIN INFO */}
            <div className="photo-detail__section">
                <h2>Main info</h2>

                <div className="photo-detail__grid">
                    <Item label="Created at" value={photo.created_at} />
                    <Item label="Captured at" value={photo.captured_at} />
                    <Item label="File created at" value={photo.file_created_at} />

                    <Item label="Width" value={photo.image_width} />
                    <Item label="Height" value={photo.image_height} />

                    <Item label="ISO" value={photo.iso} />
                    <Item label="Aperture" value={photo.aperture} />
                    <Item label="Focal length" value={photo.focal_length} />
                    <Item label="Shutter speed" value={photo.shutter_speed} />
                    <Item label="Offset time" value={photo.offset_time} />
                </div>
            </div>

            {/* DESCRIPTION */}
            <div className="photo-detail__section">
                <h2>Description</h2>

                <div className="photo-detail__text">
                    {photo.description}
                </div>

                <div className="photo-detail__text photo-detail__text--muted">
                    {photo.translated_description}
                </div>
            </div>

            {/* CAMERA */}
            {photo.camera && (
                <div className="photo-detail__section">
                    <h2>Camera</h2>

                    <div className="photo-detail__grid">
                        <Item label="Make" value={photo.camera.make} />
                        <Item label="Model" value={photo.camera.model} />
                        <Item label="Serial number" value={photo.camera.serial_number} />
                    </div>
                </div>
            )}

            {/* GEO */}
            {photo.geoposition && (
                <div className="photo-detail__section">
                    <h2>Location</h2>

                    <div className="photo-detail__grid">
                        <Item label="Latitude" value={photo.geoposition.latitude} />
                        <Item label="Longitude" value={photo.geoposition.longitude} />
                    </div>

                    {photo.geoposition.address && (
                        <div className="photo-detail__address">
                            {photo.geoposition.address}
                        </div>
                    )}

                    <a
                        className="photo-detail__map-link"
                        href={`https://www.google.com/maps?q=${photo.geoposition.latitude},${photo.geoposition.longitude}`}
                        target="_blank"
                        rel="noreferrer"
                    >
                        Open in Google Maps
                    </a>
                </div>
            )}
        </div>
    )
}