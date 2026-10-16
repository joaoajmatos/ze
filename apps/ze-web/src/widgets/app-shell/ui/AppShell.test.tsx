import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppShell } from "./AppShell";

vi.mock("@/entities/ui-manifest", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/entities/ui-manifest")>()),
  useUiManifestQuery: () => ({ data: undefined }),
}));
vi.mock("@/features/invalidate-on-ws-refresh", () => ({ RefreshHandler: () => null }));
vi.mock("@/shared/ui", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/shared/ui")>()),
  NoticeBanner: () => null,
}));
vi.mock("./TopBar", () => ({ TopBar: () => null }));
vi.mock("./ChatNavGroup", () => ({ ChatNavGroup: () => null }));

function renderShell() {
  return render(
    <MemoryRouter initialEntries={["/goals"]}>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="goals" element={<p>page</p>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe("AppShell", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockImplementation(() => ({
        matches: false,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      })),
    );
  });
  afterEach(() => vi.unstubAllGlobals());

  it("names the icon-only Settings link", () => {
    renderShell();
    const links = screen.getAllByRole("link", { name: "Settings" });
    const sidebar = links.find((l) => l.getAttribute("title") === "Settings");
    expect(sidebar).toBeDefined();
  });

  it("keeps mobile nav labels at 11px or larger", () => {
    const { container } = renderShell();
    const mobileNav = container.querySelector("nav.md\\:hidden") as HTMLElement;
    const links = mobileNav.querySelectorAll("a");
    expect(links.length).toBeGreaterThan(0);
    links.forEach((link) => {
      expect(link.className).not.toContain("text-[10px]");
      expect(link.className).toMatch(/text-\[11px\]|text-xs/);
      // eight items share 390px; tight tracking keeps "Workflows"/"Reminders" off their neighbours
      expect(link.className).toContain("tracking-tighter");
      expect(link.className).toContain("whitespace-nowrap");
    });
  });

  it("pads the scroll area on mobile so the launcher never covers the last row", () => {
    const { container } = renderShell();
    const scroller = container.querySelector("main > div.overflow-y-auto") as HTMLElement;
    expect(scroller.className).toContain("pb-32");
    expect(scroller.className).toContain("md:pb-0");
  });
});
