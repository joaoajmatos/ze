import { useState, type ReactNode } from "react";
import { ChoosePalette } from "@/features/choose-palette";
import { useConnectionTest } from "@/features/test-api-connection";
import { useUiManifestQuery } from "@/entities/ui-manifest";
import { reconnect } from "@/shared/api";
import { clearConfig, getConfig, saveConfig } from "@/shared/config";
import { resetClient } from "@/shared/lib";
import { RedirectHintTarget } from "@/shared/ui";
import { Control, Dialog, Module } from "@/shared/ui/hud";
import { PluginSettingsSection } from "./PluginSettingsSection";

/** Governance › Connections: which server Ze talks to, plugin settings and the palette. `extra` follows the settings sections; the page passes the plugin module slot (a widget cannot import a widget). */
export function Connections({ extra }: { extra?: ReactNode }) {
  const cfg = getConfig();
  const { data: manifest } = useUiManifestQuery();
  const [serverUrl, setServerUrl] = useState(cfg?.serverUrl ?? "");
  const [apiKey, setApiKey] = useState(cfg?.apiKey ?? "");
  const [saved, setSaved] = useState(false);
  const [forgetting, setForgetting] = useState(false);
  const { testing, testResult, testDetail, runTest, reset } = useConnectionTest(serverUrl, apiKey);

  function save() {
    saveConfig({ serverUrl, apiKey });
    resetClient();
    reconnect();
    setSaved(true);
    window.setTimeout(() => setSaved(false), 2000);
  }

  function forget() {
    clearConfig();
    window.location.reload();
  }

  return (
    <RedirectHintTarget hintId="connections">
      <Module label="How do I reach Ze?">
        <div className="gov-stack">
          <div className="gov-field">
            <label className="lbl" htmlFor="gov-server-url">
              Server URL
            </label>
            <input
              id="gov-server-url"
              className="gov-in"
              value={serverUrl}
              placeholder="http://localhost:8000"
              onChange={(e) => {
                setServerUrl(e.target.value);
                reset();
              }}
            />
          </div>
          <div className="gov-field">
            <label className="lbl" htmlFor="gov-api-key">
              API key
            </label>
            <input
              id="gov-api-key"
              className="gov-in"
              type="password"
              value={apiKey}
              placeholder="ZE_API_KEY"
              onChange={(e) => {
                setApiKey(e.target.value);
                reset();
              }}
            />
          </div>
          <div className="gov-actions">
            <Control onClick={() => void runTest()} disabled={testing}>
              {testing ? "Testing" : "Test"}
            </Control>
            <Control primary onClick={save}>
              {saved ? "Saved" : "Save and reconnect"}
            </Control>
          </div>
          {testResult === "ok" && <p className="gov-ok">Connected. API {testDetail}.</p>}
          {testResult === "error" && <p className="gov-err">{testDetail}</p>}

          {manifest?.settings_sections.map((entry) => (
            <PluginSettingsSection key={entry.id} entry={entry} />
          ))}

          <ChoosePalette />

          <div style={{ borderTop: "1px solid var(--hair)", paddingTop: 12 }}>
            <Control className="hot" onClick={() => setForgetting(true)}>
              Forget this server
            </Control>
          </div>
        </div>
      </Module>

      {extra}

      {forgetting && (
        <Dialog title="Forget this server?" onClose={() => setForgetting(false)}>
          <p className="gov-note">This removes the saved server URL and API key from this browser. Ze shows the setup screen. Nothing on the server changes.</p>
          <div className="gov-actions">
            <Control onClick={() => setForgetting(false)}>Cancel</Control>
            <Control className="hot" onClick={forget}>
              Forget
            </Control>
          </div>
        </Dialog>
      )}
    </RedirectHintTarget>
  );
}
