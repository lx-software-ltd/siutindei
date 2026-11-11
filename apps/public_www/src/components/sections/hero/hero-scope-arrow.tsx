'use client';

import { useEffect, useRef } from 'react';

import {
  scopeArrow,
  type ArrowBox,
} from '@/lib/small-world/scope-arrow';

const INK = '#2e1d12';
const DESKTOP_QUERY = '(min-width: 768px)';

function relativeBox(element: HTMLElement, origin: DOMRect): ArrowBox {
  const rect = element.getBoundingClientRect();
  return {
    left: rect.left - origin.left,
    top: rect.top - origin.top,
    right: rect.right - origin.left,
    bottom: rect.bottom - origin.top,
  };
}

function lastVisibleSign(hero: HTMLElement): HTMLElement | null {
  const signs = hero.querySelectorAll('.hero-scope-sign');
  for (let index = signs.length - 1; index >= 0; index -= 1) {
    const sign = signs[index];
    if (!(sign instanceof HTMLElement)) {
      continue;
    }
    if (getComputedStyle(sign).display === 'none') {
      continue;
    }
    if (sign.getBoundingClientRect().height >= 8) {
      return sign;
    }
  }
  return null;
}

function textRight(element: HTMLElement): number {
  const range = document.createRange();
  range.selectNodeContents(element);
  let right = element.getBoundingClientRect().left;
  for (const rect of range.getClientRects()) {
    right = Math.max(right, rect.right);
  }
  return right;
}

/**
 * Draws the desktop arrow after layout, because the struck words and the
 * plates move with the viewport and the language.
 */
export function HeroScopeArrow() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const hero = canvas?.closest('.small-world-hero');
    if (!canvas || !(hero instanceof HTMLElement)) {
      return undefined;
    }
    if (typeof window.matchMedia !== 'function') {
      return undefined;
    }
    const media = window.matchMedia(DESKTOP_QUERY);
    let cancelled = false;

    const draw = () => {
      if (cancelled) {
        return;
      }
      const context = canvas.getContext('2d');
      if (!context) {
        return;
      }
      const bounds = hero.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      const width = Math.max(1, Math.round(bounds.width));
      const height = Math.max(1, Math.round(bounds.height));
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
      context.clearRect(0, 0, width, height);
      if (!media.matches || bounds.width === 0) {
        return;
      }
      const word = hero.querySelector('[data-scope-strike]');
      const sign = lastVisibleSign(hero);
      const heading = hero.querySelector('h1');
      if (
        !(word instanceof HTMLElement)
        || !(sign instanceof HTMLElement)
        || !(heading instanceof HTMLElement)
      ) {
        return;
      }
      const signBox = relativeBox(sign, bounds);
      if (signBox.bottom - signBox.top < 8) {
        return;
      }
      const arrow = scopeArrow({
        word: relativeBox(word, bounds),
        sign: signBox,
        headingRight: textRight(heading) - bounds.left,
        headingBottom: heading.getBoundingClientRect().bottom - bounds.top,
        width,
      });
      if (!arrow) {
        return;
      }
      context.strokeStyle = INK;
      context.lineWidth = 3.5;
      context.lineCap = 'round';
      context.lineJoin = 'round';
      context.beginPath();
      context.moveTo(arrow.start.x, arrow.start.y);
      context.bezierCurveTo(
        arrow.startControls[0].x,
        arrow.startControls[0].y,
        arrow.startControls[1].x,
        arrow.startControls[1].y,
        arrow.corner.x,
        arrow.corner.y,
      );
      context.bezierCurveTo(
        arrow.endControls[0].x,
        arrow.endControls[0].y,
        arrow.endControls[1].x,
        arrow.endControls[1].y,
        arrow.end.x,
        arrow.end.y,
      );
      context.stroke();
      const [leftBarb, tip, rightBarb] = arrow.head;
      context.beginPath();
      context.moveTo(leftBarb.x, leftBarb.y);
      context.lineTo(tip.x, tip.y);
      context.lineTo(rightBarb.x, rightBarb.y);
      context.stroke();
    };

    draw();
    let observer: ResizeObserver | null = null;
    if (typeof ResizeObserver === 'function') {
      observer = new ResizeObserver(draw);
      observer.observe(hero);
      const signs = hero.querySelector('.hero-scope-signs');
      if (signs) {
        observer.observe(signs);
      }
    }
    media.addEventListener('change', draw);
    if (document.fonts) {
      void document.fonts.ready.then(draw);
    }
    return () => {
      cancelled = true;
      observer?.disconnect();
      media.removeEventListener('change', draw);
    };
  }, []);

  return (
    <canvas ref={canvasRef} className="hero-scope-arrow" aria-hidden="true" />
  );
}
