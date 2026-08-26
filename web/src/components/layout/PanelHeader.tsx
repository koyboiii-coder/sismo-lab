import styles from "./PanelHeader.module.css";

export function PanelHeader({ titulo, dato }: { titulo: string; dato?: string }) {
  return (
    <div className={styles.cabecera}>
      <span className={styles.titulo}>{titulo}</span>
      {dato && <span className={styles.dato}>{dato}</span>}
    </div>
  );
}
