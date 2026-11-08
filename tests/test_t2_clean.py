from pilot.t2_clean import clean_submission, extract_main_document

SUBMISSION = """<SEC-DOCUMENT>x
<SEC-HEADER>...</SEC-HEADER>
<DOCUMENT>
<TYPE>10-K
<SEQUENCE>1
<FILENAME>main.htm
<TEXT>
<?xml version="1.0" encoding="utf-8"?>
<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"><head><title>t</title></head><body>
<div style="display:none"><ix:header><ix:hidden>dei:SecretHiddenFact</ix:hidden></ix:header></div>
<p>Our business faces <span>significant</span> competition.</p>
<table><tr><td>Revenue</td><td>1,234,567</td><td>2,345,678</td></tr></table>
<table><tr><td>We sell products in many markets around the world.</td></tr></table>
<p style="display: none">invisible text</p>
<p>Risk&nbsp;factors &amp; uncertainties</p>
</body></html>
</TEXT>
</DOCUMENT>
<DOCUMENT>
<TYPE>EX-21
<TEXT>exhibit subsidiaries list</TEXT>
</DOCUMENT>
"""


def test_extracts_only_the_10k_document():
    doc = extract_main_document(SUBMISSION)
    assert "competition" in doc
    assert "subsidiaries" not in doc


def test_clean_removes_hidden_xbrl_numeric_tables_and_markup():
    text, stats = clean_submission(SUBMISSION)
    assert "our business faces significant competition." in text
    assert "we sell products in many markets" in text  # prose table kept
    assert "1,234,567" not in text  # numeric table dropped
    assert "secrethiddenfact" not in text and "invisible" not in text
    assert "<" not in text and "&amp;" not in text
    assert "risk factors & uncertainties" in text
    assert text == text.lower()
    assert stats["tables_removed"] == 1
