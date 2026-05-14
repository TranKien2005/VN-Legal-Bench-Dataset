import json
import os

from model_benchmark.scorers.multiple_choice import score_multiple_choice
from model_benchmark.utils.llm import RouterLLMClient
from model_benchmark.utils.normalize import extract_json_object, normalize_loose


JUDGE_SYSTEM_PROMPT = "Bạn là giám khảo benchmark pháp lý Việt Nam, chấm nghiêm khắc, nhất quán và chỉ dựa trên dữ liệu được cung cấp."

JUDGE_PROMPT = """Bạn được cung cấp:
1. Câu hỏi benchmark gồm tình tiết vụ án và các điều luật liên quan.
2. Đáp án đúng chuẩn.
3. Nhận định của Tòa án làm căn cứ tham chiếu.
4. Câu trả lời của model gồm đáp án và giải thích.

Nhiệm vụ:
Chấm điểm phần đáp án và giải thích của model. Không yêu cầu giải thích giống từng chữ với nhận định của Tòa, nhưng phải sử dụng đúng tình tiết, áp dụng đúng luật như Tòa án, và kết luận phải khớp với phán quyết đúng. Chấm khắt khe: lời giải thích ngắn, chung chung, nhảy thẳng đến kết luận hoặc không liên hệ fact với luật thì không được điểm tối đa.

Dạng giải thích tốt cần có cấu trúc như sau:
- Căn cứ vào tình tiết vụ án cho thấy [fact cụ thể 1]; đồng thời căn cứ vào [điều luật/quy định/nguyên tắc], có thể kết luận [kết luận pháp lý 1].
- Căn cứ vào tình tiết vụ án cho thấy [fact cụ thể 2]; đồng thời căn cứ vào [điều luật/quy định/nguyên tắc], có thể kết luận [kết luận pháp lý 2].
- Tuy nhiên/Đối với [tình tiết giảm nhẹ, tăng nặng, vai trò từng người, yêu cầu từng bên], Tòa án phân hóa trách nhiệm/kết quả như [mức án, nghĩa vụ, chấp nhận/bác yêu cầu].

Ví dụ giải thích tốt:
"Căn cứ vào tình tiết vụ án cho thấy bị cáo trực tiếp thực hiện hành vi bị cấm và hậu quả xảy ra thuộc phạm vi điều luật được viện dẫn; đồng thời căn cứ vào Điều X của luật liên quan, có thể kết luận hành vi đó cấu thành vi phạm/tội danh tương ứng. Căn cứ thêm vào vai trò của từng người, người khởi xướng hoặc thực hiện chính phải chịu trách nhiệm nặng hơn, còn người tham gia với vai trò thứ yếu được phân hóa trách nhiệm. Tuy nhiên, do có các tình tiết giảm nhẹ như thành khẩn khai báo, bồi thường hoặc nhân thân được Tòa án xem xét, mức xử lý được giảm nhẹ hoặc cho hưởng án treo/cải tạo không giam giữ nếu phù hợp."

Rubric tối đa 5 điểm:
- answer_correctness: 0, 1, hoặc 2
  * 2: đáp án/kết luận chính khớp đầy đủ với đáp án đúng.
  * 1: đúng hướng xử nhưng sai hoặc thiếu chi tiết quan trọng như số tiền, mức án, chủ thể, nghĩa vụ.
  * 0: sai kết luận chính.
- fact_usage: 0, 0.5, hoặc 1
  * 1: nêu ít nhất 2 tình tiết cụ thể, đúng với vụ án, và dùng chúng để hỗ trợ kết luận.
  * 0.5: nêu tình tiết đúng nhưng quá ít, chung chung, hoặc chưa liên hệ rõ với kết luận.
  * 0: không dùng tình tiết cụ thể, dùng sai tình tiết, hoặc bịa tình tiết.
- legal_application: 0, 0.5, hoặc 1
  * 1: nêu đúng điều luật/quy định/nguyên tắc pháp lý và liên hệ trực tiếp với tình tiết.
  * 0.5: nêu đúng hướng pháp lý nhưng thiếu điều luật, thiếu liên hệ, hoặc giải thích còn chung chung.
  * 0: áp dụng sai luật, bịa luật, hoặc không có phân tích pháp lý.
- court_reasoning_alignment: 0, 0.5, hoặc 1
  * 1: lập luận phù hợp với các lý do chính trong nhận định của Tòa án.
  * 0.5: phù hợp một phần nhưng bỏ sót nhánh lập luận quan trọng hoặc phân hóa trách nhiệm chưa rõ.
  * 0: mâu thuẫn với nhận định của Tòa án.

Quy tắc khắt khe:
- Nếu model chọn sai đáp án chính, answer_correctness = 0 và total_score tối đa là 2, dù giải thích nghe hợp lý.
- Nếu model bịa tình tiết hoặc bịa luật quan trọng, total_score tối đa là 2.
- Nếu explanation chỉ lặp lại đáp án hoặc chỉ nói "đủ căn cứ", "phù hợp pháp luật", "có nhiều tình tiết giảm nhẹ" mà không nêu fact và luật cụ thể, total_score tối đa là 3.
- Nếu explanation không nêu trực tiếp tội danh/loại vi phạm/nghĩa vụ pháp lý trọng tâm khi vụ án yêu cầu điều đó, legal_application tối đa 0.5.
- Nếu explanation nêu fact đúng nhưng không giải thích vì sao fact đó dẫn đến kết luận theo luật, fact_usage tối đa 0.5 và legal_application tối đa 0.5.
- Không phạt vì khác văn phong; chỉ chấm nội dung pháp lý, sử dụng tình tiết và mức độ khớp với nhận định của Tòa.

Câu hỏi benchmark:
{question}

Đáp án đúng chuẩn:
{gold_answer}

Nhận định của Tòa án:
{court_reasoning}

Câu trả lời của model:
{model_response}

Trả về JSON duy nhất:
{{
  "answer_correctness": 0,
  "fact_usage": 0,
  "legal_application": 0,
  "court_reasoning_alignment": 0,
  "total_score": 0,
  "is_acceptable": false,
  "reason": "giải thích ngắn, nêu rõ vì sao trừ/cho điểm"
}}"""


def parse_task_3_1_answer(raw: str) -> tuple[str, str]:
    parsed = extract_json_object(raw)
    if parsed:
        return str(parsed.get("answer", "")).strip(), str(parsed.get("explanation", "")).strip()
    return raw.strip(), ""


def score_task_3_1(sample: dict, judge_model: str | None = None) -> dict:
    answer_text, explanation_text = parse_task_3_1_answer(sample.get("model_answer", ""))
    mcq_sample = dict(sample)
    mcq_sample["model_answer"] = answer_text
    answer_score = score_multiple_choice(mcq_sample)

    model_response = json.dumps(
        {"answer": answer_text, "explanation": explanation_text},
        ensure_ascii=False,
    )
    client = RouterLLMClient(model=judge_model or os.getenv("BENCHMARK_JUDGE_MODEL") or os.getenv("BENCHMARK_MODEL") or os.getenv("LLM_MODEL"))
    prompt = JUDGE_PROMPT.format(
        question=sample.get("question", ""),
        gold_answer=sample.get("answer", ""),
        court_reasoning=sample.get("explanation", ""),
        model_response=model_response,
    )
    raw_judge = client.generate(prompt, system_prompt=JUDGE_SYSTEM_PROMPT).content
    judge = extract_json_object(raw_judge) or {
        "answer_correctness": 0,
        "fact_usage": 0,
        "legal_application": 0,
        "court_reasoning_alignment": 0,
        "total_score": 0,
        "is_acceptable": False,
        "reason": "Cannot parse judge JSON",
    }

    try:
        judge_total = float(judge.get("total_score", 0))
    except Exception:
        judge_total = 0.0

    return {
        "uid": sample.get("uid"),
        "task_id": sample.get("task_id"),
        "scoring_method": "multiple_choice_plus_llm_judge",
        "answer_score": answer_score["score"],
        "is_correct": answer_score["is_correct"],
        "selected_answer": answer_score.get("selected_answer"),
        "gold_answer": sample.get("answer", ""),
        "model_answer": answer_text,
        "model_explanation": explanation_text,
        "judge_model": client.model,
        "judge_score": judge_total,
        "judge_result": judge,
        "raw_judge_output": raw_judge,
        "score": answer_score["score"],
    }
