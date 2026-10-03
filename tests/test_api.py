import sinfony as sf


def test_public_api_names_resolve():
    for name in sf.__all__:
        assert hasattr(sf, name), name


def test_one_liner():
    piece = sf.tonal(seed=1)
    assert isinstance(piece, sf.Piece)
    assert len(piece.score) > 0
