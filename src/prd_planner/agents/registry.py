from __future__ import annotations

from dataclasses import dataclass

from prd_planner.agents.base import AgentContract
from prd_planner.agents.browser import BrowserAgent
from prd_planner.agents.competitor import CompetitorAgent
from prd_planner.agents.market import MarketAgent
from prd_planner.tools.exa_tool import build_exa_strategy_from_env
from prd_planner.tools.playwright_tool import build_playwright_tool_from_env


@dataclass
class AgentBundle:
    market: AgentContract
    competitor: AgentContract
    browser: AgentContract


def build_default_agents() -> AgentBundle:
    exa_strategy = build_exa_strategy_from_env()
    browser_tool = build_playwright_tool_from_env()
    return AgentBundle(
        market=MarketAgent(exa=exa_strategy),
        competitor=CompetitorAgent(exa=exa_strategy),
        browser=BrowserAgent(browser=browser_tool),
    )
