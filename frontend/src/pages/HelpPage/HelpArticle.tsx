import React from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

interface Props {
    topic: string
}

// Render inline [text](url) markdown links. Internal /help/* paths use React Router Link.
function RichPara({ text }: { text: string }) {
    const parts: React.ReactNode[] = []
    const linkRe = /\[([^\]]+)\]\(((?:https?:\/\/|\/)[^)]+)\)/g
    let last = 0
    let m: RegExpExecArray | null
    while ((m = linkRe.exec(text)) !== null) {
        if (m.index > last) parts.push(text.slice(last, m.index))
        const href = m[2]
        const label = m[1]
        if (href.startsWith('http')) {
            parts.push(
                <a key={m.index} href={href} target="_blank" rel="noreferrer" className="help-article__link">
                    {label}
                </a>
            )
        } else {
            parts.push(
                <Link key={m.index} to={href} className="help-article__link">
                    {label}
                </Link>
            )
        }
        last = m.index + m[0].length
    }
    if (last < text.length) parts.push(text.slice(last))
    return <>{parts}</>
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
            {intro && <p className="help-article__intro"><RichPara text={intro} /></p>}
            {body.split('\n\n').map((para, i) => (
                <p key={i}><RichPara text={para} /></p>
            ))}
            {examples && (
                <>
                    <h2 className="help-article__examples-heading">{t('help.examplesHeading')}</h2>
                    {examples.split('\n\n').map((para, i) => (
                        <p key={i}><RichPara text={para} /></p>
                    ))}
                </>
            )}
        </article>
    )
}
