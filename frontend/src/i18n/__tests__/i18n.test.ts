import { describe, it, expect, afterEach } from 'vitest'
import i18n from '../index'

afterEach(() => {
    i18n.changeLanguage('en')
})

describe('i18n setup', () => {
    it('defaults to English', () => {
        expect(i18n.language).toBe('en')
    })

    it('translates a key in English', () => {
        expect(i18n.t('search.title')).toBe('Semantic Search')
    })

    it('switches to Russian', () => {
        i18n.changeLanguage('ru')
        expect(i18n.t('search.title')).toBe('Семантический поиск')
    })

    it('switches to Spanish', () => {
        i18n.changeLanguage('es')
        expect(i18n.t('search.title')).toBe('Búsqueda semántica')
    })

    it('translates wizard.stepInstallDeps.title in Russian', () => {
        i18n.changeLanguage('ru')
        expect(i18n.t('wizard.stepInstallDeps.title')).toBe('Установка зависимостей')
    })

    it('translates wizard.stepModelPicker.title in Spanish', () => {
        i18n.changeLanguage('es')
        expect(i18n.t('wizard.stepModelPicker.title')).toBe('Elegir modelos para descargar')
    })

    it('translates settings.title in Russian', () => {
        i18n.changeLanguage('ru')
        expect(i18n.t('settings.title')).toBe('Настройки')
    })
})
