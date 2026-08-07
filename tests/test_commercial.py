from vcscout.commercial import extract_commercial_signals, is_company_website_url


def test_extracts_visible_go_to_market_signals():
    html = """
    <html><body>
      <nav>
        <a href="/pricing">Pricing</a>
        <a href="/customers">Customer stories</a>
        <a href="/enterprise">Enterprise</a>
        <a href="/careers">Careers</a>
        <a href="/security">Security</a>
        <a href="/integrations">Integrations</a>
        <a href="/docs">Docs</a>
      </nav>
      <a href="/signup">Start free</a>
      <a href="/demo">Book a demo</a>
    </body></html>
    """
    signals = extract_commercial_signals(html)
    assert signals["commercial_signal_count"] == 9
    assert signals["commercial_momentum_score"] == 100


def test_ignores_script_only_marketing_terms():
    html = "<html><script>const pricing = '/pricing';</script><body><h1>Open source project</h1></body></html>"
    signals = extract_commercial_signals(html)
    assert signals["pricing_signal"] == 0
    assert signals["commercial_momentum_score"] == 0


def test_rejects_code_and_social_hosts_as_company_websites():
    assert not is_company_website_url("https://github.com/example")
    assert not is_company_website_url("https://docs.github.com/example")
    assert not is_company_website_url("https://www.linkedin.com/company/example")
    assert is_company_website_url("https://example.com")
