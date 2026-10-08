import nextConfig from 'eslint-config-next';

const eslintConfig = [
  ...nextConfig,
  {
    ignores: [
      'node_modules/**',
      '.next/**',
      'out/**',
      'maintenance/**',
      'public/scripts/**',
    ],
  },
  {
    rules: {
      '@next/next/no-img-element': 'off',
      'react-hooks/set-state-in-effect': 'off',
    },
  },
  {
    files: ['src/components/**/*.{ts,tsx}', 'src/app/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-syntax': [
        'error',
        {
          selector: 'JSXAttribute[name.name="dangerouslySetInnerHTML"]',
          message: 'Do not use dangerouslySetInnerHTML on the public site.',
        },
        {
          selector: 'CallExpression[callee.name="eval"]',
          message: 'Do not use eval on the public site.',
        },
        {
          selector: 'NewExpression[callee.name="Function"]',
          message: 'Do not use new Function on the public site.',
        },
        {
          selector: 'JSXAttribute[name.name="style"]',
          message: 'Do not set style= in public site components.',
        },
        {
          selector: 'JSXOpeningElement[name.name="svg"]',
          message: 'Store SVGs in public/images and reference /images/.',
        },
        {
          selector:
            'MemberExpression[object.object.name="process"][object.property.name="env"][property.name=/^NEXT_PUBLIC_/]',
          message: 'Read NEXT_PUBLIC_* from src/lib/site-config.ts.',
        },
      ],
    },
  },
];

export default eslintConfig;
