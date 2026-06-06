import js from '@eslint/js'
import tseslint from 'typescript-eslint'
import reactHooks from 'eslint-plugin-react-hooks'

export default tseslint.config(
    js.configs.recommended,
    ...tseslint.configs.recommended,
    {
        plugins: { 'react-hooks': reactHooks },
        rules: {
            '@typescript-eslint/no-explicit-any': 'warn',
            '@typescript-eslint/no-unused-vars': ['error', { varsIgnorePattern: '^_', argsIgnorePattern: '^_', destructuredArrayIgnorePattern: '^_' }],
            'react-hooks/exhaustive-deps': 'warn',
            'react-hooks/rules-of-hooks': 'error',
        },
    },
    {
        // Test files — relax unused-var strictness (factory imports, mock helpers)
        files: ['**/__tests__/**', '**/*.test.ts', '**/*.test.tsx', 'src/test/**'],
        rules: {
            '@typescript-eslint/no-unused-vars': 'off',
            '@typescript-eslint/no-explicit-any': 'off',
        },
    },
    {
        ignores: ['out/**', 'dist-electron/**', 'node_modules/**', 'scripts/**'],
    }
)
