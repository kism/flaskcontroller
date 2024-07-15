"""Flask webapp that interfaces with mGBA with _emulator/<whatever>."""

import logging
import socket
import threading
import time

from flask import Blueprint, Flask, Response, jsonify, request

from . import get_flaskcontroller_config

fc_app_conf = get_flaskcontroller_config()["app"]

logger = logging.getLogger(__name__)

TESTING_MAX_LOOP = 10
HAS_COLORAMA = True
try:
    from colorama import Back, Fore, Style, init

    fg_colours = [
        Fore.BLACK,
        Fore.RED,
        Fore.GREEN,
        Fore.YELLOW,
        Fore.BLUE,
        Fore.MAGENTA,
        Fore.CYAN,
        Fore.WHITE,
    ]
    bg_colours = [
        Back.BLACK,
        Back.RED,
        Back.GREEN,
        Back.YELLOW,
        Back.BLUE,
        Back.MAGENTA,
        Back.CYAN,
        Back.WHITE,
    ]
except ImportError:
    HAS_COLORAMA = False

init()

input_queue = []
client_dict = {}

app = Flask(__name__)  # Flask app object


class FlaskWebController:
    """Object definition for the status of the socket."""

    def __init__(self) -> None:
        """Init."""
        self.current_input = 0
        self.sock_connected = False

    def get_current_input(self) -> int:
        """Get whether socket is connected."""
        return self.current_input

    def set_current_input(self, new_input: int) -> None:
        """Set current input."""
        self.current_input = new_input

    def get_sock_connected(self) -> bool:
        """Get whether socket is connected."""
        return self.sock_connected

    def set_sock_connected(self) -> None:
        """Get whether socket is connected."""
        self.sock_connected = True

    def set_sock_disconnected(self) -> None:
        """Get whether socket is connected."""
        self.sock_connected = False


bp = Blueprint("flaskcontroller", __name__)


@bp.route("/GetStatus", methods=["GET"])
def get_status() -> Response:
    """Return the status of the app."""
    # This is a 'ping' of sorts used to handle the player_count metric.
    # The js GETs this every x seconds.
    # The client_dict is a dictionary that stores the client-ids and when they last pinged.
    # Add current clients client id to the queue
    current_time = int(time.time())
    client_dict.update({request.headers.get("client-id"): int(time.time())})
    for ipaddress in client_dict.copy():
        # if host hasn't been in contact in 7 seconds, drop it
        if current_time - 7 > client_dict[ipaddress]:
            del client_dict[ipaddress]

    # Also returns the status of the mGBA socket connection
    result = {"sock_connected": fw_controller.get_sock_connected(), "players_connected": len(client_dict)}
    return jsonify(result)


@bp.route("/input/<string:da_input>", methods=["POST"])
def process_user_input(da_input: str) -> str:
    """Flask Process User Input (From Javascript)."""
    message = ""

    # Valid GB Button states passed from the js
    valid_inputs = [
        "D_GBA_L",
        "U_GBA_L",
        "D_GBA_R",
        "U_GBA_R",
        "D_GBA_START",
        "U_GBA_START",
        "D_GBA_B",
        "U_GBA_B",
        "D_GBA_A",
        "U_GBA_A",
        "D_GBA_SELECT",
        "U_GBA_SELECT",
        "D_GBA_LEFT",
        "U_GBA_LEFT",
        "D_GBA_UP",
        "U_GBA_UP",
        "D_GBA_RIGHT",
        "U_GBA_RIGHT",
        "D_GBA_DOWN",
        "U_GBA_DOWN",
    ]

    # This matches up with the button codes in mGBA
    button_code_dict = {
        "GBA_A": 1,
        "GBA_B": 2,
        "GBA_SELECT": 4,
        "GBA_START": 8,
        "GBA_RIGHT": 16,
        "GBA_LEFT": 32,
        "GBA_UP": 64,
        "GBA_DOWN": 128,
        "GBA_R": 256,
        "GBA_L": 512,
    }

    if da_input not in valid_inputs:
        message = "INVALID KEYPRESS, DROPPING"
    else:
        new_input = fw_controller.get_current_input()
        if da_input[:2] == "D_":
            msg = "Input! Down: " + da_input[2:]
            logger.debug(msg)
            new_input = new_input | button_code_dict[da_input[2:]]
        elif da_input[:2] == "U_":
            msg = "Input! Up: " + da_input[2:]
            logger.debug(msg)
            new_input = new_input & ~(button_code_dict[da_input[2:]])

        else:
            logger.warning("How did we get here?")

        fw_controller.set_current_input(new_input)

        # print input as bytes
        msg = f"{button_code_dict[da_input[2:]]:b}".rjust(10, "0")
        logger.debug(msg)

        input_queue.append(fw_controller.get_current_input())

        # Save some latency and do this last
        message = "VALID KEYPRESS"
        player_id_coloured = colour_player_id(request.headers.get("client-id"))

        if "D_GBA_" in da_input:
            print("Player: " + player_id_coloured + " " + da_input.replace("D_GBA_", ""))

    return message, 200


def socket_sender() -> None:
    """Connect to mGBA socket and send commands."""
    loop_count = 10
    while fc_app_conf["run_forever"] or loop_count < TESTING_MAX_LOOP:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

                fw_controller.set_sock_disconnected()
                while not fw_controller.get_sock_connected() or loop_count < TESTING_MAX_LOOP:
                    msg = (
                        "Connecting to socket: " + fc_app_conf["socket_address"] + ":" + str(fc_app_conf["socket_port"])
                    )
                    logging.info(msg)
                    if not fc_app_conf["run_forever"]:
                        msg = f"Loop count: {loop_count}"
                        logging.debug(msg)
                    try:
                        sock.connect((fc_app_conf["socket_address"], fc_app_conf["socket_port"]))
                        fw_controller.set_sock_connected()
                        print("Connected to socket!")
                    except ConnectionRefusedError:
                        time.sleep(1)
                        loop_count += 1

                # While the socket between this program and mGBA is connected
                # we check to see if there is anything in the input queue
                # and then send it if there is. This runs at approximately the
                # tick rate defined. It doesn't take into consideration the processing
                # time of this block of code lol.
                while fw_controller.get_sock_connected():
                    time.sleep(1 / fc_app_conf["tick_rate"])
                    try:
                        if input_queue:
                            in_input = input_queue.pop(0).to_bytes(2, "little", signed=False)
                            sock.sendall(in_input)

                    except BrokenPipeError:
                        print("Disconnected from socket, cringe")
                        fw_controller.set_sock_disconnected()
        except OSError:
            sock = None


def colour_player_id(player_id: str) -> str:
    """Fun coloured player names."""
    player_id = player_id[:6]
    player_id = player_id.ljust(6, " ")

    if HAS_COLORAMA:  # If we have colorama installed (pip)
        new_player_id = ""
        split_player_id = [""]

        # Split the player id string into chunks of 3
        for idx, i in enumerate(player_id):
            split_player_id[len(split_player_id) - 1] = split_player_id[len(split_player_id) - 1] + i
            if (idx + 1) % 3 == 0:
                split_player_id.append("")

        # Colour each chunk based on the sum of its characters
        # Uses modulus of the length of the colour array
        # So each string chunk will be coloured the same way
        for i in split_player_id:
            fun_number = sum(bytearray(i, "ascii"))
            fg_pick = fg_colours[(fun_number + fun_number) % len(fg_colours)]
            bg_pick = bg_colours[(fun_number) % len(bg_colours)]

            if fg_colours.index(fg_pick) == bg_colours.index(bg_pick):
                if bg_pick == bg_colours[len(bg_colours) - 1]:
                    bg_pick = bg_colours[0]
                else:
                    bg_pick = bg_colours[bg_colours.index(bg_pick) + 1]

            new_player_id = new_player_id + (Style.BRIGHT + fg_pick + bg_pick + i + Style.RESET_ALL)

        player_id = new_player_id

    return player_id


fw_controller = FlaskWebController()

thread = threading.Thread(target=socket_sender)
thread.start()