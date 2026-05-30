"""
analyze_service.py — Multi-paper analysis service
"""

import json
import logging
from uuid import UUID
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.deepseek_provider import DeepSeekProvider
from app.models.pdf_document import PDFDocument
from app.models.analysis import MultiAnalysis, AnalysisDocument
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_PREFIX = (
    "Bạn là chuyên gia phân tích tài liệu khoa học (Computer Science, Machine Learning).\n"
    "NHIỆM VỤ: Phân tích các đoạn trích từ bài báo khoa học và xuất kết quả DƯỚI DẠNG JSON.\n"
    "TUYỆT ĐỐI KHÔNG chào hỏi, không giải thích dài dòng. Chỉ xuất JSON hợp lệ.\n"
    "Không dùng markdown code blocks trong output. Chỉ JSON thuần túy."
)

ANALYSIS_CONFIG = {
    "benchmark_matrix": {
        "label": "Benchmark Matrix",
        "mode": "benchmark",
        "query": "architecture, accuracy metrics, mAP, FPS, dataset used, backbone",
        "top_k": 20,
        "temperature": 0.2,
        "prompt_template": (
            "Dưới đây là các đoạn trích từ {num_papers} bài báo về các model:\n\n"
            "{context}\n\n"
            "YÊU CẦU: Lập bảng so sánh các model dựa trên thông tin trong các bài báo trên.\n"
            "Xuất JSON object với cấu trúc:\n"
            '{{\n'
            '  "title": "So sánh các model",\n'
            '  "table": [ {{ "Model": "...", "mAP": "...", "FPS": "...", "Dataset": "...", "Backbone": "..." }} ],\n'
            '  "notes": "Nhận xét bổ sung (nếu có)"\n'
            '}}\n'
            "Chỉ điền thông tin CÓ trong bài báo. Nếu không có giá trị, để null.\n"
            "{custom_instruction}"
        ),
    },
    "hyperparameter_compare": {
        "label": "Hyperparameter Compare",
        "mode": "benchmark",
        "query": "training configuration, learning rate, batch size, optimizer, loss function, epochs",
        "top_k": 20,
        "temperature": 0.2,
        "prompt_template": (
            "Dưới đây là các đoạn trích từ {num_papers} bài báo:\n\n"
            "{context}\n\n"
            "YÊU CẦU: Lập bảng so sánh các thông số huấn luyện.\n"
            "Xuất JSON object với cấu trúc:\n"
            '{{\n'
            '  "title": "So sánh Hyperparameters",\n'
            '  "table": [ {{ "Model/Paper": "...", "Learning Rate": "...", "Batch Size": "...", '
            '"Optimizer": "...", "Loss Function": "...", "Epochs": "..." }} ],\n'
            '  "notes": "..."\n'
            '}}\n'
            "{custom_instruction}"
        ),
    },
    "resource_compare": {
        "label": "Resource Comparison",
        "mode": "benchmark",
        "query": "model size, parameters, FLOPs, memory, computational requirements, VRAM",
        "top_k": 20,
        "temperature": 0.2,
        "prompt_template": (
            "Dưới đây là các đoạn trích từ {num_papers} bài báo:\n\n"
            "{context}\n\n"
            "YÊU CẦU: Lập bảng so sánh tài nguyên tính toán của các model.\n"
            "Xuất JSON object với cấu trúc:\n"
            '{{\n'
            '  "title": "So sánh tài nguyên",\n'
            '  "table": [ {{ "Model": "...", "Parameters": "...", "FLOPs": "...", '
            '"Min VRAM": "...", "Inference Time": "..." }} ],\n'
            '  "notes": "..."\n'
            '}}\n'
            "{custom_instruction}"
        ),
    },
    "methodology_mapping": {
        "label": "Methodology Mapping",
        "mode": "synthesis",
        "query": "method, architecture, backbone, loss function, objective, input representation, encoder, decoder",
        "top_k": 30,
        "temperature": 0.4,
        "prompt_template": (
            "Dưới đây là các đoạn trích từ {num_papers} bài báo:\n\n"
            "{context}\n\n"
            "YÊU CẦU: So sánh các PHƯƠNG PHÁP (Methodology).\n"
            "Xác định các CHỦ ĐỀ so sánh (comparison themes) trước, "
            "rồi trong mỗi chủ đề mới phân tích đồng thuận / khác biệt.\n"
            "Ví dụ chủ đề: Kiến trúc mạng, Hàm mục tiêu (Loss), Biểu diễn đầu vào.\n"
            "Nếu một chủ đề KHÔNG có điểm chung, để consensus là null.\n"
            "Xuất JSON với cấu trúc:\n"
            '{{\n'
            '  "title": "So sánh Phương pháp & Kiến trúc",\n'
            '  "comparison_themes": [\n'
            '    {{\n'
            '      "theme_name": "Tên chủ đề (ví dụ: Kiến trúc mạng)",\n'
            '      "consensus": "Điểm chung giữa các bài (hoặc null nếu không có)",\n'
            '      "differences": "Khác biệt giữa các bài"\n'
            '    }}\n'
            '  ],\n'
            '  "recommendation": "Khuyến nghị dựa trên phân tích"\n'
            '}}\n'
            "QUAN TRỌNG: Chỉ liệt kê chủ đề nào thực sự xuất hiện trong tài liệu. "
            "Không chế tạo chủ đề cho đủ số lượng.\n"
            "{custom_instruction}"
        ),
    },
    "eval_conflicts": {
        "label": "Evaluation Conflicts",
        "mode": "synthesis",
        "query": "results, experimental findings, comparison, limitations, discussion, metric, benchmark",
        "top_k": 30,
        "temperature": 0.4,
        "prompt_template": (
            "Dưới đây là các đoạn trích từ {num_papers} bài báo:\n\n"
            "{context}\n\n"
            "YÊU CẦU: Phân tích các kết quả thực nghiệm.\n"
            "Xác định các CHỦ ĐỀ so sánh (comparison themes) trước, "
            "rồi trong mỗi chủ đề mới phân tích đồng thuận / mâu thuẫn.\n"
            "Ví dụ chủ đề: Độ chính xác (Accuracy), Tốc độ (Speed), Metric được dùng.\n"
            "Chú ý các trường hợp metric mismatch (bài A đo F1, bài B đo mAP).\n"
            "Xuất JSON với cấu trúc:\n"
            '{{\n'
            '  "title": "Tranh cãi Thực nghiệm & Hiệu năng",\n'
            '  "comparison_themes": [\n'
            '    {{\n'
            '      "theme_name": "Tên chủ đề (ví dụ: Độ chính xác)",\n'
            '      "consensus": "Điểm đồng thuận (hoặc null nếu không có)",\n'
            '      "conflicts": [\n'
            '        {{\n'
            '          "issue": "Vấn đề mâu thuẫn",\n'
            '          "paper_a_claim": "Bài A nói gì",\n'
            '          "paper_b_claim": "Bài B nói gì",\n'
            '          "possible_reason": "Nguyên nhân có thể (metric khác? dataset khác?)"\n'
            '        }}\n'
            '      ]\n'
            '    }}\n'
            '  ],\n'
            '  "overall_assessment": "Đánh giá tổng quan"\n'
            '}}\n'
            "{custom_instruction}"
        ),
    },
    "paradigm_evolution": {
        "label": "Paradigm Evolution",
        "mode": "synthesis",
        "query": "related work, background, limitations of previous approaches, motivation, improvement upon",
        "top_k": 30,
        "temperature": 0.4,
        "prompt_template": (
            "Dưới đây là các đoạn trích từ {num_papers} bài báo:\n\n"
            "{context}\n\n"
            "YÊU CẦU: Phân tích mối quan hệ KẾ THỪA (lineage) giữa các bài báo.\n"
            "Bài sau đã kế thừa ý tưởng gì từ bài trước? Khắc phục nhược điểm gì? Mở rộng theo hướng nào?\n"
            "QUAN TRỌNG: Mỗi cặp (from_paper → to_paper) CHỈ ĐƯỢC XUẤT HIỆN DUY NHẤT MỘT LẦN.\n"
            "Nếu có nhiều đoạn trích nói về cùng một cặp, hãy GỘP TẤT CẢ ý vào arrays inherited_points và improvement_points.\n"
            "Xuất JSON với cấu trúc:\n"
            '{{\n'
            '  "title": "Tiến trình & Xu hướng Công nghệ",\n'
            '  "lineage_tracks": [\n'
            '    {{\n'
            '      "from_paper": "Bài báo gốc / Phương pháp nền tảng",\n'
            '      "to_paper": "Bài báo kế thừa / Phương pháp cải tiến",\n'
            '      "inherited_points": [ "Ý tưởng được kế thừa 1", "Ý tưởng được kế thừa 2" ],\n'
            '      "improvement_points": [ "Cải tiến 1", "Cải tiến 2" ]\n'
            '    }}\n'
            '  ],\n'
            '  "summary": "Tóm tắt bức tranh tổng thể"\n'
            '}}\n'
            "{custom_instruction}"
        ),
    },
    "dataset_bias_gap": {
        "label": "Dataset Bias Gap",
        "mode": "gap",
        "query": "limitations, dataset, bias, demographic, ethical, future work",
        "top_k": 40,
        "temperature": 0.5,
        "prompt_template": (
            "Dưới đây là các đoạn trích từ {num_papers} bài báo (đặc biệt phần Limitations và Future Work):\n\n"
            "{context}\n\n"
            "YÊU CẦU: Phát hiện các lỗ hổng liên quan đến sự thiên vị (bias) trong dữ liệu.\n"
            "Phân tích: dữ liệu chủ yếu từ đâu? Thiếu nhóm đối tượng nào? Rủi ro khi áp dụng thực tế?\n"
            "Xuất JSON với cấu trúc:\n"
            '{{\n'
            '  "title": "Dataset Bias Gaps",\n'
            '  "gaps_found": [\n'
            '    {{\n'
            '      "gap": "Mô tả lỗ hổng",\n'
            '      "evidence": "Bằng chứng từ bài báo",\n'
            '      "severity": "high"\n'
            '    }}\n'
            '  ],\n'
            '  "opportunities": [ "Hướng nghiên cứu mới" ],\n'
            '  "recommendations": [ "Đề xuất cải thiện" ]\n'
            '}}\n'
            "{custom_instruction}"
        ),
    },
    "domain_gap": {
        "label": "Domain Gap",
        "mode": "gap",
        "query": "limitations, future work, application, domain, language, low-resource",
        "top_k": 40,
        "temperature": 0.5,
        "prompt_template": (
            "Dưới đây là các đoạn trích từ {num_papers} bài báo:\n\n"
            "{context}\n\n"
            "YÊU CẦU: Phát hiện các miền ứng dụng hoặc ngôn ngữ chưa được khai thác.\n"
            "Các bài báo hiện tại tập trung vào miền nào? Còn miền nào bị bỏ ngỏ?\n"
            "Xuất JSON với cấu trúc:\n"
            '{{\n'
            '  "title": "Domain Gaps",\n'
            '  "gaps_found": [\n'
            '    {{\n'
            '      "gap": "Miền bị bỏ ngỏ",\n'
            '      "evidence": "Bằng chứng",\n'
            '      "severity": "medium"\n'
            '    }}\n'
            '  ],\n'
            '  "opportunities": [ "Cơ hội nghiên cứu" ],\n'
            '  "recommendations": [ "Đề xuất" ]\n'
            '}}\n'
            "{custom_instruction}"
        ),
    },
    "performance_gap": {
        "label": "Performance Gap",
        "mode": "gap",
        "query": "future work, limitations, real-time, latency, efficiency, deployment, scalability",
        "top_k": 40,
        "temperature": 0.5,
        "prompt_template": (
            "Dưới đây là các đoạn trích từ {num_papers} bài báo (phần Future Work và Limitations):\n\n"
            "{context}\n\n"
            "YÊU CẦU: Phát hiện các vấn đề về hiệu năng được các tác giả đề cập.\n"
            "Thuật toán nào chính xác nhưng chậm? Rào cản nào khi deploy thực tế?\n"
            "Xuất JSON với cấu trúc:\n"
            '{{\n'
            '  "title": "Performance Gaps",\n'
            '  "gaps_found": [\n'
            '    {{\n'
            '      "gap": "Vấn đề hiệu năng",\n'
            '      "evidence": "Bằng chứng từ bài báo",\n'
            '      "severity": "high"\n'
            '    }}\n'
            '  ],\n'
            '  "opportunities": [ "Cơ hội tối ưu" ],\n'
            '  "recommendations": [ "Kỹ thuật có thể áp dụng: pruning, quantization, distillation..." ]\n'
            '}}\n'
            "{custom_instruction}"
        ),
    },
    "cross_domain_idea": {
        "label": "Cross-domain Idea",
        "mode": "gap",
        "query": "method, approach, architecture, core idea, algorithm, mechanism",
        "top_k": 30,
        "temperature": 0.5,
        "prompt_template": (
            "Dưới đây là các đoạn trích từ {num_papers} bài báo thuộc các lĩnh vực khác nhau:\n\n"
            "{context}\n\n"
            "YÊU CẦU: Phân tích cơ chế cốt lõi của từng phương pháp.\n"
            "Đề xuất khả năng áp dụng chéo (áp dụng phương pháp của bài này sang lĩnh vực của bài kia).\n"
            "Xuất JSON với cấu trúc:\n"
            '{{\n'
            '  "title": "Cross-domain Ideas",\n'
            '  "gaps_found": [\n'
            '    {{\n'
            '      "gap": "Cơ hội kết hợp",\n'
            '      "evidence": "Phân tích sự tương đồng về cấu trúc dữ liệu/bài toán",\n'
            '      "severity": "medium"\n'
            '    }}\n'
            '  ],\n'
            '  "opportunities": [ "Hướng nghiên cứu lai ghép cụ thể" ],\n'
            '  "recommendations": [ "Các bước thực hiện" ]\n'
            '}}\n'
            "{custom_instruction}"
        ),
    },
}


class AnalyzeService:

    @staticmethod
    async def run_analysis(
        db: AsyncSession,
        user_id: str,
        pdf_ids: list[str],
        analysis_type: str,
        custom_prompt: str | None = None,
    ) -> dict:
        cfg = ANALYSIS_CONFIG.get(analysis_type)
        if not cfg:
            raise ValueError(f"Unknown analysis type: {analysis_type}")

        logger.info(f"run_analysis: type={analysis_type}, pdf_ids={pdf_ids}")

        # 1. Retrieve chunks
        pdf_uuids = [UUID(pid) for pid in pdf_ids]
        retrieved = await RAGService.similarity_search(
            db, user_id, cfg["query"], pdf_ids=pdf_uuids, top_k=cfg["top_k"]
        )

        if not retrieved:
            return {
                "id": None,
                "analysis_type": analysis_type,
                "result_json": {"error": "Không tìm thấy đủ thông tin từ các bài báo để phân tích."},
                "pdf_names": [],
                "created_at": None,
            }

        # 2. Build context — group chunks by paper, KHÔNG đánh số theo chunk index
        paper_groups: dict[str, list[dict]] = defaultdict(list)
        pdf_name_map: dict[str, str] = {}
        for r in retrieved:
            pid = str(r["pdf_id"])
            paper_groups[pid].append(r)
            pdf_name_map[pid] = r.get("pdf_name", "Unknown")

        context_parts = []
        for paper_idx, (pid, chunks) in enumerate(paper_groups.items(), 1):
            paper_label = pdf_name_map.get(pid, f"Paper {paper_idx}")
            for chunk_data in chunks:
                context_text = chunk_data.get("context_text", chunk_data["chunk"].chunk_text)
                context_parts.append(
                    f"[Paper {paper_idx}: {paper_label}]\n{context_text}\n"
                )

        context = "\n---\n".join(context_parts)
        num_papers = len(paper_groups)
        pdf_names = list(dict.fromkeys(pdf_name_map.get(pid, f"Paper {pid[:8]}") for pid in pdf_ids))

        # 3. Build prompt
        custom_instruction = ""
        if custom_prompt:
            custom_instruction = f"\nYÊU CẦU BỔ SUNG TỪ NGƯỜI DÙNG: {custom_prompt}\n"

        user_prompt = cfg["prompt_template"].format(
            num_papers=num_papers,
            context=context,
            custom_instruction=custom_instruction,
        )

        # 4. Call DeepSeek
        import time
        t0 = time.time()
        system_prompt = SYSTEM_PROMPT_PREFIX
        answer, prompt_tokens, completion_tokens = DeepSeekProvider.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=cfg["temperature"],
            max_tokens=settings.ANALYZE_MAX_TOKENS,
        )
        elapsed = time.time() - t0

        logger.info(f"DeepSeek analysis done: {elapsed:.2f}s, tokens={prompt_tokens + completion_tokens}")

        # 5. Parse JSON
        result_json = None
        try:
            # Clean potential markdown code fences
            cleaned = answer.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[-1]
                cleaned = cleaned.rsplit("```", 1)[0]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
            result_json = json.loads(cleaned)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to parse JSON from LLM: {e}")
            result_json = {"raw_output": answer, "parse_error": str(e)}

        # 6. Save to DB
        analysis = MultiAnalysis(
            user_id=user_id,
            analysis_type=analysis_type,
            result_json=result_json,
        )
        db.add(analysis)
        await db.flush()

        for pid in pdf_ids:
            db.add(AnalysisDocument(analysis_id=analysis.id, pdf_id=UUID(pid)))
        await db.flush()

        logger.info(f"Saved analysis={analysis.id}")

        return {
            "id": str(analysis.id),
            "analysis_type": analysis_type,
            "result_json": result_json,
            "pdf_names": pdf_names,
            "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
        }
