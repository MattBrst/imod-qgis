"""
This module contains the logic for starting, communicating with, and killing a
seperate interpreter.

Modified from: 
https://gitlab.com/deltares/imod/qgis-tim/-/blob/master/plugin/qgistim/server_handler.py
"""
import json
import os
import platform
import signal
import socket
import subprocess
from contextlib import closing
from pathlib import Path

class Server:
    def __init__(self):
        self.HOST = "127.0.0.1" # = localhost in IPv4 protocol
        self.PORT = None
        self.socket = None

    def find_free_port(self) -> int:
        """
        Finds a free localhost port number.

        Returns
        -------
        portnumber: int
        """
        # from:
        # https://stackoverflow.com/questions/1365265/on-localhost-how-do-i-pick-a-free-port-number
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            sock.bind(("localhost", 0))
            return sock.getsockname()[1]

    def get_configdir(self) -> Path:
        """
        Get the location of the imod-qgis plugin settings.

        The location differs per OS.

        Returns
        -------
        configdir: pathlib.Path
        """
        if platform.system() == "Windows":
            configdir = Path(os.environ["APPDATA"]) / "imod-qgis"
        else:
            configdir = Path(os.environ["HOME"]) / ".imod-qgis"
        return configdir

    def start_server(self) -> None:
        self.PORT = self.find_free_port()

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((self.HOST, self.PORT))
        self.socket.listen(4)

    def accept_client(self):
        self.client, address = self.socket.accept()

    def start_imod(self) -> None:
        """
        Starts imod, based on the settings in the
        configuration directory.
        """
        
        configdir = self.get_configdir()

        xml_path = configdir / "qgis_viewer.imod"

        with open(configdir / "viewer_exe.txt") as f:
            viewer_exe = f.read().strip()

        with open(configdir / "environmental-variables.json", "r") as f:
            env_vars = json.loads(f.read())

        hostAddress = f"{self.HOST}:{self.PORT}"
        
        subprocess.Popen(
            [viewer_exe, "--file", str(xml_path), "--hostAddress", hostAddress], 
                env = env_vars)

        xml_path = str(xml_path)

        print(f"{viewer_exe} --file {xml_path} --hostAddress {hostAddress}")

        print(hostAddress)

    def send(self, data) -> str:
        """
        Send a data package (should be a XML string) to the external
        interpreter, running gistim.

        Parameters
        ----------
        data: str
            A XML string describing the operation and parameters

        Returns
        -------
        received: str
            Value depends on the requested operation
        """
        
        debug_path = r"c:\Users\engelen\projects_wdir\iMOD6\test_data\temp\command.xml"
        with open(debug_path, "w") as f:
            f.write(data)

        self.client.sendall(bytes(data, "utf-8"))
        #self.socket.sendall(bytes(data, "utf-8"))
        #received = str(self.socket.recv(1024), "utf-8")
        #return received

    def kill(self) -> None:
        """
        Kills the external interpreter.

        This enables shutting down the external window when the plugin is
        closed.
        """
        if self.PORT is not None:
            # Ask the process for its process_ID
            try:
                data = json.dumps({"operation": "process_ID"})
                process_ID = int(self.send(data))
                # Now kill it
                os.kill(process_ID, signal.SIGTERM)
            except ConnectionRefusedError:
                # it's already dead
                pass