# VN Legal Bench Dataset

## Giới thiệu

Bộ dữ liệu đánh giá khả năng suy luận pháp lý Việt Nam của mô hình LLM, lấy cảm hứng từ [LegalBench](https://github.com/HazyResearch/legalbench).

Thay vì chia thành hàng trăm task nguyên tử như LegalBench gốc, dự án nhóm các tác vụ thành **5 category chính** với các task đại diện, giảm khối lượng xây dựng mà vẫn đảm bảo tính toàn diện.

---

## Cấu trúc tác vụ

### 1. Issue Spotting (Phát hiện vấn đề)
| Task | Mô tả | Đầu ra | Metric |
|------|--------|--------|--------|
| 1.1 General Legal Issue Classification | Xác định nhãn vấn đề pháp lý chính (1/15 nhãn) từ tình tiết vụ án | Single-label classification | Accuracy |
| 1.2 Core Issue Generation | Sinh vấn đề cốt lõi cụ thể của tình huống | Text generation | Token-F1 / LLM Judge |

### 2. Rule Recall (Ghi nhớ quy tắc)
| Task | Mô tả | Đầu ra | Metric |
|------|--------|--------|--------|
| 2.1 Definition Recall | Trích nguyên văn định nghĩa khái niệm pháp lý | Text generation | Token-F1 / EM |
| 2.2 Article Recall | Trích nguyên văn điều luật | Text generation | Token-F1 / EM |
| 2.3 Legal Text Attribution | Xác định thông tin metadata của văn bản luật | MCQ | EM |
| 2.4 Legal Evolution | Xác định sự thay đổi luật theo thời gian | MCQ / Text | Accuracy |
| 2.5 Legal Schema Recall | Xác định quan hệ giữa các văn bản luật | MCQ | Accuracy |
| 2.6 Relevant Article Identification | Xác định điều khoản liên quan đến tình huống | MCQ | Accuracy |

### 3. Rule Application & Conclusion (Áp dụng quy tắc)
| Task | Mô tả | Đầu ra | Metric |
|------|--------|--------|--------|
| 3.1 Legal Court Decision Prediction | Dự đoán quyết định chính của tòa án (cung cấp sẵn điều luật) | MCQ | Accuracy |

### 4. Interpretation (Diễn giải)
| Task | Mô tả | Đầu ra | Metric |
|------|--------|--------|--------|
| 4.1 Clause Functional Classification | Phân loại chức năng điều khoản (1/15 nhãn) | Classification | Accuracy |
| 4.2 Legal Content Entailment | Xác minh nhận định đúng/sai dựa trên văn bản | Binary | Accuracy |
| 4.3 Legal Entity Extraction | Trích xuất thực thể pháp lý | MCQ / Text | Accuracy |
| 4.4 Legal Relation Extraction | Trích xuất quan hệ giữa các thực thể | MCQ / Text | Accuracy |
| 4.5 Core Meaning Extraction | Tóm tắt ý nghĩa cốt lõi | Text generation | TBD |

### 5. Rhetorical Understanding (Hiểu tu từ)
| Task | Mô tả | Đầu ra | Metric |
|------|--------|--------|--------|
| 5.1 Legal Argument Role Classification | Phân loại vai trò lập luận (6 loại) | Classification | Accuracy |
| 5.2 Reasoning Method Detection | Nhận diện Textualism vs Purposivism | Binary | Accuracy |
| 5.3 Argument Consistency Check | Kiểm tra nhất quán giữa lập luận và chứng cứ | Binary | Accuracy |
| 5.4 Counter-Argument Identification | Nhận diện phản nghị luận | Classification | Accuracy |

> **Lưu ý:** Danh sách task sẽ được chọn lọc sau khi xác định được phạm vi hỗ trợ từ giảng viên luật.

---

## Nguồn dữ liệu

| Nguồn | Mục đích | Ghi chú |
|-------|----------|---------|
| congbobanan.toaan.gov.vn | Bản án sơ thẩm | Nguồn chính, ưu tiên 2021-nay |
| vanban.chinhphu.vn | Văn bản quy phạm pháp luật | Rule recall tasks |
| Đề thi sinh viên luật | Câu hỏi rule recall | Cần hỗ trợ giảng viên |
| VLegal-Bench (CMC) | Tái sử dụng một số task | Cần kiểm tra bản quyền |

---

## Tech Stack

- **Python 3.11+** — Ngôn ngữ chính
- **PostgreSQL 16** (Docker) — Lưu trữ dữ liệu
- **SQLAlchemy + Alembic** — ORM & migration
- **Groq API** — LLM inference (miễn phí, thử nghiệm)
- **Scrapy / BeautifulSoup** — Thu thập dữ liệu

---

## Kế hoạch thực hiện

1. **B1 — Hoàn thiện ý tưởng**: Chọn lọc task, xác nhận hỗ trợ giảng viên
2. **B2 — Thu thập dữ liệu**: Crawl bản án, văn bản luật, đề thi
3. **B3 — Xây dựng CSDL**: Hệ thống hóa điều khoản & bản án vào PostgreSQL
4. **B4 — Thử nghiệm sinh dữ liệu**: Prompt engineering, sinh mẫu thử, QC
5. **B5 — Sinh lượng lớn**: Sinh toàn bộ benchmark, tổng hợp dữ liệu thủ công
6. **B6 — Đánh giá**: Chạy evaluation trên nhiều LLM, tổng hợp kết quả
