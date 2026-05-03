// Curated VN sample sentences across registers — used by every tool's
// "sample" button. Kept tiny on purpose; users with longer fixtures can
// paste their own.

export interface Sample {
  label: string;
  text: string;
  /** Pre-stripped diacritics (for the diacritic-restore tool's input). */
  asciiText?: string;
}

export const VN_SAMPLES: Sample[] = [
  {
    label: "Hợp đồng",
    text: "Hợp đồng số 02/HĐ/2025 được lập tại Hà Nội ngày 14 tháng 3 năm 2025 giữa hai bên A và B với tổng giá trị 1.500.000.000 đồng.",
    asciiText:
      "Hop dong so 02/HD/2025 duoc lap tai Ha Noi ngay 14 thang 3 nam 2025 giua hai ben A va B voi tong gia tri 1.500.000.000 dong.",
  },
  {
    label: "Hội thoại",
    text: "Bạn có khỏe không? Hôm nay trời đẹp lắm, chúng ta đi ăn phở nhé!",
    asciiText: "Ban co khoe khong? Hom nay troi dep lam, chung ta di an pho nhe!",
  },
  {
    label: "Văn học",
    text: "Trong đầm gì đẹp bằng sen, lá xanh bông trắng lại chen nhị vàng, nhị vàng bông trắng lá xanh.",
    asciiText:
      "Trong dam gi dep bang sen, la xanh bong trang lai chen nhi vang, nhi vang bong trang la xanh.",
  },
  {
    label: "Tổng hợp",
    text: "Tôi yêu Việt Nam, đất nước tuyệt vời với hơn 100 triệu dân.",
    asciiText: "Toi yeu Viet Nam, dat nuoc tuyet voi voi hon 100 trieu dan.",
  },
];
