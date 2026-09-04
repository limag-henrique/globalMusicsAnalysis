import streamlit as st


def main() -> None:
    st.set_page_config(page_title="Chart Observatory", layout="wide")
    st.title("Chart Observatory")
    st.caption("Recording-level, source-aware chart research. Network sources are disabled.")
    columns = st.columns(4)
    columns[0].selectbox("Country", ["BR", "US", "GB", "FR", "DE", "ES", "PT", "IT", "SE"])
    columns[1].selectbox("Platform", ["All", "Apple Music", "Spotify", "YouTube Video"])
    columns[2].selectbox("Provider", ["All", "Manual authorized file"])
    columns[3].selectbox("Native Frequency", ["All", "DAILY", "WEEKLY", "OTHER"])
    st.selectbox("Chart", ["All"])
    st.date_input("Date Range", value=[])
    st.number_input("Top N", min_value=1, max_value=200, value=100)
    st.selectbox("Resolution State", ["All", "UNRESOLVED", "NEEDS_REVIEW", "MATCHED_EXACT"])
    st.info("Use the CLI or API to preview and import an explicitly authorized local file.")


if __name__ == "__main__":
    main()
