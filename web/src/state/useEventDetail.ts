"use client";

import { useEffect, useState } from "react";
import { fetchEventDetail } from "@/lib/api";
import type { RawEventReport } from "@/lib/types";

interface Resultado {
  clusterKey: string;
  reportes: RawEventReport[];
}

/**
 * "N de 3 fuentes confirman" y el historial de soluciones (pantallas 1b/2a)
 * son los únicos lugares que necesitan la lista de reportes por fuente de
 * un evento -- pedirla para las 8 filas de la lista normal sería un
 * fetch por fila cada 30s sin necesidad (ver lib/api.ts). Se pide solo
 * para el evento que está activamente en aviso/alerta.
 */
export function useEventDetail(clusterKey: string | null): RawEventReport[] | null {
  const [resultado, setResultado] = useState<Resultado | null>(null);

  useEffect(() => {
    if (!clusterKey) return;
    let cancelado = false;
    fetchEventDetail(clusterKey)
      .then((detalle) => {
        if (!cancelado) setResultado({ clusterKey, reportes: detalle.reports });
      })
      .catch(() => {
        if (!cancelado) setResultado({ clusterKey, reportes: [] });
      });
    return () => {
      cancelado = true;
    };
  }, [clusterKey]);

  // Si clusterKey cambió y el fetch para el nuevo aún no resuelve, el
  // resultado guardado queda "viejo" (de otra clave) -- se descarta acá
  // en vez de resetear el estado sincrónicamente dentro del efecto.
  if (!clusterKey || resultado?.clusterKey !== clusterKey) return null;
  return resultado.reportes;
}
