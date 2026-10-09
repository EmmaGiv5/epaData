# used to teach the search bar EPA terminology. 
# will help with somatic searching

"""
search_utils.py

Utilities for interpreting EPA-related search terms in epaData.

This module:
- Normalizes user search input.
- Recognizes common EPA terminology and synonyms.
- Maps search terms to database fields.
- Helps the search route determine which measurement a user wants.
"""


# --------------------------------------------------
# EPA SEARCH TERM MAPPING
# --------------------------------------------------

SEARCH_TERMS = {
    # Carbon dioxide emissions
    "carbon emissions": "co2_mass",
    "carbon dioxide emissions": "co2_mass",
    "carbon dioxide": "co2_mass",
    "co2 emissions": "co2_mass",
    "co2": "co2_mass",

    # Sulfur dioxide emissions
    "sulfur dioxide emissions": "so2_mass",
    "sulphur dioxide emissions": "so2_mass",
    "sulfur dioxide": "so2_mass",
    "sulphur dioxide": "so2_mass",
    "so2 emissions": "so2_mass",
    "so2": "so2_mass",

    # Nitrogen oxide emissions
    "nitrogen oxide emissions": "nox_mass",
    "nitrogen oxides": "nox_mass",
    "nitrogen oxide": "nox_mass",
    "nox emissions": "nox_mass",
    "nox": "nox_mass",

    # Heat and operating information
    "heat input": "heat_input",
    "fuel heat input": "heat_input",
    "operating hours": "operating_time",
    "hours of operation": "operating_time",
    "operating time": "operating_time",

    # Electricity and production-related information
    "gross load": "gross_load",
    "gross generation": "gross_load",
    "steam load": "steam_load",
}


# --------------------------------------------------
# SEARCH INPUT NORMALIZATION
# --------------------------------------------------

def normalize_query(query):
    """
    Clean a user's search query.

    Example:
        "  Carbon Emissions  " -> "carbon emissions"
    """

    if not query:
        return ""

    return " ".join(query.lower().split())


# --------------------------------------------------
# SEARCH TERM DETECTION
# --------------------------------------------------

def find_search_field(query):
    """
    Identify the EPA database field associated with a query.

    Returns:
        A database field name if a known term is found.
        None if no known term is found.

    Example:
        find_search_field("Show me CO2 emissions")
        -> "co2_mass"
    """

    normalized_query = normalize_query(query)

    # Check longer phrases first to avoid matching
    # a shorter term before a more specific phrase.
    sorted_terms = sorted(
        SEARCH_TERMS.keys(),
        key=len,
        reverse=True
    )

    for term in sorted_terms:
        if term in normalized_query:
            return SEARCH_TERMS[term]

    return None


# --------------------------------------------------
# SEARCH TERM DETECTION FOR MULTIPLE MEASUREMENTS
# --------------------------------------------------

def find_search_fields(query):
    """
    Identify every recognized EPA measurement in a query.

    Example:
        find_search_fields("Compare CO2 and NOx emissions")
        -> ["co2_mass", "nox_mass"]
    """

    normalized_query = normalize_query(query)
    matched_fields = []

    sorted_terms = sorted(
        SEARCH_TERMS.keys(),
        key=len,
        reverse=True
    )

    for term in sorted_terms:
        if term in normalized_query:
            field = SEARCH_TERMS[term]

            if field not in matched_fields:
                matched_fields.append(field)

    return matched_fields


# --------------------------------------------------
# SEARCH HELPERS
# --------------------------------------------------

def get_supported_search_terms():
    """
    Return all supported search phrases.

    Useful for displaying search help on the website.
    """

    return sorted(SEARCH_TERMS.keys())