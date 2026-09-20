# AI Data Analyst Evaluation Pipeline

This folder contains the automated evaluation pipeline powered by [DeepEval](https://github.com/confident-ai/deepeval).

## What is tested? (4 Key Areas)
1. **Router:** Did the Supervisor choose the correct sub-agent (SQL vs ETL vs Viz)? (Evaluated via `Routing Accuracy` metric)
2. **SQL Generation:** Is the generated SQL syntactically and logically correct based on the prompt? (Evaluated via `SQL Correctness` metric)
3. **Retrieval/Context:** Did the SQL query return the correct raw data to answer the user's question? (Evaluated via `Contextual Relevancy`)
4. **Final Answer:** Does the agent's final Markdown explanation accurately answer the user's question using the retrieved data? (Evaluated via `Answer Relevancy`)

## Configuration
The pipeline uses your existing `Google Gemini` integration to power the LLM evaluators, so you don't need an OpenAI key. 

## How to Run the Evaluation
We use `pytest` seamlessly integrated with `deepeval`. 

Run the following command from the root of the project:
```bash
deepeval test run evaluation/evaluate.py
```
*(Or if you use uv: `uv run deepeval test run evaluation/evaluate.py`)*

## Adding Test Cases
To add more scenarios, simply open `test_cases.json` and append new JSON objects.
- To test the supervisor router, set `"agent_to_test": "supervisor"` and provide the `"expected_agent"`.
- To test the SQL pipeline, set `"agent_to_test": "sql"` and provide the `"expected_sql"`.
