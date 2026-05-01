import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CopyButton } from "../CopyButton";

describe("CopyButton", () => {
  beforeEach(() => {
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
  });

  it("copies its text to the clipboard on click", async () => {
    render(<CopyButton text="Tôi yêu Việt Nam" />);
    const btn = screen.getByRole("button", { name: /copy/i });
    await userEvent.click(btn);
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("Tôi yêu Việt Nam");
  });

  it("flips to a 'Copied' state briefly after copying", async () => {
    render(<CopyButton text="hello" />);
    const btn = screen.getByRole("button", { name: /copy/i });
    await userEvent.click(btn);
    await waitFor(() => {
      expect(btn.textContent).toMatch(/copied/i);
    });
  });

  it("is disabled when there is nothing to copy", () => {
    render(<CopyButton text="" />);
    const btn = screen.getByRole("button");
    expect(btn).toBeDisabled();
  });
});
