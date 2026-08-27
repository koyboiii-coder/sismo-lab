"use client";

import { useEffect, useState } from "react";
import { deleteNote, fetchNotes } from "@/lib/api";
import type { RawNote } from "@/lib/types";
import { NoteCanvas } from "./NoteCanvas";
import { NoteThumbnail } from "./NoteThumbnail";
import styles from "./NotesScreen.module.css";

type Vista = "lista" | "dibujando";

/**
 * Pizarra de notas manuscritas (punto 5 del feedback post-tablet -- ver
 * CLAUDE.md). Solo alcanzable desde dentro del modo exploración (ver
 * ExploreOverlay.tsx) -- comparte su mismo temporizador de inactividad,
 * extendido mientras haya trazos sin guardar (onTrazosSinGuardar).
 */
export function NotesScreen({
  onVolver,
  onTrazosSinGuardar,
}: {
  onVolver: () => void;
  onTrazosSinGuardar: (hay: boolean) => void;
}) {
  const [vista, setVista] = useState<Vista>("lista");
  const [notas, setNotas] = useState<RawNote[] | null>(null);
  const [aConfirmarBorrado, setAConfirmarBorrado] = useState<number | null>(null);

  function recargar() {
    fetchNotes()
      .then(setNotas)
      .catch(() => setNotas((actual) => actual ?? []));
  }

  useEffect(() => {
    recargar();
  }, []);

  function onBorrar(id: number) {
    if (aConfirmarBorrado !== id) {
      setAConfirmarBorrado(id);
      // Se cancela sola si no se confirma pronto -- para que un botón no
      // quede para siempre en modo "¿seguro?" por una nota que nadie
      // termina de borrar.
      setTimeout(() => setAConfirmarBorrado((actual) => (actual === id ? null : actual)), 3000);
      return;
    }
    setAConfirmarBorrado(null);
    // Optimista: desaparece de la lista ya mismo, sin esperar la
    // respuesta -- es una pizarra personal, no hay nada que reconciliar
    // si la red está lenta.
    setNotas((actual) => actual?.filter((n) => n.id !== id) ?? actual);
    deleteNote(id).catch(() => recargar());
  }

  function cancelarDibujo() {
    onTrazosSinGuardar(false);
    setVista("lista");
  }

  if (vista === "dibujando") {
    return (
      <div className={styles.pantalla}>
        <div className={styles.encabezado}>
          <span className={styles.titulo}>NUEVA NOTA</span>
          <button className={styles.botonTexto} onClick={cancelarDibujo}>
            CANCELAR
          </button>
        </div>
        <div className={styles.areaDibujo}>
          <NoteCanvas
            onGuardado={() => {
              recargar();
              setVista("lista");
            }}
            onTrazosSinGuardar={onTrazosSinGuardar}
          />
        </div>
      </div>
    );
  }

  return (
    <div className={styles.pantalla}>
      <div className={styles.encabezado}>
        <span className={styles.titulo}>NOTAS</span>
        <button className={styles.botonTexto} onClick={onVolver}>
          VOLVER
        </button>
      </div>
      <button className={styles.botonNueva} onClick={() => setVista("dibujando")}>
        + NUEVA NOTA
      </button>
      <div className={styles.grilla}>
        {notas == null && <span className={styles.vacio}>CARGANDO…</span>}
        {notas?.length === 0 && <span className={styles.vacio}>SIN NOTAS GUARDADAS</span>}
        {notas?.map((n) => (
          <div key={n.id} className={styles.tarjeta}>
            <NoteThumbnail strokes={n.strokes} className={styles.miniatura} />
            <div className={styles.piePie}>
              <span className={styles.fecha}>
                {new Date(n.created_at).toLocaleString("es-CL", { dateStyle: "short", timeStyle: "short" })}
              </span>
              <button className={styles.botonBorrar} onClick={() => onBorrar(n.id)}>
                {aConfirmarBorrado === n.id ? "¿SEGURO? TOCA DE NUEVO" : "BORRAR"}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
