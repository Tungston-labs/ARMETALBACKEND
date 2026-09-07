# utils.py
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

def get_location_name_sync(latitude, longitude):
    geolocator = Nominatim(user_agent="armetal-tracker-app")
    try:
        location = geolocator.reverse((latitude, longitude), exactly_one=True, timeout=10)
        if location and location.address:
            return location.address
        else:
            print(f"No address found for {latitude}, {longitude}")
            return f"Lat: {latitude}, Lon: {longitude}"
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f"Geocoder error: {e}")
        return f"Lat: {latitude}, Lon: {longitude}"
    except Exception as e:
        print(f"Unexpected error: {e}")
        return f"Lat: {latitude}, Lon: {longitude}"
