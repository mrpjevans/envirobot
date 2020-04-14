import logging
import time
import os
import requests

from dotenv import load_dotenv
load_dotenv()

#
# Deps for sensors
#

# I2C
try:
    from smbus2 import SMBus
except ImportError:
    from smbus import SMBus

# Temperature
from bme280 import BME280

# Gas
from enviroplus import gas

# Light
try:
    # Transitional fix for breaking change in LTR559
    from ltr559 import LTR559
    ltr559 = LTR559()
except ImportError:
    import ltr559

# Set up logging
logging.basicConfig(
    format = '%(asctime)s %(levelname)-8s %(message)s',
    level = logging.INFO,
    datefmt = '%Y-%m-%d %H:%M:%S')

# Set up sensors
bus = SMBus(1)
bme280 = BME280(i2c_dev = bus)

# Settings
cpu_factor = float(os.getenv("ENVIROPLUS_TEMP_FACTOR"))
interval = float(os.getenv("ENVIROPLUS_READ_INTERVAL"))
endpoint = ("http://{}:{}/write?db={}").format(os.getenv("INFLUXDB_HOST"), os.getenv("INFLUXDB_PORT"), os.getenv("INFLUXDB_DB"))

# Get the temperature of the CPU for compensation
def get_cpu_temperature():
    with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
        temp = f.read()
        temp = int(temp) / 1000.0
    return temp

# Get some initial readings for CPU temperature
cpu_temps = [get_cpu_temperature()] * 5

# Main loop
while True:
    
    # Temperature
    cpu_temp = get_cpu_temperature()
    cpu_temps = cpu_temps[1:] + [cpu_temp]
    avg_cpu_temp = sum(cpu_temps) / float(len(cpu_temps))
    raw_temp = bme280.get_temperature()
    comp_temp = raw_temp - ((avg_cpu_temp - raw_temp) / cpu_factor)
    logging.info("T:{:04.1f}".format(comp_temp))

    # Pressure
    pressure = bme280.get_pressure()
    logging.info("P:{:05.1f}".format(pressure))

    # Humidity
    humidity = bme280.get_humidity()
    logging.info("H:{:05.1f}".format(humidity))

    # Light
    lux = ltr559.get_lux()

    # Create payload
    payload = ("{} temp={:04.1f},lux={:05.02f},pressure={:05.02f},humidity={:05.02f}").format(os.getenv("INFLUXDB_MEASUREMENT"), comp_temp, lux, pressure, humidity)
    logging.info(payload)

    # Send to InfluxDB endpoint
    response = requests.post(endpoint, payload)
    logging.info(response)
    
    logging.info("Waiting {} seconds".format(interval))
    time.sleep(interval)
