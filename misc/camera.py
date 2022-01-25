import argparse
import time

import picamera


def ascii_art():
    print("""
██████  ██  ██████  █████  ███    ███ ██████   █████  
██   ██ ██ ██      ██   ██ ████  ████      ██ ██   ██ 
██████  ██ ██      ███████ ██ ████ ██  █████   █████  
██      ██ ██      ██   ██ ██  ██  ██ ██      ██   ██ 
██      ██  ██████ ██   ██ ██      ██ ███████  █████  
    """)


def get_args():
    parser = argparse.ArgumentParser(description='Simple convenience script for snapping still images on the RPi.')
    parser.add_argument('-s', '--start', type=int, help='start filenames from a specified index', default=1,
                        action='store')
    parser.add_argument('-c', '--count', type=int, help='number of shots to take per symbol', default=3, action='store')
    return parser.parse_args()


def main():
    # get arguments
    args = get_args()

    # print details
    ascii_art()
    print(f"[-] Filenames will start from {args.start}.")
    print(f"[-] {args.count} images will be captured for each symbol.")
    print("[-] Starting camera...")

    with picamera.PiCamera() as camera:
        # parameters
        camera.resolution = (2592, 1944)
        camera.rotation = 180

        # camera warm-up time
        camera.start_preview()
        time.sleep(1)

        # capture loop
        while True:
            symbol = input("\nEnter symbol or 'Q' to quit: ").lower().strip()

            if not symbol:
                print("[!] You need to enter a symbol!")
                continue
            elif symbol == "q":
                return

            n = args.start
            while n < (args.start + args.count):
                # capture
                filename = f'{symbol}_{n}.jpg'
                camera.capture(filename)
                print(f"[✔] capture saved to `{filename}`")

                # offer option to retake current shot
                retake = input(f"Enter 'r' to retake or any key to continue: ").strip().lower()
                if retake == "r":
                    continue

                # increment index
                n += 1


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass

    print("[✔] exited")
