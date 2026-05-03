"""Parametrized synthetic content for receipts / contracts / forms.

Each template is a callable that takes a deterministic seed and returns
(title, body_text). Names, dates, addresses, amounts, IDs are sampled
from fictional pools — no PII, no real-world references.

Why parametrize: hand-curated VN receipt + contract templates exist
in v0.1 (3 receipts), but to hit 20+ docs per category we need
deterministic per-seed variation. The templates below produce
consistent doc-style structure with varied content per seed.

Categories:
- receipt: 7 receipt-type templates x 3 seeds each = 21 docs
- contract: 5 contract-type templates x 4 seeds each = 20 docs
- form: 5 form-type templates x 4 seeds each = 20 docs
"""

from __future__ import annotations

import random
from collections.abc import Callable

# ---------- Pools of fictional content ----------

_FIRST_NAMES = (
    "Nguyễn Văn An",
    "Trần Thị Bình",
    "Lê Quang Cường",
    "Phạm Mỹ Dung",
    "Hoàng Đức Em",
    "Vũ Thị Phương",
    "Đặng Quốc Giang",
    "Bùi Thanh Hà",
    "Đỗ Minh Khôi",
    "Lý Thu Lan",
    "Phan Văn Mạnh",
    "Tạ Thị Nga",
    "Trịnh Hoàng Phúc",
    "Đào Thị Quỳnh",
    "Mai Tuấn Sơn",
    "Cao Thanh Trang",
    "Hồ Văn Uy",
    "Châu Thị Vân",
    "Lương Hữu Xuân",
    "Ngô Mỹ Yến",
)

_COMPANIES = (
    "Công ty Cổ phần Phát triển Phần mềm Hà Nội",
    "Công ty Trách nhiệm hữu hạn Văn phòng phẩm Trí Đức",
    "Công ty Cổ phần Truyền thông Sao Mai",
    "Công ty Trách nhiệm hữu hạn Du lịch Hồng Hà",
    "Công ty Cổ phần Sản xuất Vật liệu Xây dựng Việt Nhất",
    "Công ty Trách nhiệm hữu hạn Thương mại Phương Nam",
    "Công ty Cổ phần Tài chính Bảo Tín",
    "Công ty Cổ phần Chế biến Thực phẩm An Lạc",
    "Công ty Trách nhiệm hữu hạn Logistics Bắc Hà",
    "Công ty Cổ phần Cơ khí Đông Đô",
)

_ADDRESSES = (
    "Số 12, đường Tràng Thi, phường Hàng Bông, quận Hoàn Kiếm, thành phố Hà Nội",
    "Số 56, đường Nguyễn Trãi, quận Thanh Xuân, thành phố Hà Nội",
    "Số 89, đường Lý Thường Kiệt, quận Hoàn Kiếm, thành phố Hà Nội",
    "Số 17, đường Trần Phú, thành phố Vinh, tỉnh Nghệ An",
    "Số 78, đường Nguyễn Văn Linh, phường Nam Dương, quận Hải Châu, thành phố Đà Nẵng",
    "Khu công nghiệp Tân Tạo, quận Bình Tân, thành phố Hồ Chí Minh",
    "Số 234, đường Cách Mạng Tháng Tám, quận 3, thành phố Hồ Chí Minh",
    "Số 45, ngõ 90, đường Lê Trọng Tấn, phường Khương Mai, quận Thanh Xuân, Hà Nội",
    "Số 22, ngõ 85, phố Đội Cấn, quận Ba Đình, thành phố Hà Nội",
    "Số 30, đường Cửa Bắc, quận Ba Đình, thành phố Hà Nội",
)

_BANKS = ("Vietcombank", "BIDV", "Techcombank", "VietinBank", "MB Bank", "Agribank")
_PHONES = (
    "0987 654 321",
    "0905 123 456",
    "0913 765 432",
    "0972 345 678",
    "0945 678 901",
    "0908 567 123",
)


def _pick(rng: random.Random, pool: tuple[str, ...]) -> str:
    return rng.choice(pool)


def _make_id(rng: random.Random, prefix: str, n_digits: int = 9) -> str:
    return prefix + "".join(str(rng.randint(0, 9)) for _ in range(n_digits))


def _money(rng: random.Random, low: int = 1, high: int = 100) -> tuple[int, str]:
    millions = rng.randint(low, high) * 1_000_000 + rng.randint(0, 999) * 1_000
    digits = f"{millions:,}".replace(",", ".")
    return millions, digits


def _date(rng: random.Random, year: int = 2026) -> str:
    d = rng.randint(1, 28)
    m = rng.randint(1, 12)
    return f"{d:02d}/{m:02d}/{year}"


def _seeded_rng(name: str, seed: int) -> random.Random:
    return random.Random(f"{name}-{seed}")


# ---------- RECEIPT templates ----------


def receipt_tax_invoice(seed: int) -> tuple[str, str]:
    rng = _seeded_rng("tax_invoice", seed)
    seller = _pick(rng, _COMPANIES)
    buyer = _pick(rng, _COMPANIES)
    seller_addr = _pick(rng, _ADDRESSES)
    buyer_name = _pick(rng, _FIRST_NAMES)
    seller_tax = _make_id(rng, "", 10)
    buyer_tax = _make_id(rng, "", 10)
    invoice_no = f"{rng.randint(1, 9999):07d}"
    bank = _pick(rng, _BANKS)
    bank_acc = _make_id(rng, "", 10)

    # Items
    items = [
        ("Giấy in A4 70 gam", "Ream", 50, 95_000),
        ("Bút bi", "Hộp", 20, 65_000),
        ("Mực in HP đen", "Hộp", 10, 1_450_000),
        ("Sổ tay bìa cứng A5", "Quyển", 30, 75_000),
        ("Cặp tài liệu", "Cái", 25, 45_000),
        ("Máy tính bỏ túi Casio", "Cái", 8, 320_000),
        ("Mực in màu Canon", "Hộp", 6, 850_000),
        ("Giấy A3", "Ream", 15, 175_000),
    ]
    rng.shuffle(items)
    chosen = items[:4]
    lines = []
    subtotal = 0
    for i, (name, unit, qty, price) in enumerate(chosen, start=1):
        line_total = qty * price
        subtotal += line_total
        lines.append(
            f"{i} — {name} — {unit} — {qty} — {price:,} — {line_total:,}".replace(",", ".")
        )
    vat = subtotal // 10
    total = subtotal + vat

    body = f"""Mẫu số: 01GTKT0/001 Ký hiệu: AB/26P Số: {invoice_no}

Đơn vị bán hàng: {seller}
Mã số thuế: {seller_tax}
Địa chỉ: {seller_addr}.

Họ tên người mua: {buyer_name}
Đơn vị: {buyer}
Mã số thuế: {buyer_tax}
Địa chỉ: {_pick(rng, _ADDRESSES)}.

Hình thức thanh toán: Chuyển khoản
Số tài khoản: {bank_acc} — Ngân hàng {bank}

STT — Tên hàng hoá — Đơn vị tính — Số lượng — Đơn giá — Thành tiền

{chr(10).join(lines)}

Cộng tiền hàng: {subtotal:,} đồng
Thuế suất giá trị gia tăng: 10 phần trăm
Tiền thuế giá trị gia tăng: {vat:,} đồng
Tổng cộng tiền thanh toán: {total:,} đồng

Hà Nội, ngày {_date(rng)}.""".replace(",", ".")
    return ("HOÁ ĐƠN GIÁ TRỊ GIA TĂNG", body)


def receipt_payment(seed: int) -> tuple[str, str]:
    rng = _seeded_rng("payment", seed)
    payer = _pick(rng, _FIRST_NAMES)
    payer_addr = _pick(rng, _ADDRESSES)
    school = "Trường " + _pick(
        rng,
        (
            "Trung học Phổ thông Phan Đình Phùng",
            "Tiểu học Lê Quý Đôn",
            "Đại học Bách Khoa Hà Nội",
            "Trung học Cơ sở Trưng Vương",
            "Cao đẳng Sư phạm Trung ương",
        ),
    )
    receipt_no = f"{rng.randint(100, 9999):04d}/BL/2026"
    student = _pick(rng, _FIRST_NAMES)
    grade = f"{rng.randint(1, 12)}A{rng.randint(1, 5)}"
    _amount, amount_str = _money(rng, low=2, high=50)

    body = f"""Số: {receipt_no}

Đơn vị thu tiền: {school}
Địa chỉ: Số {rng.randint(1, 200)}, {_pick(rng, ("đường Cửa Bắc", "đường Hai Bà Trưng", "phố Lý Thái Tổ", "đường Cầu Giấy", "phố Lê Duẩn"))}, {_pick(rng, ("quận Ba Đình", "quận Đống Đa", "quận Cầu Giấy", "quận Hoàn Kiếm"))}, thành phố Hà Nội.
Mã đơn vị: {_make_id(rng, "04T", 7)}

Họ và tên người nộp tiền: {payer}
Địa chỉ: {payer_addr}.
Số điện thoại: {_pick(rng, _PHONES)}

Lý do nộp tiền:
Học phí học kỳ {_pick(rng, ("một", "hai"))} năm học 2025 — 2026 cho học sinh {student}, lớp {grade}.

Số tiền thu: {amount_str} đồng

Hình thức thanh toán: {_pick(rng, ("Tiền mặt", "Chuyển khoản"))}

Hà Nội, ngày {_date(rng)}.

Người nộp tiền                                  Người thu tiền
(Ký, ghi rõ họ tên)                            (Ký, ghi rõ họ tên)


{payer}                                    {_pick(rng, _FIRST_NAMES)}"""
    return ("BIÊN LAI THU TIỀN", body)


def receipt_expense_voucher(seed: int) -> tuple[str, str]:
    rng = _seeded_rng("expense", seed)
    company = _pick(rng, _COMPANIES)
    receiver = _pick(rng, _FIRST_NAMES)
    pchi_no = f"PC/2026/{rng.randint(1, 9999):04d}"
    _amount, amount_str = _money(rng, low=3, high=80)
    purpose = _pick(
        rng,
        (
            "Thanh toán tiền công tác phí cho chuyến đi khảo sát thị trường tại các tỉnh miền Trung",
            "Thanh toán tiền tổ chức hội nghị tổng kết quý 1 năm 2026",
            "Chi trả tiền thuê hội trường tổ chức buổi đào tạo nội bộ",
            "Thanh toán phí đi lại cho cán bộ tham dự khoá đào tạo nâng cao",
            "Tạm ứng chi phí mua sắm thiết bị văn phòng",
        ),
    )

    body = f"""Số: {pchi_no}

Đơn vị: {company}
Địa chỉ: {_pick(rng, _ADDRESSES)}.

Họ và tên người nhận: {receiver}
Đơn vị / Bộ phận: {_pick(rng, ("Phòng Kế toán", "Phòng Kinh doanh", "Phòng Hành chính", "Phòng Marketing", "Phòng Nhân sự"))}
Lý do chi: {purpose} từ ngày {_date(rng)} đến {_date(rng)}.

Số tiền: {amount_str} đồng

Kèm theo: {rng.randint(2, 8)} chứng từ gốc.

Hà Nội, ngày {_date(rng)}.

Giám đốc          Kế toán trưởng         Người lập phiếu        Người nhận tiền
(Ký, đóng dấu)    (Ký, ghi rõ họ tên)   (Ký, ghi rõ họ tên)   (Ký, ghi rõ họ tên)


{_pick(rng, _FIRST_NAMES)}      {_pick(rng, _FIRST_NAMES)}     {_pick(rng, _FIRST_NAMES)}      {receiver}"""
    return ("PHIẾU CHI", body)


def receipt_transport_ticket(seed: int) -> tuple[str, str]:
    rng = _seeded_rng("transport", seed)
    company = _pick(
        rng, ("Vietnam Airlines", "Bamboo Airways", "Vietravel Airlines", "VietJet Air")
    )
    flight_no = f"{_pick(rng, ('VN', 'QH', 'VJ', 'BL'))}{rng.randint(100, 999)}"
    passenger = _pick(rng, _FIRST_NAMES)
    route_from = _pick(
        rng,
        (
            "Hà Nội (HAN)",
            "TP Hồ Chí Minh (SGN)",
            "Đà Nẵng (DAD)",
            "Cần Thơ (VCA)",
            "Hải Phòng (HPH)",
        ),
    )
    route_to = _pick(
        rng,
        ("TP Hồ Chí Minh (SGN)", "Hà Nội (HAN)", "Đà Nẵng (DAD)", "Phú Quốc (PQC)", "Đà Lạt (DLI)"),
    )
    while route_to == route_from:
        route_to = _pick(rng, ("TP Hồ Chí Minh (SGN)", "Hà Nội (HAN)", "Đà Nẵng (DAD)"))
    seat = f"{rng.randint(1, 30)}{rng.choice('ABCDEF')}"
    booking = "".join(rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(6))
    _amount, amount_str = _money(rng, low=1, high=10)

    body = f"""Mã đặt chỗ: {booking}
Số vé: {_make_id(rng, "738", 10)}

Hành khách: {passenger}
Hạng vé: {_pick(rng, ("Economy", "Premium Economy", "Business"))}
Số ghế: {seat}

Hành trình:
Chặng bay: {company} {flight_no}
Khởi hành: {route_from} — Ngày {_date(rng)}, {rng.randint(6, 22):02d}:{_pick(rng, ("00", "15", "30", "45"))}
Đến: {route_to}

Thông tin thanh toán:
Tổng cộng: {amount_str} đồng
Hình thức: {_pick(rng, ("Thẻ tín dụng", "Chuyển khoản", "Ví điện tử MoMo", "Ví điện tử ZaloPay"))}

Hành lý: 1 kiện ký gửi 23 kg + 1 xách tay 7 kg.
Lưu ý: Có mặt làm thủ tục trước giờ khởi hành 90 phút.

Cảm ơn quý khách đã lựa chọn dịch vụ của chúng tôi."""
    return ("VÉ MÁY BAY ĐIỆN TỬ", body)


def receipt_donation(seed: int) -> tuple[str, str]:
    rng = _seeded_rng("donation", seed)
    org = _pick(
        rng,
        (
            "Quỹ Bảo trợ trẻ em Việt Nam",
            "Hội Chữ thập đỏ Việt Nam",
            "Quỹ Vì người nghèo",
            "Hội Khuyến học Việt Nam",
        ),
    )
    donor = _pick(rng, _FIRST_NAMES)
    _amount, amount_str = _money(rng, low=1, high=200)
    no = f"UH/2026/{rng.randint(1, 999):03d}"

    body = f"""Số: {no}

Đơn vị nhận: {org}
Địa chỉ: {_pick(rng, _ADDRESSES)}.
Mã số thuế: {_make_id(rng, "", 10)}

Người ủng hộ: {donor}
Địa chỉ: {_pick(rng, _ADDRESSES)}.
Số điện thoại: {_pick(rng, _PHONES)}

Số tiền ủng hộ: {amount_str} đồng

Mục đích ủng hộ: {_pick(rng, ("Hỗ trợ trẻ em mồ côi tại các trung tâm bảo trợ xã hội", "Quỹ học bổng cho học sinh nghèo vượt khó", "Cứu trợ đồng bào vùng lũ lụt miền Trung", "Xây dựng trường học vùng cao biên giới"))}.

Hình thức ủng hộ: {_pick(rng, ("Chuyển khoản", "Tiền mặt"))}

Hà Nội, ngày {_date(rng)}.

Đại diện đơn vị nhận                     Người ủng hộ
(Ký, đóng dấu)                          (Ký, ghi rõ họ tên)


{_pick(rng, _FIRST_NAMES)}              {donor}"""
    return ("BIÊN LAI ỦNG HỘ", body)


def receipt_utility_bill(seed: int) -> tuple[str, str]:
    rng = _seeded_rng("utility", seed)
    company = _pick(
        rng,
        (
            "Tổng công ty Điện lực Hà Nội",
            "Tổng công ty Cấp nước Hà Nội",
            "Tập đoàn Điện lực Việt Nam — Chi nhánh Đà Nẵng",
            "Công ty TNHH MTV Cấp thoát nước Bình Dương",
        ),
    )
    customer = _pick(rng, _FIRST_NAMES)
    bill_no = f"HD/{rng.randint(2026010, 2026129):08d}"
    consumption = rng.randint(80, 500)
    amount = consumption * rng.randint(2200, 3500)
    amount_str = f"{amount:,}".replace(",", ".")

    body = (
        f"""Mã hoá đơn: {bill_no}
Mã khách hàng: {_make_id(rng, "", 12)}

Tên khách hàng: {customer}
Địa chỉ: {_pick(rng, _ADDRESSES)}.
Số điện thoại: {_pick(rng, _PHONES)}

Đơn vị cung cấp: {company}

Kỳ hoá đơn: Từ ngày {_date(rng)} đến ngày {_date(rng)}.

Chỉ số đầu kỳ: {rng.randint(10000, 80000)}
Chỉ số cuối kỳ: {rng.randint(80001, 99999)}
Sản lượng tiêu thụ: {consumption} {_pick(rng, ("kWh", "m³"))}

Đơn giá trung bình: {amount // consumption} đồng / đơn vị
Tổng cộng (chưa thuế): {amount_str} đồng
Thuế giá trị gia tăng (10%): {amount // 10:,} đồng
Tổng thanh toán: {amount + amount // 10:,} đồng""".replace(",", ".")
        + f"""

Hạn thanh toán: ngày {_date(rng)}.
Hình thức thanh toán: {_pick(rng, ("Chuyển khoản qua ngân hàng", "Thanh toán trực tuyến trên cổng dịch vụ", "Tiền mặt tại quầy giao dịch"))}.

Quý khách vui lòng giữ hoá đơn để đối chiếu khi cần thiết."""
    )
    return ("HOÁ ĐƠN ĐIỆN / NƯỚC", body)


def receipt_medical(seed: int) -> tuple[str, str]:
    rng = _seeded_rng("medical", seed)
    hospital = _pick(
        rng,
        (
            "Bệnh viện Đa khoa Trung ương",
            "Bệnh viện Nhi Đồng 1",
            "Bệnh viện Bạch Mai",
            "Bệnh viện Việt Đức",
            "Phòng khám Đa khoa Quốc tế",
        ),
    )
    patient = _pick(rng, _FIRST_NAMES)
    no = f"PT/2026/{rng.randint(1, 9999):05d}"
    amount, amount_str = _money(rng, low=1, high=30)

    body = f"""Số: {no}

Đơn vị: {hospital}
Địa chỉ: {_pick(rng, _ADDRESSES)}.
Mã đơn vị: {_make_id(rng, "BV", 7)}

Họ và tên bệnh nhân: {patient}
Năm sinh: {rng.randint(1955, 2018)}
Số bảo hiểm y tế: {_make_id(rng, "GD", 13)}
Địa chỉ: {_pick(rng, _ADDRESSES)}.

Khoa khám: {_pick(rng, ("Khoa Nội tổng quát", "Khoa Ngoại Thần kinh", "Khoa Sản", "Khoa Răng hàm mặt", "Khoa Tai mũi họng"))}
Bác sĩ phụ trách: {_pick(rng, _FIRST_NAMES)}

Chi phí dịch vụ:
- Khám bệnh: {rng.randint(80, 250) * 1000:,} đồng
- Xét nghiệm: {rng.randint(2, 15) * 100 * 1000:,} đồng
- Thuốc: {rng.randint(1, 8) * 100 * 1000:,} đồng
- Khác: {rng.randint(0, 5) * 100 * 1000:,} đồng

Tổng cộng: {amount_str} đồng
Phần BHYT chi trả ({rng.randint(60, 100)}%): {amount * 80 // 100:,} đồng
Phần bệnh nhân thanh toán: {amount - amount * 80 // 100:,} đồng

Ngày khám: {_date(rng)}.""".replace(",", ".")
    return ("PHIẾU THU VIỆN PHÍ", body)


# ---------- CONTRACT templates ----------


def contract_labor(seed: int) -> tuple[str, str]:
    rng = _seeded_rng("labor", seed)
    employer = _pick(rng, _COMPANIES)
    employer_addr = _pick(rng, _ADDRESSES)
    employer_rep = _pick(rng, _FIRST_NAMES)
    employee = _pick(rng, _FIRST_NAMES)
    employee_addr = _pick(rng, _ADDRESSES)
    cccd = _make_id(rng, "", 12)
    _salary, salary_str = _money(rng, low=12, high=85)
    months = rng.choice([12, 24, 36, 0])  # 0 = không xác định thời hạn
    contract_no = f"{rng.randint(10, 999):03d}/HĐLĐ/2026"
    position = _pick(
        rng,
        (
            "Kỹ sư phần mềm",
            "Chuyên viên kế toán",
            "Giám sát kinh doanh",
            "Trưởng phòng nhân sự",
            "Nhân viên kỹ thuật",
            "Chuyên viên truyền thông",
        ),
    )
    bank = _pick(rng, _BANKS)

    term = f"{months} tháng" if months else "không xác định thời hạn"

    body = f"""Số: {contract_no}

Hôm nay, ngày {_date(rng)}, tại trụ sở {employer}, chúng tôi gồm:

BÊN A (Người sử dụng lao động):
Tên doanh nghiệp: {employer}
Địa chỉ: {employer_addr}.
Mã số doanh nghiệp: {_make_id(rng, "", 10)}
Đại diện: Ông/Bà {employer_rep} — Chức vụ: Tổng Giám đốc

BÊN B (Người lao động):
Họ và tên: {employee}
Ngày sinh: {_date(rng, year=rng.randint(1975, 2002))}
CCCD số: {cccd}, cấp ngày {_date(rng, year=2022)} tại Cục Cảnh sát Quản lý hành chính.
Địa chỉ thường trú: {employee_addr}.
Số điện thoại: {_pick(rng, _PHONES)}

Hai bên thống nhất ký kết hợp đồng lao động:

Điều 1. Công việc và địa điểm làm việc
Bên B đảm nhận chức vụ {position} tại {employer}. Địa điểm làm việc: trụ sở chính của Bên A.

Điều 2. Thời hạn hợp đồng và mức lương
Hợp đồng có thời hạn {term}, tính từ ngày {_date(rng)}. Mức lương cơ bản hàng tháng là {salary_str} đồng. Lương được trả vào ngày mùng {rng.randint(3, 10)} hàng tháng qua tài khoản ngân hàng {bank} của Bên B.

Điều 3. Bảo hiểm và quyền lợi
Bên A đóng đầy đủ bảo hiểm xã hội, bảo hiểm y tế, bảo hiểm thất nghiệp cho Bên B theo quy định của pháp luật hiện hành.

Điều 4. Quyền và nghĩa vụ
Hai bên cam kết thực hiện đầy đủ các nghĩa vụ của mình theo Bộ luật Lao động. Mọi tranh chấp phát sinh sẽ được giải quyết thông qua thương lượng; trường hợp không thoả thuận được, tranh chấp sẽ được giải quyết tại Toà án có thẩm quyền."""
    return ("HỢP ĐỒNG LAO ĐỘNG", body)


def contract_rental(seed: int) -> tuple[str, str]:
    rng = _seeded_rng("rental", seed)
    landlord = _pick(rng, _FIRST_NAMES)
    tenant = _pick(rng, _FIRST_NAMES)
    addr = _pick(rng, _ADDRESSES)
    cccd_a = _make_id(rng, "", 12)
    cccd_b = _make_id(rng, "", 12)
    _rent, rent_str = _money(rng, low=8, high=40)
    months = rng.choice([12, 18, 24, 36])
    no = f"{rng.randint(10, 999):03d}/HĐTN/2026"
    area = rng.randint(45, 200)
    floors = rng.randint(1, 5)

    body = f"""Số: {no}

Hôm nay, ngày {_date(rng)}, tại Phòng công chứng số {rng.randint(1, 12)}, chúng tôi gồm:

BÊN CHO THUÊ (Bên A):
Họ và tên: Ông/Bà {landlord}
Ngày sinh: {_date(rng, year=rng.randint(1955, 1980))}
CCCD số: {cccd_a}, cấp ngày {_date(rng, year=2022)}.
Địa chỉ thường trú: {addr}.
Số điện thoại: {_pick(rng, _PHONES)}

BÊN THUÊ (Bên B):
Họ và tên: Ông/Bà {tenant}
Ngày sinh: {_date(rng, year=rng.randint(1980, 2000))}
CCCD số: {cccd_b}, cấp ngày {_date(rng, year=2023)}.
Địa chỉ thường trú: {_pick(rng, _ADDRESSES)}.
Số điện thoại: {_pick(rng, _PHONES)}

Hai bên thống nhất ký kết hợp đồng thuê nhà với các điều khoản:

Điều 1. Đối tượng cho thuê
Bên A đồng ý cho Bên B thuê căn nhà {floors} tầng tại địa chỉ: {addr}. Diện tích sử dụng {area} mét vuông. Tình trạng nhà tốt, đầy đủ hệ thống điện nước.

Điều 2. Thời hạn và giá thuê
Thời hạn thuê là {months} tháng, từ ngày {_date(rng)} đến ngày {_date(rng, year=2028)}. Giá thuê là {rent_str} đồng mỗi tháng. Tiền thuê được thanh toán vào ngày mùng 1 hàng tháng bằng chuyển khoản qua ngân hàng {_pick(rng, _BANKS)}.

Điều 3. Đặt cọc
Bên B đặt cọc cho Bên A số tiền tương đương {rng.randint(2, 6)} tháng tiền thuê khi ký hợp đồng. Tiền cọc sẽ được hoàn trả khi kết thúc hợp đồng và nhà cửa được bàn giao trong tình trạng ban đầu.

Điều 4. Quyền và nghĩa vụ của các bên
Bên A có trách nhiệm bàn giao nhà đúng tình trạng đã cam kết và sửa chữa các hỏng hóc kết cấu lớn. Bên B có trách nhiệm sử dụng đúng mục đích, thanh toán tiền thuê đúng hạn và bảo quản tài sản trong nhà."""
    return ("HỢP ĐỒNG THUÊ NHÀ", body)


def contract_economic(seed: int) -> tuple[str, str]:
    rng = _seeded_rng("economic", seed)
    buyer = _pick(rng, _COMPANIES)
    seller = _pick(rng, _COMPANIES)
    while seller == buyer:
        seller = _pick(rng, _COMPANIES)
    no = f"{rng.randint(10, 999):03d}/HĐKT/2026"
    item = _pick(
        rng,
        (
            "xi măng PCB30",
            "thép xây dựng",
            "gạch ốp lát",
            "kính cường lực",
            "thiết bị điện gia dụng",
        ),
    )
    qty = rng.randint(500, 5000)
    unit = _pick(rng, ("tấn", "mét khối", "thanh", "tấm"))
    unit_price = rng.randint(800, 5000) * 1000
    total = qty * unit_price
    delivery_days = rng.randint(30, 120)
    bank = _pick(rng, _BANKS)

    body = f"""Số: {no}

Hôm nay, ngày {_date(rng)}, chúng tôi gồm:

BÊN A (Bên mua):
Tên doanh nghiệp: {buyer}
Địa chỉ: {_pick(rng, _ADDRESSES)}.
Mã số thuế: {_make_id(rng, "", 10)}
Đại diện: Ông/Bà {_pick(rng, _FIRST_NAMES)} — Chức vụ: Tổng Giám đốc

BÊN B (Bên bán):
Tên doanh nghiệp: {seller}
Địa chỉ: {_pick(rng, _ADDRESSES)}.
Mã số thuế: {_make_id(rng, "", 10)}
Đại diện: Ông/Bà {_pick(rng, _FIRST_NAMES)} — Chức vụ: Giám đốc

Hai bên thống nhất ký kết hợp đồng mua bán hàng hoá:

Điều 1. Đối tượng hợp đồng
Bên B bán cho Bên A {qty:,} {unit} {item}. Tổng khối lượng giao trong vòng {delivery_days} ngày kể từ ngày ký hợp đồng.

Điều 2. Giá trị hợp đồng và phương thức thanh toán
Đơn giá là {unit_price:,} đồng mỗi {unit} (đã bao gồm thuế giá trị gia tăng 10 phần trăm). Tổng giá trị hợp đồng là {total:,} đồng.

Bên A thanh toán cho Bên B bằng chuyển khoản qua ngân hàng {bank} theo lộ trình: tạm ứng 30 phần trăm khi ký hợp đồng, 50 phần trăm sau khi giao đủ một nửa hàng, và 20 phần trăm còn lại trong vòng mười lăm ngày kể từ ngày giao hàng cuối.

Điều 3. Trách nhiệm các bên
Bên B chịu trách nhiệm về chất lượng và quy cách hàng hoá theo tiêu chuẩn đã thoả thuận. Bên A có trách nhiệm thanh toán đúng hạn và tiếp nhận hàng theo lịch giao.""".replace(
        ",", "."
    )
    return ("HỢP ĐỒNG KINH TẾ", body)


def contract_service(seed: int) -> tuple[str, str]:
    rng = _seeded_rng("service", seed)
    client = _pick(rng, _COMPANIES)
    provider = _pick(rng, _COMPANIES)
    while provider == client:
        provider = _pick(rng, _COMPANIES)
    no = f"{rng.randint(10, 999):03d}/HĐDV/2026"
    service = _pick(
        rng,
        (
            "phát triển phần mềm quản lý nhân sự",
            "thiết kế và xây dựng trang web bán hàng",
            "dịch vụ kế toán thuế hằng tháng",
            "dịch vụ tư vấn pháp lý doanh nghiệp",
            "dịch vụ marketing số đa kênh",
        ),
    )
    _fee, fee_str = _money(rng, low=20, high=200)
    months = rng.randint(3, 24)

    body = f"""Số: {no}

Hôm nay, ngày {_date(rng)}, chúng tôi gồm:

BÊN A (Bên thuê dịch vụ):
Tên doanh nghiệp: {client}
Địa chỉ: {_pick(rng, _ADDRESSES)}.
Mã số thuế: {_make_id(rng, "", 10)}

BÊN B (Bên cung cấp dịch vụ):
Tên doanh nghiệp: {provider}
Địa chỉ: {_pick(rng, _ADDRESSES)}.
Mã số thuế: {_make_id(rng, "", 10)}

Hai bên thống nhất ký kết hợp đồng cung cấp dịch vụ:

Điều 1. Nội dung dịch vụ
Bên B cung cấp cho Bên A dịch vụ {service}. Phạm vi công việc cụ thể được quy định tại Phụ lục số 01 đính kèm hợp đồng này.

Điều 2. Thời hạn và giá trị hợp đồng
Hợp đồng có hiệu lực {months} tháng kể từ ngày ký. Tổng phí dịch vụ là {fee_str} đồng. Bên A thanh toán cho Bên B theo tiến độ hoàn thành công việc đã được hai bên xác nhận.

Điều 3. Quyền và nghĩa vụ
Bên A cung cấp đầy đủ thông tin, tài liệu cần thiết để Bên B triển khai công việc; đánh giá và phản hồi kịp thời các sản phẩm/dịch vụ. Bên B cam kết thực hiện đúng phạm vi công việc, đảm bảo chất lượng và tiến độ; chịu trách nhiệm bảo mật thông tin của Bên A trong và sau khi hợp đồng kết thúc."""
    return ("HỢP ĐỒNG DỊCH VỤ", body)


def contract_loan(seed: int) -> tuple[str, str]:
    rng = _seeded_rng("loan", seed)
    lender = _pick(rng, _FIRST_NAMES)
    borrower = _pick(rng, _FIRST_NAMES)
    cccd_a = _make_id(rng, "", 12)
    cccd_b = _make_id(rng, "", 12)
    _amount, amount_str = _money(rng, low=10, high=500)
    months = rng.randint(6, 60)
    rate = rng.choice([0, 5, 7, 8, 9, 10])

    body = f"""Số: {rng.randint(1, 999):03d}/HĐVTC/2026

Hôm nay, ngày {_date(rng)}, tại Phòng công chứng số {rng.randint(1, 12)}, chúng tôi gồm:

BÊN A (Bên cho vay):
Họ và tên: Ông/Bà {lender}
Ngày sinh: {_date(rng, year=rng.randint(1955, 1985))}
CCCD số: {cccd_a}, cấp ngày {_date(rng, year=2022)}.
Địa chỉ thường trú: {_pick(rng, _ADDRESSES)}.
Số điện thoại: {_pick(rng, _PHONES)}

BÊN B (Bên vay):
Họ và tên: Ông/Bà {borrower}
Ngày sinh: {_date(rng, year=rng.randint(1980, 2000))}
CCCD số: {cccd_b}, cấp ngày {_date(rng, year=2023)}.
Địa chỉ thường trú: {_pick(rng, _ADDRESSES)}.
Số điện thoại: {_pick(rng, _PHONES)}

Hai bên thống nhất ký kết hợp đồng vay tài sản:

Điều 1. Đối tượng vay
Bên A đồng ý cho Bên B vay số tiền {amount_str} đồng. Bên B nhận đủ số tiền vay khi ký hợp đồng này.

Điều 2. Thời hạn và lãi suất
Thời hạn vay là {months} tháng, kể từ ngày {_date(rng)}. Lãi suất hàng tháng là {rate} phần trăm/năm{" (vay không tính lãi)" if rate == 0 else ""}.

Điều 3. Phương thức thanh toán và bảo đảm
Bên B trả nợ gốc và lãi theo lịch hai bên thoả thuận tại Phụ lục đính kèm. Trường hợp Bên B không thực hiện đúng nghĩa vụ thanh toán, Bên A có quyền yêu cầu Bên B thanh toán toàn bộ số nợ còn lại và yêu cầu phạt vi phạm theo quy định pháp luật."""
    return ("HỢP ĐỒNG VAY TÀI SẢN", body)


# ---------- FORM templates ----------


def form_resignation(seed: int) -> tuple[str, str]:
    rng = _seeded_rng("resign", seed)
    employee = _pick(rng, _FIRST_NAMES)
    company = _pick(rng, _COMPANIES)
    cccd = _make_id(rng, "", 12)
    addr = _pick(rng, _ADDRESSES)
    dept = _pick(
        rng,
        (
            "Phòng Tài chính",
            "Phòng Kinh doanh",
            "Phòng Nhân sự",
            "Phòng Marketing",
            "Phòng Công nghệ thông tin",
        ),
    )
    role = _pick(
        rng,
        (
            "Chuyên viên kế toán",
            "Trưởng nhóm phát triển",
            "Nhân viên truyền thông",
            "Quản lý sản phẩm",
            "Kỹ sư hệ thống",
        ),
    )
    emp_id = _make_id(rng, "NV", 7)
    last_day = _date(rng)
    reason = _pick(
        rng,
        (
            "tôi cần dành thời gian chăm sóc cha mẹ tại quê nhà, đồng thời chuẩn bị cho việc học cao học",
            "tôi đã có kế hoạch chuyển công tác sang một vị trí phù hợp hơn với định hướng dài hạn",
            "vì lý do sức khoẻ cá nhân, tôi cần thời gian nghỉ ngơi và điều trị đầy đủ",
            "tôi nhận được học bổng và sẽ ra nước ngoài tiếp tục chương trình thạc sĩ",
        ),
    )

    body = f"""Kính gửi:
- Ban Giám đốc {company};
- Phòng Nhân sự {company}.

Tôi tên là: {employee}
Ngày sinh: {_date(rng, year=rng.randint(1985, 2000))}
CCCD số: {cccd}, cấp ngày {_date(rng, year=2022)} tại Cục Cảnh sát Quản lý hành chính.
Địa chỉ thường trú: {addr}.
Số điện thoại: {_pick(rng, _PHONES)}

Hiện tôi đang công tác tại: {dept}
Chức vụ: {role}
Mã nhân viên: {emp_id}
Ngày bắt đầu làm việc: {_date(rng, year=rng.randint(2018, 2024))}

Nay tôi viết đơn này kính đề nghị Ban Giám đốc và Phòng Nhân sự xem xét, cho phép tôi được nghỉ việc kể từ ngày {last_day}.

Lý do: Vì hoàn cảnh cá nhân, {reason}.

Trong thời gian từ ngày nhận được đơn này đến ngày nghỉ chính thức, tôi cam kết:
- Hoàn thành đầy đủ các công việc đang đảm nhận.
- Bàn giao công việc, hồ sơ, tài liệu cho người được phân công tiếp nhận.
- Tuân thủ quy định bảo mật thông tin của công ty.

Tôi xin chân thành cảm ơn Ban Giám đốc và các đồng nghiệp trong suốt thời gian làm việc đã tạo điều kiện và hỗ trợ tôi rất nhiều trong công việc. Kính mong được Ban Giám đốc xem xét và chấp thuận.

Hà Nội, ngày {_date(rng)}.

Người làm đơn
(Ký và ghi rõ họ tên)


{employee}"""
    return ("ĐƠN XIN NGHỈ VIỆC", body)


def form_residence_cert(seed: int) -> tuple[str, str]:
    rng = _seeded_rng("residence", seed)
    person = _pick(rng, _FIRST_NAMES)
    cccd = _make_id(rng, "", 12)
    old_addr = _pick(rng, _ADDRESSES)
    new_addr = _pick(rng, _ADDRESSES)

    body = f"""Kính gửi: Công an phường {_pick(rng, ("Phước Long", "Đại Mỗ", "Tân Định", "Hàng Bài", "Cầu Diễn"))}, {_pick(rng, ("quận 9", "quận Nam Từ Liêm", "quận 1", "quận Hoàn Kiếm", "quận Bắc Từ Liêm"))}, thành phố {_pick(rng, ("Hồ Chí Minh", "Hà Nội"))}.

Tôi tên là: {person}
Ngày sinh: {_date(rng, year=rng.randint(1985, 2000))}
CCCD số: {cccd}, cấp ngày {_date(rng, year=2022)} tại Cục Cảnh sát Quản lý hành chính.
Số điện thoại: {_pick(rng, _PHONES)}

Địa chỉ thường trú trước đây: {old_addr}.
Địa chỉ tạm trú hiện tại: {new_addr}.
Thời gian bắt đầu cư trú tại địa chỉ mới: {_date(rng, year=2024)}.

Nay tôi viết đơn này kính đề nghị Công an phường xác nhận tôi đã cư trú liên tục tại địa chỉ trên để tôi có cơ sở thực hiện các thủ tục hành chính sau:
- Đăng ký đổi giấy phép lái xe.
- Bổ sung hồ sơ vay vốn ngân hàng.
- Đăng ký học cho con tại trường tiểu học gần nhà.

Tôi cam kết các thông tin khai trên là đúng sự thật. Nếu có gian dối, tôi xin chịu hoàn toàn trách nhiệm trước pháp luật.

Kèm theo đơn:
- Bản sao CCCD (hai mặt).
- Bản sao hợp đồng thuê căn hộ.
- Hoá đơn điện, nước ba tháng gần nhất.

Hà Nội, ngày {_date(rng)}.

Người làm đơn


{person}"""
    return ("ĐƠN XIN XÁC NHẬN CƯ TRÚ", body)


def form_enrollment(seed: int) -> tuple[str, str]:
    rng = _seeded_rng("enroll", seed)
    student = _pick(rng, _FIRST_NAMES)
    cccd = _make_id(rng, "", 12)
    parent_father = _pick(rng, _FIRST_NAMES)
    parent_mother = _pick(rng, _FIRST_NAMES)
    school = _pick(
        rng,
        (
            "Đại học Bách Khoa Hà Nội",
            "Đại học Quốc gia Hà Nội",
            "Đại học Bách Khoa TP HCM",
            "Đại học Khoa học Tự nhiên TP HCM",
            "Đại học Kinh tế Quốc dân",
        ),
    )
    major = _pick(
        rng,
        (
            "Kỹ thuật Điều khiển và Tự động hoá",
            "Khoa học Máy tính",
            "Kinh tế Quốc tế",
            "Quản trị Kinh doanh",
            "Hoá học",
        ),
    )
    major_code = f"{rng.randint(7400000, 7600000)}"

    scores = "\n".join(
        f"- {sub}: {rng.randint(70, 99) / 10:.2f} điểm"
        for sub in ("Toán", "Vật Lý", "Hoá Học", "Tiếng Anh")
    )

    body = f"""Kính gửi: Hiệu trưởng {school}.

Tôi tên là: {student}
Ngày sinh: {_date(rng, year=2008)}
Nơi sinh: thành phố {_pick(rng, ("Hà Nội", "Hồ Chí Minh", "Đà Nẵng", "Nam Định", "Thanh Hoá"))}
CCCD số: {cccd}, cấp ngày {_date(rng, year=2023)} tại Cục Cảnh sát Quản lý hành chính.
Địa chỉ thường trú: {_pick(rng, _ADDRESSES)}.
Số điện thoại: {_pick(rng, _PHONES)}
Email: {student.split()[-1].lower()}@example.com

Phụ huynh:
Họ tên cha: {parent_father} — Số điện thoại: {_pick(rng, _PHONES)}
Họ tên mẹ: {parent_mother} — Số điện thoại: {_pick(rng, _PHONES)}

Tôi vừa hoàn thành kỳ thi tốt nghiệp Trung học phổ thông năm 2026 với kết quả như sau:
{scores}

Tôi đã trúng tuyển vào ngành {major}, mã ngành {major_code}, theo Thông báo số {rng.randint(1000, 9999)}/TB-{_pick(rng, ("ĐHBK", "ĐHQG", "ĐHKHTN"))} ngày {_date(rng)} của nhà trường.

Nay tôi viết đơn này kính đề nghị Ban Giám hiệu cho phép tôi được nhập học chính thức tại trường, bắt đầu từ học kỳ thứ nhất, năm học 2026 — 2027.

Tôi cam kết:
- Tuân thủ đầy đủ nội quy, quy chế của nhà trường.
- Nộp đầy đủ học phí và các khoản đóng góp theo quy định.
- Tham gia đầy đủ các hoạt động học tập và rèn luyện.

Hà Nội, ngày {_date(rng)}.

Người làm đơn


{student}"""
    return ("ĐƠN ĐĂNG KÝ NHẬP HỌC", body)


def form_leave(seed: int) -> tuple[str, str]:
    rng = _seeded_rng("leave", seed)
    employee = _pick(rng, _FIRST_NAMES)
    company = _pick(rng, _COMPANIES)
    dept = _pick(rng, ("Phòng Kế toán", "Phòng Nhân sự", "Phòng Sản xuất", "Phòng Kinh doanh"))
    days = rng.randint(2, 14)
    reason = _pick(
        rng,
        (
            "đi khám và điều trị bệnh theo lịch hẹn của bệnh viện",
            "tham dự hôn lễ của em ruột tổ chức tại quê",
            "chăm sóc cha mẹ già ốm tại quê",
            "tham gia khoá đào tạo chuyên môn ngắn hạn ở nước ngoài",
        ),
    )
    start = _date(rng)
    end = _date(rng)

    body = f"""Kính gửi:
- Ban Giám đốc {company};
- Trưởng phòng {dept};
- Phòng Nhân sự.

Tôi tên là: {employee}
Bộ phận công tác: {dept}
Mã nhân viên: {_make_id(rng, "NV", 7)}
Số điện thoại: {_pick(rng, _PHONES)}

Nay tôi viết đơn này kính đề nghị quý cơ quan cho phép tôi được nghỉ phép {days} ngày, từ ngày {start} đến ngày {end}.

Lý do nghỉ phép: Tôi cần {reason}.

Trong thời gian nghỉ phép, tôi cam kết:
- Bàn giao công việc đầy đủ cho đồng nghiệp được phân công thay thế.
- Sẵn sàng phối hợp xử lý các công việc khẩn cấp qua điện thoại.
- Quay trở lại làm việc đúng thời hạn đã đăng ký.

Tôi xin chân thành cảm ơn Ban Giám đốc đã xem xét và chấp thuận.

Hà Nội, ngày {_date(rng)}.

Người làm đơn
(Ký, ghi rõ họ tên)


{employee}

Ý KIẾN CỦA TRƯỞNG PHÒNG                       PHÊ DUYỆT CỦA BAN GIÁM ĐỐC

(Ký, ghi rõ họ tên)                          (Ký, đóng dấu)"""
    return ("ĐƠN XIN NGHỈ PHÉP", body)


def form_business_registration(seed: int) -> tuple[str, str]:
    rng = _seeded_rng("biz_reg", seed)
    person = _pick(rng, _FIRST_NAMES)
    biz_name = _pick(
        rng,
        (
            "Công ty TNHH Sản xuất Thực phẩm An Khang",
            "Hộ kinh doanh Bún Đậu Cô Tư",
            "Công ty Cổ phần Đầu tư Kim Cương Việt",
            "Công ty TNHH Vận tải Sao Việt",
            "Hộ kinh doanh Tạp hoá Bình Minh",
        ),
    )
    addr = _pick(rng, _ADDRESSES)
    biz = _pick(
        rng,
        (
            "Sản xuất và kinh doanh thực phẩm chế biến sẵn",
            "Bán lẻ hàng tạp hoá tại cửa hàng cố định",
            "Vận tải hành khách bằng xe ô tô",
            "Cho thuê văn phòng và mặt bằng kinh doanh",
            "Tư vấn và môi giới bất động sản",
        ),
    )
    _capital, capital_str = _money(rng, low=200, high=5000)

    body = f"""Kính gửi: Sở Kế hoạch và Đầu tư thành phố {_pick(rng, ("Hà Nội", "Hồ Chí Minh", "Đà Nẵng", "Hải Phòng", "Cần Thơ"))}.

Tôi tên là: {person}
Ngày sinh: {_date(rng, year=rng.randint(1975, 1995))}
CCCD số: {_make_id(rng, "", 12)}, cấp ngày {_date(rng, year=2022)} tại Cục Cảnh sát Quản lý hành chính.
Địa chỉ thường trú: {_pick(rng, _ADDRESSES)}.
Số điện thoại: {_pick(rng, _PHONES)}
Email: {person.split()[-1].lower()}@example.com

Đăng ký thành lập doanh nghiệp / hộ kinh doanh với các thông tin sau:

1. Tên doanh nghiệp / hộ kinh doanh: {biz_name}.
2. Địa điểm kinh doanh: {addr}.
3. Ngành nghề kinh doanh chính: {biz}.
4. Vốn điều lệ: {capital_str} đồng.
5. Đại diện pháp luật: {person}, chức danh Chủ doanh nghiệp.

Tôi cam kết:
- Mọi thông tin đăng ký là đúng sự thật.
- Tuân thủ các quy định pháp luật về thành lập và hoạt động doanh nghiệp.
- Nộp đầy đủ thuế và các nghĩa vụ tài chính theo quy định.

Kèm theo đơn:
- Bản sao CCCD (hai mặt) đã chứng thực.
- Hợp đồng thuê địa điểm kinh doanh.
- Sơ đồ địa điểm kinh doanh.

Hà Nội, ngày {_date(rng)}.

Người làm đơn
(Ký, ghi rõ họ tên)


{person}"""
    return ("ĐƠN ĐĂNG KÝ KINH DOANH", body)


# ---------- Public API ----------


RECEIPT_GENERATORS: tuple[Callable[[int], tuple[str, str]], ...] = (
    receipt_tax_invoice,
    receipt_payment,
    receipt_expense_voucher,
    receipt_transport_ticket,
    receipt_donation,
    receipt_utility_bill,
    receipt_medical,
)

CONTRACT_GENERATORS: tuple[Callable[[int], tuple[str, str]], ...] = (
    contract_labor,
    contract_rental,
    contract_economic,
    contract_service,
    contract_loan,
)

FORM_GENERATORS: tuple[Callable[[int], tuple[str, str]], ...] = (
    form_resignation,
    form_residence_cert,
    form_enrollment,
    form_leave,
    form_business_registration,
)
