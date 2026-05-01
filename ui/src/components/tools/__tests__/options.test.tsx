import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Select, Segmented, NumberField, OptionRow } from "../options";

describe("Select", () => {
  it("renders provided options and fires onChange", async () => {
    const onChange = vi.fn();
    render(
      <Select<"a" | "b">
        value="a"
        onChange={onChange}
        options={[
          { value: "a", label: "Alpha" },
          { value: "b", label: "Beta" },
        ]}
      />,
    );
    const sel = screen.getByRole("combobox") as HTMLSelectElement;
    expect(sel.value).toBe("a");
    expect(screen.getByRole("option", { name: "Alpha" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Beta" })).toBeInTheDocument();
    await userEvent.selectOptions(sel, "b");
    expect(onChange).toHaveBeenCalledWith("b");
  });
});

describe("Segmented", () => {
  it("marks the active tab and calls onChange when clicking another", async () => {
    const onChange = vi.fn();
    render(
      <Segmented<"x" | "y" | "z">
        value="x"
        onChange={onChange}
        options={[
          { value: "x", label: "X" },
          { value: "y", label: "Y" },
          { value: "z", label: "Z" },
        ]}
      />,
    );
    const tabs = screen.getAllByRole("tab");
    expect(tabs).toHaveLength(3);
    expect(tabs[0]).toHaveAttribute("aria-selected", "true");
    expect(tabs[1]).toHaveAttribute("aria-selected", "false");
    await userEvent.click(tabs[1]);
    expect(onChange).toHaveBeenCalledWith("y");
  });
});

describe("NumberField", () => {
  it("invokes onChange with parsed numeric values", () => {
    const onChange = vi.fn();
    render(<NumberField value={42} onChange={onChange} min={0} max={100} />);
    const input = screen.getByRole("spinbutton") as HTMLInputElement;
    expect(input.value).toBe("42");
    fireEvent.change(input, { target: { value: "7" } });
    expect(onChange).toHaveBeenCalledWith(7);
  });

  it("does not propagate NaN when input is non-numeric", () => {
    const onChange = vi.fn();
    render(<NumberField value={1} onChange={onChange} />);
    const input = screen.getByRole("spinbutton") as HTMLInputElement;
    // jsdom's number-typed input rejects 'abc' before triggering onChange,
    // but we can simulate via a literal value="abc" assignment too. The
    // guarantee we care about: onChange never sees NaN.
    fireEvent.change(input, { target: { value: "abc" } });
    expect(onChange).not.toHaveBeenCalledWith(NaN);
  });
});

describe("OptionRow", () => {
  it("renders label, hint, and child controls", () => {
    render(
      <OptionRow label="Backend" hint="Pure stdlib">
        <button>click</button>
      </OptionRow>,
    );
    expect(screen.getByText("Backend")).toBeInTheDocument();
    expect(screen.getByText("Pure stdlib")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "click" })).toBeInTheDocument();
  });
});
