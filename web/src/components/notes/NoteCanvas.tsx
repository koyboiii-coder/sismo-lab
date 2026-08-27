"use client";

import { useEffect, useRef, useState, type PointerEvent } from "react";
import { createNote } from "@/lib/api";
import { dibujarSegmentoEnVivo, dibujarTrazos } from "@/lib/strokes";
import type { RawStroke, RawStrokePoint } from "@/lib/types";
import styles from "./NoteCanvas.module.css";

const COLOR_TRAZO = "#e8e4e1"; // --tinta fija -- sin selector de color, fuera de alcance del pedido
const ANCHO_TRAZO_CSS_PX = 3;

/**
 * Lienzo de dibujo en vivo -- lápiz, dedo o mouse (PointerEvent unifica
 * los tres). Lo que se guarda es siempre el vector (arreglo de puntos),
 * nunca un bitmap: el canvas es solo la superficie de dibujo, tanto acá
 * como al reproducir una nota guardada (ver lib/strokes.ts, compartido
 * con NoteThumbnail.tsx).
 */
export function NoteCanvas({
  onGuardado,
  onTrazosSinGuardar,
}: {
  onGuardado: () => void;
  onTrazosSinGuardar: (hay: boolean) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const trazosRef = useRef<RawStroke[]>([]);
  const trazoActualRef = useRef<RawStrokePoint[] | null>(null);
  const inicioMsRef = useRef(0);
  // Recalculado en ajustarTamano -- ancho de trazo como fracción del
  // ancho del lienzo (ver lib/strokes.ts), no un valor fijo, para que se
  // vea igual de grueso sin importar el tamaño real del <canvas>.
  const anchoNormalizadoRef = useRef(0.0025);
  const [haySinGuardar, setHaySinGuardar] = useState(false);
  const [guardando, setGuardando] = useState(false);

  function redibujar() {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    dibujarTrazos(ctx, trazosRef.current, canvas.width, canvas.height, COLOR_TRAZO);
  }

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    function ajustarTamano() {
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.max(1, Math.round(rect.width * dpr));
      canvas.height = Math.max(1, Math.round(rect.height * dpr));
      anchoNormalizadoRef.current = ANCHO_TRAZO_CSS_PX / Math.max(1, rect.width);
      redibujar();
    }
    ajustarTamano();
    window.addEventListener("resize", ajustarTamano);
    return () => window.removeEventListener("resize", ajustarTamano);
  }, []);

  function puntoDesdeEvento(e: PointerEvent<HTMLCanvasElement>): RawStrokePoint {
    const rect = canvasRef.current!.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;
    // e.pressure es 0 en mouse y en la mayoría de dedo/lápiz sin presión
    // real -- 0.5 como valor neutro, no 0 (que leería como "sin fuerza en
    // absoluto" si algún día se usa para variar el ancho del trazo).
    const p = e.pressure > 0 ? e.pressure : 0.5;
    return { x, y, p, t: performance.now() - inicioMsRef.current };
  }

  function marcarSinGuardar(hay: boolean) {
    setHaySinGuardar(hay);
    onTrazosSinGuardar(hay);
  }

  function onPointerDown(e: PointerEvent<HTMLCanvasElement>) {
    e.currentTarget.setPointerCapture(e.pointerId);
    inicioMsRef.current = performance.now();
    trazoActualRef.current = [puntoDesdeEvento(e)];
  }

  function onPointerMove(e: PointerEvent<HTMLCanvasElement>) {
    const puntos = trazoActualRef.current;
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!puntos || !canvas || !ctx) return;
    const anterior = puntos[puntos.length - 1];
    const nuevo = puntoDesdeEvento(e);
    puntos.push(nuevo);
    dibujarSegmentoEnVivo(ctx, anterior, nuevo, anchoNormalizadoRef.current, canvas.width, canvas.height, COLOR_TRAZO);
  }

  function terminarTrazo() {
    const puntos = trazoActualRef.current;
    trazoActualRef.current = null;
    if (!puntos || puntos.length < 2) return; // un toque sin arrastre: no es un trazo
    trazosRef.current = [...trazosRef.current, { points: puntos, width: anchoNormalizadoRef.current }];
    marcarSinGuardar(true);
  }

  function deshacer() {
    trazosRef.current = trazosRef.current.slice(0, -1);
    marcarSinGuardar(trazosRef.current.length > 0);
    redibujar();
  }

  function limpiar() {
    trazosRef.current = [];
    marcarSinGuardar(false);
    redibujar();
  }

  async function guardar() {
    if (trazosRef.current.length === 0 || guardando) return;
    setGuardando(true);
    try {
      await createNote(trazosRef.current);
      trazosRef.current = [];
      marcarSinGuardar(false);
      redibujar();
      onGuardado();
    } catch {
      // Sin reintento automático: el dibujo queda intacto (nada se
      // pierde) para reintentar con el mismo botón.
    } finally {
      setGuardando(false);
    }
  }

  return (
    <div className={styles.contenedor}>
      <canvas
        ref={canvasRef}
        className={styles.lienzo}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={terminarTrazo}
        onPointerCancel={terminarTrazo}
        onPointerLeave={terminarTrazo}
      />
      <div className={styles.barra}>
        <button className={styles.boton} onClick={deshacer} disabled={!haySinGuardar}>
          DESHACER
        </button>
        <button className={styles.boton} onClick={limpiar} disabled={!haySinGuardar}>
          LIMPIAR
        </button>
        <span className={styles.relleno} />
        {haySinGuardar && <span className={styles.sinGuardar}>SIN GUARDAR</span>}
        <button
          className={`${styles.boton} ${styles.botonGuardar}`}
          onClick={guardar}
          disabled={!haySinGuardar || guardando}
        >
          {guardando ? "GUARDANDO…" : "GUARDAR"}
        </button>
      </div>
    </div>
  );
}
