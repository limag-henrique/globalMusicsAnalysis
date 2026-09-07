from chart_observatory.adapters.youtube_data.categories import map_regions


def test_youtube_regions_are_mapped_from_api_payload() -> None:
    payload = (
        b'{"items":[{"id":"BR","snippet":{"name":"Brazil"}},'
        b'{"id":"JP","snippet":{"name":"Japan"}}]}'
    )
    regions = map_regions(payload)
    assert [(region.code, region.name) for region in regions] == [("BR", "Brazil"), ("JP", "Japan")]
