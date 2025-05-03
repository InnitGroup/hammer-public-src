import os
import subprocess
import logging

class QuilkinController():
    """
        Wrapper for starting the Quilkin UDP Proxy ( https://github.com/googleforgames/quilkin )
    """

    quilkin_process : subprocess.Popen | None = None
    proxy_target_host : str = "127.0.0.1"
    proxy_target_port : int = 0
    proxy_listen_port : int = 0
    quilkin_executable_path : str = "./dependencies/quilkin.exe"

    is_running : bool = False

    def __init__( self, 
        proxy_target_host : str = "127.0.0.1",
        proxy_target_port : int = 53640,
        proxy_listen_port : int = 56640,
        quilkin_executable_path : str = "./dependencies/quilkin.exe",
    ) -> None:
        if not os.path.exists(quilkin_executable_path):
            raise FileNotFoundError("Quilkin executable not found")
        if proxy_listen_port < 1024:
            raise PermissionError("Cannot bind to port < 1024")
        if proxy_target_port < 1024:
            raise PermissionError("Cannot bind to port < 1024")
        if proxy_target_port > 65535:
            raise ValueError("Port number out of range")

        self.proxy_target_host = proxy_target_host
        self.proxy_target_port = proxy_target_port
        self.proxy_listen_port = proxy_listen_port
        self.quilkin_executable_path = quilkin_executable_path

    def start_quilkin( self ) -> None:
        """
            Start the Quilkin UDP Proxy
        """
        if self.is_running:
            raise Exception("Quilkin is already running")
        if self.quilkin_process is not None:
            self.quilkin_process.kill()

        self.quilkin_process = subprocess.Popen([
            self.quilkin_executable_path,
            "--no-admin", "proxy",
            "-p", str(self.proxy_listen_port),
            "-t", f"{self.proxy_target_host}:{self.proxy_target_port}"
        ], stdout = subprocess.PIPE, stderr = subprocess.PIPE )
        self.is_running = True
        logging.info(f"controllers.quilkin_controller > Quilkin started on port {self.proxy_listen_port} with target {self.proxy_target_host}:{self.proxy_target_port}")

    def stop_quilkin( self ) -> None:
        """
            Stop the Quilkin UDP Proxy
        """
        if not self.is_running:
            raise Exception("Quilkin is not running")
        if self.quilkin_process is not None:
            self.quilkin_process.kill()
        self.is_running = False

    def __del__( self ) -> None:
        if self.is_running:
            self.stop_quilkin()