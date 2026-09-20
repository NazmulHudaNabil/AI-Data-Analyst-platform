import os
import sys
import json
import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from deepeval.metrics import AnswerRelevancyMetric, ContextualRelevancyMetric, GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from deepeval.models.base_model import DeepEvalBaseLLM
from deepeval import assert_test

from main import supervisor_agent
from agents.sql_agent import sql_analyst
from utils.llm_pick import pick_llm


# -------------------------------------------------------------------
# Setup Gemini as the Evaluator Model for DeepEval
# -------------------------------------------------------------------
from langchain_core.output_parsers import StrOutputParser

class GeminiEvaluator(DeepEvalBaseLLM):
    def __init__(self):
        self.model = pick_llm("medium")
        self.chain = self.model | StrOutputParser()
        
    def load_model(self):
        return self.model
        
    def generate(self, prompt: str) -> str:
        return self.chain.invoke(prompt)
        
    async def a_generate(self, prompt: str) -> str:
        return await self.chain.ainvoke(prompt)
        
    def get_model_name(self):
        return "gemini-evaluator"

evaluator_llm = GeminiEvaluator()


# -------------------------------------------------------------------
# Load Test Cases
# -------------------------------------------------------------------
def load_test_cases():
    with open(os.path.join(os.path.dirname(__file__), "test_cases.json"), "r") as f:
        return json.load(f)

test_data = load_test_cases()


# -------------------------------------------------------------------
# Metrics Setup
# -------------------------------------------------------------------

# 1. Routing Accuracy (GEval Custom Metric)
routing_metric = GEval(
    name="Routing Accuracy",
    criteria="Determine if the actual routed agent perfectly matches the expected agent. They must be exactly identical.",
    evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.EXPECTED_OUTPUT],
    model=evaluator_llm
)

# 2. SQL Correctness (GEval Custom Metric)
sql_correctness_metric = GEval(
    name="SQL Correctness",
    criteria="Evaluate if the actual generated SQL logically matches the expected SQL and would produce the same result.",
    evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.EXPECTED_OUTPUT],
    model=evaluator_llm
)

# 3. Contextual Relevancy (Did SQL return the required info?)
context_metric = ContextualRelevancyMetric(
    threshold=0.5,
    model=evaluator_llm,
    include_reason=True
)

# 4. Answer Relevancy (Does the final answer actually answer the question?)
answer_metric = AnswerRelevancyMetric(
    threshold=0.5,
    model=evaluator_llm,
    include_reason=True
)


# -------------------------------------------------------------------
# Tests
# -------------------------------------------------------------------

@pytest.mark.parametrize("test_case", [tc for tc in test_data if tc["agent_to_test"] == "supervisor"])
def test_router(test_case):
    """Area 1: Router - Did Supervisor choose SQL/ETL correctly?"""
    
    # Run the system
    test_state = {
        "messages": [],
        "user_input": test_case["input"],
        "selected_agent": "",
        "extracted_file_path": "",
        "final_response": ""
    }
    result = supervisor_agent.invoke(test_state)
    actual_agent = result.get("selected_agent")
    
    # Wrap in DeepEval Test Case
    llm_test_case = LLMTestCase(
        input=test_case["input"],
        actual_output=actual_agent,
        expected_output=test_case["expected_agent"]
    )
    
    # Assert
    assert_test(llm_test_case, [routing_metric])


@pytest.mark.parametrize("test_case", [tc for tc in test_data if tc["agent_to_test"] == "sql"])
def test_sql_agent(test_case):
    """Area 2, 3, 4: SQL Correctness, Context Relevancy, and Final Answer."""
    
    # Run the system
    sql_input = {
        "messages": [],
        "user_question": test_case["input"],
        "curated_ques": "",
        "prompt_query_context": "",
        "generated_sql_query": "",
        "is_safe": "Yes",
        "comments": "",
        "sql_query_execution_result": "",
        "final_answer": ""
    }
    result = sql_analyst.invoke(sql_input)
    
    actual_sql = result.get("generated_sql_query")
    raw_db_context = result.get("sql_query_execution_result")
    final_answer = result.get("final_answer")
    
    # 2. SQL Correctness
    sql_test_case = LLMTestCase(
        input=test_case["input"],
        actual_output=actual_sql,
        expected_output=test_case["expected_sql"]
    )
    
    # 3 & 4. Retrieval Context & Final Answer
    qa_test_case = LLMTestCase(
        input=test_case["input"],
        actual_output=final_answer,
        retrieval_context=[raw_db_context]
    )
    
    # Run assertions
    assert_test(sql_test_case, [sql_correctness_metric])
    assert_test(qa_test_case, [context_metric, answer_metric])
