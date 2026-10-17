import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { CommandChip, Chip, Control, CountUp, Decode, DotMatrix, Dots, Glyph, Meter, Module } from "..";

describe("Glyph", () => {
  it.each(["told", "inferred", "suspected", "goal"] as const)("renders %s", (kind) => {
    const { container } = render(<Glyph kind={kind} />);
    expect(container.querySelector(`i.glyph.${kind}`)).toBeInTheDocument();
  });

  it("marks hot", () => {
    const { container } = render(<Glyph kind="told" hot />);
    expect(container.querySelector("i.glyph.hot")).toBeInTheDocument();
  });
});

describe("Meter", () => {
  it("describes the value and draws 12 ticks", () => {
    const { container } = render(<Meter value={0.5} />);
    const meter = screen.getByRole("meter");
    expect(meter).toHaveAttribute("aria-valuetext", "50 percent sure");
    expect(container.querySelectorAll("i")).toHaveLength(12);
    expect(container.querySelectorAll("i.lit")).toHaveLength(6);
  });

  it("says unknown for a null value", () => {
    render(<Meter value={null} />);
    expect(screen.getByRole("meter")).toHaveAttribute("aria-valuetext", "unknown");
  });
});

describe("Dots", () => {
  it("prints N/M in its label", () => {
    render(<Dots max={5} lit={3} label="3/5" />);
    expect(screen.getByRole("img", { name: "3/5" })).toBeInTheDocument();
  });
});

describe("DotMatrix", () => {
  it("renders a dot set for every character the prototype uses", () => {
    for (const ch of "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789·:- ") {
      const { container, unmount } = render(<DotMatrix text={ch} />);
      const paths = container.querySelectorAll("path");
      expect(paths.length, `glyph ${JSON.stringify(ch)}`).toBeGreaterThan(0);
      unmount();
    }
  });

  it("carries a title as the accessible name", () => {
    render(<DotMatrix text="ZE" title="Ze" />);
    expect(screen.getByRole("img", { name: "Ze" })).toBeInTheDocument();
  });
});

describe("Decode and CountUp", () => {
  it("Decode shows the final text at once under reduced motion", () => {
    render(<Decode text="HELLO" reducedMotion />);
    expect(screen.getByText("HELLO")).toBeInTheDocument();
  });

  it("CountUp shows the final value at once under reduced motion", () => {
    render(<CountUp to={42} reducedMotion />);
    expect(screen.getByText("42")).toBeInTheDocument();
  });
});

describe("Module", () => {
  it("renders the label as h2.lbl and omits index unless passed", () => {
    const { container, rerender } = render(<Module label="Presence">x</Module>);
    expect(screen.getByRole("heading", { level: 2, name: "Presence" })).toHaveClass("lbl");
    expect(container.querySelector(".idx")).toBeNull();
    rerender(
      <Module label="Presence" index="A·02">
        x
      </Module>,
    );
    expect(container.querySelector(".idx")).toHaveTextContent("A·02");
  });

  it("applies tone classes", () => {
    const { container } = render(
      <Module label="Slipping" tone="hot">
        x
      </Module>,
    );
    expect(container.querySelector(".mod")).toHaveClass("hot");
    expect(screen.getByRole("heading", { name: "Slipping" })).toHaveClass("hot");
  });
});

describe("Control", () => {
  it("renders a 44 px control button and forwards aria-pressed", () => {
    render(<Control pressed>Go</Control>);
    const btn = screen.getByRole("button", { name: "Go" });
    expect(btn).toHaveClass("ctl");
    expect(btn).toHaveAttribute("aria-pressed", "true");
  });

  it("renders a link with aria-current", () => {
    render(
      <MemoryRouter>
        <Control as="link" to="/ask" current>
          Ask
        </Control>
      </MemoryRouter>,
    );
    const link = screen.getByRole("link", { name: "Ask" });
    expect(link).toHaveClass("ctl");
    expect(link).toHaveAttribute("aria-current", "page");
  });

  it("marks primary", () => {
    render(<Control primary>Send</Control>);
    expect(screen.getByRole("button", { name: "Send" })).toHaveClass("primary");
  });
});

describe("CommandChip", () => {
  it("renders index, label and key hint", () => {
    render(<CommandChip index="01" keyHint="1" onClick={() => {}}>What is slipping?</CommandChip>);
    const btn = screen.getByRole("button", { name: /What is slipping\?/ });
    expect(btn).toHaveClass("ctl", "cmd");
    expect(btn).toHaveTextContent("01");
    expect(btn).toHaveTextContent("1");
  });
});

describe("Chip", () => {
  it("renders solid and dotted variants", () => {
    const { container } = render(
      <>
        <Chip kind="solid">told</Chip>
        <Chip kind="dotted">inferred</Chip>
      </>,
    );
    expect(container.querySelector(".chip.solid")).toHaveTextContent("told");
    expect(container.querySelector(".chip.dotted")).toHaveTextContent("inferred");
  });
});
