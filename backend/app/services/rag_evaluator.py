import json

from app.services.llm import complete_chat


def evaluate_rag_response(
    question: str,
    context: str,
    answer: str,
) -> dict:
    eval_prompt = f"""You are an expert AI evaluation auditor assessing the quality of a RAG (Retrieval-Augmented Generation) system.

Evaluate the following interaction based on three strict criteria:

[QUESTION]:
{question}

[RETRIEVED CONTEXT]:
{context}

[GENERATED ANSWER]:
{answer}

---
CRITERIA:

1. CONTEXT RELEVANCE (0.0 to 1.0):
   Does the retrieved context contain information directly relevant to answering the question?
   - 1.0: Highly relevant and contains exact facts/code needed.
   - 0.5: Partially relevant or contains substantial noise.
   - 0.0: Irrelevant or completely unrelated.

2. FAITHFULNESS / GROUNDEDNESS (0.0 to 1.0):
   Can every claim made in the answer be directly inferred from the retrieved context?
   - 1.0: Completely grounded; zero unverified claims or hallucinations.
   - 0.5: Mostly grounded, but contains minor speculative claims not in context.
   - 0.0: Major hallucinations or contradicts the context.

3. ANSWER RELEVANCE (0.0 to 1.0):
   Does the generated answer directly address the user's question completely and clearly?
   - 1.0: Directly and completely answers what was asked.
   - 0.5: Incomplete or partly off-topic.
   - 0.0: Does not address the question at all.

---
OUTPUT FORMAT:
Respond ONLY with a valid JSON object matching this schema:
{{
  "context_relevance": <float between 0.0 and 1.0>,
  "context_relevance_reason": "<brief explanation>",
  "faithfulness": <float between 0.0 and 1.0>,
  "faithfulness_reason": "<brief explanation>",
  "answer_relevance": <float between 0.0 and 1.0>,
  "answer_relevance_reason": "<brief explanation>"
}}"""
    try:
        raw_json = complete_chat(
            system="You are an objective AI evaluation judge. Always respond with strict valid JSON.",
            user=eval_prompt,
            temperature=0.0,
            response_format={"type": "json_object"},
        ).strip()
        result = json.loads(raw_json)
        cr = float(result.get("context_relevance", 0.0))
        faith = float(result.get("faithfulness", 0.0))
        ar = float(result.get("answer_relevance", 0.0))
        composite = round((cr + faith + ar) / 3.0, 3)
        return {
            "context_relevance_score": cr,
            "context_relevance_reason": result.get("context_relevance_reason", ""),
            "faithfulness_score": faith,
            "faithfulness_reason": result.get("faithfulness_reason", ""),
            "answer_relevance_score": ar,
            "answer_relevance_reason": result.get("answer_relevance_reason", ""),
            "composite_score": composite,
        }

    except Exception as e:
        print(f"[RAGEvaluator] Evaluation error: {e}")
        return {
            "context_relevance_score": 0.5,
            "context_relevance_reason": f"Evaluation error: {str(e)}",
            "faithfulness_score": 0.5,
            "faithfulness_reason": "Evaluator execution failed.",
            "answer_relevance_score": 0.5,
            "answer_relevance_reason": "Evaluator execution failed.",
            "composite_score": 0.5,
        }
