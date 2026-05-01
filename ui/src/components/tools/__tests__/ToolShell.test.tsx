import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Type } from "lucide-react";
import { ToolShell, Panel, EmptyHint, Spinner } from "../ToolShell";

describe("ToolShell", () => {
  it("renders title, subtitle, options, children, and footer", () => {
    render(
      <ToolShell
        icon={Type}
        title="Diacritic"
        subtitle="restore"
        options={<div>opts-here</div>}
        footer={<button>Run</button>}
      >
        <div>main</div>
      </ToolShell>,
    );
    expect(screen.getByRole("heading", { name: /Diacritic/ })).toBeInTheDocument();
    expect(screen.getByText("§ restore")).toBeInTheDocument();
    expect(screen.getByText("opts-here")).toBeInTheDocument();
    expect(screen.getByText("main")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run" })).toBeInTheDocument();
  });

  it("does not render the options aside when options prop is omitted", () => {
    render(
      <ToolShell icon={Type} title="X">
        <div>main</div>
      </ToolShell>,
    );
    // The options heading "§ options" should not appear.
    expect(screen.queryByText("§ options")).not.toBeInTheDocument();
  });
});

describe("Panel", () => {
  it("renders the section mark with the label and any rightSlot", () => {
    render(
      <Panel label="restored" hint="124 chars" rightSlot={<span>R</span>}>
        body
      </Panel>,
    );
    expect(screen.getByText("§ restored")).toBeInTheDocument();
    expect(screen.getByText("124 chars")).toBeInTheDocument();
    expect(screen.getByText("R")).toBeInTheDocument();
    expect(screen.getByText("body")).toBeInTheDocument();
  });
});

describe("EmptyHint", () => {
  it("renders its children inline", () => {
    render(<EmptyHint>nothing yet</EmptyHint>);
    expect(screen.getByText("nothing yet")).toBeInTheDocument();
  });
});

describe("Spinner", () => {
  it("renders an svg icon", () => {
    const { container } = render(<Spinner />);
    expect(container.querySelector("svg")).not.toBeNull();
  });
});
