"use client";

import { ZoomMap } from "@/components/map/ZoomMap";
import {
  descripcionMmi,
  fuentesConfirmantes,
  haceTiempo,
  horaCLT,
  km,
  magnitud,
  mmiRomano,
  rumboDesdeHome,
  sinUbicar,
} from "@/lib/derive";
import type { RawEvent, RawEventReport } from "@/lib/types";
import { MercalliScale } from "./MercalliScale";
import styles from "./AlertLayout.module.css";

function etiquetaProfundidad(depthKm: number | null): string {
  if (depthKm == null) return "";
  if (depthKm < 35) return "SUPERFICIAL";
  if (depthKm <= 120) return "INTERMEDIA";
  return "PROFUNDA";
}

export function AlertLayout({
  evento,
  reportes,
  homeLat,
  homeLon,
  ahora,
}: {
  evento: RawEvent;
  reportes: RawEventReport[] | null;
  homeLat: number;
  homeLon: number;
  ahora: Date;
}) {
  const fuentes = reportes ? fuentesConfirmantes(reportes) : [evento.preferred_source];
  const mmiTexto = mmiRomano(evento.estimated_mmi);
  const sinUbicacion = sinUbicar(evento);
  const rumbo = !sinUbicacion ? rumboDesdeHome(homeLat, homeLon, evento.latitude!, evento.longitude!) : null;

  return (
    <div className={styles.pantalla}>
      <header className={styles.franjaSuperior}>
        <span className={styles.tituloFranja}>SISMO CERCA DE TU UBICACIÓN</span>
        <span className={styles.separadorOscuro} />
        <span className={styles.detalleFranja}>
          DETECTADO {haceTiempo(evento.origin_time, ahora.getTime())} · {horaCLT(evento.origin_time)}
        </span>
        <span className={styles.rellenoFranja} />
        <span className={styles.fuentesFranja}>
          {fuentes.join(" + ")} · {fuentes.length} DE 3 FUENTES CONFIRMAN
        </span>
      </header>

      <div className={styles.cuerpo}>
        <div className={styles.panelIzquierdo}>
          <div className={styles.filaHero}>
            <div className={styles.bloqueMagnitud}>
              <span className={styles.etiquetaM}>M</span>
              <span className={styles.cifraHero}>{magnitud(evento.magnitude)}</span>
            </div>
            <div className={styles.bloqueIntensidad}>
              <span className={styles.etiquetaIntensidad}>INTENSIDAD ESTIMADA AQUÍ</span>
              <div className={styles.filaMmi}>
                <span className={styles.cifraMmi}>{mmiTexto ?? "—"}</span>
                <span className={styles.etiquetaMercalli}>MERCALLI</span>
              </div>
              <p className={styles.fraseMmi}>{descripcionMmi(evento.estimated_mmi) ?? "Sin estimación disponible para esta ubicación."}</p>
              {evento.intensity_distance_saturated && (
                <p className={styles.notaSaturada}>
                  MMI ESTIMADA CON GEOMETRÍA DE FALLA DESCONOCIDA -- LEER COMO COTA, NO CIFRA EXACTA
                </p>
              )}
            </div>
          </div>

          <div className={styles.cajaPreliminar}>
            <span>MAGNITUD PRELIMINAR -- PUEDE CORREGIRSE EN LOS PRÓXIMOS MINUTOS</span>
            <span>ÚLTIMA REVISIÓN {horaCLT(evento.updated_at)} · REV. {evento.revision}</span>
          </div>

          <div className={styles.bloqueEpicentro}>
            <span className={styles.etiquetaEpicentro}>EPICENTRO</span>
            <span className={styles.textoEpicentro}>{sinUbicacion ? "SIN UBICAR" : evento.region ?? "región desconocida"}</span>
            {!sinUbicacion && (
              <span className={styles.coordenadas}>
                {evento.latitude!.toFixed(3)}°, {evento.longitude!.toFixed(3)}°
              </span>
            )}
          </div>

          <div className={styles.pieCeldas}>
            <div className={styles.celdaPie}>
              <span className={styles.etiquetaCelda}>DISTANCIA</span>
              <span className={styles.valorCelda}>{km(evento.distance_km)}</span>
              {rumbo && <span className={styles.subCelda}>AL {rumbo}</span>}
            </div>
            <div className={styles.celdaPie}>
              <span className={styles.etiquetaCelda}>PROFUNDIDAD</span>
              <span className={styles.valorCelda}>{km(evento.depth_km)}</span>
              <span className={styles.subCelda}>{etiquetaProfundidad(evento.depth_km)}</span>
            </div>
            <div className={styles.celdaPie}>
              <span className={styles.etiquetaCelda}>HORA LOCAL</span>
              <span className={styles.valorCelda}>{horaCLT(evento.origin_time)}</span>
            </div>
            <div className={styles.celdaPie}>
              <span className={styles.etiquetaCelda}>ESCALA MERCALLI</span>
              <MercalliScale mmi={evento.estimated_mmi} />
            </div>
          </div>
        </div>

        <div className={styles.panelDerecho}>
          <div className={styles.cabeceraDerecha}>
            <span>EPICENTRO Y DISTANCIA</span>
            <span className={styles.subCabeceraDerecha}>ANILLOS 50 / 100 / 200 KM</span>
          </div>
          <ZoomMap homeLat={homeLat} homeLon={homeLon} eventoLat={evento.latitude} eventoLon={evento.longitude} />
          <div className={styles.historial}>
            <span className={styles.tituloHistorial}>HISTORIAL DE SOLUCIONES</span>
            {reportes == null ? (
              <span className={styles.cargandoHistorial}>CARGANDO…</span>
            ) : reportes.length === 0 ? (
              <span className={styles.cargandoHistorial}>SIN REPORTES INDIVIDUALES DISPONIBLES</span>
            ) : (
              reportes
                .slice()
                .reverse()
                .map((r, i) => (
                  <div key={`${r.source}-${r.received_at}-${i}`} className={styles.filaHistorial}>
                    <span>{horaCLT(r.received_at)}</span>
                    <span>{r.source}</span>
                  </div>
                ))
            )}
          </div>
          <p className={styles.reglaSalida}>
            LA PANTALLA VUELVE AL ESTADO NORMAL 20 MIN DESPUÉS DE LA ÚLTIMA RÉPLICA M 3.5+
          </p>
        </div>
      </div>
    </div>
  );
}
