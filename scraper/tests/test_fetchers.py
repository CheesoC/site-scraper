from scraper.fetchers import short_error


def test_short_error_messages():
    long = "Unexpected error in _crawl_web at line 799\nError: Failed on navigating ACS-GOTO:\nPage.goto: net::ERR_TUNNEL_CONNECTION_FAILED at https://x/\nCall log: ..."
    assert short_error(long) == "net::ERR_TUNNEL_CONNECTION_FAILED"
    assert short_error("Unexpected error in x\nTimeout 30000ms exceeded.\nmore") == "Timeout 30000ms exceeded."
