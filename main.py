#!/usr/bin/env python3


from multiprocessing import Process, Queue

from misc.buzzer import beep_buzzer
from communication.stm32 import STMLink
from communication.android import AndroidLink
from communication.communicator import Message


class RaspberryPi:
    def __init__(self):
        # communication links
        self.android_link = AndroidLink()
        self.stm_link = STMLink()

        # queues
        self.outgoing_message_queue = Queue()
        self.rpi_action_queue = Queue()

    def start(self):
        try:
            # establish bluetooth connection with android
            self.android_link.connect()
            self.outgoing_message_queue.put(Message(destination='android', payload='You are connected to the RPi!'))

            # establish connection with STM32
            self.stm_link.connect()

            # define processes
            actions_proc = Process(target=self.rpi_action)
            sender_proc = Process(target=self.sender)
            recv_android_proc = Process(target=self.recv_android)
            recv_stm32_proc = Process(target=self.recv_stm)

            # start processes
            actions_proc.start()
            sender_proc.start()
            recv_android_proc.start()
            recv_stm32_proc.start()

        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        self.android_link.disconnect()
        self.stm_link.disconnect()
        print("[✔] Program exited!")

    def recv_android(self):
        print("[✔] recv_android() started")
        while True:
            message = self.android_link.recv()

            if message is None: continue

            print(f"Received from android: {message}")

            # forward movement commands to STM32
            if message.startswith(('F', 'B', 'T')):
                self.outgoing_message_queue.put(Message(destination='stm', payload=message))
            # put rpi actions to queue
            elif message in ["RPI_SNAP", "RPI_BEEP"]:
                self.rpi_action_queue.put(message)

    def recv_stm(self):
        print("[✔] recv_stm() started")
        while True:
            message = self.stm_link.recv()

            print(f"Received from STM: {message}")

            # forward messages from STM to Android
            self.outgoing_message_queue.put(Message(destination='android', payload=message))

    def sender(self):
        """
        Responsible for retrieving messages from the message queue and sending them over the correct link
        """
        print("[✔] sender() started")

        while True:
            # retrieve outgoing messages from queue
            message: Message = self.outgoing_message_queue.get()

            # check destination and send it over the correct link
            if message.destination == "android":
                self.android_link.send(message.payload)
            elif message.destination == "stm":
                self.stm_link.send(message.payload)

    def rpi_action(self):
        print("[✔] rpi_action() started")

        while True:
            # retrieve actions from queue
            action = self.rpi_action_queue.get()

            if action == "RPI_SNAP":
                print("Snapping picture..")
                self.outgoing_message_queue.put(Message(destination='android', payload='OK'))
            elif action == "RPI_BEEP":
                print("BEEPING")
                beep_buzzer(3)


if __name__ == "__main__":
    rpi = RaspberryPi()
    rpi.start()
