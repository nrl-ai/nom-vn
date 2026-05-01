import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { DiffView } from "../DiffView";

describe("DiffView", () => {
  it("renders the after-text exactly when input matches output", () => {
    const { container } = render(<DiffView before="Hop dong" after="Hop dong" />);
    expect(container.textContent).toBe("Hop dong");
    // No highlighted spans when nothing changed.
    expect(container.querySelectorAll("span[title^='was:']")).toHaveLength(0);
  });

  it("highlights diacritic-only word changes in place", () => {
    const { container } = render(<DiffView before="Hop dong nay" after="Hợp đồng này" />);
    expect(container.textContent).toBe("Hợp đồng này");
    const highlighted = container.querySelectorAll("span[title^='was:']");
    expect(highlighted).toHaveLength(3);
    expect(highlighted[0].textContent).toBe("Hợp");
    expect(highlighted[0].getAttribute("title")).toBe("was: Hop");
  });

  it("does not highlight punctuation or whitespace", () => {
    const { container } = render(<DiffView before="Hop dong, ne." after="Hợp đồng, nè." />);
    const highlighted = container.querySelectorAll("span[title^='was:']");
    // 'Hop' → 'Hợp', 'dong' → 'đồng', 'ne' → 'nè'. Comma + period unchanged.
    expect(highlighted).toHaveLength(3);
  });

  it("treats đ/Đ as a stroke-only difference (still same word)", () => {
    const { container } = render(<DiffView before="dong" after="đồng" />);
    const highlighted = container.querySelectorAll("span[title^='was:']");
    expect(highlighted).toHaveLength(1);
    expect(highlighted[0].textContent).toBe("đồng");
  });
});
