from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import PrivateAttr


class ScriptedChatModel(BaseChatModel):
    """Returns pre-scripted AIMessages in order; bind_tools is a no-op."""

    responses: list[AIMessage]
    _i: int = PrivateAttr(default=0)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        msg = self.responses[self._i]
        self._i += 1
        return ChatResult(generations=[ChatGeneration(message=msg)])

    def bind_tools(self, tools, **kwargs):
        return self


def call(name: str, args: dict, call_id: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


def standard_script(picks: list[dict], first_picks: list[dict] | None = None) -> list[AIMessage]:
    """get_universe -> snapshots -> (optional failing evaluate) -> passing evaluate -> Decision."""
    msgs = [call("get_universe", {}, "c1"), call("get_stock_snapshots", {"tickers": []}, "c2")]
    n = 3
    if first_picks:
        msgs.append(call("evaluate_portfolio", {"picks": first_picks}, f"c{n}"))
        n += 1
    slim = [{"ticker": p["ticker"], "target_weight": p["target_weight"]} for p in picks]
    msgs.append(call("evaluate_portfolio", {"picks": slim}, f"c{n}"))
    msgs.append(
        call(
            "Decision",
            {"picks": picks, "strategy_summary": "balanced mix", "assumptions": ["fixture data"]},
            f"c{n + 1}",
        )
    )
    return msgs
