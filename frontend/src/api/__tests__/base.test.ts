it('falls back to localhost:8000 when no env var', async () => {
    const saved = import.meta.env.VITE_API_BASE_URL
    import.meta.env.VITE_API_BASE_URL = ''
    const { getBaseUrl } = await import('../base')
    const url = await getBaseUrl()
    expect(url).toBe('http://localhost:8000')
    import.meta.env.VITE_API_BASE_URL = saved
})