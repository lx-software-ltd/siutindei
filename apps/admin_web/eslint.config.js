const nextConfig = require('eslint-config-next');

const adminUiPlugin = {
  rules: {
    'no-hand-rolled-field-error': {
      meta: {
        type: 'problem',
        docs: {
          description:
            'Field errors go through AdminInlineError or AdminField.',
        },
        schema: [],
        messages: {
          handRolled:
            'Use AdminInlineError or AdminField for field errors.',
        },
      },
      create(context) {
        return {
          JSXAttribute(node) {
            if (
              node.name.type !== 'JSXIdentifier' ||
              node.name.name !== 'className'
            ) {
              return;
            }
            const source = context.sourceCode.getText(node);
            const hasSize = /text-(xs|sm)\b/.test(source);
            const hasRed = /text-red-600\b/.test(source);
            if (hasSize && hasRed) {
              context.report({ node, messageId: 'handRolled' });
            }
          },
        };
      },
    },
  },
};

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
    plugins: { 'admin-ui': adminUiPlugin },
    rules: {
      'admin-ui/no-hand-rolled-field-error': 'error',
    },
  },
  {
    files: ['src/**/*.tsx'],
    ignores: ['src/components/icons/**'],
    rules: {
      'no-restricted-syntax': [
        'error',
        {
          selector: 'JSXOpeningElement[name.name="svg"]',
          message: 'Add icons in src/components/icons/action-icons.tsx.',
        },
      ],
    },
  },
];
