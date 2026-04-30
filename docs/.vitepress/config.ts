import { defineConfig } from "vitepress";
import { withMermaid } from "vitepress-plugin-mermaid";

// nom-vn documentation site — published at https://nom-vn.nrl.ai
//
// Vietnamese is the primary language; the English structure is
// scaffolded under /en/ so we can fill it in incrementally without
// re-architecting later. Default landing page is the Vietnamese index.

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
      // Cross-language deep links resolve only after both locales fill in.
      /^\/en\//,
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
    ],

    head: [
      ["link", { rel: "icon", type: "image/png", href: "/favicon.png" }],
      ["meta", { name: "theme-color", content: "#c46a37" }],
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
            "Khôi phục dấu, sửa chính tả, OCR, RAG cục bộ — mã nguồn mở, ưu tiên tiếng Việt.",
        },
      ],
    ],

    appearance: false,

    locales: {
      root: {
        label: "Tiếng Việt",
        lang: "vi-VN",
        title: "Nôm",
        description:
          "Bộ công cụ AI tiếng Việt — khôi phục dấu, sửa chính tả, OCR, RAG, đánh chỉ mục cục bộ.",
        themeConfig: {
          nav: [
            { text: "Bắt đầu", link: "/vi/quickstart" },
            { text: "Tài liệu", link: "/vi/" },
            { text: "Mô hình", link: "/vi/models" },
            { text: "Đánh giá", link: "/benchmark" },
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

          sidebar: {
            "/vi/": [
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
                  {
                    text: "Khôi phục dấu",
                    link: "/tasks/diacritic-restoration",
                  },
                  {
                    text: "Sửa chính tả",
                    link: "/tasks/spell-correction",
                  },
                ],
              },
              {
                text: "Tham khảo",
                items: [
                  { text: "Kiến trúc", link: "/architecture" },
                  { text: "Pipeline", link: "/pipeline" },
                  { text: "Recipes", link: "/recipes" },
                  { text: "Đánh giá", link: "/benchmark" },
                  { text: "Bộ dữ liệu", link: "/datasets" },
                  { text: "SOTA tiếng Việt 2026Q2", link: "/sota_vn_2026q2" },
                ],
              },
            ],
            "/tasks/": [
              {
                text: "Tác vụ",
                items: [
                  {
                    text: "Khôi phục dấu",
                    link: "/tasks/diacritic-restoration",
                  },
                  {
                    text: "Sửa chính tả",
                    link: "/tasks/spell-correction",
                  },
                ],
              },
            ],
          },

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
        },
      },
      en: {
        label: "English",
        lang: "en-US",
        link: "/en/",
        title: "Nôm",
        description:
          "Vietnamese AI toolkit — diacritic restoration, spell correction, OCR, RAG, on-device indexing.",
        themeConfig: {
          nav: [
            { text: "Get started", link: "/en/quickstart" },
            { text: "Docs", link: "/en/" },
            { text: "Models", link: "/en/models" },
            { text: "Benchmarks", link: "/benchmark" },
            {
              text: "Links",
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

          sidebar: {
            "/en/": [
              {
                text: "Start here",
                items: [
                  { text: "Introduction", link: "/en/" },
                  { text: "Quickstart", link: "/en/quickstart" },
                  { text: "Trained models", link: "/en/models" },
                ],
              },
              {
                text: "Tasks",
                items: [
                  {
                    text: "Diacritic restoration",
                    link: "/tasks/diacritic-restoration",
                  },
                  {
                    text: "Spell correction",
                    link: "/tasks/spell-correction",
                  },
                ],
              },
              {
                text: "Reference",
                items: [
                  { text: "Architecture", link: "/architecture" },
                  { text: "Pipeline", link: "/pipeline" },
                  { text: "Recipes", link: "/recipes" },
                  { text: "Benchmarks", link: "/benchmark" },
                  { text: "Datasets", link: "/datasets" },
                  { text: "VN SOTA 2026Q2", link: "/sota_vn_2026q2" },
                ],
              },
            ],
          },

          editLink: {
            pattern:
              "https://github.com/nrl-ai/nom-vn/edit/main/docs/:path",
            text: "Edit on GitHub",
          },
        },
      },
    },

    themeConfig: {
      logo: "/logo.svg",
      siteTitle: "Nôm",

      search: {
        provider: "local",
        options: {
          locales: {
            root: {
              translations: {
                button: {
                  buttonText: "Tìm kiếm",
                  buttonAriaLabel: "Tìm kiếm",
                },
                modal: {
                  noResultsText: "Không có kết quả cho",
                  resetButtonTitle: "Xoá tìm kiếm",
                  footer: {
                    selectText: "chọn",
                    navigateText: "di chuyển",
                  },
                },
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
