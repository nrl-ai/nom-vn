"""Generate a realistic Vietnamese scanned-document evaluation set.

Earlier OCR baselines used `synthetic_ocr_vi/` which is line-level
crops (1017x78 px). Real users scan multi-page contracts, receipts,
government decrees, and forms — the OCR-fallback path needs to be
measured on whole-document inputs, not lines.

This generator builds 12 documents across four categories that real
nom-vn users would scan:

- Contracts (3): hợp đồng lao động, hợp đồng kinh tế, hợp đồng thuê nhà
- Receipts (3): biên lai thu tiền, hoá đơn bán hàng, phiếu chi
- Government (3): công văn, thông báo, quyết định
- Forms (3): đơn xin nghỉ việc, đơn xác nhận, biểu mẫu khai báo

Each document:
1. Is rendered to PNG pages with PIL + DejaVuSans (1700x2200px @ 200 dpi A4-ish).
2. Is then embedded into an image-only PDF (no text layer) so
   `pdf_to_docx` is forced through the OCR fallback path.
3. Ships with per-page ground-truth text in `metadata.jsonl`.

Content is synthetic — names, dates, IDs, amounts are all fictional.
This keeps the dataset publishable as CC0 / Apache-2.0 with no PII or
copyright concern.

Run:
    python benchmarks/data/vn_documents_ocr/_generate.py

Outputs (under benchmarks/data/vn_documents_ocr/):
    pages/<doc_id>_p<n>.png       — one PNG per page
    docs/<doc_id>.pdf             — image-only PDF assembled from pages
    metadata.jsonl                — {doc_id, category, n_pages, pages: [{path, text}]}
    README.md                     — dataset card (CC0)
"""

from __future__ import annotations

import json
import textwrap
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as rl_canvas

ROOT = Path(__file__).resolve().parent
PAGES_DIR = ROOT / "pages"
DOCS_DIR = ROOT / "docs"

DEJAVU_REGULAR = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
DEJAVU_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")

# A4-ish at ~200 dpi: 8.27 x 11.69 in → 1654 x 2339 px. Round.
PAGE_W = 1700
PAGE_H = 2200
MARGIN = 120
BODY_FONT_SIZE = 28
TITLE_FONT_SIZE = 38
HEADER_FONT_SIZE = 32


@dataclass
class Doc:
    doc_id: str
    category: str
    title: str
    body: str  # plain text, paragraphs separated by blank lines

    def pages_text(self) -> list[str]:
        """Split body into pages by paragraph fitting heuristic."""
        # We keep it simple: one page unless the body overflows the wrap.
        # Pages are produced by the renderer; this function just returns
        # the canonical text split into pages by the same rule the
        # renderer uses (so ground truth and rendering stay aligned).
        return _split_into_pages(self.title, self.body)


def _split_into_pages(title: str, body: str) -> list[str]:
    """Yield page text in the same order the renderer lays them out.

    The renderer paginates by line count; this function mirrors it so
    metadata.jsonl matches what's drawn on each page. Approximation:
    the title takes 3 lines on page 1, then ~52 wrapped body lines fit
    per page. `body` paragraphs are separated by blank lines.
    """
    lines_per_page = 52  # body lines after the title block
    page_one_body = lines_per_page - 4

    paras = body.strip().split("\n\n")
    wrapped: list[str] = []
    for p in paras:
        wrapped.extend(textwrap.wrap(p, width=70) or [""])
        wrapped.append("")  # paragraph break

    # Page 1: title + first chunk
    pages: list[str] = []
    cur: list[str] = [title, "", ""]
    cap = page_one_body
    for ln in wrapped:
        if cap <= 0:
            pages.append("\n".join(cur).rstrip())
            cur = [ln]
            cap = lines_per_page - 1
        else:
            cur.append(ln)
            cap -= 1
    if cur:
        pages.append("\n".join(cur).rstrip())
    return pages


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def _render_page(text: str, *, is_first: bool) -> Image.Image:
    img = Image.new("RGB", (PAGE_W, PAGE_H), color="white")
    draw = ImageDraw.Draw(img)

    body_font = _font(DEJAVU_REGULAR, BODY_FONT_SIZE)
    title_font = _font(DEJAVU_BOLD, TITLE_FONT_SIZE)

    y = MARGIN
    lines = text.splitlines()
    if not lines:
        return img

    if is_first:
        # First non-empty line is title (centered, bold)
        title = lines[0].strip() or " "
        bbox = draw.textbbox((0, 0), title, font=title_font)
        title_w = bbox[2] - bbox[0]
        draw.text(((PAGE_W - title_w) // 2, y), title, fill="black", font=title_font)
        y += TITLE_FONT_SIZE + 30
        lines = lines[1:]

    for ln in lines:
        if y > PAGE_H - MARGIN:
            break
        # Skip leading empty lines on the first body line
        draw.text((MARGIN, y), ln, fill="black", font=body_font)
        y += int(BODY_FONT_SIZE * 1.35)
    return img


def _assemble_pdf(pages: list[Image.Image], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    # PDF page sized to native pixel dims @ 200 dpi → simulates a 200dpi scan.
    page_w_pt = PAGE_W * 72 / 200
    page_h_pt = PAGE_H * 72 / 200
    c = rl_canvas.Canvas(str(out), pagesize=(page_w_pt, page_h_pt))
    for img in pages:
        c.drawImage(ImageReader(img), 0, 0, page_w_pt, page_h_pt)
        c.showPage()
    c.save()


# ---------- Document templates ----------

CONTRACTS = [
    Doc(
        doc_id="contract_lao_dong",
        category="contract",
        title="HỢP ĐỒNG LAO ĐỘNG",
        body="""Số: 042/HĐLĐ/2026

Hôm nay, ngày 15 tháng 04 năm 2026, tại trụ sở Công ty Cổ phần Phát triển Phần mềm Hà Nội, chúng tôi gồm có:

BÊN A (Người sử dụng lao động):
Tên doanh nghiệp: Công ty Cổ phần Phát triển Phần mềm Hà Nội
Địa chỉ: Số 12, đường Tràng Thi, phường Hàng Bông, quận Hoàn Kiếm, thành phố Hà Nội.
Mã số doanh nghiệp: 0312345678
Đại diện: Ông Nguyễn Văn An — Chức vụ: Tổng Giám đốc

BÊN B (Người lao động):
Họ và tên: Bà Lê Thị Hương
Ngày sinh: 12/06/1992
CCCD số: 024092001234, cấp ngày 03/05/2021 tại Cục Cảnh sát Quản lý hành chính.
Địa chỉ thường trú: Số 45, ngõ 90, đường Lê Trọng Tấn, phường Khương Mai, quận Thanh Xuân, thành phố Hà Nội.
Số điện thoại liên hệ: 0987 654 321

Hai bên cùng thống nhất ký kết hợp đồng lao động này với các điều khoản và điều kiện sau đây:

Điều 1. Công việc và địa điểm làm việc
Bên B đồng ý đảm nhận chức vụ Kỹ sư phần mềm cao cấp tại bộ phận phát triển sản phẩm. Địa điểm làm việc: trụ sở chính của Bên A.

Điều 2. Thời hạn hợp đồng và mức lương
Hợp đồng có thời hạn ba mươi sáu tháng, tính từ ngày 01/05/2026 đến ngày 30/04/2029. Mức lương cơ bản hàng tháng là 35.000.000 đồng (Ba mươi lăm triệu đồng). Lương được trả vào ngày mùng 5 hàng tháng qua tài khoản ngân hàng Vietcombank của Bên B.

Điều 3. Bảo hiểm và quyền lợi
Bên A đóng đầy đủ bảo hiểm xã hội, bảo hiểm y tế, bảo hiểm thất nghiệp cho Bên B theo quy định của pháp luật hiện hành.""",
    ),
    Doc(
        doc_id="contract_thue_nha",
        category="contract",
        title="HỢP ĐỒNG THUÊ NHÀ",
        body="""Số: 087/HĐTN/2026

Hôm nay, ngày 22 tháng 03 năm 2026, tại Phòng công chứng số 5 thành phố Đà Nẵng, chúng tôi gồm:

BÊN CHO THUÊ (Bên A):
Họ và tên: Ông Trần Quốc Hùng
Ngày sinh: 25/11/1968
CMND số: 201234567, cấp ngày 15/06/2009 tại Công an thành phố Đà Nẵng.
Địa chỉ thường trú: Số 78, đường Nguyễn Văn Linh, phường Nam Dương, quận Hải Châu, thành phố Đà Nẵng.

BÊN THUÊ (Bên B):
Họ và tên: Bà Phạm Thị Ngọc Mai
Ngày sinh: 03/02/1985
CCCD số: 048085003456, cấp ngày 10/08/2022 tại Cục Cảnh sát Quản lý hành chính.
Địa chỉ thường trú: Số 12, ngõ 5, đường Hoàng Diệu, quận Hải Châu, thành phố Đà Nẵng.
Số điện thoại: 0905 123 456

Hai bên thống nhất ký kết hợp đồng thuê nhà với các điều khoản:

Điều 1. Đối tượng cho thuê
Bên A đồng ý cho Bên B thuê căn nhà ba tầng tại địa chỉ: Số 78, đường Nguyễn Văn Linh, phường Nam Dương, quận Hải Châu, thành phố Đà Nẵng. Diện tích sử dụng 120 mét vuông. Tình trạng nhà tốt, đầy đủ hệ thống điện nước.

Điều 2. Thời hạn và giá thuê
Thời hạn thuê là hai mươi bốn tháng, từ ngày 01/04/2026 đến ngày 31/03/2028. Giá thuê là 18.000.000 đồng mỗi tháng (Mười tám triệu đồng). Tiền thuê được thanh toán vào ngày mùng 1 hàng tháng bằng chuyển khoản.""",
    ),
    Doc(
        doc_id="contract_kinh_te",
        category="contract",
        title="HỢP ĐỒNG KINH TẾ",
        body="""Số: 015/HĐKT/2026

Hôm nay, ngày 08 tháng 02 năm 2026, tại trụ sở Công ty Trách nhiệm hữu hạn Thương mại Phương Nam, chúng tôi gồm:

BÊN A (Bên mua):
Tên doanh nghiệp: Công ty Cổ phần Sản xuất Vật liệu Xây dựng Việt Nhất
Địa chỉ: Khu công nghiệp Tân Tạo, quận Bình Tân, thành phố Hồ Chí Minh.
Mã số thuế: 0301234567
Đại diện: Ông Vũ Thanh Long — Tổng Giám đốc

BÊN B (Bên bán):
Tên doanh nghiệp: Công ty Trách nhiệm hữu hạn Thương mại Phương Nam
Địa chỉ: Số 234, đường Cách Mạng Tháng Tám, quận 3, thành phố Hồ Chí Minh.
Mã số thuế: 0312456789
Đại diện: Bà Đặng Bích Vân — Giám đốc

Hai bên thống nhất ký kết hợp đồng mua bán hàng hoá:

Điều 1. Đối tượng hợp đồng
Bên B bán cho Bên A một nghìn năm trăm tấn xi măng PCB30, đóng bao 50 kilôgam, sản xuất tại nhà máy Hà Tiên 2. Tổng khối lượng giao trong vòng sáu mươi ngày kể từ ngày ký hợp đồng.

Điều 2. Giá trị hợp đồng và phương thức thanh toán
Đơn giá là 1.450.000 đồng mỗi tấn (đã bao gồm thuế giá trị gia tăng 10 phần trăm). Tổng giá trị hợp đồng là 2.175.000.000 đồng (Hai tỷ một trăm bảy mươi lăm triệu đồng).

Bên A thanh toán cho Bên B bằng chuyển khoản qua ngân hàng VietinBank theo lộ trình: tạm ứng 30 phần trăm khi ký hợp đồng, 50 phần trăm sau khi giao đủ một nửa hàng, và 20 phần trăm còn lại trong vòng mười lăm ngày kể từ ngày giao hàng cuối.""",
    ),
]

RECEIPTS = [
    Doc(
        doc_id="receipt_hoa_don",
        category="receipt",
        title="HOÁ ĐƠN GIÁ TRỊ GIA TĂNG",
        body="""Mẫu số: 01GTKT0/001
Ký hiệu: AB/26P
Số: 0000128

Đơn vị bán hàng: Công ty Trách nhiệm hữu hạn Văn phòng phẩm Trí Đức
Mã số thuế: 0314567890
Địa chỉ: Số 56, đường Nguyễn Trãi, quận Thanh Xuân, thành phố Hà Nội.
Số điện thoại: 024 3858 7654

Họ tên người mua: Bà Hoàng Thị Lan
Đơn vị: Công ty Cổ phần Truyền thông Sao Mai
Mã số thuế: 0301678234
Địa chỉ: Số 89, đường Lý Thường Kiệt, quận Hoàn Kiếm, thành phố Hà Nội.

Hình thức thanh toán: Chuyển khoản
Mã số tài khoản: 0123456789 — Ngân hàng Vietcombank Chi nhánh Hà Nội

STT — Tên hàng hoá — Đơn vị tính — Số lượng — Đơn giá — Thành tiền

1 — Giấy in A4 70 gam Bãi Bằng — Ream — 50 — 95.000 — 4.750.000
2 — Bút bi Thiên Long TL-027 — Hộp — 20 — 65.000 — 1.300.000
3 — Mực in HP CC388A đen — Hộp — 10 — 1.450.000 — 14.500.000
4 — Sổ tay bìa cứng A5 — Quyển — 30 — 75.000 — 2.250.000

Cộng tiền hàng: 22.800.000 đồng
Thuế suất giá trị gia tăng: 10 phần trăm
Tiền thuế giá trị gia tăng: 2.280.000 đồng
Tổng cộng tiền thanh toán: 25.080.000 đồng

Bằng chữ: Hai mươi lăm triệu không trăm tám mươi nghìn đồng chẵn.

Hà Nội, ngày 12 tháng 04 năm 2026.""",
    ),
    Doc(
        doc_id="receipt_bien_lai",
        category="receipt",
        title="BIÊN LAI THU TIỀN",
        body="""Số: 0345/BL/2026

Đơn vị thu tiền: Trường Trung học Phổ thông Phan Đình Phùng
Địa chỉ: Số 30, đường Cửa Bắc, quận Ba Đình, thành phố Hà Nội.
Mã đơn vị: 04T0123456

Họ và tên người nộp tiền: Bà Đỗ Thị Hồng
Địa chỉ: Số 22, ngõ 85, phố Đội Cấn, quận Ba Đình, thành phố Hà Nội.
Số điện thoại: 0913 765 432

Lý do nộp tiền:
Học phí học kỳ hai năm học 2025 — 2026 cho học sinh Đỗ Minh Quân, lớp 11A3.

Số tiền thu: 4.500.000 đồng
Bằng chữ: Bốn triệu năm trăm nghìn đồng chẵn.

Hình thức thanh toán: Tiền mặt

Hà Nội, ngày 18 tháng 03 năm 2026.

Người nộp tiền                                  Người thu tiền
(Ký, ghi rõ họ tên)                            (Ký, ghi rõ họ tên)


Đỗ Thị Hồng                                    Nguyễn Hoài Thu""",
    ),
    Doc(
        doc_id="receipt_phieu_chi",
        category="receipt",
        title="PHIẾU CHI",
        body="""Số: PC/2026/0089

Đơn vị: Công ty Trách nhiệm hữu hạn Du lịch Hồng Hà
Địa chỉ: Số 17, đường Trần Phú, thành phố Vinh, tỉnh Nghệ An.

Họ và tên người nhận: Ông Lương Quang Trí
Đơn vị / Bộ phận: Phòng Kế toán
Lý do chi: Thanh toán tiền công tác phí cho chuyến đi khảo sát thị trường tại các tỉnh miền Trung từ ngày 05/03 đến 12/03/2026.

Số tiền: 12.450.000 đồng
Bằng chữ: Mười hai triệu bốn trăm năm mươi nghìn đồng chẵn.

Kèm theo: Bốn chứng từ gốc (vé máy bay, hoá đơn khách sạn, hoá đơn ăn uống, vé taxi).

Vinh, ngày 14 tháng 03 năm 2026.

Giám đốc          Kế toán trưởng         Người lập phiếu        Người nhận tiền
(Ký, đóng dấu)    (Ký, ghi rõ họ tên)   (Ký, ghi rõ họ tên)   (Ký, ghi rõ họ tên)


Trần Văn Sơn      Phạm Thị Bình         Nguyễn Hoài An         Lương Quang Trí""",
    ),
]

GOVERNMENT = [
    Doc(
        doc_id="govt_cong_van",
        category="government",
        title="CÔNG VĂN",
        body="""Số: 1234/UBND-VX
Về việc tổ chức lễ kỷ niệm Ngày Giải phóng miền Nam thống nhất đất nước.

Kính gửi:
— Các sở, ban, ngành thành phố;
— Uỷ ban nhân dân các quận, huyện;
— Các cơ quan, đơn vị, doanh nghiệp đóng trên địa bàn thành phố.

Căn cứ Luật Tổ chức chính quyền địa phương ngày 19 tháng 6 năm 2015;

Căn cứ Nghị định số 145/2023/NĐ-CP ngày 18 tháng 12 năm 2023 của Chính phủ về tổ chức các sự kiện chính trị quan trọng;

Thực hiện Kế hoạch số 234/KH-UBND ngày 15 tháng 03 năm 2026 của Uỷ ban nhân dân thành phố,

Chủ tịch Uỷ ban nhân dân thành phố yêu cầu các cơ quan, đơn vị thực hiện một số nội dung sau:

Một là, tổ chức tuyên truyền sâu rộng về ý nghĩa lịch sử của Ngày 30 tháng 4. Triển khai treo cờ tổ quốc, băng rôn, khẩu hiệu tại trụ sở cơ quan, các tuyến đường chính, khu dân cư từ ngày 25 tháng 4 đến hết ngày 02 tháng 5 năm 2026.

Hai là, tổ chức lễ dâng hương tại Đài tưởng niệm các anh hùng liệt sĩ vào hồi 7 giờ 30 phút ngày 30 tháng 4 năm 2026. Mời lãnh đạo các sở, ban, ngành tham dự.

Ba là, các cơ quan tổ chức gặp mặt cán bộ hưu trí, thân nhân gia đình chính sách trên địa bàn. Báo cáo kết quả về Văn phòng Uỷ ban nhân dân thành phố trước ngày 10 tháng 5 năm 2026.

Đề nghị các cơ quan, đơn vị nghiêm túc triển khai thực hiện.

Trân trọng.

Hà Nội, ngày 18 tháng 04 năm 2026.

KT. CHỦ TỊCH
PHÓ CHỦ TỊCH
Trần Quốc Hoàng""",
    ),
    Doc(
        doc_id="govt_thong_bao",
        category="government",
        title="THÔNG BÁO",
        body="""Số: 567/TB-SGD
Về việc tổ chức kỳ thi tốt nghiệp Trung học phổ thông năm 2026.

Kính gửi: Hiệu trưởng các trường Trung học phổ thông trên địa bàn tỉnh.

Căn cứ Thông tư số 15/2024/TT-BGDĐT ngày 22 tháng 11 năm 2024 của Bộ Giáo dục và Đào tạo về Quy chế thi tốt nghiệp Trung học phổ thông;

Căn cứ Kế hoạch số 89/KH-SGD ngày 02 tháng 03 năm 2026 của Sở Giáo dục và Đào tạo,

Sở Giáo dục và Đào tạo thông báo:

Thứ nhất, kỳ thi tốt nghiệp Trung học phổ thông năm 2026 được tổ chức trong hai ngày, từ 27 đến 28 tháng 6 năm 2026, tại 25 điểm thi trên toàn tỉnh.

Thứ hai, lịch thi cụ thể như sau:
— Ngày 27 tháng 6 năm 2026: buổi sáng thi môn Ngữ Văn (120 phút), buổi chiều thi môn Toán (90 phút).
— Ngày 28 tháng 6 năm 2026: buổi sáng thi tổ hợp Khoa học Tự nhiên hoặc Khoa học Xã hội (150 phút), buổi chiều thi môn Ngoại ngữ (60 phút).

Thứ ba, các trường có trách nhiệm hoàn thành công tác đăng ký dự thi cho học sinh trước ngày 30 tháng 4 năm 2026. Tổ chức ôn tập, hướng dẫn quy chế thi cho học sinh và phụ huynh.

Đề nghị Hiệu trưởng các trường nghiêm túc triển khai thực hiện. Trong quá trình thực hiện, nếu có vướng mắc, đề nghị liên hệ về Phòng Khảo thí của Sở để được hướng dẫn.

Trân trọng.

Đà Lạt, ngày 24 tháng 03 năm 2026.

GIÁM ĐỐC SỞ
Lê Thanh Tùng""",
    ),
    Doc(
        doc_id="govt_quyet_dinh",
        category="government",
        title="QUYẾT ĐỊNH",
        body="""Số: 789/QĐ-UBND
Về việc phê duyệt dự án đầu tư xây dựng Trường Tiểu học Lê Quý Đôn.

CHỦ TỊCH UỶ BAN NHÂN DÂN THÀNH PHỐ

Căn cứ Luật Tổ chức chính quyền địa phương số 77/2015/QH13 ngày 19 tháng 6 năm 2015;

Căn cứ Luật Đầu tư công số 39/2019/QH14 ngày 13 tháng 6 năm 2019;

Căn cứ Nghị định số 40/2020/NĐ-CP ngày 06 tháng 4 năm 2020 của Chính phủ quy định chi tiết Luật Đầu tư công;

Xét Tờ trình số 156/TTr-SXD ngày 20 tháng 02 năm 2026 của Sở Xây dựng,

QUYẾT ĐỊNH:

Điều 1. Phê duyệt dự án đầu tư xây dựng Trường Tiểu học Lê Quý Đôn, phường Tân Phú, quận 7, thành phố Hồ Chí Minh, với những nội dung chính như sau:

Tên dự án: Trường Tiểu học Lê Quý Đôn.
Chủ đầu tư: Ban Quản lý dự án Đầu tư xây dựng quận 7.
Địa điểm: Đường Lê Văn Lương, phường Tân Phú, quận 7.
Diện tích đất: 8.500 mét vuông.
Quy mô: Trường gồm 32 lớp học, 1 phòng đa năng, khu hành chính, sân thể thao và bãi gửi xe.
Tổng mức đầu tư: 86.000.000.000 đồng (Tám mươi sáu tỷ đồng).
Nguồn vốn: Ngân sách thành phố.
Thời gian thực hiện: 18 tháng kể từ ngày khởi công.

Điều 2. Giao Sở Xây dựng chủ trì, phối hợp với Sở Tài chính, Uỷ ban nhân dân quận 7 và các đơn vị liên quan tổ chức triển khai thực hiện theo đúng quy định.

Điều 3. Quyết định này có hiệu lực kể từ ngày ký. Chánh Văn phòng Uỷ ban nhân dân thành phố và các cơ quan liên quan chịu trách nhiệm thi hành Quyết định này.

Thành phố Hồ Chí Minh, ngày 28 tháng 02 năm 2026.

CHỦ TỊCH
Phan Thị Mỹ Lan""",
    ),
]

FORMS = [
    Doc(
        doc_id="form_xin_nghi_viec",
        category="form",
        title="ĐƠN XIN NGHỈ VIỆC",
        body="""Kính gửi:
— Ban Giám đốc Công ty Cổ phần Tài chính Bảo Tín;
— Phòng Nhân sự Công ty Cổ phần Tài chính Bảo Tín.

Tôi tên là: Vũ Thị Thảo Linh
Ngày sinh: 18 tháng 09 năm 1990
CCCD số: 001190001234, cấp ngày 12 tháng 05 năm 2021 tại Cục Cảnh sát Quản lý hành chính.
Địa chỉ thường trú: Số 27, ngõ 102, đường Đại La, quận Hai Bà Trưng, thành phố Hà Nội.
Số điện thoại: 0987 234 567

Hiện tôi đang công tác tại: Phòng Tài chính
Chức vụ: Chuyên viên kế toán
Mã nhân viên: NV2018045
Ngày bắt đầu làm việc: 03 tháng 03 năm 2018

Nay tôi viết đơn này kính đề nghị Ban Giám đốc và Phòng Nhân sự xem xét, cho phép tôi được nghỉ việc kể từ ngày 15 tháng 05 năm 2026.

Lý do: Vì hoàn cảnh gia đình, tôi cần dành thời gian chăm sóc cha mẹ tại quê nhà, đồng thời chuẩn bị cho việc học cao học vào học kỳ mùa thu năm 2026.

Trong thời gian từ ngày nhận được đơn này đến ngày nghỉ chính thức, tôi cam kết:
— Hoàn thành đầy đủ các công việc đang đảm nhận.
— Bàn giao công việc, hồ sơ, tài liệu cho người được phân công tiếp nhận.
— Tuân thủ quy định bảo mật thông tin của công ty.

Tôi xin chân thành cảm ơn Ban Giám đốc và các đồng nghiệp trong suốt thời gian tám năm làm việc đã tạo điều kiện và hỗ trợ tôi rất nhiều trong công việc.

Kính mong được Ban Giám đốc xem xét và chấp thuận.

Hà Nội, ngày 30 tháng 03 năm 2026.

Người làm đơn
(Ký và ghi rõ họ tên)


Vũ Thị Thảo Linh""",
    ),
    Doc(
        doc_id="form_xac_nhan_cu_tru",
        category="form",
        title="ĐƠN XIN XÁC NHẬN CƯ TRÚ",
        body="""Kính gửi: Công an phường Phước Long, quận 9, thành phố Hồ Chí Minh.

Tôi tên là: Nguyễn Đức Mạnh
Ngày sinh: 04 tháng 11 năm 1986
CCCD số: 077086004567, cấp ngày 25 tháng 08 năm 2022 tại Cục Cảnh sát Quản lý hành chính.
Số điện thoại: 0908 567 123

Địa chỉ thường trú trước đây: Số 18, đường Phan Văn Trị, phường 5, quận Gò Vấp, thành phố Hồ Chí Minh.
Địa chỉ tạm trú hiện tại: Căn hộ 1205, toà nhà Sun View, số 250 đường Đỗ Xuân Hợp, phường Phước Long, quận 9, thành phố Hồ Chí Minh.
Thời gian bắt đầu cư trú tại địa chỉ mới: 15 tháng 02 năm 2024.

Nay tôi viết đơn này kính đề nghị Công an phường xác nhận tôi đã cư trú liên tục tại địa chỉ trên để tôi có cơ sở thực hiện các thủ tục hành chính sau:
— Đăng ký đổi giấy phép lái xe.
— Bổ sung hồ sơ vay vốn ngân hàng.
— Đăng ký học cho con tại trường tiểu học gần nhà.

Tôi cam kết các thông tin khai trên là đúng sự thật. Nếu có gian dối, tôi xin chịu hoàn toàn trách nhiệm trước pháp luật.

Kèm theo đơn:
— Bản sao CCCD (hai mặt).
— Bản sao hợp đồng thuê căn hộ.
— Hoá đơn điện, nước ba tháng gần nhất.

Thành phố Hồ Chí Minh, ngày 12 tháng 04 năm 2026.

Người làm đơn


Nguyễn Đức Mạnh""",
    ),
    Doc(
        doc_id="form_dang_ky_hoc",
        category="form",
        title="ĐƠN ĐĂNG KÝ NHẬP HỌC",
        body="""Kính gửi: Hiệu trưởng Trường Đại học Bách Khoa Hà Nội.

Tôi tên là: Trịnh Hoàng Bảo Lâm
Ngày sinh: 28 tháng 07 năm 2008
Nơi sinh: thành phố Nam Định
CCCD số: 036208005678, cấp ngày 19 tháng 10 năm 2023 tại Cục Cảnh sát Quản lý hành chính.
Địa chỉ thường trú: Số 56, đường Trần Quang Khải, phường Vị Hoàng, thành phố Nam Định.
Số điện thoại: 0945 678 901
Email: lam.trinh@example.com

Phụ huynh:
Họ tên cha: Trịnh Hoàng Nam — Số điện thoại: 0913 456 789
Họ tên mẹ: Phạm Thanh Hằng — Số điện thoại: 0972 345 678

Tôi vừa hoàn thành kỳ thi tốt nghiệp Trung học phổ thông năm 2026 với kết quả như sau:
— Toán: 9.25 điểm
— Vật Lý: 9.00 điểm
— Hoá Học: 8.75 điểm
— Tiếng Anh: 8.50 điểm

Tôi đã trúng tuyển vào ngành Kỹ thuật Điều khiển và Tự động hoá, mã ngành 7520216, theo Thông báo số 1567/TB-ĐHBK ngày 18 tháng 08 năm 2026 của nhà trường.

Nay tôi viết đơn này kính đề nghị Ban Giám hiệu cho phép tôi được nhập học chính thức tại trường, bắt đầu từ học kỳ thứ nhất, năm học 2026 — 2027.

Tôi cam kết:
— Tuân thủ đầy đủ nội quy, quy chế của nhà trường.
— Nộp đầy đủ học phí và các khoản đóng góp theo quy định.
— Tham gia đầy đủ các hoạt động học tập và rèn luyện.

Hà Nội, ngày 25 tháng 08 năm 2026.

Người làm đơn


Trịnh Hoàng Bảo Lâm""",
    ),
]


def main() -> int:
    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    if not DEJAVU_REGULAR.exists() or not DEJAVU_BOLD.exists():
        print(f"error: missing fonts at {DEJAVU_REGULAR} / {DEJAVU_BOLD}")
        print("install: sudo apt install fonts-dejavu")
        return 1

    all_docs = CONTRACTS + RECEIPTS + GOVERNMENT + FORMS
    metadata: list[dict] = []

    for doc in all_docs:
        pages_text = doc.pages_text()
        page_imgs: list[Image.Image] = []
        page_records: list[dict] = []
        for i, ptext in enumerate(pages_text):
            page_path = PAGES_DIR / f"{doc.doc_id}_p{i + 1}.png"
            img = _render_page(ptext, is_first=(i == 0))
            img.save(page_path)
            page_imgs.append(img)
            page_records.append(
                {
                    "page_no": i + 1,
                    "image": f"pages/{doc.doc_id}_p{i + 1}.png",
                    "text": ptext,
                }
            )

        pdf_path = DOCS_DIR / f"{doc.doc_id}.pdf"
        _assemble_pdf(page_imgs, pdf_path)

        metadata.append(
            {
                "doc_id": doc.doc_id,
                "category": doc.category,
                "title": doc.title,
                "n_pages": len(pages_text),
                "pdf": f"docs/{doc.doc_id}.pdf",
                "pages": page_records,
                "full_text": "\n\n".join(pages_text),
            }
        )
        print(f"  {doc.category:<11s} {doc.doc_id:<24s} {len(pages_text)}p")

    meta_path = ROOT / "metadata.jsonl"
    with meta_path.open("w", encoding="utf-8") as f:
        for r in metadata:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\nGenerated {len(all_docs)} documents.")
    print(f"  Pages dir : {PAGES_DIR}")
    print(f"  Docs dir  : {DOCS_DIR}")
    print(f"  Metadata  : {meta_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
