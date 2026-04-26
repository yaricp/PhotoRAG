from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import time

class GeoEnricher:
    def __init__(self, user_agent="Photo_Describer_App"):
        self.geolocator = Nominatim(user_agent=user_agent)

    def reverse_geocode(self, latitude: float, longitude: float) -> str:
        """
        Converts coordinates to a human-readable address.
        Returns 'City, Country' or a full address if possible.
        """
        try:
            # Respect OSM usage policy (max 1 req/sec)
            location = self.geolocator.reverse(f"{latitude}, {longitude}", language='en')
            if location and 'address' in location.raw:
                address = location.raw['address']
                city = address.get('city') or address.get('town') or address.get('village', '')
                country = address.get('country', '')
                
                if city and country:
                    return f"{city}, {country}"
                return location.address
            return "Unknown Location"
            
        except (GeocoderTimedOut, GeocoderServiceError):
            return "Geocoding Service Unavailable"
        except Exception as e:
            print(f"Geo Error: {e}")
            return f"Error: {latitude}, {longitude}"
