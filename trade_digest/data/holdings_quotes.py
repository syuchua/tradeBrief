from trade_digest.data.sector_flow import fetch_etf_quotes


def enrich_holdings_with_quotes(holdings: dict) -> list[dict]:
    flat = []
    for category, cat_data in holdings["categories"].items():
        for position in cat_data["positions"]:
            flat.append({**position, "category": category})

    codes = [p["code"] for p in flat if p.get("code")]
    quotes = fetch_etf_quotes(codes)

    for position in flat:
        code = position.get("code")
        quote = quotes.get(code) if code else None
        position["price"] = quote["price"] if quote else None

    return flat
