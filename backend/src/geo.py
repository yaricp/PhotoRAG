import time
from loguru import logger
from PIL import ExifTags
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

from src.utils import make_json_safe



class GeoEnricher:
    def __init__(self, user_agent="Photo_Describer_App"):
        self.geolocator = Nominatim(user_agent=user_agent)
        self.lat = None
        self.lon = None
        self.address = None

    def dms_to_decimal(self, dms, ref):
        try:
            degrees, minutes, seconds = dms
            decimal = degrees + minutes / 60 + seconds / 3600

            if ref in ["S", "W"]:
                decimal = -decimal

            return decimal

        except Exception as err:
            logger.warning(f"Failed to convert DMS: {err}")
            return None

    def extract_gps(self, exif_raw):
        try:
            gps = exif_raw.get("GPSInfo")
            if not gps:
                return None

            gps_data = {}
            for key in gps:
                name = ExifTags.GPSTAGS.get(key, key)
                gps_data[name] = make_json_safe(gps[key])

            logger.info(f"GPS data extracted: {gps_data}")
            self.lat = self.dms_to_decimal(
                gps_data.get("GPSLatitude"), 
                gps_data.get("GPSLatitudeRef")
            )
            self.lon = self.dms_to_decimal(
                gps_data.get("GPSLongitude"),
                gps_data.get("GPSLongitudeRef")
            )

            logger.info(f"GPS data extracted: {self.lat}, {self.lon}")
            return gps_data

        except Exception as err:
            logger.exception(f"Failed to extract GPS: {err}")
            return None

    def reverse_geocode(self, latitude: float, longitude: float) -> str:
        """
        Converts coordinates to a human-readable address.
        Returns 'City, Country' or a full address if possible.
        """
        try:
            # Respect OSM usage policy (max 1 req/sec)
            location = self.geolocator.reverse(f"{latitude}, {longitude}", language='en')
            
            if location and 'display_name' in location.raw:
                logger.info(f"Location: {location.raw['display_name']}")
                return location.raw['display_name']
                # address = location.raw['address']
                # city = address.get('city') or address.get('town') or address.get('village', '')
                # country = address.get('country', '')
                
                # logger.info(f"City: {city}, Country: {country}")
                # if city and country:
                #     return f"{city}, {country}"
                # logger.info(f"Location: {location.address}")
                # return location.address
            logger.info("Unknown Location")
            return "Unknown Location"
            
        except (GeocoderTimedOut, GeocoderServiceError):
            logger.error("Geocoding Service Unavailable")
            return "Geocoding Service Unavailable"
        except Exception as e:
            logger.error(f"Geo Error: {e}")
            return f"Error: {latitude}, {longitude}"

    def geocode_photo(self, exif_raw):
        self.extract_gps(exif_raw)
        if self.lat and self.lon:
            self.address = self.reverse_geocode(self.lat, self.lon)
        else:
            self.address = None

        return {
            "latitude": self.lat,
            "longitude": self.lon,
            "address": self.address
        }
        