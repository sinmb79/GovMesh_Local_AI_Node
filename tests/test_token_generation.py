from scripts.generate_local_tokens import TOKEN_NAMES, generate_tokens


def test_generate_local_tokens_returns_all_required_names() -> None:
    tokens = generate_tokens(bytes_per_token=8)

    assert set(tokens) == set(TOKEN_NAMES)
    assert all(tokens.values())
    assert len(set(tokens.values())) == len(TOKEN_NAMES)
