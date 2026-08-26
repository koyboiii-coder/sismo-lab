"use client";

import { Component, type ReactNode } from "react";
import { descripcionMmi, horaCLT, km, magnitud, mmiRomano } from "@/lib/derive";
import type { RawEvent } from "@/lib/types";
import styles from "./AlertErrorBoundary.module.css";

interface Props {
  evento: RawEvent;
  children: ReactNode;
}

interface State {
  fallo: boolean;
}

/**
 * Última línea de defensa de la pantalla más crítica del sistema: si algo
 * revienta al renderizar AlertLayout (un campo con forma inesperada, un
 * bug futuro), esto evita que Next reemplace toda la pantalla por su
 * fallback genérico ("This page couldn't load", sin ningún dato). En un
 * sismo real, mostrar magnitud/distancia/MMI a medias es preferible a no
 * mostrar nada -- ver CLAUDE.md.
 *
 * Solo envuelve <AlertLayout>: los datos del fallback (`evento`) llegan
 * por prop, no por lectura del subárbol que falló, así que siguen
 * disponibles aunque ese subárbol nunca haya terminado de montar.
 */
export class AlertErrorBoundary extends Component<Props, State> {
  state: State = { fallo: false };

  static getDerivedStateFromError(): State {
    return { fallo: true };
  }

  componentDidCatch(error: unknown, info: { componentStack?: string | null }) {
    console.error("AlertLayout falló al renderizar, mostrando fallback mínimo", error, info.componentStack);
  }

  render() {
    if (!this.state.fallo) return this.props.children;

    const { evento } = this.props;
    const mmiTexto = mmiRomano(evento.estimated_mmi);

    return (
      <div className={styles.pantalla} role="alert">
        <span className={styles.franja}>SISMO CERCA DE TU UBICACIÓN -- VISTA REDUCIDA POR UN ERROR</span>
        <div className={styles.cuerpo}>
          <div className={styles.celda}>
            <span className={styles.etiqueta}>MAGNITUD</span>
            <span className={styles.cifra}>M {magnitud(evento.magnitude)}</span>
          </div>
          <div className={styles.celda}>
            <span className={styles.etiqueta}>DISTANCIA</span>
            <span className={styles.cifra}>{km(evento.distance_km)}</span>
          </div>
          <div className={styles.celda}>
            <span className={styles.etiqueta}>MERCALLI AQUÍ</span>
            <span className={styles.cifra}>{mmiTexto ?? "—"}</span>
          </div>
          <div className={styles.celda}>
            <span className={styles.etiqueta}>HORA LOCAL</span>
            <span className={styles.cifra}>{horaCLT(evento.origin_time)}</span>
          </div>
        </div>
        <p className={styles.frase}>{descripcionMmi(evento.estimated_mmi) ?? "Sin estimación disponible para esta ubicación."}</p>
        <p className={styles.nota}>
          EL PANEL COMPLETO NO PUDO CARGAR. ESTOS DATOS SON LOS ÚLTIMOS RECIBIDOS PARA ESTE EVENTO.
        </p>
      </div>
    );
  }
}
