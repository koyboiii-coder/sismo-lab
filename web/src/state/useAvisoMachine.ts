"use client";

/**
 * Máquina de estados de la escalera de aviso -- handoff §5.1. El backend
 * no expone un objeto `aviso` (ver lib/types.ts): esto lo deriva de
 * estimated_mmi/magnitude por evento (lib/derive.ts:nivelAviso).
 *
 * Reglas implementadas:
 * - Un aviso por sismo: una vez abierta la ventana para un cluster_key,
 *   las revisiones de ESE evento actualizan el contenido en el lugar, no
 *   abren una segunda ventana.
 * - Escalada en sitio: si el nivel de un evento activo sube de 2 a 3, el
 *   popup arranca su cuenta de 45s desde cero en ese momento.
 * - El nivel nunca se muestra hacia abajo (igual que
 *   daemon/alerts.py:should_notify -- no se re-notifica por una revisión
 *   que no cruza un umbral nuevo), aunque la cifra de magnitud/MMI sí se
 *   actualiza en vivo con cada revisión.
 * - Salida del estado de alerta: 20 min sin una réplica M>=3.5 (handoff
 *   §4). Simplificación deliberada: no hay clustering espacial de
 *   réplicas en el cliente (eso es trabajo de dedup.py sobre cluster_key,
 *   no de esta UI) -- cualquier evento significativo M>=3.5 posterior al
 *   inicio de la ventana extiende la salida. Es conservador: en una
 *   secuencia sísmica real activa, esto mantiene la pantalla en alerta un
 *   poco más de lo estrictamente necesario, nunca menos.
 *
 * Todo lo que se muestra se deriva puramente de `ventana` + `ahoraMs`,
 * ambos useState (no una ref leída/mutada durante el render): solo el
 * efecto que reacciona a `eventos` decide cuándo abrir/escalar una
 * ventana, vía setVentana.
 */
import { useEffect, useState } from "react";
import {
  ALERTA_REPLICA_MAGNITUD_MIN,
  ALERTA_SALIDA_MINUTOS,
  DURACION_AVISO_NIVEL2_S,
  DURACION_AVISO_NIVEL3_S,
} from "@/lib/constants";
import { nivelAviso, type NivelAviso } from "@/lib/derive";
import { reproducirTonoAlerta } from "@/lib/sound";
import type { RawEvent } from "@/lib/types";

interface Ventana {
  clusterKey: string;
  nivelMostrado: NivelAviso;
  abiertoEnMs: number;
  cerradoManualmente: boolean;
}

export interface EstadoAviso {
  nivel: NivelAviso;
  evento: RawEvent | null;
  abiertoEnMs: number | null;
  cierraEnMs: number | null;
  enAlerta: boolean; // layout 1b activo (popup de 45s ya terminado)
  cerrarPopupAhora: () => void;
}

const SIN_AVISO: Pick<EstadoAviso, "nivel" | "evento" | "abiertoEnMs" | "cierraEnMs" | "enAlerta"> = {
  nivel: 1,
  evento: null,
  abiertoEnMs: null,
  cierraEnMs: null,
  enAlerta: false,
};

const SIN_ACCION = () => {};

export function useAvisoMachine(eventos: RawEvent[], silencioNocturno: boolean): EstadoAviso {
  const [ventana, setVentana] = useState<Ventana | null>(null);
  const [ahoraMs, setAhoraMs] = useState<number>(() => Date.now());
  // Última lista de `eventos` ya procesada, para el patrón "ajustar estado
  // durante el render" (recomendado por React para derivar estado de un
  // prop sin un useEffect de por medio -- evita el pase de render extra
  // que tendría un efecto, y de paso evita el setState-en-efecto que el
  // linter de React 19 marca como error). El sonido es un efecto real
  // aparte más abajo: reproducir audio SÍ es un efecto secundario externo,
  // no debe ejecutarse durante el render.
  const [eventosProcesados, setEventosProcesados] = useState<RawEvent[] | null>(null);
  const [avisoParaSonar, setAvisoParaSonar] = useState<string | null>(null);

  if (eventos !== eventosProcesados) {
    setEventosProcesados(eventos);

    const candidatos = eventos
      .filter((e) => nivelAviso(e) >= 2)
      .slice()
      .sort((a, b) => new Date(b.origin_time).getTime() - new Date(a.origin_time).getTime());
    const principal = candidatos[0];

    if (principal) {
      const nivelCandidato = nivelAviso(principal);
      const origenMs = new Date(principal.origin_time).getTime();

      if (!ventana || ventana.clusterKey !== principal.cluster_key) {
        // Evento nuevo (o el anterior ya terminó): solo abrir ventana si
        // sigue siendo "reciente" -- si estamos cargando 48h de historial
        // al montar la página no hay que reabrir avisos de hace horas.
        const antiguedadS = (ahoraMs - origenMs) / 1000;
        const ventanaMaximaS =
          nivelCandidato === 3
            ? DURACION_AVISO_NIVEL3_S + ALERTA_SALIDA_MINUTOS * 60
            : DURACION_AVISO_NIVEL2_S;
        if (antiguedadS <= ventanaMaximaS) {
          setVentana({ clusterKey: principal.cluster_key, nivelMostrado: nivelCandidato, abiertoEnMs: origenMs, cerradoManualmente: false });
          if (nivelCandidato === 3) setAvisoParaSonar(`${principal.cluster_key}:${nivelCandidato}`);
        }
      } else if (nivelCandidato > ventana.nivelMostrado) {
        // Escalada en sitio: 2 -> 3 reinicia el popup desde ahora.
        setVentana({ ...ventana, nivelMostrado: nivelCandidato, abiertoEnMs: ahoraMs, cerradoManualmente: false });
        setAvisoParaSonar(`${principal.cluster_key}:${nivelCandidato}`);
      }
    }
  }

  useEffect(() => {
    if (avisoParaSonar && !silencioNocturno) reproducirTonoAlerta();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [avisoParaSonar]);

  // Reloj propio para que las cuentas regresivas avancen sin depender de
  // que lleguen nuevos eventos.
  useEffect(() => {
    const id = setInterval(() => setAhoraMs(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const cerrarPopupAhora = () => setVentana((actual) => (actual ? { ...actual, cerradoManualmente: true } : actual));

  if (!ventana) return { ...SIN_AVISO, cerrarPopupAhora: SIN_ACCION };

  const eventoActual = eventos.find((e) => e.cluster_key === ventana.clusterKey) ?? null;
  if (!eventoActual) return { ...SIN_AVISO, cerrarPopupAhora: SIN_ACCION };

  const elapsedS = ventana.cerradoManualmente ? Infinity : (ahoraMs - ventana.abiertoEnMs) / 1000;

  if (ventana.nivelMostrado === 2) {
    if (elapsedS >= DURACION_AVISO_NIVEL2_S) return { ...SIN_AVISO, cerrarPopupAhora: SIN_ACCION };
    return {
      nivel: 2,
      evento: eventoActual,
      abiertoEnMs: ventana.abiertoEnMs,
      cierraEnMs: ventana.abiertoEnMs + DURACION_AVISO_NIVEL2_S * 1000,
      enAlerta: false,
      cerrarPopupAhora,
    };
  }

  // nivel 3
  if (elapsedS < DURACION_AVISO_NIVEL3_S) {
    return {
      nivel: 3,
      evento: eventoActual,
      abiertoEnMs: ventana.abiertoEnMs,
      cierraEnMs: ventana.abiertoEnMs + DURACION_AVISO_NIVEL3_S * 1000,
      enAlerta: false,
      cerrarPopupAhora,
    };
  }

  // Popup terminado: estado de alerta (1b) hasta 20 min sin réplica M>=3.5.
  const ultimaReplicaMs = eventos
    .filter((e) => (e.magnitude ?? 0) >= ALERTA_REPLICA_MAGNITUD_MIN && e.is_significant)
    .map((e) => new Date(e.origin_time).getTime())
    .filter((t) => t >= ventana.abiertoEnMs)
    .reduce((max, t) => Math.max(max, t), ventana.abiertoEnMs);

  const salidaMs = ultimaReplicaMs + ALERTA_SALIDA_MINUTOS * 60_000;
  if (ahoraMs > salidaMs) return { ...SIN_AVISO, cerrarPopupAhora: SIN_ACCION };

  return {
    nivel: 3,
    evento: eventoActual,
    abiertoEnMs: ventana.abiertoEnMs,
    cierraEnMs: salidaMs,
    enAlerta: true,
    cerrarPopupAhora,
  };
}
