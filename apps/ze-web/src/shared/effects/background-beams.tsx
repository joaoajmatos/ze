"use client";
import { useEffect, useRef } from "react";
import { cn } from "@/shared/lib/cn";

// Simplified canvas-based version for richer effect
export function BackgroundBeamsCanvas({ className }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;

    function resize() {
      if (!canvas) return;
      canvas.width = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    }
    resize();
    window.addEventListener("resize", resize);

    let t = 0;
    function draw() {
      if (!canvas || !ctx) return;
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const beams = 6;
      for (let i = 0; i < beams; i++) {
        const phase = (t + i * 1.2) % (Math.PI * 2);
        const opacity = Math.max(0, Math.sin(phase) * 0.25);

        const x1 = (i / beams) * canvas.width + Math.sin(t * 0.3 + i) * 40;
        const x2 = ((i + 0.5) / beams) * canvas.width + Math.cos(t * 0.2 + i) * 60;

        const grad = ctx.createLinearGradient(x1, 0, x2, canvas.height);
        grad.addColorStop(0, `rgba(128, 82, 255, ${opacity})`);
        grad.addColorStop(0.5, `rgba(128, 82, 255, ${opacity * 0.5})`);
        grad.addColorStop(1, "rgba(128, 82, 255, 0)");

        ctx.beginPath();
        ctx.moveTo(x1, 0);
        ctx.lineTo(x2, canvas.height);
        ctx.strokeStyle = grad as unknown as string;
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }

      t += 0.008;
      animId = requestAnimationFrame(draw);
    }
    draw();

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className={cn("absolute inset-0 w-full h-full pointer-events-none", className)}
    />
  );
}
