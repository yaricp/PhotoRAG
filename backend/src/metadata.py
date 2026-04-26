import exifread

def get_exif_data(filepath: str) -> dict:
    try:
        with open(filepath, 'rb') as f:
            tags = exifread.process_file(f, details=False)
            return {
                "model": str(tags.get('Image Model', 'Unknown')),
                "datetime": str(tags.get('Image DateTime', 'Unknown')),
                "gps_lat": tags.get('GPS GPSLatitude'),
                "gps_lon": tags.get('GPS GPSLongitude')
            }
    except Exception:
        return {
            "model": "Unknown",
            "datetime": "Unknown",
            "gps_lat": None,
            "gps_lon": None
        }
