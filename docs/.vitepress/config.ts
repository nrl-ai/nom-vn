import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import { defineConfig } from "vitepress";
import { withMermaid } from "vitepress-plugin-mermaid";

const require = createRequire(import.meta.url);

// pnpm doesn't hoist these into node_modules/<pkg> at the project root, so
// Vite's bare-package resolution fails. Resolve each package's entry through
// Node and walk relative for ESM-shaped sub-paths.
const resolveEntry = (pkg: string) => require.resolve(pkg);
const resolveSubpath = (pkg: string, relative: string) => {
  const entry = require.resolve(pkg);
  return fileURLToPath(new URL(relative, `file://${entry}`));
};
const dayjsEsmEntry = resolveSubpath("dayjs", "./esm/index.js");
const sanitizeUrlEntry = resolveEntry("@braintree/sanitize-url");
const dompurifyEntry = resolveEntry("dompurify");
const cytoscapeEntry = resolveEntry("cytoscape");

// nom-vn documentation site — published at https://nom-vn.nrl.ai
//
// Vietnamese-only. The /vi/ URL prefix is kept for the deep
// pages (intro / quickstart / models) so existing links still work,
// while the root `/` index renders the Vietnamese landing page.

export default withMermaid(
  defineConfig({
    title: "Nôm",
    description:
      "Bộ công cụ AI tiếng Việt — khôi phục dấu, sửa chính tả, OCR, RAG, đánh chỉ mục cục bộ.",
    lang: "vi-VN",

    srcDir: ".",
    cleanUrls: true,

    srcExclude: [
      "research/**",
      "screenshots/**",
      "**/node_modules/**",
      // Historical planning / landscape docs from 2026 Q2. They stay
      // in the repo as decision-record artifacts (GitHub search still
      // finds them) but aren't built into the public site, where the
      // per-task pages and CHANGELOG are the canonical references.
      "training_plan_2026q2.md",
      "sota_vn_2026q2.md",
      "oss_landscape_2026q2.md",
    ],

    // Existing docs/*.md files predate this site and link out to repo
    // paths (training/, benchmarks/, CHANGELOG, etc.) that don't render
    // inside VitePress. We don't want to mass-rewrite those — the docs
    // also serve as repo-root navigation when read directly on GitHub.
    // Allow all repo-relative cross-links; keep external HTTPS link
    // checks active so we still catch real broken external URLs.
    ignoreDeadLinks: [
      "localhost",
      /^https?:\/\/(localhost|127\.0\.0\.1)/,
      // Repo paths surfaced from inside docs/ — present on GitHub but
      // not built into the VitePress site.
      /^(\.\.\/)+(?:training|benchmarks|tests|src|ui|scripts|CHANGELOG|README|CONTRIBUTING)/,
      /(\/|^)CHANGELOG$/,
      /\/training\/.*\/README$/,
      // Sibling docs that are catalogued in markdown indexes but not
      // first-class pages in the rendered site (research notes, dataset
      // index landings inside benchmarks/data, etc.).
      /\/(research|index)$/,
      // Research notes are excluded via srcExclude; suppress link
      // checks on the same paths so the catalog pages still build.
      /^\.\/research\//,
      // Out-of-tree references to the marketing site repo (handled
      // separately).
      /www\.nrl\.ai/,
      // Historical 2026Q2 docs are excluded from the site build but
      // some pages still link to them (catalog / readme refs); GitHub
      // resolves the links, the website doesn't try to.
      /(sota_vn|oss_landscape|training_plan)_2026q2/,
    ],

    head: [
      ["link", { rel: "icon", type: "image/svg+xml", href: "/logo.svg" }],
      ["meta", { name: "theme-color", content: "#b5563a" }],
      [
        "meta",
        {
          property: "og:title",
          content: "Nôm — Bộ công cụ AI tiếng Việt",
        },
      ],
      [
        "meta",
        {
          property: "og:description",
          content:
            "Khôi phục dấu, sửa chính tả, OCR, RAG cục bộ — mã nguồn mở, dành cho tiếng Việt.",
        },
      ],
      // Formspree — used by the enterprise contact form on /doanh-nghiep/.
      // VitePress is an SPA, so we listen for navigation and init Formspree
      // each time the form mounts. We only load the ajax script when at least
      // one such page actually wants it.
      [
        "script",
        {},
        `
          (function () {
            window.formspree = window.formspree || function () {
              (formspree.q = formspree.q || []).push(arguments);
            };
            var loaded = false;
            function ensureScript() {
              if (loaded) return;
              loaded = true;
              var s = document.createElement("script");
              s.src = "https://unpkg.com/@formspree/ajax@1";
              s.defer = true;
              document.head.appendChild(s);
            }
            function tryInit() {
              if (!document.getElementById("nom-enterprise-form")) return;
              ensureScript();
              window.formspree("initForm", {
                formElement: "#nom-enterprise-form",
                formId: "mdabkvky",
              });
            }
            if (document.readyState === "loading") {
              document.addEventListener("DOMContentLoaded", tryInit);
            } else {
              tryInit();
            }
            // SPA navigations: re-check on each route change.
            var origPush = history.pushState;
            history.pushState = function () {
              var ret = origPush.apply(this, arguments);
              setTimeout(tryInit, 50);
              return ret;
            };
            window.addEventListener("popstate", function () {
              setTimeout(tryInit, 50);
            });
          })();
        `,
      ],
    ],

    appearance: false,

    vite: {
      resolve: {
        // Array form so we can use exact-match regexes — object aliases do
        // prefix-replace which breaks `dayjs/plugin/*` sub-paths.
        alias: [
          // vitepress-plugin-mermaid pulls these via optimizeDeps but pnpm
          // doesn't hoist them to node_modules/<pkg>. Without a root-reachable
          // path, Vite serves the raw CJS file and named-imports break. Alias
          // each bare specifier to its absolute entry so Vite's pre-bundler can
          // perform CJS→ESM interop and expose named exports correctly.
          { find: /^dayjs$/, replacement: dayjsEsmEntry },
          { find: /^@braintree\/sanitize-url$/, replacement: sanitizeUrlEntry },
          { find: /^dompurify$/, replacement: dompurifyEntry },
          { find: /^cytoscape$/, replacement: cytoscapeEntry },
        ],
      },
      // Force-bundle mermaid so the browser doesn't fan out to hundreds of
      // individual d3-* requests (ERR_INSUFFICIENT_RESOURCES on the home
      // page). The mermaid plugin doesn't add mermaid itself; we do.
      optimizeDeps: {
        include: ["mermaid"],
      },
    },

    themeConfig: {
      logo: { src: "/logo.svg", alt: "Nôm" },
      siteTitle: "Nôm",

      nav: [
        { text: "Bắt đầu", link: "/vi/quickstart" },
        { text: "Tài liệu", link: "/vi/" },
        {
          text: "Tác vụ",
          items: [
            { text: "Tổng quan", link: "/tasks/" },
            { text: "Khôi phục dấu", link: "/tasks/diacritic-restoration" },
            { text: "Sửa chính tả", link: "/tasks/spell-correction" },
            { text: "Chuẩn hoá văn bản", link: "/tasks/text-normalization" },
            { text: "Tách từ", link: "/tasks/word-segmentation" },
            { text: "OCR", link: "/tasks/ocr" },
            { text: "Trích văn bản PDF", link: "/tasks/pdf-extraction" },
            { text: "Embedding", link: "/tasks/embedding" },
            { text: "Reranker", link: "/tasks/reranker" },
            { text: "RAG end-to-end", link: "/tasks/rag" },
            { text: "Tuân thủ Luật 134/2025", link: "/tasks/compliance" },
          ],
        },
        { text: "Mô hình", link: "/vi/models" },
        { text: "Đánh giá", link: "/benchmark" },
        { text: "Tuân thủ", link: "/compliance/" },
        { text: "Doanh nghiệp", link: "/doanh-nghiep/" },
        {
          text: "Liên kết",
          items: [
            { text: "GitHub", link: "https://github.com/nrl-ai/nom-vn" },
            { text: "PyPI", link: "https://pypi.org/project/nom-vn" },
            {
              text: "Hugging Face",
              link: "https://huggingface.co/nrl-ai",
            },
          ],
        },
      ],

      sidebar: [
        {
          text: "Bắt đầu",
          items: [
            { text: "Giới thiệu", link: "/vi/" },
            { text: "Cài đặt nhanh", link: "/vi/quickstart" },
            { text: "Mô hình đã huấn luyện", link: "/vi/models" },
          ],
        },
        {
          text: "Tác vụ",
          items: [
            { text: "Tổng quan", link: "/tasks/" },
            { text: "Khôi phục dấu", link: "/tasks/diacritic-restoration" },
            { text: "Sửa chính tả", link: "/tasks/spell-correction" },
            { text: "Chuẩn hoá văn bản", link: "/tasks/text-normalization" },
            { text: "Tách từ", link: "/tasks/word-segmentation" },
            { text: "OCR", link: "/tasks/ocr" },
            { text: "Trích văn bản PDF", link: "/tasks/pdf-extraction" },
            { text: "Embedding", link: "/tasks/embedding" },
            { text: "Reranker", link: "/tasks/reranker" },
            { text: "RAG end-to-end", link: "/tasks/rag" },
            { text: "Tuân thủ Luật 134/2025", link: "/tasks/compliance" },
          ],
        },
        {
          text: "Tuân thủ",
          items: [
            { text: "Tổng quan", link: "/compliance/" },
            { text: "Tóm tắt Luật 134/2025", link: "/compliance/luat-134-2025" },
            { text: "Chi tiết kỹ thuật", link: "/tasks/compliance" },
          ],
        },
        {
          text: "Tham khảo",
          items: [
            { text: "Kiến trúc", link: "/architecture" },
            { text: "Pipeline", link: "/pipeline" },
            { text: "Công thức triển khai", link: "/recipes" },
            { text: "Đánh giá", link: "/benchmark" },
            { text: "Bộ dữ liệu", link: "/datasets" },
          ],
        },
      ],

      outline: {
        level: [2, 3],
        label: "Trên trang",
      },
      docFooter: {
        prev: "Trang trước",
        next: "Trang sau",
      },
      lastUpdatedText: "Cập nhật lần cuối",
      darkModeSwitchLabel: "Giao diện",
      sidebarMenuLabel: "Menu",
      returnToTopLabel: "Lên đầu trang",
      editLink: {
        pattern:
          "https://github.com/nrl-ai/nom-vn/edit/main/docs/:path",
        text: "Chỉnh sửa trên GitHub",
      },

      search: {
        provider: "local",
        options: {
          translations: {
            button: {
              buttonText: "Tìm kiếm",
              buttonAriaLabel: "Tìm kiếm",
            },
            modal: {
              displayDetails: "Hiện chi tiết",
              resetButtonTitle: "Xoá tìm kiếm",
              backButtonTitle: "Quay lại",
              noResultsText: "Không có kết quả cho",
              footer: {
                selectText: "chọn",
                selectKeyAriaLabel: "Enter",
                navigateText: "di chuyển",
                navigateUpKeyAriaLabel: "lên",
                navigateDownKeyAriaLabel: "xuống",
                closeText: "đóng",
                closeKeyAriaLabel: "Esc",
              },
            },
          },
        },
      },

      socialLinks: [
        { icon: "github", link: "https://github.com/nrl-ai/nom-vn" },
      ],

      footer: {
        message:
          'Phát hành theo giấy phép <a href="https://github.com/nrl-ai/nom-vn/blob/main/LICENSE">Apache 2.0</a>.',
        copyright:
          'Copyright © 2026 <a href="mailto:vietanh@nrl.ai">Viet-Anh Nguyen</a> · Neural Research Lab',
      },
    },
  }),
);
