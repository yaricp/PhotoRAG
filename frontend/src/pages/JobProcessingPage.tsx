import React, { useEffect, useState } from 'react'
import { getJobs } from '@/api/client'
import { PhotoCard } from '@/components/photos/PhotoCard'
import { Spinner } from '@/components/ui/Spinner'
import type { Job, Photo } from '@/types/api'
import './JobProcessingPage.css'


export function JobProcessingPage() {
    const [jobs, setJobs] = useState<Job[]>([])
    const [loading, setLoading] = useState(true)

    const loadJobs = async () => {
        try {
            const data = await getJobs()
            setJobs(data)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        loadJobs()

        // 🔁 polling
        const interval = setInterval(loadJobs, 4000)
        return () => clearInterval(interval)
    }, [])

    return (
        <div className="jobs-page">

            {/* HEADER */}
            <div className="jobs-page__header">
                <h2>Processing</h2>
                <span>{jobs.length} jobs</span>
            </div>

            {/* LOADING */}
            {loading && (
                <div className="jobs-page__center">
                    <Spinner size="lg" />
                </div>
            )}

            {/* GRID */}
            {!loading && jobs.length > 0 && (
                <div className="jobs-page__grid">

                    {jobs.map(job => {
                        // ⚠️ fake photo для PhotoCard
                        const fakePhoto: Photo = {
                            id: job.photo_id,
                            file_path: job.file_path,
                            created_at: job.created_at,
                        } as Photo

                        return (
                            <div key={job.id} className="job-tile">

                                <PhotoCard photo={fakePhoto} />

                                {/* STATUS BLOCK */}
                                <div className="job-tile__meta">

                                    <div className={`job-tile__phase job-tile__phase--${job.phase}`}>
                                        Phase: {job.phase}
                                    </div>

                                    <div className="job-tile__tasks">
                                        {job.tasks}
                                    </div>

                                    <div className="job-tile__date">
                                        {new Date(job.created_at).toLocaleString()}
                                    </div>

                                </div>
                            </div>
                        )
                    })}

                </div>
            )}

            {/* EMPTY */}
            {!loading && jobs.length === 0 && (
                <div className="jobs-page__center">
                    No active jobs
                </div>
            )}
        </div>
    )
}