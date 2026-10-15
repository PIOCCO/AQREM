from app.services.retrieval.keywords import extract_keyword_terms


def test_extract_name_from_who_is():
    assert extract_keyword_terms("who is gammal oussama") == ["gammal", "oussama"]


def test_extract_experience_question():
    terms = extract_keyword_terms("what experience has he done")
    assert "experience" not in terms or "he" not in terms
