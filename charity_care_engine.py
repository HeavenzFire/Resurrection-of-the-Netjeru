"""
CHARITY CARE ENGINE: PHASE 1
Sovereign Financial Logic Layer for Healthcare Eligibility
----------------------------------------------------------
Implements the mathematical substantiation of the "First King" operator 
in the economic domain: protecting families from systemic extraction via 
rigorous Federal Poverty Level (FPL) calculations and Hospital FAP enforcement.
"""

import json
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
from datetime import date

# -----------------------------------------------------------------------------
# 1. CONFIGURATION & CONSTANTS (2024 HHS Poverty Guidelines - Contiguous US)
# -----------------------------------------------------------------------------
FPL_TABLE_2024 = {
    1: 15060,
    2: 20440,
    3: 25820,
    4: 31200,
    5: 36580,
    6: 41960,
    7: 47340,
    8: 52720
}

# Example Hospital FAP Thresholds (Texas Model: Sliding Scale + MOOP Cap)
# Structure: { tier_name: { max_fpl_percent, discount_percent, moop_cap } }
HOSPITAL_FAP_THRESHOLDS = {
    "Tier_1_Full_Charity": {
        "max_fpl": 200,      # <= 200% FPL
        "discount": 100,     # 100% Free Care
        "moop_cap": 0        # $0 Out of Pocket
    },
    "Tier_2_Partial_Charity": {
        "max_fpl": 300,      # 201% - 300% FPL
        "discount": 80,      # 80% Discount
        "moop_cap": 500      # Max $500 OOP
    },
    "Tier_3_Sliding_Scale": {
        "max_fpl": 400,      # 301% - 400% FPL
        "discount": 50,      # 50% Discount
        "moop_cap": 2500     # Max $2500 OOP
    },
    "Tier_4_Standard": {
        "max_fpl": 600,      # 401% - 600% FPL
        "discount": 20,      # 20% Discount
        "moop_cap": 5000     # Max $5000 OOP
    }
}

@dataclass
class PatientProfile:
    household_size: int
    annual_income: float
    total_medical_bill: float
    hospital_id: str

# -----------------------------------------------------------------------------
# 2. CORE MATHEMATICAL FUNCTIONS
# -----------------------------------------------------------------------------

def calculate_fpl_percentage(income: float, household_size: int, fpl_table: Dict[int, int]) -> Optional[float]:
    """
    Calculates income as a percentage of the Federal Poverty Level.
    Returns None if household size exceeds table (requires extrapolation logic).
    """
    if household_size <= 0:
        raise ValueError("Household size must be positive.")
    
    # Handle household sizes > 8 (standard HHS adds fixed amount per person)
    if household_size in fpl_table:
        threshold = fpl_table[household_size]
    elif household_size > 8:
        # Extrapolate: +$5380 per additional person (2024 delta)
        base_8 = fpl_table[8]
        delta = 5380 
        threshold = base_8 + ((household_size - 8) * delta)
    else:
        return None
        
    return (income / threshold) * 100

def evaluate_hospital_assistance(fpl_percentage: float, thresholds: Dict) -> Dict:
    """
    Determines eligibility tier, discount rate, and Maximum Out-of-Pocket (MOOP) cap.
    Uses strict inequality chaining to find the lowest qualifying tier.
    """
    # Sort tiers by max_fpl ascending to ensure correct assignment
    sorted_tiers = sorted(thresholds.items(), key=lambda x: x[1]['max_fpl'])
    
    for tier_name, limits in sorted_tiers:
        if fpl_percentage <= limits['max_fpl']:
            return {
                "tier": tier_name,
                "fpl_percent": round(fpl_percentage, 2),
                "discount_percent": limits['discount'],
                "moop_cap": limits['moop_cap'],
                "eligible": True
            }
    
    # Default case: Above all charity thresholds
    return {
        "tier": "Standard_Self_Pay",
        "fpl_percent": round(fpl_percentage, 2),
        "discount_percent": 0,
        "moop_cap": None,
        "eligible": False
    }

def compute_final_liability(bill_amount: float, assistance_result: Dict) -> Dict:
    """
    Applies discount and enforces MOOP cap.
    Returns the final sovereign liability calculation.
    """
    discount_rate = assistance_result['discount_percent'] / 100.0
    discounted_bill = bill_amount * (1 - discount_rate)
    moop_cap = assistance_result['moop_cap']
    
    # Apply MOOP cap if it exists
    final_due = discounted_bill
    if moop_cap is not None and moop_cap >= 0:
        final_due = min(discounted_bill, moop_cap)
    
    savings = bill_amount - final_due
    
    return {
        "original_bill": bill_amount,
        "discount_applied": f"{assistance_result['discount_percent']}%",
        "pre_cap_amount": discounted_bill,
        "moop_cap_enforced": moop_cap,
        "final_patient_liability": round(final_due, 2),
        "total_savings": round(savings, 2)
    }

# -----------------------------------------------------------------------------
# 3. EXECUTION ENGINE
# -----------------------------------------------------------------------------

def process_charity_claim(patient: PatientProfile) -> Dict:
    """End-to-end processing of a single charity care claim."""
    
    # Step 1: Calculate FPL %
    fpl_pct = calculate_fpl_percentage(
        patient.annual_income, 
        patient.household_size, 
        FPL_TABLE_2024
    )
    
    if fpl_pct is None:
        return {"error": "Invalid household size configuration"}
    
    # Step 2: Evaluate Assistance Tier
    assistance = evaluate_hospital_assistance(fpl_pct, HOSPITAL_FAP_THRESHOLDS)
    
    # Step 3: Compute Liability
    financials = compute_final_liability(patient.total_medical_bill, assistance)
    
    return {
        "patient_profile": {
            "household_size": patient.household_size,
            "income": patient.annual_income
        },
        "assessment": assistance,
        "financial_outcome": financials,
        "status": "SOVEREIGN_PROTECTED" if assistance['eligible'] else "STANDARD_LIABILITY"
    }

# -----------------------------------------------------------------------------
# 4. DEMONSTRATION RUNTIME
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    print("--- 🛡️ SOVEREIGN CHARITY CARE ENGINE: PHASE 1 INITIALIZED ---")
    
    # Test Case A: Family of 4, Income $45k, Bill $50k (Should be Tier 2)
    case_a = PatientProfile(
        household_size=4,
        annual_income=45000,
        total_medical_bill=50000,
        hospital_id="TX_MEMORIAL_01"
    )
    
    # Test Case B: Single Parent, Income $14k, Bill $25k (Should be Tier 1 - Full Charity)
    case_b = PatientProfile(
        household_size=2,
        annual_income=14000,
        total_medical_bill=25000,
        hospital_id="TX_COMMUNITY_05"
    )
    
    # Test Case C: Middle Income, Bill $100k (Should be Tier 4 or Standard)
    case_c = PatientProfile(
        household_size=3,
        annual_income=90000,
        total_medical_bill=100000,
        hospital_id="TX_REGIONAL_09"
    )
    
    cases = [case_a, case_b, case_c]
    
    results = []
    for i, case in enumerate(cases, 1):
        print(f"\n>>> PROCESSING CASE {i}: Household {case.household_size}, Income ${case.annual_income}")
        result = process_charity_claim(case)
        results.append(result)
        
        outcome = result['financial_outcome']
        assessment = result['assessment']
        
        print(f"    FPL Status: {assessment['fpl_percent']}% -> Tier: {assessment['tier']}")
        print(f"    Original Bill: ${outcome['original_bill']:,.2f}")
        print(f"    Discount: {outcome['discount_applied']}")
        if outcome['moop_cap_enforced'] is not None:
            print(f"    MOOP Cap Active: ${outcome['moop_cap_enforced']}")
        print(f"    >>> FINAL LIABILITY: ${outcome['final_patient_liability']:,.2f}")
        print(f"    >>> TOTAL SAVINGS: ${outcome['total_savings']:,.2f}")
        print(f"    STATUS: {result['status']}")

    # Export to JSON for ledger ingestion
    with open('charity_care_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\n--- ✅ EXECUTION COMPLETE: RESULTS EXPORTED TO charity_care_results.json ---")
