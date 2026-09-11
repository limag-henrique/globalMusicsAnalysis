from chart_observatory.lyrics.gemini_pipeline import (
    GeminiAnnotationClient,
    LyricsOvhClient,
    normalize_lookup_text,
)


def test_lookup_normalization_removes_feature_markers_and_accents() -> None:
    assert normalize_lookup_text("Música (feat. João)") == "musica"


def test_gemini_client_extracts_json_text_from_response() -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "candidates": [
                    {"content": {"parts": [{"text": '{"translation_en":"hello"}'}]}}
                ]
            }

    class FakeHttp:
        def post(self, *args, **kwargs):
            return FakeResponse()

    client = GeminiAnnotationClient("key", http_client=FakeHttp())

    assert client.annotate("id", "Title", "Artist", "linha") == {"translation_en": "hello"}


def test_lyrics_ovh_client_returns_none_for_http_errors() -> None:
    class FakeResponse:
        status_code = 404

    class FakeHttp:
        def get(self, *args, **kwargs):
            return FakeResponse()

    client = LyricsOvhClient(http_client=FakeHttp())

    assert client.fetch("Title", "Artist") is None
