import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TextInput } from "../TextInput";

describe("TextInput", () => {
  it("renders the textarea and forwards changes", async () => {
    const onChange = vi.fn();
    render(<TextInput value="" onChange={onChange} placeholder="Enter…" />);
    const ta = screen.getByPlaceholderText("Enter…");
    await userEvent.type(ta, "ab");
    expect(onChange).toHaveBeenLastCalledWith("b");
  });

  it("shows char + word counts", () => {
    render(<TextInput value="Hợp đồng số 02" onChange={() => {}} />);
    expect(screen.getByText(/14 chars/)).toBeInTheDocument();
    expect(screen.getByText(/4 words/)).toBeInTheDocument();
  });

  it("loads a sample when its button is clicked", async () => {
    const onChange = vi.fn();
    render(
      <TextInput
        value=""
        onChange={onChange}
        samples={[{ label: "Demo", text: "Tôi yêu Việt Nam" }]}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: /demo/i }));
    expect(onChange).toHaveBeenCalledWith("Tôi yêu Việt Nam");
  });

  it("clear-input button clears the value", async () => {
    const onChange = vi.fn();
    render(<TextInput value="abc" onChange={onChange} />);
    await userEvent.click(screen.getByLabelText(/clear input/i));
    expect(onChange).toHaveBeenCalledWith("");
  });
});
