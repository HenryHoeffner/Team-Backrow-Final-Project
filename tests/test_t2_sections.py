from pilot.t2_sections import MIN_SECTION_WORDS, extract_sections, find_section

PROSE = "the company faces many risks in its markets and discusses them here."  # 13 words


def body(tag: str, n_lines: int = 0) -> str:
    n = n_lines or MIN_SECTION_WORDS // 13 + 5
    return "\n".join(f"{tag} {PROSE}" for _ in range(n))


def test_standard_items_skip_table_of_contents():
    # CAT/PFE layout: index lists every item, body repeats them with text.
    text = "\n".join([
        "table of contents", "item 1a. risk factors", "item 1b. unresolved staff comments",
        "item 7. management's discussion and analysis of financial condition and results of operations",
        "item 7a. quantitative and qualitative disclosures about market risk",
        "item 1a.", "risk factors.", body("rf"),
        "item 1b. unresolved staff comments", "none.",
        "item 7.", "management's discussion and analysis of financial condition and results of operations.",
        body("mdna"),
        "item 7a. quantitative and qualitative disclosures about market risk", "market text",
    ])
    rf, info = find_section(text, "risk_factors")
    assert rf.startswith("item 1a.") and "rf the company" in rf and "mdna" not in rf
    assert "unresolved" not in rf and info["candidates"] >= 2
    assert info["heading"] == "item 1a. risk factors."  # the body heading, not the index line
    md, _ = find_section(text, "mdna")
    assert "mdna the company" in md and "rf the company" not in md and "market text" not in md


def test_subheading_inside_item_does_not_cut_it_short():
    # CAT FY2022+: MD&A has a "risk factors" pointer sub-heading; it must stay inside MD&A,
    # and must not be taken as the risk factors section either.
    text = "\n".join([
        "item 1a. risk factors", body("rf"), "item 1b. unresolved staff comments",
        "item 7. management's discussion and analysis", body("mdna1"),
        "risk factors", "risk factors are disclosed within item 1a.", body("mdna2"),
        "item 7a. quantitative and qualitative disclosures about market risk",
    ])
    md, _ = find_section(text, "mdna")
    assert "mdna1" in md and "mdna2" in md
    rf, _ = find_section(text, "risk_factors")
    assert "rf the company" in rf and "mdna" not in rf


def test_plain_name_headings_with_running_headers():
    # INTC/MCD layout: no Item numbers in the body; MD&A comes before risk factors.
    text = "\n".join([
        "item 7 management's discussion and analysis", "item 7a quantitative and qualitative disclosures about market risk",
        "management's discussion and analysis", body("mdna"),
        "risk factors and other key information", "risk factors", body("rf"),
        "risk factors and other key information", body("rf2", 5),
        "sales and marketing", "other text",
    ])
    md, _ = find_section(text, "mdna")
    assert "mdna the company" in md and "rf the company" not in md
    rf, _ = find_section(text, "risk_factors")
    assert "rf the company" in rf and "rf2" in rf and "other text" not in rf


def test_pointer_section_is_not_found_and_exhibit_is_used():
    # PFE FY2015-2019: Item 7 in the 10-K points to the EX-13 "financial review".
    main = "\n".join(["item 1a. risk factors", body("rf"), "item 1b. unresolved staff comments",
                      "item 7. management's discussion and analysis of financial condition and results of operations",
                      "incorporated by reference from the financial review in our 2018 financial report.",
                      "item 7a. quantitative and qualitative disclosures about market risk"])
    assert find_section(main, "mdna")[0] == ""
    exhibit = "\n".join(["financial review", body("fr"), "financial review", body("fr", 5),
                         "management's report on internal control over financial reporting", "auditor text"])
    found = extract_sections(main, exhibit, ["risk_factors", "mdna"])
    assert found["risk_factors"][1]["source"] == "10-K"
    md, info = found["mdna"]
    assert info["source"] == "EX-13" and "fr the company" in md and "auditor" not in md
    # "financial review" is only a heading inside an exhibit, never in the 10-K itself
    assert find_section(exhibit, "mdna")[0] == ""


def test_missing_section_returns_empty():
    text, info = find_section("nothing relevant here\n" + body("x"), "risk_factors")
    assert text == "" and info["candidates"] == 0


def test_market_risks_plural_ends_plain_risk_factors():
    # HON FY2020+: plain-name headings repeated as page headers, MD&A before risk factors,
    # and "market risks" (plural) after risk factors.
    text = "\n".join([
        "management's discussion and analysis of financial condition and results of operations", body("mdna"),
        "risk factors", body("rf1"), "risk factors", body("rf2"),
        "quantitative and qualitative disclosures about market risks", body("market"),
    ])
    rf, _ = find_section(text, "risk_factors")
    assert "rf1 the company" in rf and "rf2 the company" in rf and "market the company" not in rf


def test_wrapped_item_7_titles():
    # HON FY2016: title cut after "and results"; COP FY2019: title wraps after "and".
    for title in ["item 7. management's discussion and analysis of financial condition and results",
                  "item 7.\nmanagement's discussion and"]:
        text = "\n".join([title, "analysis of financial condition and results of operations", body("mdna"),
                          "item 7a. quantitative and qualitative disclosures about market risk", "x"])
        md, info = find_section(text, "mdna")
        assert "mdna the company" in md and info["n_words"] >= MIN_SECTION_WORDS, title


def test_unrecognised_headings_return_no_section():
    # A filing that words its headings differently yields "" so the T2 check can flag it.
    text = "\n".join(["business overview", body("x"), "operating and financial review", body("y")])
    for sec in ("risk_factors", "mdna"):
        out, info = find_section(text, sec)
        assert out == "" and info["start_line"] is None
