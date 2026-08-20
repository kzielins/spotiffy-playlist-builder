from src.parser import extract_queries, is_boilerplate, suggest_playlist_name


def test_extracts_tracks_and_drops_promo() -> None:
    text = """Track list:
00:00 Daft Punk - One More Time
Follow Magic Club
Blinding Lights
"""
    queries = extract_queries(text)
    assert [q.query for q in queries] == ["Daft Punk One More Time", "Blinding Lights"]


def test_boilerplate() -> None:
    assert is_boilerplate("Stream/Download")
    assert not is_boilerplate("Daft Punk - One More Time")


def test_suggest_name_clamped() -> None:
    name = suggest_playlist_name(video_title=("A" * 150) + " | YouTube", queries=[])
    assert len(name) <= 100
