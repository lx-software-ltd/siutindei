'use client';

import { useMemo, useState } from 'react';

import type { LanguageCode } from '../../lib/translations';
import { languageOptions } from '../../lib/translations';
import { Input } from './input';
import { Label } from './label';
import { Textarea } from './textarea';

interface LanguageToggleInputProps {
  id: string;
  label: string;
  values: Record<LanguageCode, string>;
  onChange: (language: LanguageCode, value: string) => void;
  description?: string;
  multiline?: boolean;
  rows?: number;
  required?: boolean;
  hasError?: boolean;
  inputClassName?: string;
  readOnly?: boolean;
}

export function LanguageToggleInput({
  id,
  label,
  values,
  onChange,
  description,
  multiline = false,
  rows = 3,
  required = false,
  hasError = false,
  inputClassName = '',
  readOnly = false,
}: LanguageToggleInputProps) {
  const [activeLanguage, setActiveLanguage] = useState<LanguageCode>('en');

  const activeValue = values[activeLanguage] ?? '';

  const hasValueByLanguage = useMemo(() => {
    const result: Record<LanguageCode, boolean> = {
      en: false,
      zh: false,
      yue: false,
    };
    for (const option of languageOptions) {
      result[option.code] = Boolean(values[option.code]?.trim());
    }
    return result;
  }, [values]);

  const input = multiline ? (
    <Textarea
      id={id}
      rows={rows}
      value={activeValue}
      readOnly={readOnly}
      aria-readonly={readOnly || undefined}
      onChange={(event) => {
        if (!readOnly) {
          onChange(activeLanguage, event.target.value);
        }
      }}
      className={inputClassName}
      aria-invalid={hasError || undefined}
    />
  ) : (
    <Input
      id={id}
      value={activeValue}
      readOnly={readOnly}
      aria-readonly={readOnly || undefined}
      onChange={(event) => {
        if (!readOnly) {
          onChange(activeLanguage, event.target.value);
        }
      }}
      className={inputClassName}
      aria-invalid={hasError || undefined}
    />
  );

  return (
    <div className='space-y-1'>
      <div className='flex flex-wrap items-start justify-between gap-3'>
        <Label className='mb-0' htmlFor={id}>
          {label}
          {required ? (
            <span className='ml-1 text-red-500' aria-hidden='true'>
              *
            </span>
          ) : null}
        </Label>
        <div className='flex items-center gap-2'>
          {languageOptions.map((option) => {
            const isActive = option.code === activeLanguage;
            const hasValue = hasValueByLanguage[option.code];
            return (
              <button
                key={option.code}
                type='button'
                onClick={() => setActiveLanguage(option.code)}
                className={`relative flex h-5 items-center justify-center rounded border px-1 py-0 box-border transition ${
                  isActive
                    ? 'border-slate-400 bg-slate-50 ring-2 ring-slate-200'
                    : 'border-slate-200 hover:border-slate-300'
                }`}
                aria-pressed={isActive}
                aria-label={`Select ${option.label}`}
                title={option.label}
                data-has-value={hasValue}
              >
                <img
                  src={option.flagSrc}
                  alt={`${option.label} flag`}
                  width={20}
                  height={14}
                  loading='lazy'
                />
                {hasValue ? (
                  <span className='absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full border border-white bg-emerald-500' />
                ) : null}
              </button>
            );
          })}
        </div>
      </div>
      {description ? (
        <p className='text-xs text-slate-500'>{description}</p>
      ) : null}
      {input}
    </div>
  );
}
