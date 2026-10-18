const MIMES = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/mp4"];

export function pickMime(isTypeSupported: (mime: string) => boolean): string | null {
  return MIMES.find((m) => isTypeSupported(m)) ?? null;
}

export function extensionFor(mime: string): string {
  if (mime.startsWith("audio/ogg")) return "ogg";
  if (mime.startsWith("audio/mp4")) return "m4a";
  return "webm";
}
