import type { Metadata, Viewport } from "next";
import { Archivo } from "next/font/google";
import "./globals.css";

const archivo = Archivo({
  variable: "--font-archivo",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800", "900"],
});

export const metadata: Metadata = {
  title: "Monitor Sísmico",
  description: "Monitoreo sísmico en tiempo real -- Ñuñoa, Santiago",
};

// Fijo a 1920x1200: pantalla de pared, no responsive (handoff §1).
// initialScale/minimumScale/maximumScale son necesarios, no solo width: sin
// ellos, el WebView de Android (Fully Kiosk incluido) no siempre respeta
// width=1920 como viewport de layout -- calculaba uno propio (más chico) y
// forzaba scroll horizontal. "Versión de escritorio" del navegador se veía
// bien porque ese modo fija su propio ancho de viewport por su cuenta,
// enmascarando el bug. Fijar los tres explícitamente a 1 elimina la
// ambigüedad para cualquier WebView.
export const viewport: Viewport = {
  width: 1920,
  initialScale: 1,
  minimumScale: 1,
  maximumScale: 1,
  userScalable: false,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" className={archivo.variable}>
      <body>{children}</body>
    </html>
  );
}
