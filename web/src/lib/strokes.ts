/**
 * Rutina única para convertir trazos guardados (arreglo de puntos
 * normalizados 0-1, ver types.ts:RawStroke) en píxeles de canvas -- la
 * comparte el lienzo en vivo (NoteCanvas.tsx) y las miniaturas de notas
 * guardadas (NoteThumbnail.tsx), así una nota se ve igual sin importar en
 * qué tamaño se dibujó o en qué tamaño se muestra después.
 */
import type { RawStroke, RawStrokePoint } from "./types";

export function dibujarTrazos(
  ctx: CanvasRenderingContext2D,
  trazos: RawStroke[],
  anchoPx: number,
  altoPx: number,
  color: string,
): void {
  ctx.strokeStyle = color;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  for (const trazo of trazos) {
    dibujarUnTrazo(ctx, trazo.points, trazo.width * anchoPx, anchoPx, altoPx);
  }
}

function dibujarUnTrazo(
  ctx: CanvasRenderingContext2D,
  puntos: RawStrokePoint[],
  lineWidthPx: number,
  anchoPx: number,
  altoPx: number,
): void {
  if (puntos.length < 2) return;
  ctx.lineWidth = lineWidthPx;
  ctx.beginPath();
  let anterior = { x: puntos[0].x * anchoPx, y: puntos[0].y * altoPx };
  ctx.moveTo(anterior.x, anterior.y);
  for (let i = 1; i < puntos.length; i++) {
    const actual = { x: puntos[i].x * anchoPx, y: puntos[i].y * altoPx };
    const medio = { x: (anterior.x + actual.x) / 2, y: (anterior.y + actual.y) / 2 };
    ctx.quadraticCurveTo(anterior.x, anterior.y, medio.x, medio.y);
    anterior = actual;
  }
  ctx.lineTo(anterior.x, anterior.y);
  ctx.stroke();
}

/** Un segmento suelto, mientras el trazo todavía se está dibujando (antes
 * de que exista como RawStroke completo) -- para no esperar a soltar el
 * dedo/lápiz para ver algo en pantalla. `anchoNormalizado` es el mismo
 * valor que terminará guardado como `width` del trazo. */
export function dibujarSegmentoEnVivo(
  ctx: CanvasRenderingContext2D,
  desde: RawStrokePoint,
  hasta: RawStrokePoint,
  anchoNormalizado: number,
  anchoPx: number,
  altoPx: number,
  color: string,
): void {
  ctx.strokeStyle = color;
  ctx.lineWidth = anchoNormalizado * anchoPx;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.beginPath();
  ctx.moveTo(desde.x * anchoPx, desde.y * altoPx);
  ctx.lineTo(hasta.x * anchoPx, hasta.y * altoPx);
  ctx.stroke();
}
