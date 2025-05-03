import subprocess
import threading
import logging
import aiohttp
import time
import asyncio
from controllers.quilkin_controller import QuilkinController
from soap_formatting import RCCSOAPMessages
from enums.ProcessYear import ProcessYear

class ControllerExceptions():
    class RCCServiceNotRunning( Exception ):
        pass
    class SOAPRequestTimedOut( Exception ):
        pass
    class UnexpectedException( Exception ):
        pass

class SOAPResponse():
    status_code : int = 0
    content : str = ""
    
    def __init__( self, status_code : int, content : str ) -> None:
        self.status_code = status_code
        self.content = content

class RCCService():
    process : subprocess.Popen = None
    rcc_soap_port : int = 64989
    executable_path : str | None = None
    kill_on_job_end : bool = False
    job_watcher_thread = None
    quilkin_controller : QuilkinController | None = None
    rcc_version : ProcessYear | None = None
    PlaceIdStartupBypassOverwrite : int = 0
    start_time : float | None = None
    assigned_server_uuid : str | None = None
    on_instance_killed_callback = None
    
    soap_message_formatter : RCCSOAPMessages = RCCSOAPMessages()
    
    def __init__(
        self,
        executable_path : str,
        rcc_soap_port : int = 64989,
        kill_on_job_end : bool = False,
        rcc_version : ProcessYear = ProcessYear.TwentyOne,
        
        PlaceIdStartupBypassOverwrite : int = 0
    ):
        if executable_path is None:
            raise ValueError("RCCService > executable_path cannot be None")
        
        self.executable_path = executable_path
        self.rcc_soap_port = rcc_soap_port
        self.kill_on_job_end = kill_on_job_end
        self.rcc_version = rcc_version
        self.PlaceIdStartupBypassOverwrite = PlaceIdStartupBypassOverwrite
        
    def kill_rcc( self, context : str = "") -> None:
        if self.process is None:
            return
        logging.info(f"RCCService > kill_rcc > Killing RCCService with context: {context}")
        self.process.kill()
        self.process = None
        asyncio.create_task( self.report_dead_to_webmaster() )
        
    def __del__( self ) -> None:
        self.kill_rcc( context = "Destructor called")
        if self.quilkin_controller is not None:
            self.quilkin_controller.stop_quilkin()
    
    def is_rcc_running( self ) -> int:
        if self.process is None:
            return False
        return self.process.poll() is None
    
    async def report_dead_to_webmaster( self ):
        """
            This is just a just in case function in an event when
            RCCService is closed unexpectedly or for whatever reason without
            itself being able to report to the webmaster
        """
        if self.assigned_server_uuid is None:
            return
        if self.on_instance_killed_callback is None:
            return
        asyncio.create_task( self.on_instance_killed_callback( self.assigned_server_uuid ) )
        
    async def ping_rcc_root( self ) -> bool:
        if self.process is None or self.is_rcc_running() == False:
            return False
        session_timeout_settings = aiohttp.ClientTimeout(total = None, sock_connect = 1, sock_read = 1)
        try:
            async with aiohttp.ClientSession(timeout = session_timeout_settings) as session:
                async with session.get(f"http://127.0.0.1:{self.rcc_soap_port}/") as response:
                    return True
        except aiohttp.ClientConnectionError:
            return False
        except Exception as e:
            logging.error(f"RCCService > ping_rcc_root > Error: {e}")
            return False
    
    async def ping_till_alive( self, timeout_time : int = 30 ) -> bool:
        starting_time = time.time()
        while time.time() - starting_time < timeout_time:
            if await self.ping_rcc_root():
                return True
            await asyncio.sleep(1)
        
        return False
        
    async def start_rcc(
        self,
        rcc_soap_port : int = 64989,
        stdout = None,
        stderr = None,
        use_verbose : bool = False,
        
        PlaceIdStartupBypassOverwrite : int = 0
    ):
        if self.process is not None:
            logging.error("RCCService > start_rcc > Process already running")
            return
        logging.info(f"RCCService > start_rcc > Starting RCCService with executable_path: {self.executable_path} and rcc_soap_port: {rcc_soap_port}")
        
        starting_script_arguments : list[str] = [
            self.executable_path,
            f"{ str( rcc_soap_port) }",
            f"-PlaceId:{ PlaceIdStartupBypassOverwrite }",
            "-Console"
        ]
        if use_verbose:
            starting_script_arguments.append("-verbose")
        self.process = subprocess.Popen(
            starting_script_arguments,
            stdout = stdout,
            stderr = stderr
        )
        logging.info(f"RCCService > start_rcc > Waiting for RCCService to start on rcc_soap_port: {rcc_soap_port}")
        is_successful = await self.ping_till_alive()
        if not is_successful:
            logging.error(f"RCCService > start_rcc > Failed to start RCCService with executable_path: \"{self.executable_path}\" and rcc_soap_port: {rcc_soap_port}")
            self.process = None
            return
        logging.info(f"RCCService > start_rcc > Successfully started RCCService on rcc_soap_port: {rcc_soap_port} with version {self.rcc_version.name}. ProcessID: {self.process.pid}")
        
        if self.kill_on_job_end:
            await self.start_job_watcher()
        
    async def attach_quilkin_controller( self, quilkin_controller : QuilkinController ) -> None:
        if self.quilkin_controller is not None:
            self.quilkin_controller.stop_quilkin()
        if isinstance(quilkin_controller, QuilkinController) == False:
            raise ValueError("RCCService > attach_quilkin_controller > quilkin_controller must be an instance of QuilkinController")
        self.quilkin_controller = quilkin_controller
        
    async def send_soap_request( self, data = "", timeout_time : int = 5 ) -> SOAPResponse:
        if not self.is_rcc_running():
            raise ControllerExceptions.RCCServiceNotRunning("RCCService > send_soap_request > RCCService is not running")
        
        session_timeout_settings = aiohttp.ClientTimeout(total = None, sock_connect = timeout_time, sock_read = timeout_time)
        try:
            async with aiohttp.ClientSession(timeout = session_timeout_settings) as session:
                async with session.post(f"http://127.0.0.1:{self.rcc_soap_port}/", data = data) as response:
                    response_content = await response.text()
                    return SOAPResponse( response.status, response_content )
        except aiohttp.ClientConnectionError as e:
            raise ControllerExceptions.SOAPRequestTimedOut(f"RCCService > send_soap_request > Connection Error : {e}")
        except Exception as e:
            raise ControllerExceptions.UnexpectedException(f"RCCService > send_soap_request > Error: {e}")
        
    async def get_running_jobs( self ) -> list[ dict | None ]:
        soap_response : SOAPResponse = await self.send_soap_request(
            data = self.soap_message_formatter.GetAllJobsMsg,
            timeout_time = 5
        )
        
        if soap_response.status_code != 200:
            logging.error(f"RCCService > get_running_jobs > SOAP Request failed with status code: {soap_response.status_code}")
            return []
        if soap_response.content == "":
            logging.error("RCCService > get_running_jobs > SOAP Request failed with empty response content")
            return []
        running_jobs : list[dict] = self.soap_message_formatter.ParseGetAllJobsResponse( soap_response.content )
        return running_jobs
    
    async def job_watcher_task( self ) -> None:
        while True:
            await asyncio.sleep(15)
            if not self.is_rcc_running():
                asyncio.create_task( self.report_dead_to_webmaster() )
                logging.info("RCCService > job_watcher_task > RCCService is not running, killing job_watcher_task")
                self.process = None
                break
            
            running_jobs : list = await self.get_running_jobs()
            if len(running_jobs) == 0:
                logging.info("RCCService > job_watcher_task > No running jobs, killing RCCService")
                self.kill_rcc( context = "job_watcher_task" )
                break
    
    async def start_job_watcher( self ) -> None:
        if self.is_rcc_running() == False:
            raise ControllerExceptions.RCCServiceNotRunning("RCCService > start_job_watcher > RCCService is not running")
        if self.job_watcher_thread is not None:
            return
        logging.info(f"RCCService > start_job_watcher > Starting job_watcher_task for RCCService with ProcessID: {self.process.pid}")
        self.job_watcher_thread = asyncio.create_task( self.job_watcher_task(), name = f"rccservice_job_watcher_task:{ self.process.pid }")
        
    async def send_open_job_request( self, job_id : str , job_expiration : int = 20, assigned_cores : int = 1, script_name : str = "run_script", run_script : str = "", script_arguments = [], request_timeout : int = 5) -> SOAPResponse:
        if self.is_rcc_running() is False:
            raise ControllerExceptions.RCCServiceNotRunning("RCCService > send_open_job_request was called before RCC was started")
        OpenJobData : str = self.soap_message_formatter.FormatOpenJobMessage(job_id, job_expiration, assigned_cores, script_name, run_script, script_arguments)
        return await self.send_soap_request(data = OpenJobData, timeout_time = request_timeout)
    
    async def send_batch_job_request( self, job_id : str , job_expiration : int = 20, assigned_cores : int = 1, script_name : str = "run_script", run_script : str = "", script_arguments = [], request_timeout : int = 5) -> SOAPResponse:
        if self.is_rcc_running() is False:
            raise ControllerExceptions.RCCServiceNotRunning("RCCService > send_batch_job_request was called before RCC was started")
        BatchJobData : str = self.soap_message_formatter.FormatBatchJobMessage(job_id, job_expiration, assigned_cores, script_name, run_script, script_arguments)
        return await self.send_soap_request(data = BatchJobData, timeout_time = request_timeout)
    
    async def send_close_job_request(self, job_id : str) -> SOAPResponse:
        if self.is_rcc_running() is False:
            raise ControllerExceptions.RCCServiceNotRunning("RCCService > send_close_job_request was called before RCC was started")
        CloseJobData : str = self.soap_message_formatter.FormatCloseJobMessage(job_id)
        return await self.send_soap_request(data = CloseJobData)
    
    async def send_execute_script_request(self, job_id : str, script_name : str = "Script", script : str = "", script_arguments = []) -> SOAPResponse:
        if self.is_rcc_running() is False:
            raise ControllerExceptions.RCCServiceNotRunning("RCCService > send_execute_script_request was called before RCC was started")
        ExecuteScriptData : str = self.soap_message_formatter.FormatExecuteScriptMessage(job_id, script_name, script, script_arguments)
        return await self.send_soap_request(data = ExecuteScriptData)
        
async def create_rcc_instance(
    executable_path : str,
    rcc_soap_port : int = 64989,
    kill_on_job_end : bool = False,
    rcc_version : ProcessYear = ProcessYear.TwentyOne,
    use_verbose : bool = False,
    
    PlaceIdStartupBypassOverwrite : int = 0    
) -> RCCService:
    rcc_instance = RCCService(
        executable_path = executable_path,
        rcc_soap_port = rcc_soap_port,
        kill_on_job_end = kill_on_job_end,
        rcc_version = rcc_version,
        
        PlaceIdStartupBypassOverwrite = PlaceIdStartupBypassOverwrite
    )
    await rcc_instance.start_rcc(
        rcc_soap_port = rcc_instance.rcc_soap_port,
        use_verbose = use_verbose,
        PlaceIdStartupBypassOverwrite = PlaceIdStartupBypassOverwrite
    )
    return rcc_instance