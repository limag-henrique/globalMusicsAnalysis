import csv
from pathlib import Path

import streamlit as st


def _market_inventory() -> list[dict[str, str]]:
    path = Path("research/market_capabilities.csv")
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    st.set_page_config(page_title="Chart Observatory", layout="wide")
    st.title("Chart Observatory")
    st.caption("Global-first, source-aware chart research with explicit provenance.")
    inventory = _market_inventory()
    markets = sorted({row["country_code"] for row in inventory if row.get("available") == "True"})
    platforms = sorted({row["origin_platform"] for row in inventory})
    providers = sorted({row["provider"] for row in inventory})
    columns = st.columns(4)
    columns[0].selectbox("Market", ["All", *markets])
    columns[1].selectbox("Platform", ["All", *platforms])
    columns[2].selectbox("Provider", ["All", *providers])
    columns[3].selectbox("Native Frequency", ["All", "DAILY", "WEEKLY", "OTHER"])
    st.selectbox("Chart", ["All"])
    st.date_input("Date Range", value=[])
    st.number_input("Top N", min_value=1, max_value=200, value=100)
    st.selectbox("Resolution State", ["All", "UNRESOLVED", "NEEDS_REVIEW", "MATCHED_EXACT"])
    if inventory:
        st.metric("Discovered source capabilities", len(inventory))
        st.dataframe(inventory, use_container_width=True, hide_index=True)
    else:
        st.info("Run `chart-observatory sources coverage` to build the dynamic market inventory.")


if __name__ == "__main__":
    main()
