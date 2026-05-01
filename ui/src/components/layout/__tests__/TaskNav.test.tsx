import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TaskNav } from "../TaskNav";

describe("TaskNav", () => {
  it("renders all six task buttons grouped by category", () => {
    render(<TaskNav active="chat" onSelect={() => {}} />);
    expect(screen.getByText("documents")).toBeInTheDocument();
    expect(screen.getByText("text tools")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Chat & RAG/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Khôi phục dấu/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Tách từ/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Chuẩn hoá/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Bỏ dấu/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Sinh nhiễu/ })).toBeInTheDocument();
  });

  it("marks the active task with aria-current", () => {
    render(<TaskNav active="diacritic" onSelect={() => {}} />);
    const active = screen.getByRole("button", { name: /Khôi phục dấu/ });
    expect(active).toHaveAttribute("aria-current", "page");
    const inactive = screen.getByRole("button", { name: /Chat & RAG/ });
    expect(inactive).not.toHaveAttribute("aria-current");
  });

  it("forwards the chosen task key to onSelect", async () => {
    const onSelect = vi.fn();
    render(<TaskNav active="chat" onSelect={onSelect} />);
    await userEvent.click(screen.getByRole("button", { name: /Sinh nhiễu/ }));
    expect(onSelect).toHaveBeenCalledWith("noise");
  });
});
