import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { BreadcrumbProvider } from "@/shared/lib/breadcrumb";
import { PageHeaderProvider } from "@/shared/lib/page-header";
import { TopBarActionsProvider } from "@/shared/lib/top-bar-actions";
import { TopBar } from "./TopBar";

vi.mock("@/widgets/notification-bell", () => ({ NotificationBell: () => null }));

function Where() {
  return <p data-testid="where">{useLocation().pathname}</p>;
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <BreadcrumbProvider>
        <PageHeaderProvider>
          <TopBarActionsProvider>
            <TopBar />
            <Routes>
              <Route path="*" element={<Where />} />
            </Routes>
          </TopBarActionsProvider>
        </PageHeaderProvider>
      </BreadcrumbProvider>
    </MemoryRouter>,
  );
}

describe("TopBar", () => {
  it("shows the current route title on list pages", () => {
    renderAt("/goals");
    expect(screen.getByText("Goals")).toBeInTheDocument();
  });

  it("gives the detail-page back control a 44px tap target that returns to the list", () => {
    renderAt("/goals/abc");
    const back = screen.getByRole("button", { name: /goals/i });

    expect(back.className).toContain("min-h-11");
    expect(back.className).toContain("min-w-11");
    fireEvent.click(back);
    expect(screen.getByTestId("where")).toHaveTextContent("/goals");
  });
});
