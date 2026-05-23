import { describe, test, expect } from 'vitest'
import en from '../locales/en.json'
import ru from '../locales/ru.json'
import es from '../locales/es.json'

function getAllKeys(obj: object, prefix = ''): string[] {
    return Object.entries(obj).flatMap(([k, v]) =>
        typeof v === 'object' && v !== null
            ? getAllKeys(v as object, `${prefix}${k}.`)
            : [`${prefix}${k}`]
    )
}

const enKeys = getAllKeys(en)
const ruKeys = getAllKeys(ru)
const esKeys = getAllKeys(es)

describe('locale completeness', () => {
    test('ru has all keys from en', () => {
        const missing = enKeys.filter(k => !ruKeys.includes(k))
        expect(missing).toEqual([])
    })

    test('es has all keys from en', () => {
        const missing = enKeys.filter(k => !esKeys.includes(k))
        expect(missing).toEqual([])
    })

    test('ru has no extra keys beyond en', () => {
        const extra = ruKeys.filter(k => !enKeys.includes(k))
        expect(extra).toEqual([])
    })

    test('es has no extra keys beyond en', () => {
        const extra = esKeys.filter(k => !enKeys.includes(k))
        expect(extra).toEqual([])
    })
})
