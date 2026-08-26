/**
 * handoff §5.1: "Sonido: solo nivel 3 -- dos tonos de 0,4 s, sin
 * repetición." Web Audio en vez de un archivo de audio: dos beeps son
 * más simples de generar que de empaquetar, y evita otra dependencia.
 * Los navegadores bloquean audio sin gesto previo del usuario -- en un
 * kiosco eso se configura a nivel de navegador/OS (ver web/README.md);
 * acá simplemente se ignora el rechazo si ocurre, no es un error fatal.
 */
export function reproducirTonoAlerta(): void {
  try {
    const AudioContextCtor =
      window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    const ctx = new AudioContextCtor();
    const tono = (frecuencia: number, inicioS: number) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.frequency.value = frecuencia;
      osc.type = "sine";
      gain.gain.setValueAtTime(0.0001, ctx.currentTime + inicioS);
      gain.gain.exponentialRampToValueAtTime(0.2, ctx.currentTime + inicioS + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + inicioS + 0.4);
      osc.connect(gain).connect(ctx.destination);
      osc.start(ctx.currentTime + inicioS);
      osc.stop(ctx.currentTime + inicioS + 0.4);
    };
    tono(880, 0);
    tono(660, 0.45);
    setTimeout(() => ctx.close(), 1200);
  } catch {
    // Autoplay bloqueado u otra restricción del navegador: no es fatal,
    // el aviso visual sigue apareciendo igual.
  }
}
