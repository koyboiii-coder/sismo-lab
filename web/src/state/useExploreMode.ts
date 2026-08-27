"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  EXPLORACION_AVISO_DESCARTE_S,
  EXPLORACION_INACTIVIDAD_S,
  EXPLORACION_PRESION_LARGA_MS,
} from "@/lib/constants";

export interface EstadoExploracion {
  activo: boolean;
  /** Últimos EXPLORACION_AVISO_DESCARTE_S antes de descartar una nota sin
   * guardar -- ver NoteCanvas.tsx. */
  avisoDescarte: boolean;
  segundosRestantes: number | null;
  registrarActividad: () => void;
  marcarTrazosSinGuardar: (hay: boolean) => void;
  /** Entra directo, sin pasar por la presión larga -- usado por el botón
   * NOTAS (siempre visible, ver ExploreOverlay.tsx) para que abrir la
   * pizarra ya deje el modo con su reloj de inactividad/salida normal en
   * marcha, en vez de vivir fuera de ese ciclo. */
  activar: () => void;
  salir: () => void;
}

/**
 * Único punto de entrada táctil del dashboard (puntos 4/5 del feedback
 * post-tablet -- CLAUDE.md). Entrada deliberada: mantener presionado
 * ~800ms, no un simple tap -- un roce contra la pared no debe sacar el
 * dashboard de su lectura normal, sobre todo si ocurre justo cuando
 * alguien mira si hubo un sismo. Salida automática por inactividad --
 * nunca depende de que alguien "cierre bien" el modo, el kiosco tiene que
 * poder quedar solo.
 *
 * `deshabilitado` (Dashboard.tsx, true mientras aviso.nivel === 3) apaga
 * la entrada y fuerza la salida mientras el popup de emergencia o la
 * pantalla de alerta están activos: un toque ahí es para ESA pantalla.
 *
 * `hayTrazosSinGuardar` (NoteCanvas.tsx) extiende la salida: mientras haya
 * un trazo de nota sin guardar, no se fuerza la salida a los 2 min --
 * primero se avisa (avisoDescarte, últimos 30s) y solo entonces se
 * descarta. Escribir a mano toma más que mirar un mapa; sin esto se
 * perdía por el mismo umbral que cualquier otra exploración.
 *
 * El chequeo de inactividad vive DENTRO del callback del setInterval de
 * abajo (no en un useEffect reactivo aparte con `activo`/tiempos como
 * dependencia): un setState disparado por un timer externo es el patrón
 * que el lint de React 19 (react-hooks/set-state-in-effect) espera --
 * derivarlo en un efecto que reacciona a cada tick synchronamente es
 * exactamente lo que marca error (mismo motivo documentado en
 * useAvisoMachine.ts para su propio patrón de "ajustar estado durante el
 * render").
 */
export function useExploreMode(deshabilitado: boolean): EstadoExploracion {
  const [activo, setActivo] = useState(false);
  const [ultimaActividadMs, setUltimaActividadMs] = useState<number | null>(null);
  const [ahoraMs, setAhoraMs] = useState<number>(() => Date.now());
  const [hayTrazosSinGuardar, setHayTrazosSinGuardar] = useState(false);

  const salir = useCallback(() => {
    setActivo(false);
    setUltimaActividadMs(null);
    setHayTrazosSinGuardar(false);
  }, []);

  const registrarActividad = useCallback(() => setUltimaActividadMs(Date.now()), []);

  const activar = useCallback(() => {
    setActivo(true);
    setUltimaActividadMs(Date.now());
  }, []);

  // Espejo en refs: el tick de 1Hz (creado una sola vez, ver abajo)
  // necesita leer el valor MÁS RECIENTE de estos, no el capturado cuando
  // el efecto se montó. Asignar dentro de un efecto (sin dependencias:
  // corre tras cada render), no directo en el cuerpo del componente --
  // mutar un ref durante el render es justamente lo que el lint de
  // refs (react-hooks/refs) prohíbe.
  const activoRef = useRef(activo);
  const deshabilitadoRef = useRef(deshabilitado);
  const ultimaActividadRef = useRef(ultimaActividadMs);
  const hayTrazosRef = useRef(hayTrazosSinGuardar);
  useEffect(() => {
    activoRef.current = activo;
    deshabilitadoRef.current = deshabilitado;
    ultimaActividadRef.current = ultimaActividadMs;
    hayTrazosRef.current = hayTrazosSinGuardar;
  });

  useEffect(() => {
    const id = setInterval(() => {
      const ahora = Date.now();
      setAhoraMs(ahora);
      if (deshabilitadoRef.current) {
        if (activoRef.current) salir();
        return;
      }
      if (activoRef.current && ultimaActividadRef.current != null) {
        const inactividadS = (ahora - ultimaActividadRef.current) / 1000;
        const limiteS = EXPLORACION_INACTIVIDAD_S + (hayTrazosRef.current ? EXPLORACION_AVISO_DESCARTE_S : 0);
        if (inactividadS >= limiteS) salir();
      }
    }, 1000);
    return () => clearInterval(id);
  }, [salir]);

  // Presión larga global: activa el modo desde cualquier punto de la
  // pantalla sin que ningún componente necesite su propio listener.
  useEffect(() => {
    if (deshabilitado || activo) return;

    let timer: ReturnType<typeof setTimeout> | null = null;
    let inicioX = 0;
    let inicioY = 0;

    function limpiar() {
      if (timer) clearTimeout(timer);
      window.removeEventListener("pointerup", limpiar);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointercancel", limpiar);
    }

    function onMove(ev: PointerEvent) {
      // Umbral chico: distingue "mantener presionado" de arrastrar el
      // dedo (que no debe activar el modo, p. ej. un gesto accidental).
      if (Math.hypot(ev.clientX - inicioX, ev.clientY - inicioY) > 12) limpiar();
    }

    function onPointerDown(e: PointerEvent) {
      inicioX = e.clientX;
      inicioY = e.clientY;
      timer = setTimeout(() => {
        setActivo(true);
        setUltimaActividadMs(Date.now());
      }, EXPLORACION_PRESION_LARGA_MS);
      window.addEventListener("pointerup", limpiar);
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointercancel", limpiar);
    }

    window.addEventListener("pointerdown", onPointerDown);
    return () => {
      window.removeEventListener("pointerdown", onPointerDown);
      limpiar();
    };
  }, [deshabilitado, activo]);

  // Ya adentro: cualquier toque reinicia el reloj de inactividad.
  useEffect(() => {
    if (!activo) return;
    function onPointerDown() {
      registrarActividad();
    }
    window.addEventListener("pointerdown", onPointerDown);
    return () => window.removeEventListener("pointerdown", onPointerDown);
  }, [activo, registrarActividad]);

  const inactividadS = activo && ultimaActividadMs != null ? (ahoraMs - ultimaActividadMs) / 1000 : 0;
  const limiteS = EXPLORACION_INACTIVIDAD_S + (hayTrazosSinGuardar ? EXPLORACION_AVISO_DESCARTE_S : 0);
  const avisoDescarte = activo && hayTrazosSinGuardar && inactividadS >= EXPLORACION_INACTIVIDAD_S;
  const segundosRestantes = activo ? Math.max(0, Math.round(limiteS - inactividadS)) : null;

  return {
    activo,
    avisoDescarte,
    segundosRestantes,
    registrarActividad,
    marcarTrazosSinGuardar: setHayTrazosSinGuardar,
    activar,
    salir,
  };
}
