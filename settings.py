# contains various configuration settings for the project

# STM32 BOARD SERIAL CONNECTION
# SERIAL_PORT = "/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0"  # nodemcu esp8266 testing board
SERIAL_PORT = "/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0002-if00-port0"  # stm32
BAUD_RATE = 115200

# API DETAILS
API_IP = '192.168.28.15'  # tran's laptop hosting the api
API_PORT = 5000

# ROBOT SETTINGS
OUTDOOR_BIG_TURN = False
