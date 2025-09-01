# WeatherBot-Persian

**WeatherBot-Persian** is a Persian desktop bot that displays the **current weather**, **daily forecast**, and **Air Quality Index (AQI)**. It has **Dark/Light/Auto themes**, can automatically detect your city, and keeps track of **favorites** and **search history**.

## Requirements

- Windows 10/11  
- Python 3.10 or newer  
- Stable Internet connection

## Check Python Installation

1. Open PowerShell in Windows.  
2. Type:
```bash
python --version
```
3. If a version appears (e.g., 3.12.x), Python is installed.  
   If you get an error, download the latest version from [python.org](https://www.python.org) and check "Add python.exe to PATH" during installation.

## Setup Project Folder

1. Create a folder, for example:
```text
C:\Users\YourName\Desktop\weather-app
```
2. Place the program file inside:
```text
weather_bot_pyside6_v700.py
```

## Install Required Libraries

Open cmd in the project folder and run:
```bash
python -m pip install --upgrade pip
pip install PySide6 requests
```
> If your internet is slow, installation may take a few minutes. Be patient.

## Running the Program

While in the project folder, run:
```bash
python .\weather_bot_pyside6_v700.py
```
On first run, Windows may ask for network access. Click **Allow access**.

## Quick Guide

- **Search:** Type a city and press Enter or click "Search".  
- **Weather Card:** Shows emoji, current temperature, description, local time, feels-like temp, humidity, pressure, wind speed/direction, sunrise/sunset, and AQI.  
- **Daily Forecast:** 5 cards showing min/max temperatures and representative icons.  
- **Favorites:** Click " Add to favorites"; each favorite has a "Remove" button.  
- **History:** Access the last 10 searches via the "History" menu; you can also clear history.  
- **Shortcuts:** Ctrl+F (search), Ctrl+R (refresh), Ctrl+S (settings).  
- **Auto Theme:** Switches light/dark based on day/night in that city.

## Tips

- For limited internet, set the auto-update interval to 10 or 30 minutes in Settings.  
- Increase cache duration (e.g., 30–60 minutes) to reduce requests.

## Reset Program

1. Close the app.  
2. Delete this folder:
```text
C:\Users\YourName\.weatherapp_pyside6
```
> This removes `settings.json`, `weather_cache.json`, and `history.json`, restoring the program to its initial state.

## FAQ

- **How to change temperature/wind units?** From Settings.  
- **How to quickly open a favorite city?** Add it to Favorites.  
- **Does the program switch themes automatically?** Yes, if "Auto" is selected, it changes based on day/night in that city.
