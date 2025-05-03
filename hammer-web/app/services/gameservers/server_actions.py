import json
from typing import Literal
from app.services.gameservers import gameserver_comm
from app.models.gameserver import GameServer

async def gracefully_shutdown_server(
    target_gameserver : GameServer,
    server_jobid : str,
    reason_type : Literal["Developer", "Roblox"] = "Developer"
) -> gameserver_comm.GameServerHttpResponse:
    return await gameserver_comm.perform_post(
        TargetGameserver = target_gameserver,
        Endpoint = "execute_script",
        JSONData = {
            "target_server_uuid": server_jobid,
            "script_name": "Shutdown",
            "script_arguments": [],
            "script": json.dumps({ "Mode" : "ServerAction", "MessageVersion" : 1, "Settings":{ "Action" : "Shutdown", "Reason": reason_type }})
        }
    )
    
async def evict_player_json(
    target_gameserver : GameServer,
    server_jobid : str,
    player_id : int
) -> gameserver_comm.GameServerHttpResponse:
    return await gameserver_comm.perform_post(
        TargetGameserver = target_gameserver,
        Endpoint = "execute_script",
        JSONData = {
            "target_server_uuid": server_jobid,
            "script_name": "EvictPlayer",
            "script_arguments": [ player_id ],
            "script": json.dumps({ "Mode" : "EvictPlayer", "MessageVersion" : 1, "Settings":{ "PlayerId": player_id }})
        }
    )
    
async def request_close_server_instance(
    target_gameserver : GameServer,
    server_jobid : str,
    reason_type : Literal["Developer", "Roblox"] = "Developer"
) -> gameserver_comm.GameServerHttpResponse:
    graceful_attempt = await gracefully_shutdown_server( target_gameserver = target_gameserver, server_jobid = server_jobid, reason_type = reason_type )
    if graceful_attempt.status_code == 200:
        return graceful_attempt
    return await gameserver_comm.perform_post(
        TargetGameserver = target_gameserver,
        Endpoint = "close_game",
        JSONData = {"job_id": server_jobid}
    )