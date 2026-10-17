import { useState } from "react";

/**
 * Checks the typed URL and key. `/version` is public, so it only proves the server answers;
 * one authed route (`/notifications/unread-count`) proves the key. Returns the reason on failure.
 */
async function probe(serverUrl: string, apiKey: string): Promise<{ ok: true; version: string } | { ok: false; reason: string }> {
  const base = serverUrl.replace(/\/$/, "");
  try {
    const res = await fetch(`${base}/api/v0/version`);
    if (!res.ok) return { ok: false, reason: `The server answered ${res.status}.` };
    const body = (await res.json()) as { api_version?: string };
    const authed = await fetch(`${base}/api/v0/notifications/unread-count`, { headers: { Authorization: `Bearer ${apiKey}` } });
    if (authed.status === 401 || authed.status === 403) return { ok: false, reason: "The server is reachable, but it rejected the API key." };
    if (!authed.ok) return { ok: false, reason: `The server answered ${authed.status}.` };
    return { ok: true, version: body.api_version ?? "unknown" };
  } catch {
    return { ok: false, reason: "Could not reach the server." };
  }
}

export function useConnectionTest(serverUrl: string, apiKey: string) {
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<"ok" | "error" | null>(null);
  const [testDetail, setTestDetail] = useState<string | null>(null);

  async function runTest() {
    setTesting(true);
    setTestResult(null);
    setTestDetail(null);
    try {
      const result = await probe(serverUrl, apiKey);
      setTestResult(result.ok ? "ok" : "error");
      setTestDetail(result.ok ? result.version : result.reason);
    } finally {
      setTesting(false);
    }
  }

  function reset() {
    setTestResult(null);
    setTestDetail(null);
  }

  return { testing, testResult, testDetail, runTest, reset };
}
