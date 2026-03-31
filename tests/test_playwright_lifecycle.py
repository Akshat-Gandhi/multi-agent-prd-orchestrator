from prd_planner.tools.playwright_tool import DummyPlaywrightMCPClient, PlaywrightLifecycleTool


def test_playwright_always_closes_page():
    client = DummyPlaywrightMCPClient()
    tool = PlaywrightLifecycleTool(client)

    result = tool.capture("https://example.com")

    assert result.opened is True
    assert client.closed_pages
