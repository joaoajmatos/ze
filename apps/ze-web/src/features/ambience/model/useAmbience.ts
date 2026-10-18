import { useCallback, useEffect, useRef, useState } from "react";
import { usePresenceStore } from "@/entities/presence";
import { useReducedMotion } from "@/shared/lib/use-reduced-motion";

const KEY = "ze.ambience";
const LEVEL = 0.16;

function readPreference(): boolean {
  try {
    return localStorage.getItem(KEY) === "on";
  } catch {
    return false;
  }
}

function writePreference(on: boolean): void {
  try {
    localStorage.setItem(KEY, on ? "on" : "off");
  } catch {
    // Storage is blocked; the choice lasts until reload.
  }
}

/** A quiet synthesized drone. Off by default, remembered per browser, started only by a gesture. */
export function useAmbience() {
  const reducedMotion = useReducedMotion();
  const [stored] = useState(readPreference);
  // Under reduced motion a remembered "on" is not armed: only a press of the toggle starts the sound.
  const [on, setOn] = useState(() => stored && !reducedMotion);
  const [gestured, setGestured] = useState(false);
  const recording = usePresenceStore((s) => s.presence.voice === "recording");
  const ctxRef = useRef<AudioContext | null>(null);
  const gainRef = useRef<GainNode | null>(null);
  const recordingRef = useRef(recording);
  useEffect(() => {
    recordingRef.current = recording;
  }, [recording]);

  const toggle = useCallback(() => {
    const next = !on;
    writePreference(next);
    setOn(next);
    // The press is itself the gesture browsers ask for.
    if (next) setGestured(true);
  }, [on]);

  useEffect(() => {
    if (!on || gestured) return;
    const arm = () => setGestured(true);
    window.addEventListener("pointerdown", arm, { once: true });
    window.addEventListener("keydown", arm, { once: true });
    return () => {
      window.removeEventListener("pointerdown", arm);
      window.removeEventListener("keydown", arm);
    };
  }, [on, gestured]);

  const playing = on && gestured;
  useEffect(() => {
    if (!playing) return;
    const AC = window.AudioContext;
    if (!AC) return;
    const ctx = new AC();
    // Safari creates the context suspended when it is made outside the gesture's own task.
    void ctx.resume();
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
    master.gain.setTargetAtTime(recordingRef.current ? 0 : LEVEL, ctx.currentTime, 1.2);
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
  }, [playing]);

  // The drone goes silent while the mic is open, so it never leaks into the transcript.
  useEffect(() => {
    const master = gainRef.current;
    const ctx = ctxRef.current;
    if (master && ctx) master.gain.setTargetAtTime(recording ? 0 : LEVEL, ctx.currentTime, 0.1);
  }, [recording, playing]);

  return { on, toggle };
}
