"""Printed GST tax-head matchers (CGST / SGST / IGST).

Relocated verbatim from v1 ``parser.py`` during the v2 migration (A2). These
regexes are a domain vocabulary used by both ``classify`` (deciding) and the
reading pipeline's printed-tax capture. Keeping the canonical copy in the domain
lets the reader depend on the domain, not the reverse. Behaviour is unchanged.
"""

import re

# A labelled tax line, e.g. "CGST 9%   675.00" / "Add: IGST @ 18%  1,234.00".
# The rate (a bare "9%" / "@18%") is stripped before taking the amount so the
# percentage is never mistaken for the tax value.
TAX_HEAD_RES = {
    "cgst": re.compile(r"\bCGST\b", re.I),
    "sgst": re.compile(r"\b(?:SGST|UTGST)\b", re.I),
    "igst": re.compile(r"\bIGST\b", re.I),
}
