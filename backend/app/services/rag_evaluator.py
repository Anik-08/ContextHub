"""
rag_evaluator.py — Quantitative RAG Triad evaluation engine (Context Relevance, Faithfulness, Answer Relevance).

WHAT WE ARE BUILDING:
  An evaluation framework that quantitatively benchmarks RAG performance using
  the LLM-as-a-Judge methodology (the industry standard formalized by TruLens and Ragas).

THE RAG TRIAD:
  A production RAG system has two core components:
    1. Retrieval (finding the right data).
    2. Generation (synthesizing an accurate answer from that data).
  
  The RAG Triad evaluates both components across three independent axes:

  ┌────────────────────────────────────────────────────────┐
  │                                                        │
  │                  1. Context Relevance                  │
  │               (Query ──> Retrieved Chunks)             │
  │                                                        │
  └───────────────────────────┬────────────────────────────┘
                              │
                              ▼
  ┌────────────────────────────────────────────────────────┐
  │                                                        │
  │                    2. Groundedness                     │
  │             (Retrieved Chunks ──> Answer)              │
  │                                                        │
  └───────────────────────────┬────────────────────────────┘
                              │
                              ▼
  ┌────────────────────────────────────────────────────────┐
  │                                                        │
  │                  3. Answer Relevance                   │
  │                   (Query ──> Answer)                   │
  │                                                        │
  └────────────────────────────────────────────────────────┘

1. Context Relevance (0.0 to 1.0):
   - Measures: Did the retrieval engine pull chunks relevant to the user's query?
   - Low score means: Poor chunking, embedding drift, or lack of hybrid search.
   - Consequence: Flooding the LLM with irrelevant text causes the "lost-in-the-middle" effect.

2. Groundedness / Faithfulness (0.0 to 1.0):
   - Measures: Is every claim in the answer backed by facts in the retrieved context?
   - Low score means: Hallucination! The LLM is inventing facts or drawing from pre-training.
   - This is the #1 metric for enterprise AI safety and compliance.

3. Answer Relevance (0.0 to 1.0):
   - Measures: Did the generated answer actually address the user's original question?
   - Low score means: The LLM went off-topic, answered a different question, or was evasive.

INTERVIEW ANGLE:
  "How do you evaluate and monitor a RAG system in production?"
  Answer:
    1. Automated Triad evaluation: Sample 5% of production queries and run LLM-as-a-judge
       evaluations on Context Relevance, Faithfulness, and Answer Relevance.
    2. Retrieval metrics: Track Recall@K, Mean Reciprocal Rank (MRR), and NDCG against
       labeled golden benchmark datasets.
    3. User feedback loops: Thumbs up/thumbs down ratings with source chunk click-throughs.
    4. Guardrails: Flag queries with low Faithfulness scores (< 0.8) for human review.
"""

import json

from app.services.llm import complete_chat


def evaluate_rag_response(
    question: str,
    context: str,
    answer: str,
) -> dict:
    """
    Compute RAG Triad scores using LLM-as-a-Judge.

    Args:
        question: The user's input question.
        context: The concatenated retrieved context passed to the LLM.
        answer: The generated answer from the RAG pipeline.

    Returns:
        dict containing:
          - context_relevance_score (float: 0.0 to 1.0)
          - context_relevance_reason (str)
          - faithfulness_score (float: 0.0 to 1.0)
          - faithfulness_reason (str)
          - answer_relevance_score (float: 0.0 to 1.0)
          - answer_relevance_reason (str)
          - composite_score (float: average of all three)
    """
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
