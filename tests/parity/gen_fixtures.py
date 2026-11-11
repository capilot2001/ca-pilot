"""Build varied pre-classify invoice fixtures for the parity gate (v2 models)."""
import json, os, string
from pathlib import Path
from shared.models import Invoice, LineItem
from app.domain.validate import validate_gstin

_B36 = string.digits + string.ascii_uppercase

def valid_gstin(base14: str) -> str:
    """base14 ends at the 'Z' (pos 14); brute-force the pos-15 check digit."""
    for c in _B36:
        g = base14 + c
        if validate_gstin(g)[0]:
            return g
    raise ValueError(f"no valid check digit for {base14}")

# party GSTINs with real check digits so vouchers are not excluded on INVALID_GSTIN
UP  = valid_gstin("09ABCDE1234F1Z")
OD  = valid_gstin("21PQRSX6789K1Z")
MH  = valid_gstin("27LMNOP4321Q1Z")
DRY = valid_gstin("21DAIRY6789K1Z")

def inv(**k): return Invoice(**k)
def li(**k): return LineItem(**k)

fixtures = [
    # 1. purchase, inter-state (supplier UP 09 vs company Odisha 21) -> IGST, 18%
    inv(source_file="P-100.pdf", direction="purchase", party_name="UP Steel Supplies",
        party_gstin=UP, party_state_code="09", party_state="Uttar Pradesh",
        party_address="Industrial Area, Kanpur", party_pincode="208001",
        invoice_number="P-100", invoice_date="2024-05-10", invoice_date_display="10-May-2024",
        place_of_supply="Odisha", place_of_supply_code="21",
        items=[li(description="Steel Rod 12mm", hsn_sac="7213", quantity=10, unit="Kgs",
                  rate=50.0, gst_rate=18.0, taxable_value=500.0, amount=500.0)]),
    # 2. purchase, intra-state (supplier Odisha 21) -> CGST+SGST, 12%, two lines
    inv(source_file="P-200.pdf", direction="purchase", party_name="Odisha Traders",
        party_gstin=OD, party_state_code="21", party_state="Odisha",
        party_address="Main Road, Cuttack", party_pincode="753001",
        invoice_number="P-200", invoice_date="2024-06-01", invoice_date_display="1-Jun-2024",
        place_of_supply="Odisha", place_of_supply_code="21",
        items=[li(description="Cotton Bag", hsn_sac="4202", quantity=100, unit="Nos",
                  rate=20.0, gst_rate=12.0, taxable_value=2000.0, amount=2000.0),
               li(description="Jute Roll", hsn_sac="5310", quantity=5, unit="Roll",
                  rate=300.0, gst_rate=12.0, taxable_value=1500.0, amount=1500.0)]),
    # 3. sale, inter-state (buyer Maharashtra 27) -> IGST, 5%
    inv(source_file="S-10.pdf", direction="sale", party_name="Mumbai Retail Pvt Ltd",
        party_gstin=MH, party_state_code="27", party_state="Maharashtra",
        party_address="Andheri East, Mumbai", party_pincode="400069",
        invoice_number="S-10", invoice_date="2024-06-15", invoice_date_display="15-Jun-2024",
        place_of_supply="Maharashtra", place_of_supply_code="27",
        items=[li(description="Rice Bag 25kg", hsn_sac="1006", quantity=40, unit="Bag",
                  rate=800.0, gst_rate=5.0, taxable_value=32000.0, amount=32000.0)]),
    # 4. purchase, intra-state, exempt (0%)
    inv(source_file="P-300.pdf", direction="purchase", party_name="Fresh Dairy",
        party_gstin=DRY, party_state_code="21", party_state="Odisha",
        party_address="Milk Colony, Sambalpur", party_pincode="768001",
        invoice_number="P-300", invoice_date="2024-06-20", invoice_date_display="20-Jun-2024",
        place_of_supply="Odisha", place_of_supply_code="21",
        items=[li(description="Fresh Milk", hsn_sac="0401", quantity=200, unit="Ltr",
                  rate=30.0, gst_rate=0.0, taxable_value=6000.0, amount=6000.0)]),
]

out = Path(os.environ["OUT"])
out.write_text(json.dumps([i.model_dump() for i in fixtures], indent=2))
print("wrote", len(fixtures), "fixtures to", out)
