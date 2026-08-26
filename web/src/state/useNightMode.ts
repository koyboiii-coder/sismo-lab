"use client";

import { useEffect } from "react";
import { NOCHE_FIN_HORA, NOCHE_INICIO_HORA } from "@/lib/constants";
import { esHorarioNocturno } from "@/lib/derive";
import { useClock } from "./useClock";

/**
 * handoff §5.1: 23:00-07:00 hora de Chile, el aviso aparece sin sonido y
 * al 45% de brillo. El brillo se aplica como filtro CSS global
 * (data-noche en <html>, ver theme/tokens.css) en vez de recalcular
 * colores: es una atenuación de pantalla física, no un tema distinto.
 *
 * `forzar` (Dashboard.tsx, ?noche=true|false) sobrescribe el cálculo por
 * hora -- para revisar el diseño a brillo pleno en desarrollo sin cambiar
 * la hora del sistema. `null`/`undefined` (el caso normal) deja el reloj
 * real a cargo.
 */
export function useNightMode(forzar: boolean | null = null): boolean {
  const ahora = useClock();
  const esNoche = forzar ?? esHorarioNocturno(ahora, NOCHE_INICIO_HORA, NOCHE_FIN_HORA);

  useEffect(() => {
    document.documentElement.dataset.noche = esNoche ? "true" : "false";
  }, [esNoche]);

  return esNoche;
}
