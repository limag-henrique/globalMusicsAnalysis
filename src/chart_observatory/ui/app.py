from pathlib import Path

import streamlit as st

from chart_observatory.ui.source_inventory import load_capabilities, load_manifests


def _market_inventory() -> list[dict[str, str]]:
    return load_capabilities(Path("research/market_capabilities.csv"))


def _source_inventory() -> list[dict[str, str]]:
    return load_manifests(Path("research/mgd_source_manifest.json"))


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
    capabilities_tab, sources_tab = st.tabs(["Market capabilities", "Data Sources"])
    with capabilities_tab:
        if inventory:
            st.metric("Discovered source capabilities", len(inventory))
            st.dataframe(inventory, use_container_width=True, hide_index=True)
        else:
            st.info(
                "Run `chart-observatory sources coverage` to build the dynamic market inventory."
            )
    with sources_tab:
        sources = _source_inventory()
        if sources:
            st.metric("Inventoried source artifacts", len(sources))
            st.dataframe(sources, use_container_width=True, hide_index=True)
        else:
            st.info("Run `chart-observatory sources mgd inspect` to build the source inventory.")


if __name__ == "__main__":
    main()
