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
        self.rpi_queue = Queue()
        self.message_queue = Queue()

    def start(self):
        try:
            # establish bluetooth connection with android
            self.android_link.connect()
            self.message_queue.put(Message(destination='android', payload='you are connected!'))

            # create and start processes
            sender_proc = Process(target=self.sender)
            recv_android_proc = Process(target=self.recv_android)
            rpi_action_proc = Process(target=self.rpi_action)
            sender_proc.start()
            recv_android_proc.start()
            rpi_action_proc.start()

        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        self.android_link.disconnect()
        print("[✔] Program exited!")

    def recv_android(self):
        print("[✔] recv_android() started")
        while True:
            message = self.android_link.recv()

            if message is None:
                continue
            else:
                message.strip()

            print(f"Received from android: {message}")

            # actions
            if message == "beep":
                self.rpi_queue.put(message)

    # todo: recv_stm() after implementing STMLink class
    def recv_stm(self):
        print("[✔] recv_stm() started")
        while True:
            message = self.stm_link.recv()

            if message is None:
                continue
            else:
                message.strip()

            print(f"Received from STM: {message}")

    def rpi_action(self):
        while True:
            message = self.rpi_queue.get()

            if message == "beep":
                beep_buzzer(3)

    def sender(self):
        """
        Responsible for retrieving messages from the message queue and sending them over the correct link
        """
        print("[✔] sender() started")

        while True:
            # retrieve message from queue
            message: Message = self.message_queue.get()

            # check destination and send it over the correct link
            if message.destination == "android":
                self.android_link.send(message.json)
            elif message.destination == "stm":
                self.stm_link.send(message.json)


if __name__ == "__main__":
    rpi = RaspberryPi()
    rpi.start()
