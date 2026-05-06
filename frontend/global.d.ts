export { }

declare global {
    interface Window {
        api: {
            selectFolder: () => Promise<string | null>
        }
    }
}