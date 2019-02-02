import json
import datetime
from dateutil import tz

from kivy.app import App
from kivy.lang import Builder
from kivy.properties import (ObjectProperty, ListProperty, StringProperty, NumericProperty)

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.listview import ListItemButton
from kivy.uix.modalview import ModalView
from kivy.uix.recycleview import RecycleView

from kivy.clock import Clock
from kivy.factory import Factory
from kivy.storage.jsonstore import JsonStore
from kivy.network.urlrequest import UrlRequest


def weatherAPI(call):
    apiUrl = "http://api.openweathermap.org/data/2.5/"
    apiKey = "c4de46d5d450961a51a025fc4c595bf4"
    return apiUrl + call + "&APPID=" + apiKey

def weatherIMG(img):
    apiUrl ="http://openweathermap.org/img/w/"
    return apiUrl + img

def locations_args_converter(index, data_item):
    city, country = data_item
    return {'location': (city, country)}

def degrees_to_cardinal(d):
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    ix = ix = int((d)/22.5)
    return dirs[ix % 16]

class LocationButton(ListItemButton):
    location = ListProperty()

class AddAboutForm(ModalView):
    close_button = ObjectProperty()

class AddLocationForm(ModalView):
    search_input = ObjectProperty()
    search_results = ObjectProperty()
  
    def search_location(self):
        search_template = weatherAPI("find?q={}&type=like")
        search_url = search_template.format(self.search_input.text)
        request = UrlRequest(search_url, self.found_location)

    def found_location(self, request, data):
        data = json.loads(data.decode()) if not isinstance(data, dict) else data
        cities = [(d['name'], d['sys']['country']) for d in data['list']]
        self.search_results.item_strings = cities
        del self.search_results.adapter.data[:]

        self.search_results.adapter.data.extend(cities)
        self.search_results._trigger_reset_populate()


class CurrentWeather(BoxLayout):
    location = ListProperty(['New York', 'US'])
    conditions = StringProperty()
    conditions_image = StringProperty()
    temp = NumericProperty()
    temp_min = NumericProperty()
    temp_max = NumericProperty()
    pressure = NumericProperty()
    humidity = NumericProperty()
    sunrise = StringProperty()
    sunset = StringProperty()

    def update_weather(self):
        config = WeatherApp.get_running_app().config
        temp_type = config.getdefault("General", "temp_type", "metric").lower()
        weather_template = weatherAPI("weather?q={},{}&units={}")
        weather_url = weather_template.format(self.location[0], self.location[1], temp_type)
        request = UrlRequest(weather_url, self.weather_retrieved)

    def weather_retrieved(self, request, result):
        data = json.loads(result.decode()) if not isinstance(result, dict) else result
        self.conditions = data['weather'][0]['description']
        self.conditions_image = weatherIMG("{}.png").format(data['weather'][0]['icon'])
        self.temp = data['main']['temp']
        self.temp_min = data['main']['temp_min']
        self.temp_max = data['main']['temp_max']
        self.pressure =  data['main']['pressure']
        self.humidity =  data['main']['humidity']
        self.sunrise = datetime.datetime.fromtimestamp(data['sys']['sunrise']).strftime("%H:%M") 
        self.sunset = datetime.datetime.fromtimestamp(data['sys']['sunset']).strftime("%H:%M") 


class Forecast(BoxLayout):
    location = ListProperty(['New York', 'US'])
    forecast_container = ObjectProperty()

    def update_weather(self):
        config = WeatherApp.get_running_app().config
        temp_type = config.getdefault("General", "temp_type", "metric").lower()
        weather_template = weatherAPI("forecast?q={},{}&units={}&cnt=5")
        weather_url = weather_template.format(self.location[0], self.location[1], temp_type)
        request = UrlRequest(weather_url, self.weather_retrieved)

    def weather_retrieved(self, request, data):
        data = json.loads(data.decode()) if not isinstance(data, dict) else data
        self.forecast_container.clear_widgets()
        to_zone = tz.tzlocal()
        from_zone = tz.tzutc()
        for day in data['list']:
            label = Factory.ForecastLabel()
            utc = datetime.datetime.fromtimestamp(day['dt']).replace(tzinfo=from_zone).astimezone(to_zone)
            label.date = utc.strftime("%a %d. %H:%M") 
            label.conditions = day['weather'][0]['description']
            label.conditions_image = weatherIMG("{}.png").format(day['weather'][0]['icon'])
            label.temp = day['main']['temp']
            label.pressure = day['main']['pressure']
            label.humidity = day['main']['humidity']
            label.wind_speed = day['wind']['speed']
            label.wind_directon = degrees_to_cardinal(day['wind']['deg'])
            self.forecast_container.add_widget(label)


class WeatherRoot(BoxLayout):
    carousel = ObjectProperty()
    current_weather = ObjectProperty()
    forecast = ObjectProperty()
    locations = ObjectProperty()
    add_location_form = ObjectProperty()

    def __init__(self, **kwargs):
        super(WeatherRoot, self).__init__(**kwargs)
        self.store = JsonStore("weather_store.json")
        if self.store.exists('locations'):
            locations = self.store.get('locations')
            self.locations.locations_list.adapter.data.extend(locations['locations'])
            current_location = locations["current_location"]
            self.show_current_weather(current_location)

    def show_current_weather(self, location):
        if location not in self.locations.locations_list.adapter.data:
            self.locations.locations_list.adapter.data.append(location)
            self.locations.locations_list._trigger_reset_populate()
            self.store.put("locations",
                locations=list(self.locations.locations_list.adapter.data),
                current_location=location)

        self.current_weather.location = location
        self.current_weather.update_weather()
        self.forecast.location = location
        self.forecast.update_weather()

        self.carousel.load_slide(self.current_weather)
        if self.add_location_form is not None:
            self.add_location_form.dismiss()

    def show_add_location_form(self):
        self.add_location_form = AddLocationForm()
        self.add_location_form.open()

    def show_about_form(self):
        self.add_about_form = AddAboutForm()
        self.add_about_form.open()


class WeatherApp(App):
    def build_config(self, config):
        config.setdefaults('General', {'temp_type': "Metric"})

    def build_settings(self, settings):
        settings.add_json_panel("Weather Settings", self.config, data="""
            [
                {   
                    "type": "options",
                    "title": "Temperature System",
                    "section": "General",
                    "key": "temp_type",
                    "options": ["Metric", "Imperial"]
                }
            ]"""
            )

    def on_config_change(self, config, section, key, value):
        if config is self.config and key == "temp_type":
            try:
                self.root.current_weather.update_weather()
                self.root.forecast.update_weather()
            except AttributeError:
                pass

if __name__ == '__main__':
	WeatherApp().run()