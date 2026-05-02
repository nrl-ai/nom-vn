import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ApiPage } from "../pages/ApiPage";

describe("ApiPage", () => {
  it("renders the install + run setup section", () => {
    render(<ApiPage />);
    expect(screen.getByText(/cài đặt và chạy/)).toBeInTheDocument();
    expect(
      screen.getAllByText((_, el) => (el?.textContent ?? "").includes("pip install")).length,
    ).toBeGreaterThan(0);
    // The serve command appears in multiple snippets — assert at least one.
    expect(
      screen.getAllByText((_, el) => (el?.textContent ?? "").includes("nom serve --in-memory"))
        .length,
    ).toBeGreaterThan(0);
  });

  it("documents Ollama, llama.cpp, and cloud backends", () => {
    render(<ApiPage />);
    expect(screen.getByText(/Ollama \(đơn giản nhất\)/)).toBeInTheDocument();
    expect(screen.getByText(/llama\.cpp \(không daemon, tương thích OpenAI\)/)).toBeInTheDocument();
    expect(screen.getByText(/Đám mây \(OpenAI/)).toBeInTheDocument();
  });

  it("includes copyable curl examples for the stateless tools", () => {
    render(<ApiPage />);
    const healthExample = screen.getAllByText(
      (_, el) =>
        (el?.tagName === "PRE" && (el?.textContent ?? "").includes("/api/health")) || false,
    );
    expect(healthExample.length).toBeGreaterThan(0);
    expect(
      screen.getAllByText((_, el) =>
        (el?.textContent ?? "").includes("/api/tools/diacritic/restore"),
      ).length,
    ).toBeGreaterThan(0);
  });

  it("links to OpenAPI / ReDoc", () => {
    render(<ApiPage />);
    const swagger = screen.getByRole("link", { name: /OpenAPI/i });
    expect(swagger).toHaveAttribute("href", "/docs");
    const redoc = screen.getByRole("link", { name: /ReDoc/i });
    expect(redoc).toHaveAttribute("href", "/redoc");
  });
});
