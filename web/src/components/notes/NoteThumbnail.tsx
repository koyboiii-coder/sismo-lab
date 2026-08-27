"use client";

import { useEffect, useRef } from "react";
import { dibujarTrazos } from "@/lib/strokes";
import type { RawStroke } from "@/lib/types";

/** Miniatura de solo lectura de una nota guardada -- misma rutina de
 * dibujo que el lienzo en vivo (lib/strokes.ts), a cualquier tamaño. */
export function NoteThumbnail({ strokes, className }: { strokes: RawStroke[]; className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.max(1, Math.round(rect.width * dpr));
    canvas.height = Math.max(1, Math.round(rect.height * dpr));
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    dibujarTrazos(ctx, strokes, canvas.width, canvas.height, "#e8e4e1");
  }, [strokes]);

  return <canvas ref={canvasRef} className={className} />;
}
