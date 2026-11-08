from pilot.t8_diff import sentence_diff

OLD = ("we operate in many countries around the world.\n"
       "revenue in 2023 was driven by strong demand for our products.\n"
       "we face intense competition in all markets.\n")
NEW = ("we operate in many countries around the world.\n"
       "revenue in 2024 was driven by strong demand for our products.\n"
       "new export controls could restrict sales to some customers.\n")


def test_sentence_diff_ignores_year_rollover_and_finds_real_changes():
    added, removed = sentence_diff(OLD, NEW)
    assert added == ["new export controls could restrict sales to some customers."]
    assert removed == ["we face intense competition in all markets."]
