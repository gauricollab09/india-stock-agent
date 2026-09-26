from __future__ import annotations

import json
import time
from dataclasses import dataclass

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.messages import AIMessage, ToolMessage

from stock_advisor.prompts import SYSTEM_PROMPT
from stock_advisor.schemas import Decision


@dataclass
class RunTrace:
    tool_calls: int = 0
    evaluate_attempts: int = 0
    evaluate_failures: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0


def build_agent(model, tools, system_prompt: str = SYSTEM_PROMPT):
    return create_agent(
        model, tools=tools, system_prompt=system_prompt, response_format=ToolStrategy(Decision)
    )


def run_agent(agent, user_message: str, max_steps: int) -> tuple[Decision, RunTrace]:
    t0 = time.perf_counter()
    result = agent.invoke(
        {"messages": [{"role": "user", "content": user_message}]},
        config={"recursion_limit": max_steps},
    )
    trace = RunTrace(latency_ms=int((time.perf_counter() - t0) * 1000))
    for m in result["messages"]:
        if isinstance(m, ToolMessage):
            if m.name == "Decision":
                continue
            trace.tool_calls += 1
            if m.name == "evaluate_portfolio":
                trace.evaluate_attempts += 1
                try:
                    ok = json.loads(m.content).get("ok", False)
                except (TypeError, ValueError):
                    ok = '"ok": true' in str(m.content)
                if not ok:
                    trace.evaluate_failures += 1
        elif isinstance(m, AIMessage) and m.usage_metadata:
            trace.input_tokens += int(m.usage_metadata.get("input_tokens", 0))
            trace.output_tokens += int(m.usage_metadata.get("output_tokens", 0))
    return result["structured_response"], trace
