'use client';

import { useRef } from 'react';
import type { ChangeEvent } from 'react';

import { Button } from './button';

interface FileUploadButtonProps {
  id: string;
  accept?: string;
  multiple?: boolean;
  disabled?: boolean;
  onChange: (event: ChangeEvent<HTMLInputElement>) => void;
  buttonLabel?: string;
  selectedFileName?: string | null;
  emptyLabel?: string;
  containerClassName?: string;
  buttonClassName?: string;
  fileNameClassName?: string;
  inputAriaLabel?: string;
}

export function FileUploadButton({
  id,
  accept,
  multiple = false,
  disabled = false,
  onChange,
  buttonLabel = 'Choose file',
  selectedFileName,
  emptyLabel,
  containerClassName = '',
  buttonClassName = '',
  fileNameClassName = '',
  inputAriaLabel,
}: FileUploadButtonProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);

  const containerClasses = [
    'flex flex-wrap items-center gap-2',
    containerClassName,
  ]
    .filter(Boolean)
    .join(' ');

  const buttonClasses = ['w-fit', buttonClassName]
    .filter(Boolean)
    .join(' ');

  const fileNameClasses = [
    'text-sm text-ink-700',
    fileNameClassName,
  ]
    .filter(Boolean)
    .join(' ');

  const trimmedFileName = selectedFileName?.trim();
  const fileNameText =
    trimmedFileName && trimmedFileName.length > 0
      ? trimmedFileName
      : emptyLabel;

  function handleButtonClick() {
    if (disabled) {
      return;
    }
    inputRef.current?.click();
  }

  return (
    <div className={containerClasses}>
      <input
        id={id}
        ref={inputRef}
        type='file'
        accept={accept}
        multiple={multiple}
        onChange={onChange}
        disabled={disabled}
        aria-label={inputAriaLabel}
        className='sr-only'
      />
      <Button
        type='button'
        variant='secondary'
        onClick={handleButtonClick}
        disabled={disabled}
        className={buttonClasses}
      >
        {buttonLabel}
      </Button>
      {fileNameText ? (
        <span className={fileNameClasses}>{fileNameText}</span>
      ) : null}
    </div>
  );
}
