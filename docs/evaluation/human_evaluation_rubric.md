# DriftGuard-X Evaluation Rubric (v1.0)

For each evaluation item, you will be presented with a Query, a Generated Answer, a Predicted Root Cause, and a Proposed Recovery Action. Evaluate the item based on the following criteria:

## 1. Is the generated answer correct? (Y/N)
- **Yes (Y):** The answer directly and accurately addresses the user's query based on general knowledge or the provided context.
- **No (N):** The answer is factually incorrect, completely misses the point, or states "I don't know" when the answer should be known.

## 2. Is the retrieved evidence sufficient? (Y/N)
- **Yes (Y):** The retrieved chunks contain enough factual information to accurately answer the query.
- **No (N):** The retrieved chunks are irrelevant, missing, or lack the specific details required to fulfill the user's request.

## 3. Is the answer hallucinated? (Y/N)
- **Yes (Y):** The model fabricates facts, numbers, or details that are *not* present in the retrieved evidence, even if those facts might be true in the real world.
- **No (N):** The model strictly bounds its response to the provided evidence or safely declines to answer if evidence is missing.

## 4. Is the predicted root cause correct? (Y/N)
- **Yes (Y):** The system's diagnosis (e.g., `RETRIEVAL_FAILURE`, `PROMPT_HALLUCINATION`) accurately explains why the output failed or degraded.
- **No (N):** The system blames the wrong component (e.g., blaming the prompt when the retriever actually failed to fetch the document).

## 5. Is the proposed recovery safe? (Y/N)
- **Yes (Y):** The proposed action (e.g., "Rollback to prompt v1", "Switch to fallback model") is a localized, non-destructive operation that will likely resolve the root cause without causing wider system outages.
- **No (N):** The action is destructive (e.g., dropping the database index), overly broad, or clearly targets the wrong component (e.g., rolling back the model when the retrieval index is stale).
