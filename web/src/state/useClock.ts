"use client";

import { useEffect, useState } from "react";

/** Reloj de 1 Hz para la hora CLT de la barra superior y para forzar el
 * recálculo de "hace X" en toda la UI. */
export function useClock(): Date {
  const [ahora, setAhora] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setAhora(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  return ahora;
}
