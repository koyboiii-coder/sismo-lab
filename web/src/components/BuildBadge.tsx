"use client";

import styles from "./BuildBadge.module.css";

/**
 * Commit que corre en *este* contenedor `web`, para confirmar de un
 * vistazo que un deploy realmente tomó -- el bug que motivó esto era
 * justo lo contrario: el contenedor llevaba 2h corriendo un build previo
 * al fix, sin nada que lo delatara (ver CLAUDE.md, decisiones sobre
 * `?escenario=alerta`). `NEXT_PUBLIC_GIT_SHA` se hornea en build time
 * (web/Dockerfile, vía infra/deploy.sh) -- no es una llamada a la API, así
 * que sigue mostrando algo incluso si el backend está caído.
 */
export function BuildBadge() {
  const sha = process.env.NEXT_PUBLIC_GIT_SHA || "unknown";
  return (
    <span className={styles.badge} aria-hidden="true">
      {sha}
    </span>
  );
}
