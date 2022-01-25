#!/usr/bin/env python3


# Example from: https://github.com/pybluez/pybluez/blob/master/examples/simple/rfcomm-server.py

import os
import bluetooth

# set discoverable in order for service to be advertisable
os.system("hciconfig hci0 piscan")

server_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
server_sock.bind(("", bluetooth.PORT_ANY))
server_sock.listen(1)

port = server_sock.getsockname()[1]
uuid = "94f39d29-7d6d-437d-973b-fba39e49d4ee"

bluetooth.advertise_service(server_sock, "SampleServer", service_id=uuid,
                            service_classes=[uuid, bluetooth.SERIAL_PORT_CLASS],
                            profiles=[bluetooth.SERIAL_PORT_PROFILE],
                            # protocols=[bluetooth.OBEX_UUID]
                            )

print("Waiting for connection on RFCOMM channel", port)
client_sock, client_info = server_sock.accept()
print("Accepted connection from", client_info)

# send greeting after accepting connection
client_sock.send(b"You are now connected to me!")

try:
    while True:
        data = client_sock.recv(1024)
        if not data:
            print("No data, break")
            break
        print("Received:", data)

        client_sock.send(f"I received '{data.strip().decode()}' from you!\r\n".encode("utf-8"))
except OSError as e:
    print(e)
    pass

print("Disconnected.")

client_sock.close()
server_sock.close()
print("All done.")
