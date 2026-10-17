import { useState } from "react";

/** Asks the server for its version with the typed URL and key; returns the version or the reason it failed. */
async function probe(serverUrl: string, apiKey: string): Promise<{ ok: true; version: string } | { ok: false; reason: string }> {
  try {
    const res = await fetch(`${serverUrl.replace(/\/$/, "")}/api/v0/version`, { headers: { Authorization: `Bearer ${apiKey}` } });
    if (res.status === 401 || res.status === 403) return { ok: false, reason: "The server rejected the API key." };
    if (!res.ok) return { ok: false, reason: `The server answered ${res.status}.` };
    const body = (await res.json()) as { api_version?: string };
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
