import styles from "./MercalliScale.module.css";

const NUMERALES = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"];

export function MercalliScale({ mmi }: { mmi: number | null }) {
  const activo = mmi != null ? Math.min(12, Math.max(1, Math.round(mmi))) : null;
  return (
    <div className={styles.escala}>
      {NUMERALES.map((num, i) => {
        const nivel = i + 1;
        const esActivo = nivel === activo;
        return (
          <span
            key={num}
            className={esActivo ? styles.celdaActiva : styles.celda}
            style={!esActivo ? { color: `color-mix(in srgb, var(--tinta) ${20 + i * 5}%, var(--tinta-4))` } : undefined}
          >
            {num}
          </span>
        );
      })}
    </div>
  );
}
