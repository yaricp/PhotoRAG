import React from 'react'
import { useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { HelpSidebar } from './HelpSidebar'
import { HelpArticle } from './HelpArticle'
import { VALID_TOPIC_IDS } from './topics'
import './HelpPage.css'

export function HelpPage() {
    const { topic = 'getting-started' } = useParams<{ topic: string }>()
    const { t } = useTranslation()
    const validTopic = VALID_TOPIC_IDS.has(topic) ? topic : 'getting-started'

    return (
        <div className="help-page" data-testid="page-help">
            <HelpSidebar currentTopic={validTopic} />
            <HelpArticle topic={validTopic} />
        </div>
    )
}
