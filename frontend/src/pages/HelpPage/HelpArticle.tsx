import React from 'react'
import { useTranslation } from 'react-i18next'

interface Props {
    topic: string
}

export function HelpArticle({ topic }: Props) {
    const { t } = useTranslation()
    const title = t(`help.topics.${topic}.title`)
    const intro = t(`help.topics.${topic}.intro`)
    const body = t(`help.topics.${topic}.body`)
    const examples = t(`help.topics.${topic}.examples`)

    return (
        <article className="help-article" data-testid="help-article">
            <h1 className="help-article__title">{title}</h1>
            {intro && <p className="help-article__intro">{intro}</p>}
            {body.split('\n\n').map((para, i) => (
                <p key={i}>{para}</p>
            ))}
            {examples && (
                <>
                    <h2 className="help-article__examples-heading">{t('help.examplesHeading')}</h2>
                    {examples.split('\n\n').map((para, i) => (
                        <p key={i}>{para}</p>
                    ))}
                </>
            )}
        </article>
    )
}
