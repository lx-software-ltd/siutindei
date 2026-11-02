import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const PUBLIC_DIR = resolve(__dirname, '../../public');
const LOGO_MARK = resolve(
  PUBLIC_DIR,
  'images/brand/siutindei-logo-mark.svg',
);
const FAVICON_SVG = resolve(PUBLIC_DIR, 'favicon.svg');
const FAVICON_ICO = resolve(PUBLIC_DIR, 'favicon.ico');

function readIcoDirectory(buffer: Buffer): Array<{
  width: number;
  height: number;
  isPng: boolean;
}> {
  const reserved = buffer.readUInt16LE(0);
  const type = buffer.readUInt16LE(2);
  const count = buffer.readUInt16LE(4);
  expect(reserved).toBe(0);
  expect(type).toBe(1);
  expect(count).toBeGreaterThan(0);

  const entries = [];
  for (let index = 0; index < count; index += 1) {
    const offset = 6 + index * 16;
    const widthByte = buffer.readUInt8(offset);
    const heightByte = buffer.readUInt8(offset + 1);
    const bytesInRes = buffer.readUInt32LE(offset + 8);
    const imageOffset = buffer.readUInt32LE(offset + 12);
    const payload = buffer.subarray(imageOffset, imageOffset + bytesInRes);
    entries.push({
      width: widthByte === 0 ? 256 : widthByte,
      height: heightByte === 0 ? 256 : heightByte,
      isPng: payload.subarray(0, 8).equals(
        Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
      ),
    });
  }
  return entries;
}

describe('public favicon assets', () => {
  it('keeps favicon.svg as a copy of the logo mark', () => {
    const logoMark = readFileSync(LOGO_MARK);
    const faviconSvg = readFileSync(FAVICON_SVG);
    expect(faviconSvg.equals(logoMark)).toBe(true);
  });

  it('stores the logo mark as a multi-size PNG ICO', () => {
    const entries = readIcoDirectory(readFileSync(FAVICON_ICO));
    expect(entries.map((entry) => `${entry.width}x${entry.height}`)).toEqual([
      '16x16',
      '32x32',
    ]);
    expect(entries.every((entry) => entry.isPng)).toBe(true);
    expect(readFileSync(FAVICON_ICO).length).toBeLessThan(15 * 1024);
  });
});
