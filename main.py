#!/usr/bin/env python3

import io
import json
import time
from multiprocessing import Process, Queue, Lock, Value, Event

import picamera
import requests

from communication.android import AndroidLink, AndroidMessage
from communication.stm32 import STMLink
from logger import prepare_logger
from settings import API_IP, API_PORT


class PiAction:
    """
    Represents an action that the Pi is responsible for:
    - Changing the robot's mode (manual/path)
    - Requesting a path from the API
    - Snapping an image and requesting the image-rec result from the API
    """

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
        # prepare logger
        self.logger = prepare_logger()

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

            self.logger.info("Child Processes started")

        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        self.android_link.disconnect()
        self.stm_link.disconnect()
        self.logger.info("Program exited!")

    def recv_android(self) -> None:
        while True:
            msg_str = self.android_link.recv()

            # if an error occurred in recv()
            if msg_str is None:
                continue

            message = json.loads(msg_str)

            # change mode command
            if message['cat'] == "mode":
                self.rpi_action_queue.put(PiAction(**message))
                self.logger.debug(f"Change mode PiAction added to queue: {message}")

            # manual movement commands
            elif message['cat'] == "manual":
                if self.robot_mode.value == 0:  # robot must be in manual mode
                    self.command_queue.put(message['value'])
                    self.logger.debug(f"Manual Movement added to command queue: {message['value']}")
                else:
                    self.android_outgoing_queue.put(
                        AndroidMessage(cat="error", value="Manual movement not allowed in Path mode."))
                    self.logger.warning("Manual movement not allowed in Path mode.")

            # set obstacles
            elif message['cat'] == "obstacles":
                if self.robot_mode.value == 1:  # robot must be in path mode
                    self.rpi_action_queue.put(PiAction(**message))
                    self.logger.debug(f"Set obstacles PiAction added to queue: {message}")
                else:
                    self.android_outgoing_queue.put(
                        AndroidMessage(cat="error", value="Robot must be in Path mode to set obstacles."))
                    self.logger.warning("Robot must be in Path mode to set obstacles.")

            # commencing path following
            elif message['cat'] == "control":
                if self.robot_mode.value == 1:  # robot must be in path mode
                    if message['value'] == "start":
                        if not self.command_queue.empty():
                            self.unpause.set()
                            self.logger.info("Start command received, starting robot on path!")
                        else:
                            self.logger.warning("The command queue is empty, please set obstacles.")
                            self.android_outgoing_queue.put(
                                AndroidMessage(cat="error", value="Command queue is empty, did you set obstacles?"))
                else:
                    self.android_outgoing_queue.put(
                        AndroidMessage(cat="error", value="Robot must be in Path mode to start robot on path."))
                    self.logger.warning("Robot must be in Path mode to start robot on path.")

            # around obstacle
            elif message['cat'] == "single-obstacle":
                if self.robot_mode.value == 1:  # robot must be in path mode
                    self.rpi_action_queue.put(PiAction(**message))
                    self.logger.debug(f"Single-obstacle PiAction added to queue: {message}")
                else:
                    self.android_outgoing_queue.put(
                        AndroidMessage(cat="error", value="Robot must be in Path mode to set single obstacle."))
                    self.logger.warning("Robot must be in Path mode to set single obstacle.")

    def recv_stm(self) -> None:
        """
        Receive acknowledgement messages from STM32, and release the movement lock
        """
        while True:
            message = self.stm_link.recv()

            if message.startswith(("ACK", "OK")):
                # release movement lock
                self.movement_lock.release()
                self.logger.debug("ACK from STM32 received, movement lock released.")

                # if in path mode, get new location and notify android
                if self.robot_mode.value == 1:
                    temp = self.path_queue.get()
                    location = {
                        "x": temp['x'],
                        "y": temp['y'],
                        "d": temp['d'],
                    }
                    self.android_outgoing_queue.put(AndroidMessage(cat='location', value=location))
            else:
                raise Exception(f"Unknown message from STM32: {message}")

    def android_sender(self) -> None:
        """
        Responsible for retrieving messages from the outgoing message queue and sending them over the Android Link
        """
        while True:
            # retrieve from queue
            message: AndroidMessage = self.android_outgoing_queue.get()

            # send it over the android link
            self.android_link.send(message)

    def command_follower(self) -> None:
        while True:
            # retrieve next movement command
            command = self.command_queue.get()

            # wait for unpause event to be true
            self.unpause.wait()

            # acquire lock first (needed for both moving, and snapping pictures)
            self.movement_lock.acquire()

            # path movement commands
            if command.startswith(("FW", "BW", "FL", "FR", "BL", "BR", "TL", "TR", "A", "C", "STOP")):
                self.stm_link.send(command)

            # snap command, add this task to queue
            elif command.startswith("SNAP"):
                obstacle_id = command.replace("SNAP", "")
                self.rpi_action_queue.put(PiAction(cat="snap", value=obstacle_id))

            # end of path
            elif command == "FIN":
                # clear the unpause event (no new command will be retrieved from queue)
                self.unpause.clear()
                self.movement_lock.release()
                self.logger.info("Commands queue finished.")
                self.android_outgoing_queue.put(AndroidMessage(cat="info", value="Commands queue finished."))
            else:
                raise Exception(f"Unknown command: {command}")

    def rpi_action(self):
        while True:
            action: PiAction = self.rpi_action_queue.get()
            self.logger.debug(f"PiAction retrieved from queue: {action.cat} {action.value}")

            if action.cat == "mode":
                self.change_mode(action.value)
            elif action.cat == "obstacles":
                self.request_algo(action.value)
            elif action.cat == "snap":
                self.snap_and_rec(obstacle_id=action.value)
            elif action.cat == "single-obstacle":
                self.request_algo(action.value, around=True)

    def snap_and_rec(self, obstacle_id: str) -> None:
        """
        RPi snaps an image and calls the API for image-rec.
        The response is then forwarded back to the android
        :param obstacle_id: the current obstacle ID
        """

        # notify android
        self.logger.info(f"Capturing image for obstacle id: {obstacle_id}")
        self.android_outgoing_queue.put(
            AndroidMessage(cat="info", value=f"Capturing image for obstacle id: {obstacle_id}"))

        # capture an image
        stream = io.BytesIO()
        with picamera.PiCamera() as camera:
            camera.start_preview()
            time.sleep(1)
            camera.capture(stream, format='jpeg')

        # notify android
        self.android_outgoing_queue.put(
            AndroidMessage(cat="info", value="Image captured. Calling image-rec api..."))
        self.logger.info("Image captured. Calling image-rec api...")

        # call image-rec API endpoint
        self.logger.debug("Requesting from image API")
        url = f"http://{API_IP}:{API_PORT}/image"
        filename = f"{obstacle_id}_{int(time.time())}.jpeg"
        image_data = stream.getvalue()
        response = requests.post(url, files={"file": (filename, image_data)})

        if response.status_code != 200:
            raise Exception("Something went wrong when requesting path from image-rec API.")

        results = json.loads(response.content)

        if results.get("stop"):
            self.unpause.clear()
            while not self.command_queue.empty():
                self.command_queue.get()
            self.logger.info("Found non-bullseye face, remaining commands and path cleared.")
            self.android_outgoing_queue.put(
                AndroidMessage(cat="info", value="Found non-bullseye face, remaining commands and path cleared."))

        self.logger.info(f"Image recognition results: {results}")

        # notify android
        self.android_outgoing_queue.put(AndroidMessage(cat="image-rec", value=results))

        # release lock so that bot can continue moving
        self.movement_lock.release()

    def request_algo(self, data: str, around: bool = False):
        """
        Requests for a series of commands and the path from the algo API
        The received commands and path are then queued in the respective queues
        If around=true, will call the /navigate endpoint instead, else /path is used
        """
        if not around:
            url = f"http://{API_IP}:{API_PORT}/path"
        else:
            url = f"http://{API_IP}:{API_PORT}/navigate"

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

        self.logger.info("Commands and path received Algo API. Robot is ready to move.")

        # notify android
        self.android_outgoing_queue.put(
            AndroidMessage(cat="info", value="Commands and path received Algo API. Robot is ready to move."))

    def change_mode(self, new_mode):
        # if robot already in correct mode
        if new_mode == "manual" and self.robot_mode.value == 0:
            self.android_outgoing_queue.put(AndroidMessage(cat='error', value='Robot already in Manual mode.'))
            self.logger.warning("Robot already in Manual mode.")
        elif new_mode == "path" and self.robot_mode.value == 1:
            self.android_outgoing_queue.put(AndroidMessage(cat='error', value='Robot already in Path mode.'))
            self.logger.warninig("Robot already in Path mode.")
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
            self.logger.info(f"Robot is now in {new_mode.title()} mode.")

    def clear_queues(self):
        while not self.command_queue.empty():
            self.command_queue.get()
        while not self.path_queue.empty():
            self.path_queue.get()


if __name__ == "__main__":
    rpi = RaspberryPi()
    rpi.start()
