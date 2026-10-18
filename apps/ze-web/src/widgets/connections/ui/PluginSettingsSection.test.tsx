import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import legacy from "../../../../../../packages/ze-ui/fixtures/legacy-stored-tree.json";
import button from "../../../../../../packages/ze-ui/fixtures/button.json";
import type { UiContribution } from "@/entities/ui-manifest";
import { PluginSettingsSection } from "./PluginSettingsSection";

const { usePluginSettingsQuery } = vi.hoisted(() => ({ usePluginSettingsQuery: vi.fn() }));

vi.mock("@/entities/ui-manifest", () => ({ usePluginSettingsQuery }));
vi.mock("@/features/primitive-tree", async (orig) => ({
  ...(await orig<typeof import("@/features/primitive-tree")>()),
  usePrimitiveActions: () => ({}),
}));

const entry = { id: "ze_news.settings", plugin: "ze_news", kind: "settings", label: "News", icon: "newspaper" } as UiContribution;
const answer = (data: unknown) =>
  usePluginSettingsQuery.mockReturnValue({ data, isLoading: false, isError: false, refetch: vi.fn() });

describe("PluginSettingsSection", () => {
  it("renders a shared fixture under the section's ui_version", () => {
    answer({ tree: button, ui_version: "2.0" });
    render(<PluginSettingsSection entry={entry} />);
    expect(screen.getByRole("button", { name: "Ask" })).toBeEnabled();
  });

  it("renders a section with no version in legacy mode", () => {
    answer({ tree: legacy });
    render(<PluginSettingsSection entry={entry} />);
    expect(screen.getByRole("button", { name: "Yes" })).toBeDisabled();
  });

  it("shows the older-view note for a legacy section that cannot be parsed", () => {
    answer({ tree: [{ type: "col" }] });
    render(<PluginSettingsSection entry={entry} />);
    expect(screen.getByText("This older view can't be shown.")).toBeInTheDocument();
  });
});
