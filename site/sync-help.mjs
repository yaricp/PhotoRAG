import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const siteDir = path.dirname(fileURLToPath(import.meta.url))
const repoDir = path.dirname(siteDir)
const sourceTopics = await readFile(path.join(repoDir, 'frontend/src/pages/HelpPage/topics.ts'), 'utf8')
const topicIds = [...sourceTopics.matchAll(/\{ id: '([^']+)' \}/g)].map(match => match[1])
const checkOnly = process.argv.includes('--check')

if (topicIds.length === 0 || new Set(topicIds).size !== topicIds.length) {
    throw new Error('Help topic IDs are missing or duplicated')
}

const outputDir = path.join(siteDir, 'help-content')
if (!checkOnly) await mkdir(outputDir, { recursive: true })

for (const lang of ['en', 'ru', 'es']) {
    const source = JSON.parse(await readFile(path.join(repoDir, `frontend/src/i18n/locales/${lang}.json`), 'utf8'))
    const help = source.help
    if (!help || !help.title || !help.examplesHeading || !help.topics) {
        throw new Error(`Incomplete ${lang} help translation`)
    }
    const translatedIds = Object.keys(help.topics)
    if (translatedIds.length !== topicIds.length || topicIds.some(id => !translatedIds.includes(id))) {
        throw new Error(`${lang} help topics differ from the application topic list`)
    }
    for (const id of topicIds) {
        const topic = help.topics[id]
        if (!['title', 'intro', 'body'].every(key => typeof topic[key] === 'string')) {
            throw new Error(`Incomplete ${lang} help topic: ${id}`)
        }
    }

    const output = JSON.stringify({
        title: help.title,
        examplesHeading: help.examplesHeading,
        topicOrder: topicIds,
        topics: help.topics,
    }, null, 2) + '\n'
    const file = path.join(outputDir, `${lang}.json`)
    if (checkOnly) {
        let existing
        try {
            existing = await readFile(file, 'utf8')
        } catch {
            throw new Error(`${file} is missing; run node site/sync-help.mjs`)
        }
        if (existing !== output) {
            throw new Error(`${file} is outdated; run node site/sync-help.mjs`)
        }
    } else {
        await writeFile(file, output)
    }
}

console.log(checkOnly ? 'Site help matches the application in EN/RU/ES' : 'Site help updated from the application in EN/RU/ES')
