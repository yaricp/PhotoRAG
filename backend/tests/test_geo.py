import pytest
from unittest.mock import MagicMock, patch
from src.geo import GeoEnricher

@pytest.fixture
def geo_enricher():
    return GeoEnricher()

@patch('geopy.geocoders.Nominatim.reverse')
def test_reverse_geocode_success(mock_reverse, geo_enricher):
    # Mock behavior for a successful lookup
    mock_location = MagicMock()
    mock_location.raw = {
        'address': {
            'city': 'Paris',
            'country': 'France'
        },
        'display_name': 'Paris, France'
    }
    mock_reverse.return_value = mock_location
    
    result = geo_enricher.reverse_geocode(48.8584, 2.2945)
    assert result == "Paris, France"

@patch('geopy.geocoders.Nominatim.reverse')
def test_reverse_geocode_fallback(mock_reverse, geo_enricher):
    # Mock behavior for missing specific city/country keys
    mock_location = MagicMock()
    mock_location.raw = {
        'address': {},
        'display_name': 'Eiffel Tower, Paris'
    }
    mock_reverse.return_value = mock_location
    
    result = geo_enricher.reverse_geocode(48.8584, 2.2945)
    assert result == "Eiffel Tower, Paris"

@patch('geopy.geocoders.Nominatim.reverse')
def test_reverse_geocode_timeout(mock_reverse, geo_enricher):
    from geopy.exc import GeocoderTimedOut
    mock_reverse.side_effect = GeocoderTimedOut("Timeout")
    
    result = geo_enricher.reverse_geocode(48.8, 2.2)
    assert "Unavailable" in result
