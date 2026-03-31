from __future__ import annotations

from dataclasses import dataclass

from prd_planner.agents.base import AgentContract
from prd_planner.agents.browser import BrowserAgent
from prd_planner.agents.competitor import CompetitorAgent
from prd_planner.agents.market import MarketAgent
from prd_planner.models.provider import ModelRegistry
from prd_planner.tools.exa_tool import build_exa_strategy_from_env
from prd_planner.tools.playwright_tool import build_playwright_tool_from_env


@dataclass
class AgentBundle:
    market: AgentContract
    competitor: AgentContract
    browser: AgentContract


def build_default_agents(model_registry: ModelRegistry | None = None) -> AgentBundle:
    exa_strategy = build_exa_strategy_from_env()
    browser_tool = build_playwright_tool_from_env()
    models = model_registry or ModelRegistry()
    return AgentBundle(
        market=MarketAgent(exa=exa_strategy, model=models.get("market_agent")),
        competitor=CompetitorAgent(exa=exa_strategy, model=models.get("competitor_agent")),
        browser=BrowserAgent(browser=browser_tool, exa=exa_strategy, model=models.get("browser_agent")),
    )
