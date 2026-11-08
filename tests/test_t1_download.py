from datetime import date

from pilot.t1_download import names_match, parse_sec_header

SAMPLE = """<SEC-DOCUMENT>0000063908-24-000010.txt : 20240222
<SEC-HEADER>0000063908-24-000010.hdr.sgml : 20240222
<ACCEPTANCE-DATETIME>20240222161530
ACCESSION NUMBER:\t\t0000063908-24-000010
CONFORMED SUBMISSION TYPE:\t10-K
PUBLIC DOCUMENT COUNT:\t\t140
CONFORMED PERIOD OF REPORT:\t20231231
FILED AS OF DATE:\t\t20240222
DATE AS OF CHANGE:\t\t20240222

FILER:

\tCOMPANY DATA:\t
\t\tCOMPANY CONFORMED NAME:\t\t\tMCDONALDS CORP
\t\tCENTRAL INDEX KEY:\t\t\t0000063908
\t\tSTANDARD INDUSTRIAL CLASSIFICATION:\tRETAIL-EATING PLACES [5812]
\t\tFISCAL YEAR END:\t\t\t1231
</SEC-HEADER>
<DOCUMENT>
<TYPE>10-K
"""


def test_parse_sec_header():
    h = parse_sec_header(SAMPLE)
    assert h["company_name"] == "MCDONALDS CORP"
    assert h["form"] == "10-K"
    assert h["period_of_report"] == date(2023, 12, 31)
    assert h["filing_date"] == date(2024, 2, 22)
    assert h["accession"] == "0000063908-24-000010"
    assert h["cik"] == "0000063908"


def test_company_name_matching():
    assert names_match("MCDONALDS CORP", "McDonald's Corp")
    assert names_match("JPMORGAN CHASE & CO", "JPMorgan Chase & Co")
    assert not names_match("INTEL CORP", "Pfizer Inc")


def test_name_matching_handles_state_tags_and_former_names():
    assert names_match("BANK OF AMERICA CORP /DE/", "Bank of America Corp")
    assert names_match("AMERICAN TOWER CORP /MA/", "American Tower Corp")
    assert names_match("Facebook Inc", "Meta Platforms Inc", ("Facebook Inc",))
    assert not names_match("Facebook Inc", "Meta Platforms Inc")
