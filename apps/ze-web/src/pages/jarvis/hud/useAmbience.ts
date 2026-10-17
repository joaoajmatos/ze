import { useCallback, useEffect, useRef, useState } from "react";

/** A quiet synthesized drone, off by default; starts only on a user gesture. */
export function useAmbience() {
  const [on, setOn] = useState(false);
  const ctxRef = useRef<AudioContext | null>(null);
  const gainRef = useRef<GainNode | null>(null);

  const toggle = useCallback(() => {
    setOn((v) => !v);
  }, []);

  useEffect(() => {
    if (!on) return;
    const AC = window.AudioContext;
    if (!AC) return;
    const ctx = new AC();
    const master = ctx.createGain();
    master.gain.value = 0;
    master.connect(ctx.destination);
    const freqs = [55, 82.4, 110, 164.8];
    const nodes: OscillatorNode[] = [];
    for (const [i, f] of freqs.entries()) {
      const o = ctx.createOscillator();
      o.type = i % 2 ? "triangle" : "sine";
      o.frequency.value = f;
      const g = ctx.createGain();
      g.gain.value = 0.18 / (i + 1);
      const lfo = ctx.createOscillator();
      lfo.frequency.value = 0.05 + i * 0.03;
      const lg = ctx.createGain();
      lg.gain.value = 0.6 + i * 0.2;
      lfo.connect(lg).connect(o.detune);
      o.connect(g).connect(master);
      o.start();
      lfo.start();
      nodes.push(o, lfo);
    }
    const lp = ctx.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.value = 420;
    master.disconnect();
    master.connect(lp).connect(ctx.destination);
    master.gain.setTargetAtTime(0.16, ctx.currentTime, 1.2);
    ctxRef.current = ctx;
    gainRef.current = master;
    return () => {
      master.gain.setTargetAtTime(0, ctx.currentTime, 0.35);
      window.setTimeout(() => {
        for (const n of nodes) n.stop();
        ctx.close().catch(() => undefined);
      }, 1400);
      ctxRef.current = null;
      gainRef.current = null;
    };
  }, [on]);

  return { on, toggle };
}
