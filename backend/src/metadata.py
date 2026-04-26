import exifread
from datetime import datetime

def get_exif_data(filepath: str) -> dict:
    try:
        with open(filepath, 'rb') as f:
            tags = exifread.process_file(f, details=False)
            
            # Extract Capture Time
            exif_date_str = str(tags.get('Image DateTime', 'Unknown'))
            captured_at_obj = None
            if exif_date_str != 'Unknown':
                try:
                    # Standard EXIF date format: YYYY:MM:DD HH:MM:SS
                    captured_at_obj = datetime.strptime(exif_date_str, '%Y:%m:%d %H:%M:%S')
                except ValueError:
                    pass

            return {
                "model": str(tags.get('Image Model', 'Unknown')),
                # Store the datetime object for the RDBM column
                "captured_at_obj": captured_at_obj,
                # Store the string version for the JSON blob
                "captured_at_str": exif_date_str,
                "gps_lat": str(tags.get('GPS GPSLatitude', 'None')),
                "gps_lon": str(tags.get('GPS GPSLongitude', 'None')),
                "all_tags": {k: str(v) for k, v in tags.items()}
            }
    except Exception:
        return {
            "model": "Unknown",
            "captured_at_obj": None,
            "captured_at_str": "Unknown",
            "gps_lat": 'None',
            "gps_lon": 'None',
            "all_tags": {}
        }
