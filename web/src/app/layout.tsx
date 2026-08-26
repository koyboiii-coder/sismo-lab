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
export const viewport: Viewport = {
  width: 1920,
  userScalable: false,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" className={archivo.variable}>
      <body>{children}</body>
    </html>
  );
}
