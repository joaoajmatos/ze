import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { RedirectTo } from "./RedirectTo";

function Here() {
  const { pathname, search, hash } = useLocation();
  return <p data-testid="here">{`${pathname}${search}${hash}`}</p>;
}

function renderRedirect(entry: string, props: React.ComponentProps<typeof RedirectTo>) {
  render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="/old" element={<RedirectTo {...props} />} />
        <Route path="/old/:id" element={<RedirectTo {...props} />} />
        <Route path="*" element={<Here />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("RedirectTo", () => {
  it("keeps the query and hash when the entry has no hint", () => {
    renderRedirect("/old?x=1#h", { to: "/new" });
    expect(screen.getByTestId("here")).toHaveTextContent("/new?x=1#h");
  });

  it("carries params", () => {
    renderRedirect("/old/7", { to: "/new/:id" });
    expect(screen.getByTestId("here")).toHaveTextContent("/new/7");
  });

  it("replaces the incoming hash with the hint and keeps the query", () => {
    renderRedirect("/old?x=1#whatever", { to: "/governance", hint: "connections" });
    expect(screen.getByTestId("here")).toHaveTextContent("/governance?x=1#connections");
  });

  it("adds the hint when there was no hash", () => {
    renderRedirect("/old", { to: "/governance", hint: "files" });
    expect(screen.getByTestId("here")).toHaveTextContent("/governance#files");
  });

  it("lets a listed incoming hash win through hintMap", () => {
    renderRedirect("/old?x=1#your-data", { to: "/governance", hint: "connections", hintMap: { "your-data": "data" } });
    expect(screen.getByTestId("here")).toHaveTextContent("/governance?x=1#data");
  });

  it("falls back to the hint when the incoming hash is not in hintMap", () => {
    renderRedirect("/old#other", { to: "/governance", hint: "connections", hintMap: { "your-data": "data" } });
    expect(screen.getByTestId("here")).toHaveTextContent("/governance#connections");
  });
});
