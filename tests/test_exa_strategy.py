from prd_planner.tools.exa_tool import DummyExaAPIClient, DummyExaMCPClient, ExaSearchStrategy


def test_exa_prefers_mcp():
    strategy = ExaSearchStrategy(mcp=DummyExaMCPClient(should_fail=False), api=DummyExaAPIClient())
    results, source = strategy.search("b2b workflow automation")
    assert source == "mcp"
    assert len(results) >= 1


def test_exa_falls_back_to_api_when_mcp_fails():
    strategy = ExaSearchStrategy(mcp=DummyExaMCPClient(should_fail=True), api=DummyExaAPIClient())
    results, source = strategy.search("b2b workflow automation")
    assert source == "api_fallback"
    assert len(results) == 1
