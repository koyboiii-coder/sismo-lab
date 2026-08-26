"use client";

import { ALERTA_REPLICA_MAGNITUD_MIN, DURACION_AVISO_NIVEL3_S } from "@/lib/constants";
import {
  cuentaRegresiva,
  descripcionMmi,
  fuentesConfirmantes,
  haceTiempo,
  horaCLT,
  km,
  magnitud,
  mmiRomano,
} from "@/lib/derive";
import type { RawEvent, RawEventReport } from "@/lib/types";
import styles from "./AvisoPopup.module.css";

export function AvisoPopup({
  evento,
  eventosRelacionados,
  reportes,
  cierraEnMs,
  ahoraMs,
  silencioNocturno,
  onCerrar,
}: {
  evento: RawEvent;
  eventosRelacionados: RawEvent[];
  reportes: RawEventReport[] | null;
  cierraEnMs: number;
  ahoraMs: number;
  silencioNocturno: boolean;
  onCerrar: () => void;
}) {
  const restanteS = Math.max(0, Math.round((cierraEnMs - ahoraMs) / 1000));
  const progreso = Math.max(0, Math.min(1, restanteS / DURACION_AVISO_NIVEL3_S));
  const fuentes = reportes ? fuentesConfirmantes(reportes) : [evento.preferred_source];
  const mmiTexto = mmiRomano(evento.estimated_mmi);
  const origenMs = new Date(evento.origin_time).getTime();

  const replicas = eventosRelacionados.filter(
    (e) => e.cluster_key !== evento.cluster_key && (e.magnitude ?? 0) >= ALERTA_REPLICA_MAGNITUD_MIN && new Date(e.origin_time).getTime() > origenMs,
  );
  const minutosTranscurridos = Math.max(1, Math.round((ahoraMs - origenMs) / 60_000));

  return (
    <div className={styles.velo} role="alertdialog" aria-label="Sismo cerca de tu ubicación">
      <div className={styles.ventana}>
        <header className={styles.cabecera}>
          <span className={styles.puntoPulsante} style={silencioNocturno ? { animation: "none" } : undefined} aria-hidden />
          <span className={styles.titulo}>SISMO CERCA DE TU UBICACIÓN</span>
          <span className={styles.relleno} />
          <span className={styles.hace}>{haceTiempo(evento.origin_time, ahoraMs)} · {horaCLT(evento.origin_time)}</span>
        </header>

        <div className={styles.bloqueDatos}>
          <div className={styles.celdaMagnitud}>
            <span className={styles.etiquetaPequena}>MAGNITUD PRELIMINAR · {evento.magnitude_type ?? "Mw"}</span>
            <div className={styles.filaM}>
              <span className={styles.etiquetaM}>M</span>
              <span className={styles.cifraM}>{magnitud(evento.magnitude)}</span>
            </div>
            <span className={styles.fuentesConfirman}>
              {fuentes.join(" + ")} · {fuentes.length} DE 3 FUENTES CONFIRMAN
            </span>
          </div>
          <div className={styles.celdaIntensidad}>
            <span className={styles.etiquetaPequena}>INTENSIDAD ESTIMADA AQUÍ</span>
            <div className={styles.filaMmi}>
              <span className={styles.cifraMmi}>{mmiTexto ?? "—"}</span>
              <span className={styles.etiquetaMercalli}>MERCALLI</span>
            </div>
            <p className={styles.fraseMmi}>{descripcionMmi(evento.estimated_mmi) ?? "Sin estimación disponible."}</p>
          </div>
        </div>

        <div className={styles.rejilla}>
          <div className={styles.celdaRejilla}>
            <span className={styles.etiquetaCelda}>EPICENTRO</span>
            <span className={styles.epicentro}>{evento.region ?? "región desconocida"}</span>
          </div>
          <div className={styles.celdaRejilla}>
            <span className={styles.etiquetaCelda}>DISTANCIA</span>
            <span className={styles.valorRejilla}>{km(evento.distance_km)}</span>
          </div>
          <div className={styles.celdaRejilla}>
            <span className={styles.etiquetaCelda}>PROFUNDIDAD</span>
            <span className={styles.valorRejilla}>{km(evento.depth_km)}</span>
          </div>
          <div className={styles.celdaRejilla}>
            <span className={styles.etiquetaCelda}>RÉPLICAS M 3.5+</span>
            <span className={styles.valorRejilla}>
              {replicas.length} en {minutosTranscurridos} min
            </span>
          </div>
        </div>

        <div className={styles.pie}>
          <span className={styles.textoCierre}>
            EL AVISO SE CIERRA SOLO EN {cuentaRegresiva(restanteS)} Y EL TABLERO QUEDA EN ESTADO DE ALERTA
          </span>
          <div className={styles.barraProgreso}>
            <div className={styles.barraProgresoRelleno} style={{ width: `${progreso * 100}%` }} />
          </div>
          <button type="button" className={styles.boton} onClick={onCerrar}>
            TOCAR PARA CERRAR AHORA
          </button>
        </div>
      </div>

      <div className={styles.notasPie}>
        <p className={styles.notaAmbar}>
          NO ES ALERTA TEMPRANA -- este aviso llega después del sismo (5-90 s), depende de la publicación de CSN/USGS.
        </p>
        <p className={styles.notaNeutra}>
          POR QUÉ INTERRUMPE -- nadie mira la pantalla en el momento; esta ventana pone la respuesta al centro para
          quien gira la cabeza después de sentirlo.
        </p>
      </div>
    </div>
  );
}
