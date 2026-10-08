const nextConfig = require('eslint-config-next');

const adminUiPlugin = {
  rules: {
    'no-record-table-min-width': {
      meta: {
        type: 'problem',
        docs: {
          description: 'Record tables do not set a min-width utility.',
        },
        schema: [],
        messages: {
          minWidth:
            'Do not set min-w-* on a record table. Use the scroll container.',
        },
      },
      create(context) {
        return {
          JSXOpeningElement(node) {
            if (
              node.name.type !== 'JSXIdentifier' ||
              node.name.name !== 'table'
            ) {
              return;
            }
            const classAttr = node.attributes.find(
              (attr) =>
                attr.type === 'JSXAttribute' &&
                attr.name.type === 'JSXIdentifier' &&
                attr.name.name === 'className',
            );
            if (!classAttr) {
              return;
            }
            const source = context.sourceCode.getText(classAttr);
            if (/min-w-(?!0\b)/.test(source)) {
              context.report({ node: classAttr, messageId: 'minWidth' });
            }
          },
        };
      },
    },
    'no-expandable-row-border-x': {
      meta: {
        type: 'problem',
        docs: {
          description: 'Expandable rows do not use border-x utilities.',
        },
        schema: [],
        messages: {
          borderX:
            'Do not put border-x-* on an expandable row. Frame it with admin-row-framed.',
        },
      },
      create(context) {
        return {
          JSXOpeningElement(node) {
            if (
              node.name.type !== 'JSXIdentifier' ||
              node.name.name !== 'tr'
            ) {
              return;
            }
            const classAttr = node.attributes.find(
              (attr) =>
                attr.type === 'JSXAttribute' &&
                attr.name.type === 'JSXIdentifier' &&
                attr.name.name === 'className',
            );
            if (!classAttr) {
              return;
            }
            const source = context.sourceCode.getText(classAttr);
            if (/border-x-/.test(source)) {
              context.report({ node: classAttr, messageId: 'borderX' });
            }
          },
        };
      },
    },
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
    files: [
      'src/components/ui/admin-record-table.tsx',
      'src/components/ui/admin-data-table.tsx',
    ],
    plugins: { 'admin-ui': adminUiPlugin },
    rules: {
      'admin-ui/no-record-table-min-width': 'error',
    },
  },
  {
    files: ['src/components/ui/admin-expandable-row.tsx'],
    plugins: { 'admin-ui': adminUiPlugin },
    rules: {
      'admin-ui/no-expandable-row-border-x': 'error',
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
