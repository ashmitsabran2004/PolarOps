"""Weather retrieval with timeouts and last-successful-reading fallback."""
import json
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen
from django.core.exceptions import ValidationError
from risk.models import WeatherReading

def fetch_open_meteo(expedition, opener=urlopen, timeout=5):
    """Fetch one current weather sample and return normalized operational fields."""
    query=urlencode({'latitude':float(expedition.latitude),'longitude':float(expedition.longitude),'current':'temperature_2m,wind_speed_10m,visibility','daily':'daylight_duration','forecast_days':1,'timezone':'UTC'})
    request_url='https://api.open-meteo.com/v1/forecast?'+query
    try:
        with opener(request_url,timeout=timeout) as response: payload=json.loads(response.read().decode('utf-8'))
        current=payload['current']; daily=payload['daily']
        return {'temperature':round(float(current['temperature_2m']),1),'wind_kph':round(float(current['wind_speed_10m'])),'visibility_km':round(float(current['visibility'])/1000,1),'daylight_hours':round(float(daily['daylight_duration'][0])/3600,1),'payload':payload}
    except (URLError,TimeoutError,OSError,ValueError,KeyError,TypeError,IndexError) as error:
        raise ValidationError('Weather provider is unavailable or returned incomplete data.') from error

def latest_weather(expedition):
    """Return the most recent successful weather sample or None."""
    return WeatherReading.objects.filter(expedition=expedition).order_by('-fetched_at').first()
