import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import legacy from "../../../../../../packages/ze-ui/fixtures/legacy-stored-tree.json";
import statRow from "../../../../../../packages/ze-ui/fixtures/button.json";
import type { UiContribution } from "@/entities/ui-manifest";
import { PluginScreen } from "./PluginScreen";

const { usePluginPageQuery, useSetPageHeader } = vi.hoisted(() => ({
  usePluginPageQuery: vi.fn(),
  useSetPageHeader: vi.fn(),
}));

vi.mock("@/entities/ui-manifest", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/entities/ui-manifest")>();
  return {
    ...actual,
    usePluginPageQuery,
  };
});

vi.mock("@/shared/lib", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/shared/lib")>();
  return {
    ...actual,
    useSetPageHeader,
  };
});

vi.mock("@/features/primitive-tree", async (orig) => ({
  ...(await orig<typeof import("@/features/primitive-tree")>()),
  usePrimitiveActions: () => ({
    onAction: vi.fn(),
    onFormSubmit: vi.fn(),
    onDisconnected: vi.fn(),
  }),
}));

const entry: UiContribution = {
  id: "ze_news.overview",
  plugin: "ze_news",
  kind: "nav",
  label: "News",
  icon: "newspaper",
  path: "news",
  page_operation_id: "getNewsPage",
  show_in_mobile_nav: true,
  priority: 100,
};

const validTree = [
  {
    type: "col",
    children: [{ type: "text", content: "Hello", style: "body", color: "default" }],
    gap: "sm",
  },
];

describe("PluginScreen", () => {
  it("shows loading skeleton while page query is loading", () => {
    usePluginPageQuery.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      refetch: vi.fn(),
    });

    const { container } = render(<PluginScreen entry={entry} />);

    expect(container.querySelector(".animate-pulse")).toBeTruthy();
  });

  it("renders primitive tree and pushes title/icon to the top bar on success", () => {
    usePluginPageQuery.mockReturnValue({
      data: { title: "News", tree: validTree },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });

    render(<PluginScreen entry={entry} />);

    expect(screen.getByText("Hello")).toBeInTheDocument();
    expect(useSetPageHeader).toHaveBeenCalledWith(
      expect.objectContaining({ title: "News" }),
    );
  });

  it("shows error state when page query fails", () => {
    usePluginPageQuery.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      refetch: vi.fn(),
    });

    render(<PluginScreen entry={entry} />);

    expect(screen.getByText("Could not load news.")).toBeInTheDocument();
  });

  it("shows error state for invalid UI tree", () => {
    usePluginPageQuery.mockReturnValue({
      data: { title: "News", tree: [{ type: "col" }] },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });

    render(<PluginScreen entry={entry} />);

    expect(screen.getByText("This page returned an invalid UI tree.")).toBeInTheDocument();
  });

  it("renders a shared fixture under the page's ui_version", () => {
    usePluginPageQuery.mockReturnValue({
      data: { title: "News", tree: statRow, ui_version: "2.0" },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    render(<PluginScreen entry={entry} />);
    expect(screen.getByRole("button", { name: "Ask" })).toBeEnabled();
  });

  it("renders a page with no version in legacy mode", () => {
    usePluginPageQuery.mockReturnValue({
      data: { title: "News", tree: legacy },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    render(<PluginScreen entry={entry} />);
    expect(screen.getByRole("button", { name: "Yes" })).toBeDisabled();
  });

  it("shows the older-view note for a legacy page that cannot be parsed", () => {
    usePluginPageQuery.mockReturnValue({
      data: { title: "News", tree: [{ type: "col" }] },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    render(<PluginScreen entry={entry} />);
    expect(screen.getByText("This older view can't be shown.")).toBeInTheDocument();
  });
});
