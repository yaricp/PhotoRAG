_UNAVAILABLE_ADDRESS_VALUES = {
    "unknown location",
    "geocoding service unavailable",
}


def normalize_geocoded_address(address: str | None) -> str | None:
    """Return a user-visible address, or None for geocoder failures/placeholders."""
    if address is None:
        return None
    value = str(address).strip()
    if not value:
        return None
    if value.lower() in _UNAVAILABLE_ADDRESS_VALUES:
        return None
    if value.lower().startswith("error:"):
        return None
    return value
