from trade_digest.data.sector_flow import fetch_etf_quotes
from trade_digest.data.market_overview import fetch_gold_spot_price


def enrich_holdings_with_quotes(holdings: dict) -> list[dict]:
    flat = []
    for category, cat_data in holdings["categories"].items():
        for position in cat_data["positions"]:
            flat.append({**position, "category": category})

    codes = [p["code"] for p in flat if p.get("code") and p["category"] != "gold"]
    quotes = fetch_etf_quotes(codes)
    gold_price = fetch_gold_spot_price() if any(p["category"] == "gold" for p in flat) else None

    for position in flat:
        if position["category"] == "gold":
            position["price"] = gold_price
            position["change_pct"] = None
            continue
        code = position.get("code")
        quote = quotes.get(code) if code else None
        if quote:
            position["price"] = quote["price"]
            position["change_pct"] = quote.get("change_pct")
        else:
            position["price"] = None
            position["change_pct"] = None

    return flat
