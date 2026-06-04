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
from app.models.embedding import PDFChunk
from app.models.analysis import MultiAnalysis, AnalysisDocument
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_PREFIX = (
    "You are PaperSanta Analyzer, a CS/ML paper analysis assistant. "
    "Analyze only the retrieved paper excerpts and return valid JSON only. "
    "Do not greet, do not use markdown code fences, and do not add prose outside JSON. "
    "If a field is not supported by the excerpts, use null instead of guessing. "
    "Every non-null claim should be grounded in the provided evidence references when possible."
)


ANALYSIS_RETRIEVAL_QUERIES: dict[str, list[str]] = {
    "benchmark_matrix": [
        "model architecture backbone method",
        "accuracy metrics mAP AP F1 benchmark results dataset",
        "speed FPS latency real-time inference",
    ],
    "hyperparameter_compare": [
        "training configuration optimizer learning rate batch size epochs",
        "loss function augmentation schedule implementation details",
    ],
    "resource_compare": [
        "parameters model size FLOPs memory VRAM computational cost",
        "inference time latency FPS deployment efficiency",
    ],
    "methodology_mapping": [
        "method architecture pipeline input representation objective",
        "backbone encoder decoder loss function module design",
        "algorithm steps inference training procedure",
    ],
    "eval_conflicts": [
        "experimental results benchmark metrics comparison",
        "evaluation setup dataset metric mismatch limitations",
        "ablation study discussion findings",
    ],
    "paradigm_evolution": [
        "related work previous methods motivation limitation",
        "improvement over prior work contribution novelty",
        "method evolution inheritance extension",
    ],
    "dataset_bias_gap": [
        "dataset collection bias demographic limitation ethical",
        "limitations future work dataset coverage failure cases",
    ],
    "domain_gap": [
        "application domain limitation future work low-resource language",
        "generalization domain shift deployment scenario",
    ],
    "performance_gap": [
        "real-time latency efficiency deployment scalability limitation",
        "speed accuracy tradeoff runtime bottleneck future work",
    ],
    "cross_domain_idea": [
        "core method mechanism architecture algorithm representation",
        "transferable idea cross-domain application generality",
    ],
}


ANALYSIS_SCHEMA_INSTRUCTIONS: dict[str, str] = {
    "benchmark_matrix": (
        'Return {"title": string, "table": ['
        '{"Paper": string, "Model": string|null, "Metric": string|null, "Score": string|null, '
        '"Dataset": string|null, "Backbone": string|null, "Speed": string|null, "Evidence": [string]}'
        '], "notes": string|null}.'
    ),
    "hyperparameter_compare": (
        'Return {"title": string, "table": ['
        '{"Paper": string, "Learning Rate": string|null, "Batch Size": string|null, '
        '"Optimizer": string|null, "Loss Function": string|null, "Epochs": string|null, "Evidence": [string]}'
        '], "notes": string|null}.'
    ),
    "resource_compare": (
        'Return {"title": string, "table": ['
        '{"Paper": string, "Parameters": string|null, "FLOPs": string|null, '
        '"Memory/VRAM": string|null, "Inference Time/FPS": string|null, "Evidence": [string]}'
        '], "notes": string|null}.'
    ),
    "methodology_mapping": (
        'Return {"title": string, "comparison_themes": ['
        '{"theme_name": string, "consensus": string|null, "differences": string|null, "Evidence": [string]}'
        '], "recommendation": string|null}.'
    ),
    "eval_conflicts": (
        'Return {"title": string, "comparison_themes": ['
        '{"theme_name": string, "consensus": string|null, "conflicts": ['
        '{"issue": string, "paper_a_claim": string|null, "paper_b_claim": string|null, '
        '"possible_reason": string|null, "Evidence": [string]}]}], "overall_assessment": string|null}.'
    ),
    "paradigm_evolution": (
        'Return {"title": string, "lineage_tracks": ['
        '{"from_paper": string|null, "to_paper": string|null, '
        '"inherited_points": [string], "improvement_points": [string], "Evidence": [string]}'
        '], "summary": string|null}.'
    ),
    "dataset_bias_gap": (
        'Return {"title": string, "gaps_found": ['
        '{"gap": string, "evidence": string|null, "severity": "low"|"medium"|"high", "Evidence": [string]}'
        '], "opportunities": [string], "recommendations": [string]}.'
    ),
    "domain_gap": (
        'Return {"title": string, "gaps_found": ['
        '{"gap": string, "evidence": string|null, "severity": "low"|"medium"|"high", "Evidence": [string]}'
        '], "opportunities": [string], "recommendations": [string]}.'
    ),
    "performance_gap": (
        'Return {"title": string, "gaps_found": ['
        '{"gap": string, "evidence": string|null, "severity": "low"|"medium"|"high", "Evidence": [string]}'
        '], "opportunities": [string], "recommendations": [string]}.'
    ),
    "cross_domain_idea": (
        'Return {"title": string, "gaps_found": ['
        '{"gap": string, "evidence": string|null, "severity": "low"|"medium"|"high", "Evidence": [string]}'
        '], "opportunities": [string], "recommendations": [string]}.'
    ),
}

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


def _clean_llm_json(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        cleaned = cleaned.rsplit("```", 1)[0].strip()
    if cleaned.lower().startswith("json"):
        cleaned = cleaned[4:].strip()
    return cleaned


def _parse_json_answer(answer: str) -> dict:
    cleaned = _clean_llm_json(answer)
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
        return {"items": parsed}
    except Exception as exc:
        logger.warning("Failed to parse Analyzer JSON: %s", exc)
        return {"raw_output": answer, "parse_error": str(exc)}


def _analysis_queries(analysis_type: str, fallback_query: str) -> list[str]:
    queries = ANALYSIS_RETRIEVAL_QUERIES.get(analysis_type) or [fallback_query]
    clean_queries: list[str] = []
    seen: set[str] = set()
    for query in [fallback_query, *queries]:
        normalized = query.strip()
        key = normalized.lower()
        if normalized and key not in seen:
            seen.add(key)
            clean_queries.append(normalized)
    return clean_queries


async def _retrieve_analysis_context(
    db: AsyncSession,
    user_id: str,
    pdf_uuids: list[UUID],
    analysis_type: str,
    fallback_query: str,
    top_k: int,
) -> list[dict]:
    fused: dict[UUID, dict] = {}
    queries = _analysis_queries(analysis_type, fallback_query)
    per_query_top_k = max(6, min(12, top_k))

    for query in queries:
        results = await RAGService.similarity_search(
            db,
            user_id,
            query,
            pdf_ids=pdf_uuids,
            top_k=per_query_top_k,
        )
        for rank, result in enumerate(results, 1):
            chunk = result["chunk"]
            if chunk.id not in fused:
                fused[chunk.id] = {
                    **result,
                    "analysis_queries": [],
                    "analysis_rank_score": 0.0,
                }
            fused_item = fused[chunk.id]
            fused_item["analysis_queries"].append(query)
            fused_item["analysis_rank_score"] += 1.0 / (rank + 2)

    sorted_results = sorted(
        fused.values(),
        key=lambda item: (
            item["analysis_rank_score"],
            item.get("score") or 0.0,
        ),
        reverse=True,
    )
    return sorted_results[:top_k]


def _build_analysis_context(retrieved: list[dict]) -> tuple[str, dict[str, str], list[dict], int]:
    paper_groups: dict[str, list[dict]] = defaultdict(list)
    pdf_name_map: dict[str, str] = {}
    for result in retrieved:
        pid = str(result["pdf_id"])
        paper_groups[pid].append(result)
        pdf_name_map[pid] = result.get("pdf_name", "Unknown")

    context_parts: list[str] = []
    evidence_map: dict[str, str] = {}
    evidence_sources: list[dict] = []

    for paper_idx, (pid, chunks) in enumerate(paper_groups.items(), 1):
        paper_label = pdf_name_map.get(pid, f"Paper {paper_idx}")
        for evidence_idx, chunk_data in enumerate(chunks, 1):
            chunk: PDFChunk = chunk_data["chunk"]
            evidence_id = f"P{paper_idx}-E{evidence_idx}"
            context_text = chunk_data.get("context_text", chunk.chunk_text)
            page = chunk.page_number or "unknown"
            section = " > ".join(chunk.section_path or [])
            header = f"[{evidence_id}] Paper {paper_idx}: {paper_label}, page {page}"
            if section:
                header = f"{header}, section: {section}"
            context_parts.append(f"{header}\n{context_text}\n")
            evidence_map[evidence_id] = header
            evidence_sources.append({
                "evidence_id": evidence_id,
                "pdf_id": pid,
                "pdf_name": paper_label,
                "page_number": chunk.page_number,
                "chunk_id": str(chunk.id),
                "block_id": str(chunk.block_id) if chunk.block_id else None,
                "section_path": chunk.section_path,
                "source_block_type": chunk.source_block_type,
                "retrieval_sources": chunk_data.get("retrieval_sources", []),
                "analysis_queries": chunk_data.get("analysis_queries", []),
                "preview": chunk.chunk_text[:240],
            })

    return "\n---\n".join(context_parts), evidence_map, evidence_sources, len(paper_groups)


def _build_analysis_prompt(
    analysis_type: str,
    cfg: dict,
    num_papers: int,
    context: str,
    custom_prompt: str | None,
) -> str:
    schema = ANALYSIS_SCHEMA_INSTRUCTIONS.get(analysis_type)
    if not schema:
        schema = 'Return {"title": string, "notes": string|null}.'

    custom_instruction = ""
    if custom_prompt:
        custom_instruction = f"\nUser focus: {custom_prompt.strip()}\n"

    return (
        f"Analysis type: {cfg.get('label', analysis_type)}\n"
        f"Number of papers with retrieved evidence: {num_papers}\n\n"
        f"Evidence excerpts:\n{context}\n\n"
        "Instructions:\n"
        "- Use only the evidence excerpts above.\n"
        "- Keep paper-specific claims separated by paper.\n"
        "- Do not fabricate values, metrics, datasets, model names, or limitations.\n"
        "- If a requested field is not present in the evidence, use null.\n"
        "- Add Evidence arrays with evidence IDs such as P1-E1 or P2-E3 for important claims.\n"
        "- JSON must be valid and must not contain markdown fences.\n"
        f"{custom_instruction}\n"
        f"Required JSON schema: {schema}"
    )


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

        # 1. Retrieve chunks from multiple analysis-specific angles.
        pdf_uuids = [UUID(pid) for pid in pdf_ids]
        retrieval_queries = _analysis_queries(analysis_type, cfg["query"])
        retrieved = await _retrieve_analysis_context(
            db=db,
            user_id=user_id,
            pdf_uuids=pdf_uuids,
            analysis_type=analysis_type,
            fallback_query=cfg["query"],
            top_k=cfg["top_k"],
        )

        if not retrieved:
            return {
                "id": None,
                "analysis_type": analysis_type,
                "result_json": {"error": "Không tìm thấy đủ thông tin từ các bài báo để phân tích."},
                "pdf_names": [],
                "created_at": None,
            }

        # 2. Build evidence-indexed context.
        context, evidence_map, evidence_sources, num_papers = _build_analysis_context(retrieved)
        pdf_names = list(dict.fromkeys(source["pdf_name"] for source in evidence_sources))

        # 3. Build prompt.
        user_prompt = _build_analysis_prompt(
            analysis_type=analysis_type,
            cfg=cfg,
            num_papers=num_papers,
            context=context,
            custom_prompt=custom_prompt,
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

        # 5. Parse JSON and attach evidence trace.
        result_json = _parse_json_answer(answer)
        result_json["_evidence_sources"] = evidence_sources
        result_json["_evidence_map"] = evidence_map
        result_json["_retrieval_queries"] = retrieval_queries

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
