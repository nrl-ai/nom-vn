"""Build v0.2 of the Vietnamese scanned-document evaluation set.

v0.1 was 100% PIL-rendered synthetic content. v0.2 replaces the
government / form / contract categories with **real public-domain
documents** from two domains (central + provincial) and keeps
receipts as synthetic but adds scan artifacts (paper grain, mild
rotation, JPEG round-trip) so the synthetic split looks like a scan.

Two configs covering 7+ document types and 6+ issuing agencies:

- ``real`` — 9 real PD documents, page 1 each, ground-truthed by
  direct visual reading. License: PD per Luật SHTT Điều 15.

  * 6 from `chinhphu.vn` (central government):
    Quyết định / Công văn / Nghị quyết / Thông tư from PM,
    Government, VPCP, Ministry of Industry & Trade, Ministry of
    Public Security. Real image-only scans with stamps, signatures,
    skew artifacts.
  * 3 from `hanoi.gov.vn` (Hà Nội provincial UBND):
    Quyết định / Thông báo / Kế hoạch. Born-digital PDFs rendered
    to 200 dpi image-only PDFs (forces OCR fallback path).

- ``synthetic_scan`` — 3 synthetic receipt templates from v0.1,
  re-rendered with realistic scan artifacts. License: CC0
  (synthetic content). Tests OCR on simulated business documents
  with column-formatted signature blocks.

Run::

    python benchmarks/data/vn_documents_ocr_v2/_generate.py

Inputs (already committed):

- ``benchmarks/data/vn_documents_ocr_v2/sources/<id>.pdf`` — original
  multi-page PDFs as downloaded from chinhphu.vn.
- ``benchmarks/data/vn_documents_ocr_v2/pages/<id>_p1.png`` — page 1
  rendered at 200 dpi from each original.
- ``benchmarks/data/vn_documents_ocr/pages/receipt_*_p1.png`` — the v0.1
  receipts; we layer scan artifacts on top.

Outputs::

    docs/<id>.pdf              image-only PDF (forces OCR fallback)
    pages/<id>_p1.png          page 1 (real scans copied; synthetic
                                receipts re-rendered with artifacts)
    metadata.jsonl             one record per doc (text, source_url,
                                license, category, gen_method)
    README.md                  dataset card (CC0)
    LICENSE                    CC0 1.0 / PD provenance per record
"""

from __future__ import annotations

import io
import json
import random
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageFilter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as rl_canvas

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
V1_RECEIPT_PAGES = REPO / "benchmarks" / "data" / "vn_documents_ocr" / "pages"


# ---------- REAL category — 6 PD scans, page 1 each ----------


@dataclass
class RealDoc:
    doc_id: str
    title: str
    issuer: str
    source_url: str
    text: str  # corrected ground truth (visual reading + OCR-assisted)


REAL = [
    RealDoc(
        doc_id="real_qd_729_ttg",
        title="Quyết định 729/QĐ-TTg",
        issuer="Thủ tướng Chính phủ",
        source_url="https://datafiles.chinhphu.vn/cpp/files/vbpq/2026/4/729-ttg.signed.pdf",
        text="""THỦ TƯỚNG CHÍNH PHỦ
CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc

Số: 729/QĐ-TTg

Hà Nội, ngày 23 tháng 4 năm 2026

QUYẾT ĐỊNH
Phê chuẩn kết quả bầu chức vụ Chủ tịch
Ủy ban nhân dân thành phố Đà Nẵng nhiệm kỳ 2026 - 2031

THỦ TƯỚNG CHÍNH PHỦ

Căn cứ Luật Tổ chức Chính phủ ngày 19 tháng 02 năm 2025;

Căn cứ Luật Tổ chức chính quyền địa phương ngày 16 tháng 6 năm 2025;

Căn cứ Nghị định số 300/2025/NĐ-CP ngày 17 tháng 11 năm 2025 của Chính phủ quy định khung số lượng Phó Chủ tịch Ủy ban nhân dân, số lượng và cơ cấu Ủy viên Ủy ban nhân dân; quy trình giới thiệu, bầu cử và phê chuẩn các chức danh thuộc Hội đồng nhân dân, Ủy ban nhân dân; điều động, cách chức Chủ tịch, Phó Chủ tịch Ủy ban nhân dân và giao quyền Chủ tịch Ủy ban nhân dân;

Xét đề nghị của Thường trực Hội đồng nhân dân thành phố Đà Nẵng tại Tờ trình số 10/TTr-HĐND ngày 14 tháng 4 năm 2026 và đề nghị của Bộ trưởng Bộ Nội vụ tại Tờ trình số 252/TTr-BNV ngày 17 tháng 4 năm 2026.

QUYẾT ĐỊNH:

Điều 1. Phê chuẩn kết quả bầu chức vụ Chủ tịch Ủy ban nhân dân thành phố Đà Nẵng nhiệm kỳ 2026 - 2031 đối với ông Nguyễn Mạnh Hùng, Phó Bí thư Thành ủy Đà Nẵng nhiệm kỳ 2025 - 2030.

Điều 2. Quyết định này có hiệu lực thi hành kể từ ngày ký ban hành.

Điều 3. Bộ trưởng Bộ Nội vụ, Hội đồng nhân dân, Ủy ban nhân dân thành phố Đà Nẵng và ông Nguyễn Mạnh Hùng chịu trách nhiệm thi hành Quyết định này./.

Nơi nhận:
- Như Điều 3;
- Thủ tướng, các Phó Thủ tướng CP;
- Ban TCĐ chính Trung ương;
- Văn phòng Trung ương;
- VPCP: BTCN, các PCN, Trợ lý TTg, VPDCCP, TGĐ Cổng TTĐTCP;
- Lưu: VT, QHĐP (3) Cương

KT. THỦ TƯỚNG
PHÓ THỦ TƯỚNG

Lê Minh Hưng""",
    ),
    RealDoc(
        doc_id="real_cv_3722_metro",
        title="Công văn 3722/VPCP-CN",
        issuer="Văn phòng Chính phủ",
        source_url="https://datafiles.chinhphu.vn/cpp/files/vbpq/2026/4/3722-cn.signed.pdf",
        text="""VĂN PHÒNG CHÍNH PHỦ
CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc

Số: 3722/VPCP-CN
V/v cơ chế đặc thù xây dựng công trình khẩn cấp đối với Dự án kéo dài tuyến Metro Bến Thành - Suối Tiên đến Trung tâm hành chính tỉnh và Cảng hàng không quốc tế Long Thành

Hà Nội, ngày 28 tháng 4 năm 2026

Kính gửi:
- Các Bộ: Công an, Tư pháp, Tài chính, Xây dựng, Nông nghiệp và Môi trường;
- Ủy ban nhân dân tỉnh Đồng Nai.

Xét đề nghị của Ủy ban nhân dân tỉnh Đồng Nai tại văn bản số 92/TTr-UBND ngày 21 tháng 4 năm 2026 về việc ban hành Quyết định áp dụng cơ chế đặc thù đối với Dự án kéo dài tuyến Metro Bến Thành - Suối Tiên đến Trung tâm hành chính tỉnh và Cảng hàng không quốc tế Long Thành, Phó Thủ tướng Thường trực Chính phủ Phạm Gia Túc có ý kiến như sau:

Giao các Bộ: Công an, Tài chính, Xây dựng, Tư pháp, Nông nghiệp và Môi trường có ý kiến đối với đề xuất, kiến nghị của Ủy ban nhân dân tỉnh Đồng Nai tại Tờ trình số 92/TTr-UBND nêu trên (trong đó lưu ý làm rõ sự phù hợp với quy định của pháp luật đối với cơ chế đặc thù, thẩm quyền giải quyết các vấn đề có liên quan), ý kiến của Ủy ban nhân dân tỉnh Đồng Nai trước ngày 10 tháng 5 năm 2026 để báo cáo Thủ tướng Chính phủ.

Văn phòng Chính phủ thông báo để các Bộ, cơ quan biết, thực hiện./.

Nơi nhận:
- Như trên;
- Thủ tướng, PTTgTT Phạm Gia Túc (để b/c);
- UBND TP. Hồ Chí Minh;
- VPCP: BTCN, PCN Phạm Mạnh Cường, các Vụ: TH, PL, TGĐ Cổng TTĐT;
- Lưu: VT, CN, Cm.

KT. BỘ TRƯỞNG, CHỦ NHIỆM
PHÓ CHỦ NHIỆM

Phạm Mạnh Cường""",
    ),
    RealDoc(
        doc_id="real_nq_115_ba_vi",
        title="Nghị quyết 115/NQ-CP",
        issuer="Chính phủ",
        source_url="https://datafiles.chinhphu.vn/cpp/files/vbpq/2026/4/115-nqcp.signed.pdf",
        text="""CHÍNH PHỦ
CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc

Số: 115/NQ-CP

Hà Nội, ngày 29 tháng 4 năm 2026

NGHỊ QUYẾT
Về việc chuyển giao Vườn quốc gia Ba Vì
về Ủy ban nhân dân Thành phố Hà Nội quản lý

CHÍNH PHỦ

Căn cứ Luật Tổ chức Chính phủ ngày 18 tháng 02 năm 2025;

Căn cứ Luật Tổ chức chính quyền địa phương ngày 16 tháng 6 năm 2025;

Căn cứ Nghị quyết số 02-NQ/TW ngày 17 tháng 3 năm 2026 của Bộ Chính trị về xây dựng và phát triển Thủ đô Hà Nội trong kỷ nguyên mới;

Căn cứ Nghị định số 39/2022/NĐ-CP ngày 18 tháng 6 năm 2022 của Chính phủ ban hành Quy chế làm việc của Chính phủ;

Theo đề nghị của Bộ Nông nghiệp và Môi trường tại Tờ trình số 4017/TTr-BNNMT ngày 23 tháng 4 năm 2026 và Báo cáo số 4123/BC-BNNMT ngày 26 tháng 4 năm 2026; của Ủy ban nhân dân Thành phố Hà Nội tại Tờ trình số 83/TTr-UBND ngày 31 tháng 3 năm 2026, các văn bản số 1407/UBND-NNMT ngày 05 tháng 4 năm 2026 và số 1446/UBND-NNMT ngày 07 tháng 4 năm 2026; và Báo cáo số 139/BC-UBND ngày 23 tháng 4 năm 2026.

Trên cơ sở kết quả biểu quyết của các Thành viên Chính phủ.

QUYẾT NGHỊ:

Điều 1.

1. Đồng ý chủ trương chuyển giao chủ thể quản lý Vườn quốc gia Ba Vì từ Bộ Nông nghiệp và Môi trường về Ủy ban nhân dân Thành phố Hà Nội trực tiếp quản lý như đề nghị của Bộ Nông nghiệp và Môi trường tại Tờ trình 4017/TTr-BNNMT ngày 23 tháng 4 năm 2026 và Báo cáo số 4123/BC-BNNMT ngày 26 tháng 4 năm 2026; của Ủy ban nhân dân Thành phố Hà Nội tại Tờ trình số 83/TTr-UBND ngày 31 tháng 3 năm 2026 và các văn bản số 1407/UBND-NNMT ngày 05 tháng 4 năm 2026, số 1446/UBND-NNMT ngày 07 tháng 4 năm 2026 và Báo cáo số 139/BC-UBND ngày 23 tháng 4 năm 2026.

Việc quản lý tài nguyên rừng, đất đai, tài sản, tài chính và nhân sự của Vườn quốc gia Ba Vì thực hiện theo đúng quy định của pháp luật về lâm nghiệp, môi trường, đất đai, đầu tư, tài chính, công sản và pháp luật khác có liên quan.""",
    ),
    RealDoc(
        doc_id="real_qd_707_ttg",
        title="Quyết định 707/QĐ-TTg",
        issuer="Thủ tướng Chính phủ",
        source_url="https://datafiles.chinhphu.vn/cpp/files/vbpq/2026/4/707-ttg.signed.pdf",
        text="""THỦ TƯỚNG CHÍNH PHỦ
CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc

Số: 707/QĐ-TTg

Hà Nội, ngày 22 tháng 4 năm 2026

QUYẾT ĐỊNH
Về việc ban hành Kế hoạch hành động quốc gia về phòng, chống rửa tiền,
tài trợ khủng bố và tài trợ phổ biến vũ khí hủy diệt hàng loạt giai đoạn
2026 - 2030, chuẩn bị cho đánh giá đa phương lần 3 của Nhóm Châu Á -
Thái Bình Dương về chống rửa tiền (APG) đối với Việt Nam

THỦ TƯỚNG CHÍNH PHỦ

Căn cứ Luật Tổ chức Chính phủ ngày 18 tháng 02 năm 2025;

Căn cứ Luật Ngân hàng Nhà nước Việt Nam ngày 16 tháng 6 năm 2010;

Căn cứ Luật Phòng, chống rửa tiền ngày 15 tháng 11 năm 2022;

Căn cứ Luật Phòng, chống khủng bố ngày 12 tháng 6 năm 2013;

Căn cứ Nghị định số 81/2019/NĐ-CP ngày 11 tháng 11 năm 2019 của Chính phủ về phòng, chống phổ biến vũ khí hủy diệt hàng loạt;

Theo đề nghị của Thống đốc Ngân hàng Nhà nước Việt Nam tại Tờ trình số 52/TTr-NHNN ngày 31 tháng 3 năm 2026.

QUYẾT ĐỊNH:

Điều 1. Ban hành kèm theo Quyết định này Kế hoạch hành động quốc gia về phòng, chống rửa tiền, tài trợ khủng bố và tài trợ phổ biến vũ khí hủy diệt hàng loạt giai đoạn 2026 - 2030, chuẩn bị cho đánh giá đa phương lần 3 của Nhóm Châu Á - Thái Bình Dương về chống rửa tiền (APG) đối với Việt Nam.

Điều 2. Quyết định này có hiệu lực thi hành kể từ ngày ký ban hành.""",
    ),
    RealDoc(
        doc_id="real_tt_21_bct_fuel",
        title="Thông tư 21/2026/TT-BCT",
        issuer="Bộ Công Thương",
        source_url="https://datafiles.chinhphu.vn/cpp/files/vbpq/2026/4/21-bct.signed.pdf",
        text="""BỘ CÔNG THƯƠNG
CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc

Số: 21/2026/TT-BCT

Hà Nội, ngày 28 tháng 4 năm 2026

THÔNG TƯ
Bãi bỏ một phần khoản 2 Điều 1 của Thông tư số 18/2025/TT-BCT ngày 13
tháng 3 năm 2025 của Bộ trưởng Bộ Công Thương sửa đổi, bổ sung, bãi bỏ
một số quy định tại các Thông tư quy định về kinh doanh xăng dầu

Căn cứ Luật Ban hành văn bản quy phạm pháp luật số 64/2025/QH15 được sửa đổi, bổ sung bởi Luật số 87/2025/QH15;

Căn cứ Nghị định số 40/2025/NĐ-CP của Chính phủ quy định chức năng, nhiệm vụ, quyền hạn và cơ cấu tổ chức của Bộ Công Thương, được sửa đổi, bổ sung bởi Nghị định số 109/2025/NĐ-CP và Nghị định số 193/2025/NĐ-CP;

Căn cứ Nghị định số 83/2014/NĐ-CP của Chính phủ về kinh doanh xăng dầu được sửa đổi, bổ sung bởi Nghị định số 95/2021/NĐ-CP và Nghị định số 80/2023/NĐ-CP;

Thực hiện Kết luận số 14-KL/TW ngày 20 tháng 3 năm 2026 của Bộ Chính trị về khắc phục các hạn chế trong định giá nhiên liệu;

Theo đề nghị của Cục trưởng Cục Quản lý và Phát triển thị trường trong nước;

Bộ trưởng Bộ Công Thương ban hành Thông tư bãi bỏ một phần khoản 2 Điều 1 của Thông tư số 18/2025/TT-BCT ngày 13 tháng 3 năm 2025 của Bộ trưởng Bộ Công Thương sửa đổi, bổ sung, bãi bỏ một số quy định tại các Thông tư quy định về kinh doanh xăng dầu.

Điều 1. Bãi bỏ một phần khoản 2 Điều 1 của Thông tư số 18/2025/TT-BCT ngày 13 tháng 3 năm 2025 của Bộ trưởng Bộ Công Thương sửa đổi, bổ sung, bãi bỏ một số quy định tại các Thông tư quy định về kinh doanh xăng dầu

Bãi bỏ cụm từ "dấu hỏa" tại khoản 2 Điều 1 của Thông tư số 18/2025/TT-BCT.

Điều 2. Điều khoản thi hành

1. Thông tư này có hiệu lực thi hành kể từ ngày 29 tháng 4 năm 2026.""",
    ),
    # ----- Provincial government — UBND Hà Nội -----
    RealDoc(
        doc_id="real_hanoi_qd_2280_water",
        title="Quyết định 2280/QĐ-UBND",
        issuer="UBND TP Hà Nội",
        source_url="https://datafiles.hanoi.gov.vn/gov-hni/6244/VanBan/2026/4/29/QD-2280-2026.pdf",
        text="""ỦY BAN NHÂN DÂN
THÀNH PHỐ HÀ NỘI
CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc

Số: /QĐ-UBND

Hà Nội, ngày tháng năm 2026

QUYẾT ĐỊNH
Phê duyệt Kế hoạch Bảo đảm thoát nước, chống úng ngập
khu vực nội thành Thành phố mùa mưa năm 2026

ỦY BAN NHÂN DÂN THÀNH PHỐ HÀ NỘI

Căn cứ Luật Tổ chức chính quyền địa phương ngày 16/6/2025;

Căn cứ Luật Xây dựng ngày 18/6/2014; Luật sửa đổi, bổ sung một số điều của Luật Xây dựng ngày 17/6/2020;

Căn cứ Thông báo số 212-TB/TU ngày 23/01/2026 của Thành ủy Hà Nội;

Căn cứ Kế hoạch số 325/KH-UBND ngày 03/12/2025 của UBND Thành phố về khắc phục tình trạng úng ngập trên địa bàn Thành phố;

Theo đề nghị của Sở Xây dựng tại Tờ trình số 191/TTr-SXD ngày 10/4/2026 về Kế hoạch Bảo đảm thoát nước, chống úng ngập khu vực nội thành Thành phố mùa mưa năm 2026.

QUYẾT ĐỊNH:

Điều 1. Phê duyệt Kế hoạch bảo đảm thoát nước, chống úng ngập khu vực nội thành Thành phố mùa mưa năm 2026, kèm theo Quyết định này.

Điều 2. Quyết định này có hiệu lực từ ngày ký.

Điều 3. Chánh Văn phòng Ủy ban nhân dân Thành phố; Giám đốc, Thủ trưởng các Sở, ban, ngành Thành phố, Chủ tịch Ủy ban nhân dân các xã, phường và các đơn vị, cá nhân có liên quan chịu trách nhiệm thi hành Quyết định này.

Nơi nhận:
- Đ/c Bí thư Thành ủy;
- Thường trực Thành ủy; (để b/c)
- Chủ tịch UBND Thành phố;
- Các PCT UBND Thành phố;
- Văn phòng Thành ủy;
- Các Sở, ban, ngành Thành phố;
- UBND các phường, xã; (để ph/h th/h)
- Các Ban QLDA ĐTXD Thành phố;
- Cty TNHH MTV Thoát nước HN;
- Các đơn vị duy trì thoát nước và XLNT;
- VP UBĐT: CVP, các PCVP, Các phòng: NNMT, TH, ĐT, KGVX, KT, Trung tâm TT, ĐL vs CNS TP;
- Lưu: VT, ĐT (M).

TM. ỦY BAN NHÂN DÂN
KT. CHỦ TỊCH
PHÓ CHỦ TỊCH

Trương Việt Dũng""",
    ),
    RealDoc(
        doc_id="real_hanoi_tb_453_flag",
        title="Thông báo 453/TB-UBND",
        issuer="UBND TP Hà Nội",
        source_url="https://datafiles.hanoi.gov.vn/gov-hni/6235/VanBan/2026/4/29/TB-453-2026.pdf",
        text="""ỦY BAN NHÂN DÂN
THÀNH PHỐ HÀ NỘI
CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc

Số: /TB-UBND

Hà Nội, ngày tháng năm

THÔNG BÁO
Về việc treo cờ Tổ quốc

Nhân dịp Đại hội đại biểu toàn quốc Mặt trận Tổ quốc Việt Nam lần thứ XI, nhiệm kỳ 2026 - 2031. Ủy ban nhân dân thành phố Hà Nội đề nghị các cơ quan, đơn vị của Trung ương; các sở, ban, ngành, đơn vị và các hộ gia đình trên địa bàn Thành phố treo cờ Tổ quốc từ ngày 10/5/2026 đến hết ngày 14/5/2026.

Ủy ban nhân dân các phường, xã có trách nhiệm chỉ đạo, kiểm tra, nhắc nhở việc treo cờ Tổ quốc ở địa bàn dân cư; Thủ trưởng các cơ quan, đơn vị chỉ đạo, kiểm tra việc treo cờ Tổ quốc ở các đơn vị thuộc quyền quản lý đảm bảo đúng quy định./.

Nơi nhận:
- Đ/c Bí thư Thành ủy;
- Thường trực Thành ủy;
- Thường trực HĐND Thành phố;
- Chủ tịch UBND Thành phố;
- Các Phó Chủ tịch UBND Thành phố;
- UB MTTQ VN TP và các đoàn thể TP;
- UBND các phường, xã;
- Cơ quan Báo&PT, TH Thành phố;
- VPUB: CVP, PCVP P.T.T.Huyền, phòng: KGVX, TH, HC-QT, Trung tâm TTĐL&CNS Thành phố;
- Lưu: VT, KGVX

TL. CHỦ TỊCH
KT. CHÁNH VĂN PHÒNG
PHÓ CHÁNH VĂN PHÒNG

Võ Tuấn Anh""",
    ),
    RealDoc(
        doc_id="real_hanoi_kh_173_festival",
        title="Kế hoạch 173/KH-UBND",
        issuer="UBND TP Hà Nội",
        source_url="https://datafiles.hanoi.gov.vn/gov-hni/6249/VanBan/2026/4/28/KH-173-2026.pdf",
        text="""ỦY BAN NHÂN DÂN
THÀNH PHỐ HÀ NỘI
CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc

Số: /KH-UBND

Hà Nội, ngày tháng năm 2026

KẾ HOẠCH
Tổ chức "Festival Thăng Long - Hà Nội lần thứ II, năm 2026"

Thực hiện Nghị quyết số 02-NQ/TW ngày 17/3/2026 của Bộ Chính trị về Xây dựng và phát triển Thủ đô Hà Nội trong kỷ nguyên mới, Nghị quyết số 80-NQ/TW ngày 07/01/2026 của Bộ Chính trị về phát triển văn hoá Việt Nam, Chương trình hành động số 08-CTr/TU ngày 17/3/2026 của Thành ủy Hà Nội thực hiện Nghị quyết số 80-NQ/TW ngày 07/01/2026 của Bộ Chính trị về phát triển văn hoá Việt Nam, Kế hoạch số 128/KH-UBND ngày 30/3/2026 của UBND Thành phố về triển khai Chương trình hành động số 08-CTr/TU ngày 17/3/2026 của Thành ủy Hà Nội thực hiện Nghị quyết số 80-NQ/TW ngày 07/01/2026 của Bộ Chính trị về phát triển văn hoá Việt Nam, UBND thành phố Hà Nội ban hành Kế hoạch tổ chức "Festival Thăng Long - Hà Nội, lần thứ II năm 2026", cụ thể như sau:

I. MỤC ĐÍCH, YÊU CẦU

1. Mục đích

- Festival Thăng Long - Hà Nội lần thứ II, năm 2026 được tổ chức nhằm tôn vinh và quảng bá sâu rộng giá trị lịch sử, văn hoá của Thăng Long - Hà Nội, góp phần khẳng định vị thế của Thủ đô ngàn năm văn hiến- nơi hội tụ, kết tinh bản sắc và lan toả sáng tạo, từng bước phát huy vai trò là trung tâm lớn về văn hoá và động lực phát triển các ngành công nghiệp văn hoá, là bước đi thiết thực góp phần hiện thực hoá các mục tiêu, chỉ tiêu xây dựng Chương trình hành động số 08-CTr/TU ngày 17/3/2026 của Thành ủy Hà Nội về việc thực hiện Nghị quyết số 80-NQ/TW ngày 07/01/2026 của Bộ Chính trị về phát triển văn hoá Việt Nam, UBND thành phố Hà Nội ban hành Kế hoạch tổ chức "Festival Thăng Long - Hà Nội, lần thứ II năm 2026.

- Giới thiệu rộng rãi tới nhân dân trong nước và bạn bè quốc tế những giá trị tiêu biểu, đặc sắc của di sản văn hoá vật thể và phi vật thể của Hà Nội; tăng cường giáo dục truyền thống yêu nước và quốc tế, tạo không gian gặp gỡ, trao đổi giữa các địa phương, quốc gia, tổ chức văn hoá - nghệ thuật; thúc đẩy hợp tác, sáng tạo, tổ chức nhiều hoạt động văn hoá - nghệ thuật; thúc đẩy hợp tác, sáng tạo, hình thành các sản phẩm mới có giá trị, phong phú phát triển hệ sinh thái công nghiệp văn hoá của Thủ đô.

- Góp phần kích cầu du lịch, thúc đẩy phát triển kinh tế - xã hội của Thủ đô hình thành các sản phẩm văn hoá, nghệ thuật về Lễ hội đặc trưng mang thương hiệu Hà Nội; xây dựng và định vị thương hiệu Hà Nội mang tầm quốc tế là điểm đến "Văn hiến - Bản sắc - sáng tạo - hội nhập".""",
    ),
    RealDoc(
        doc_id="real_tt_37_bca_vehicle",
        title="Thông tư 37/2026/TT-BCA",
        issuer="Bộ Công an",
        source_url="https://datafiles.chinhphu.vn/cpp/files/vbpq/2026/4/37-bca.pdf",
        text="""BỘ CÔNG AN
CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc

Số: 37/2026/TT-BCA

Hà Nội, ngày 24 tháng 4 năm 2026

THÔNG TƯ
Sửa đổi, bổ sung một số điều của các Thông tư quy định
về đăng ký, kiểm định phương tiện

Căn cứ Luật Giao thông đường thủy nội địa số 23/2004/QH11 được sửa đổi, bổ sung bởi Luật số 48/2014/QH13, Luật số 97/2015/QH13, Luật số 35/2018/QH14, Luật số 44/2019/QH14, Luật số 84/2025/QH15 và Luật số 112/2025/QH15;

Căn cứ Luật Trật tự, an toàn giao thông đường bộ số 36/2024/QH15;

Căn cứ Nghị định số 02/2025/NĐ-CP ngày 18 tháng 02 năm 2025 của Chính phủ quy định chức năng, nhiệm vụ, quyền hạn và cơ cấu tổ chức của Bộ Công an được sửa đổi, bổ sung bởi Nghị định số 11/2025/NĐ-CP;

Theo đề nghị của Cục trưởng Cục Cảnh sát giao thông;

Bộ trưởng Bộ Công an ban hành Thông tư sửa đổi, bổ sung một số điều của các Thông tư quy định về đăng ký, kiểm định phương tiện.

Chương I

SỬA ĐỔI, BỔ SUNG MỘT SỐ ĐIỀU CỦA THÔNG TƯ SỐ 79/2024/TT-BCA NGÀY 15 THÁNG 11 NĂM 2024 CỦA BỘ TRƯỞNG BỘ CÔNG AN QUY ĐỊNH VỀ CẤP, THU HỒI CHỨNG NHẬN ĐĂNG KÝ XE, BIỂN SỐ XE CƠ GIỚI, XE MÁY CHUYÊN DÙNG ĐÃ ĐƯỢC SỬA ĐỔI, BỔ SUNG BỞI THÔNG TƯ SỐ 13/2025/TT-BCA NGÀY 28 THÁNG 02 NĂM 2025 VÀ THÔNG TƯ SỐ 51/2025/TT-BCA NGÀY 31 THÁNG 3 NĂM 2025 CỦA BỘ TRƯỞNG BỘ CÔNG AN

Điều 1. Sửa đổi, bổ sung khoản 6 Điều 3

"6. Việc nhận kết quả đăng ký xe được thực hiện thông qua Cổng dịch vụ công hoặc thông qua dịch vụ bưu chính nhận tại trụ sở cơ quan đăng ký xe theo nhu cầu của chủ xe.

Cổng dịch vụ công quốc gia, ứng dụng giao thông thiết bị di động, ứng dụng định danh quốc gia, ứng dụng giao thông thiết bị số dành cho công dân của Bộ Công an quản lý, vận hành (VNeTraffic)."

Điều 2. Sửa đổi, bổ sung điểm c khoản 2 Điều 16

"c. Chứng từ chuyển quyền sở hữu theo quy định.

Trường hợp dữ liệu tình trạng hôn nhân của chủ xe đã được cập nhật trên Cơ sở dữ liệu Quốc gia về dân cư hoặc Cơ sở dữ liệu chuyên ngành thì không cần chứng từ chuyển quyền sở hữu bản giấy.\"""",
    ),
]


# ---------- SYNTHETIC_SCAN category — receipts with scan artifacts ----------


def _add_scan_artifacts(img: Image.Image, *, seed: int) -> Image.Image:
    """Layer paper grain + slight rotation + JPEG round-trip + mild yellowing
    on a clean rendered page so it reads as a scanned document.

    Conservative settings tuned to a typical 200 dpi consumer scan:
      - rotation:  uniform [-1.5°, +1.5°]
      - grain:     gaussian sigma=4 over a luminance noise field
      - JPEG:      85% quality round-trip (matches what most office
                   scanners emit by default)
      - yellow:    multiply (1.00, 0.99, 0.95) — barely-perceptible
                   age cast that drops the white-point off pure white
    """
    rng = random.Random(seed)

    # 1. Mild rotation (±1.5°) with white fill
    angle = rng.uniform(-1.5, 1.5)
    img = img.rotate(angle, resample=Image.BICUBIC, fillcolor=(255, 255, 255), expand=False)

    # 2. Mild yellowing — multiply the channels
    rgb = img.convert("RGB").split()
    rgb = (
        rgb[0],
        rgb[1].point(lambda p: int(p * 0.99)),
        rgb[2].point(lambda p: int(p * 0.95)),
    )
    img = Image.merge("RGB", rgb)

    # 3. Gaussian paper grain — additive low-amplitude noise
    import numpy as np

    arr = np.array(img, dtype=np.int16)
    noise = (np.random.default_rng(seed).normal(0, 4, arr.shape)).astype(np.int16)
    arr = np.clip(arr + noise, 0, 255).astype("uint8")
    img = Image.fromarray(arr, mode="RGB")

    # 4. Slight blur to mimic scanner optics
    img = img.filter(ImageFilter.GaussianBlur(radius=0.4))

    # 5. JPEG round-trip at 85% — typical scanner output quality
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    buf.seek(0)
    return Image.open(buf).convert("RGB").copy()


SYNTHETIC_RECEIPTS = [
    # (v0.1 doc_id, gold-truth text reused from v0.1 metadata.jsonl)
]


def _load_v1_receipts() -> list[dict]:
    """Pull the three receipt records from v0.1's flat metadata.jsonl."""
    v1_meta = REPO / "benchmarks" / "data" / "vn_documents_ocr" / "metadata.jsonl"
    docs = [json.loads(line) for line in v1_meta.read_text(encoding="utf-8").splitlines()]
    return [d for d in docs if d["category"] == "receipt"]


def _assemble_image_only_pdf(img: Image.Image, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    page_w = img.size[0] * 72 / 200
    page_h = img.size[1] * 72 / 200
    c = rl_canvas.Canvas(str(out), pagesize=(page_w, page_h))
    c.drawImage(ImageReader(img), 0, 0, page_w, page_h)
    c.showPage()
    c.save()


def main() -> int:
    out_pages = ROOT / "pages"
    out_docs = ROOT / "docs"
    out_pages.mkdir(parents=True, exist_ok=True)
    out_docs.mkdir(parents=True, exist_ok=True)

    metadata: list[dict] = []

    # ----- REAL config -----
    for doc in REAL:
        page_path = out_pages / f"{doc.doc_id}_p1.png"
        pdf_path = out_docs / f"{doc.doc_id}.pdf"

        if not page_path.exists() or not pdf_path.exists():
            print(f"  WARN: real source missing for {doc.doc_id} — re-run earlier extract step")
            continue

        record = {
            "doc_id": doc.doc_id,
            "config": "real",
            "category": "government_real",
            "title": doc.title,
            "issuer": doc.issuer,
            "source_url": doc.source_url,
            "license": "Public Domain (Luật SHTT VN, Điều 15)",
            "gen_method": "real_scan_chinhphu_vn",
            "n_pages": 1,
            "pdf": f"docs/{doc.doc_id}.pdf",
            "image": f"pages/{doc.doc_id}_p1.png",
            "text": doc.text.strip(),
        }
        metadata.append(record)
        print(f"  real        {doc.doc_id:30s} {len(doc.text)} chars")

    # ----- SYNTHETIC_SCAN config — re-render v0.1 receipts with artifacts -----
    receipts = _load_v1_receipts()
    if not receipts:
        print(
            "  WARN: v0.1 receipts missing; run benchmarks/data/vn_documents_ocr/_generate.py first"
        )
    for r in receipts:
        doc_id = f"synth_scan_{r['doc_id']}"
        v1_png = V1_RECEIPT_PAGES / Path(r["pages"][0]["image"]).name
        if not v1_png.exists():
            print(f"  skip {doc_id}: source PNG not found at {v1_png}")
            continue

        img = Image.open(v1_png).convert("RGB")
        img = _add_scan_artifacts(img, seed=hash(doc_id) & 0xFFFF)

        page_path = out_pages / f"{doc_id}_p1.png"
        img.save(page_path, format="PNG")
        pdf_path = out_docs / f"{doc_id}.pdf"
        _assemble_image_only_pdf(img, pdf_path)

        record = {
            "doc_id": doc_id,
            "config": "synthetic_scan",
            "category": "receipt_synthetic_scan",
            "title": r["title"],
            "issuer": "synthetic — fictional",
            "source_url": None,
            "license": "CC0 1.0 (synthetic content)",
            "gen_method": "v0.1_template + scan_artifacts",
            "n_pages": 1,
            "pdf": f"docs/{doc_id}.pdf",
            "image": f"pages/{doc_id}_p1.png",
            "text": r["full_text"],
        }
        metadata.append(record)
        print(f"  synth_scan  {doc_id:30s} {len(r['full_text'])} chars")

    # ----- write metadata + LICENSE -----
    meta_path = ROOT / "metadata.jsonl"
    with meta_path.open("w", encoding="utf-8") as f:
        for rec in metadata:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"\nGenerated {len(metadata)} records → {meta_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
