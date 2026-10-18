import { levelFromSamples } from "./level";

let level = 0;

/** The latest input level 0..1 from the analyser. */
export function recorderLevel(): number {
  return level;
}

export interface Recorder {
  stop: () => Promise<Blob>;
}

export async function startRecorder({ mime, onLevel }: { mime: string; onLevel?: (level: number) => void }): Promise<Recorder> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const release = () => stream.getTracks().forEach((t) => t.stop());
  let ctx: AudioContext | null = null;
  let raf = 0;
  let recorder: MediaRecorder;
  const chunks: Blob[] = [];
  try {
    recorder = new MediaRecorder(stream, { mimeType: mime, audioBitsPerSecond: 64000 });
    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.push(e.data);
    };
    ctx = new AudioContext();
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 1024;
    ctx.createMediaStreamSource(stream).connect(analyser);
    const buf = new Float32Array(analyser.fftSize);
    const tick = () => {
      analyser.getFloatTimeDomainData(buf);
      level = levelFromSamples(buf);
      onLevel?.(level);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    recorder.start(250);
  } catch (err) {
    cancelAnimationFrame(raf);
    release();
    void ctx?.close();
    throw err;
  }
  return {
    stop: () =>
      new Promise<Blob>((resolve) => {
        recorder.onstop = () => {
          cancelAnimationFrame(raf);
          release();
          void ctx?.close();
          level = 0;
          resolve(new Blob(chunks, { type: mime }));
        };
        recorder.stop();
      }),
  };
}
