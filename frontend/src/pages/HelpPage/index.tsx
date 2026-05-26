import React, { useRef, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { HelpSidebar } from './HelpSidebar'
import { HelpArticle } from './HelpArticle'
import { VALID_TOPIC_IDS } from './topics'
import './HelpPage.css'

export function HelpPage() {
    const { topic = 'getting-started' } = useParams<{ topic: string }>()
    const validTopic = VALID_TOPIC_IDS.has(topic) ? topic : 'getting-started'
    const articleRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        articleRef.current?.scrollTo?.({ top: 0, behavior: 'smooth' })
    }, [validTopic])

    return (
        <div className="help-page" data-testid="page-help">
            <HelpSidebar currentTopic={validTopic} />
            <div className="help-article-scroll" ref={articleRef}>
                <HelpArticle topic={validTopic} />
            </div>
        </div>
    )
}
