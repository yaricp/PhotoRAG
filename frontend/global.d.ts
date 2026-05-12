export { }

declare module '*.css' {}

declare global {
    interface Window {
        api: {
            selectFolder: () => Promise<string | null>
        }
    }
}