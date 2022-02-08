#!/usr/bin/env python3
import json
import time
from multiprocessing import Process, Queue, Lock, Value, Event

import requests

from communication.stm32 import STMLink
from communication.android import AndroidLink
from communication.communicator import AndroidMessage
from settings import API_IP, API_PORT


class PiAction:
    def __init__(self, cat, value):
        self._cat = cat
        self._value = value

    @property
    def cat(self):
        return self._cat

    @property
    def value(self):
        return self._value


class RaspberryPi:
    def __init__(self):
        # 0: manual, 1: path (default: 1)
        self.robot_mode = Value('i', 1)

        # communication links
        self.android_link = AndroidLink()
        self.stm_link = STMLink()

        # movement lock
        # commands can only be sent to stm32 if this lock is released
        self.movement_lock = Lock()

        # pause execution of commands queue
        # used to wait for the 'start' command in path mode before moving robot
        self.unpause = Event()

        # queues
        self.android_outgoing_queue = Queue()
        self.rpi_action_queue = Queue()
        self.command_queue = Queue()
        self.path_queue = Queue()

    def start(self):
        try:
            # establish bluetooth connection with Android
            self.android_link.connect()
            self.android_outgoing_queue.put(AndroidMessage(cat='status', value='You are connected to the RPi!'))

            # establish connection with STM32
            self.stm_link.connect()

            # todo: ping test to API

            # define processes
            proc_recv_android = Process(target=self.recv_android)
            proc_recv_stm32 = Process(target=self.recv_stm)
            proc_android_sender = Process(target=self.android_sender)
            proc_command_follower = Process(target=self.command_follower)
            proc_rpi_action = Process(target=self.rpi_action)

            # start processes
            proc_recv_android.start()
            proc_recv_stm32.start()
            proc_android_sender.start()
            proc_command_follower.start()
            proc_rpi_action.start()

            print("[✔] Child Processes started")

        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        self.android_link.disconnect()
        self.stm_link.disconnect()
        print("[✔] Program exited!")

    def recv_android(self):
        while True:
            msg_str = self.android_link.recv()

            # todo: check if this is needed
            if msg_str is None:
                continue

            print(f"Received from android: {msg_str}")

            message = json.loads(msg_str)

            # change mode command
            if message['cat'] == "mode":
                self.rpi_action_queue.put(PiAction(**message))

            # manual movement commands
            elif message['cat'] == "manual":
                if self.robot_mode.value == 0:  # robot must be in manual mode
                    self.command_queue.put(message['value'])
                    print(f"Manual movement command added to command queue: {message['value']}")
                else:
                    self.android_outgoing_queue.put(
                        AndroidMessage(cat="error", value="Manual movement not allowed in Path mode."))
                    print("Manual movement not allowed in Path mode.")

            # set obstacles
            elif message['cat'] == "obstacles":
                if self.robot_mode.value == 1:  # robot must be in path mode
                    self.rpi_action_queue.put(PiAction(**message))
                    print("Added to PiAction queue: Set obstacles")
                else:
                    self.android_outgoing_queue.put(
                        AndroidMessage(cat="error", value="Robot must be in Path mode to set obstacles."))
                    print("Robot must be in Path mode to set obstacles.")

            # commencing path following
            elif message['cat'] == "control":
                if self.robot_mode.value == 1:  # robot must be in path mode
                    if message['value'] == "start":
                        if not self.command_queue.empty():
                            self.unpause.set()
                            print("Start received, unpause event set!")
                        else:
                            print("Command queue is empty, did you set obstacles?")
                            self.android_outgoing_queue.put(
                                AndroidMessage(cat="error", value="Command queue is empty, did you set obstacles?"))
                else:
                    self.android_outgoing_queue.put(
                        AndroidMessage(cat="error", value="Robot must be in Path mode to start robot on path."))
                    print("Robot must be in Path mode to start robot on path.")

    def recv_stm(self):
        """
        Receive acknowledgement messages from STM32, and release the movement lock
        """
        while True:
            message = self.stm_link.recv()

            print(f"Received from STM: {message}")

            if message == "OK":
                # release movement lock
                self.movement_lock.release()
                print("Ack received, movement lock released.")

                # if in path mode, get new location and notify android
                if self.robot_mode.value == 1:
                    temp = self.path_queue.get()
                    location = [temp['x'], temp['y'], temp['d']]
                    self.android_outgoing_queue.put(AndroidMessage(cat='location', value=location))

    def android_sender(self):
        """
        Responsible for retrieving messages from the message queue and sending them over the correct link
        """
        while True:
            # retrieve outgoing messages from queue
            message = self.android_outgoing_queue.get()

            # send it over the android link
            self.android_link.send(message)

    def command_follower(self):
        while True:
            # retrieve next movement command
            command = self.command_queue.get()

            # wait for unpause event to be true
            self.unpause.wait()

            # acquire lock first (needed for both moving, and snapping pictures)
            self.movement_lock.acquire()

            time.sleep(0.5)

            # path movement commands
            if command.startswith(("FW", "BW", "FL", "FR", "BL", "BR", "TL", "TR", "STOP")):
                self.stm_link.send(command)

            # snap command, add this task to queue
            elif command.startswith("SNAP"):
                obstacle_id = command.replace("SNAP", "")
                self.rpi_action_queue.put(PiAction(cat="snap", value=obstacle_id))

            # end of path
            elif command == "END":
                # clear the unpause event (no new command will be retrieved from queue)
                self.unpause.clear()

            else:
                raise Exception(f"Unknown command: {command}")

    def rpi_action(self):
        while True:
            action: PiAction = self.rpi_action_queue.get()
            print(f"PiAction retrieved from queue: {action.cat} {action.value}")

            if action.cat == "mode":
                self.change_mode(action.value)
            elif action.cat == "obstacles":
                self.request_algo(action.value)
            elif action.cat == "snap":
                self.snap_image(obstacle_id=action.value)
            elif action.cat == "image-rec":
                self.rec_image(**action.value)

    def snap_image(self, obstacle_id):
        # take pic
        print("Snapping picture... 3seconds")
        time.sleep(3)
        image_data = "encoded image"

        # release lock so that bot can continue moving
        self.movement_lock.release()

        # add rpi action to call image rec
        self.rpi_action_queue.put(
            PiAction(cat="image-rec", value={"obstacle_id": obstacle_id, "image_data": image_data}))

    def request_algo(self, data: str):
        url = f"http://{API_IP}:{API_PORT}/path"
        # headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
        # data = '{"obstacles" : [{"x" : 5, "y" : 10, "id": 1, "d" : 2} ]}'
        response = requests.post(url, json=data)

        if response.status_code != 200:
            raise Exception("Something went wrong when requesting path from Algo API.")

        # parse response
        data = json.loads(response.content)['data']

        # put commands and paths into queues
        self.clear_queues()
        for c in data['commands']:
            self.command_queue.put(c)
        for p in data['path'][1:]:  # ignore first element as it is the starting position of the robot
            self.path_queue.put(p)

        print("Received commands and path from Algo API. Robot is ready to move.")

    def rec_image(self, obstacle_id, image_data):
        # call image-rec api
        # add response to android outgoing queue
        pass

    def change_mode(self, new_mode):
        # if robot already in correct mode
        if new_mode == "manual" and self.robot_mode.value == 0:
            self.android_outgoing_queue.put(AndroidMessage(cat='error', value='Robot already in Manual mode.'))
            print("[!] Robot already in Manual mode.")
        elif new_mode == "path" and self.robot_mode.value == 1:
            self.android_outgoing_queue.put(AndroidMessage(cat='error', value='Robot already in Path mode.'))
            print("[!] Robot already in Path mode.")
        else:
            # change robot mode
            self.robot_mode.value = 0 if new_mode == 'manual' else 1

            # clear command, path queues
            self.clear_queues()

            # set unpause event, so that robot can freely move
            if new_mode == "manual":
                self.unpause.set()
            else:
                self.unpause.clear()

            # notify android
            self.android_outgoing_queue.put(
                AndroidMessage(cat='info', value=f'Robot is now in {new_mode.title()} mode.'))
            print(f"[✔] Robot is now in {new_mode.title()} mode.")

    def clear_queues(self):
        while not self.command_queue.empty():
            self.command_queue.get()
        while not self.path_queue.empty():
            self.path_queue.get()


if __name__ == "__main__":
    rpi = RaspberryPi()
    rpi.start()
