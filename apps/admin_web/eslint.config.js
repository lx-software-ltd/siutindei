const nextConfig = require('eslint-config-next');

module.exports = [
  ...nextConfig,
  {
    ignores: ['node_modules/**', 'e2e/**', 'playwright.config.ts'],
  },
  {
    rules: {
      '@next/next/no-img-element': 'off',
    },
  },
  {
    files: ['src/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-syntax': [
        'error',
        {
          selector: 'Literal[value=/text-xs text-red-600/]',
          message:
            'Use AdminInlineError or AdminField for field errors.',
        },
      ],
    },
  },
  {
    files: ['src/**/*.tsx'],
    ignores: ['src/components/icons/**'],
    rules: {
      'no-restricted-syntax': [
        'error',
        {
          selector: 'Literal[value=/text-xs text-red-600/]',
          message:
            'Use AdminInlineError or AdminField for field errors.',
        },
        {
          selector: 'JSXOpeningElement[name.name="svg"]',
          message:
            'Add icons in src/components/icons/action-icons.tsx.',
        },
      ],
    },
  },
];
