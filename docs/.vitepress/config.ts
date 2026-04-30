import { defineConfig } from "vitepress";
import { withMermaid } from "vitepress-plugin-mermaid";

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
            "Khôi phục dấu, sửa chính tả, OCR, RAG cục bộ — mã nguồn mở, ưu tiên tiếng Việt.",
        },
      ],
    ],

    appearance: false,

    themeConfig: {
      logo: { src: "/logo.svg", alt: "Nôm" },
      siteTitle: "Nôm",

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
            { text: "Khôi phục dấu", link: "/tasks/diacritic-restoration" },
            { text: "Sửa chính tả", link: "/tasks/spell-correction" },
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
            { text: "SOTA tiếng Việt 2026Q2", link: "/sota_vn_2026q2" },
            { text: "Bức tranh OSS 2026Q2", link: "/oss_landscape_2026q2" },
            { text: "Kế hoạch huấn luyện 2026Q2", link: "/training_plan_2026q2" },
            { text: "Phát hành", link: "/release" },
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
