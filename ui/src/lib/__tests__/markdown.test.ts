import { describe, expect, it } from "vitest";
import { renderMarkdown } from "../markdown";

describe("renderMarkdown — existing features still work", () => {
  it("bold + italic", () => {
    expect(renderMarkdown("**bold** and *italic*")).toContain("<strong>bold</strong>");
    expect(renderMarkdown("**bold** and *italic*")).toContain("<em>italic</em>");
  });

  it("bullet list", () => {
    const out = renderMarkdown("- one\n- two\n- three");
    expect(out).toContain("<ul");
    expect(out).toContain("<li>one</li>");
    expect(out).toContain("<li>three</li>");
  });

  it("inline code", () => {
    expect(renderMarkdown("use `nom serve`")).toContain('<code class="md-code">nom serve</code>');
  });

  it("escapes HTML in user input", () => {
    expect(renderMarkdown("<script>alert(1)</script>")).not.toContain("<script>");
    expect(renderMarkdown("<script>alert(1)</script>")).toContain("&lt;script&gt;");
  });
});

describe("renderMarkdown — headings (new)", () => {
  it("H1 through H6", () => {
    expect(renderMarkdown("# H1")).toContain('<h1 class="md-h1">H1</h1>');
    expect(renderMarkdown("## H2")).toContain('<h2 class="md-h2">H2</h2>');
    expect(renderMarkdown("### H3")).toContain('<h3 class="md-h3">H3</h3>');
    expect(renderMarkdown("###### H6")).toContain('<h6 class="md-h6">H6</h6>');
  });

  it("optional trailing #s are stripped", () => {
    expect(renderMarkdown("## Section ##")).toContain('<h2 class="md-h2">Section</h2>');
  });
});

describe("renderMarkdown — GFM tables (new)", () => {
  it("renders a simple 2-column table", () => {
    const md = `| Name | Score |\n|------|-------|\n| Alice | 95 |\n| Bob | 80 |`;
    const out = renderMarkdown(md);
    expect(out).toContain('<table class="md-table">');
    expect(out).toContain("<thead>");
    expect(out).toContain("<th>Name</th>");
    expect(out).toContain("<th>Score</th>");
    expect(out).toContain("<td>Alice</td>");
    expect(out).toContain("<td>95</td>");
  });

  it("respects column alignment markers", () => {
    const md = `| L | C | R |\n|:---|:---:|---:|\n| a | b | c |`;
    const out = renderMarkdown(md);
    expect(out).toContain('style="text-align:left"');
    expect(out).toContain('style="text-align:center"');
    expect(out).toContain('style="text-align:right"');
  });

  it("VN content with diacritics survives", () => {
    const md = `| Tháng | Doanh thu |\n|---|---|\n| Tháng 1 | 850 tỷ |`;
    const out = renderMarkdown(md);
    expect(out).toContain("<th>Tháng</th>");
    expect(out).toContain("<td>Tháng 1</td>");
    expect(out).toContain("<td>850 tỷ</td>");
  });
});

describe("renderMarkdown — inline charts (new)", () => {
  it("renders a bar chart from a fenced JSON block", () => {
    const md =
      '```chart\n{"type":"bar","title":"Doanh thu","data":[{"label":"T1","value":100},{"label":"T2","value":200}]}\n```';
    const out = renderMarkdown(md);
    expect(out).toContain('<figure class="md-chart">');
    expect(out).toContain("<svg");
    expect(out).toContain('class="md-chart-bar"');
    expect(out).toContain("Doanh thu");
    // bar count = data point count
    expect((out.match(/md-chart-bar/g) ?? []).length).toBe(2);
  });

  it("renders a line chart with the line variant", () => {
    const md =
      '```chart\n{"type":"line","data":[{"label":"a","value":1},{"label":"b","value":3},{"label":"c","value":2}]}\n```';
    const out = renderMarkdown(md);
    expect(out).toContain('class="md-chart-line"');
    expect((out.match(/md-chart-dot/g) ?? []).length).toBe(3);
  });

  it("falls back to <pre> on malformed JSON", () => {
    const md = "```chart\nthis is not JSON\n```";
    const out = renderMarkdown(md);
    expect(out).toContain('<pre class="md-pre">');
    expect(out).not.toContain("<svg");
  });
});

describe("renderMarkdown — fenced code blocks", () => {
  it("non-chart fenced block renders as <pre>", () => {
    const out = renderMarkdown("```python\nprint('hi')\n```");
    expect(out).toContain('<pre class="md-pre">');
    expect(out).toContain("print(&#39;hi&#39;)");
  });
});
