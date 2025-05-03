"""
    This script is to be ran by the automated powershell installation script
    to register the server with the Master webserver automatically.
"""

import sys
import os
import requests
import ctypes
import winreg
import time

if sys.platform != "win32":
    print( "Platform unsupported" )
    sys.exit( 1 )
try:
    is_admin = os.getuid() == 0
except AttributeError:
    is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    
if not is_admin:
    print( "This script must be ran as an administrator" )
    sys.exit( 1 )

if len( sys.argv ) != 3:
    print( "Usage: python server_registration.py <registration_key> <server_flags>" )
    sys.exit( 1 )

registration_key = sys.argv[1]
server_flags : int = int( sys.argv[2] )

def write_access_key( value : str ):
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\ROBLOX Corporation\Roblox", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "AccessKey", 0, winreg.REG_SZ, value)
        winreg.CloseKey(key)
    except Exception as e:
        print( f"Failed to write access key: {e}" )
        sys.exit( 1 )

try:
    is_registered_key = winreg.OpenKey( winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\HammerArbiter", 0, winreg.KEY_READ )
    is_registered = winreg.QueryValueEx( is_registered_key, "IsRegistered" )[0] == "True"
    winreg.CloseKey( is_registered_key )
except FileNotFoundError:
    is_registered = False

if is_registered:
    print( "Server is already registered" )
    sys.exit( 1 )

from server_config import ServerConfig
config_class = ServerConfig()

try:
    register_response = requests.post(
        f"https://internal.{config_class.base_domain}/v1/register-arbiter",
        headers = {
            "User-Agent": "HAMMER-Gameserver-Communication/1.1",
            "Authorization": registration_key
        },
        json = {
            "port": config_class.arbiter_port,
            "flags": server_flags
        }
    )
    if register_response.status_code != 200:
        print( f"Failed to register the server: {register_response.status_code}, body: {register_response.text}" )
        sys.exit( 1 )
    json_response = register_response.json()
    if "access_key" not in json_response:
        print( f"Failed to register the server: {register_response.status_code}, body: {register_response.text}" )
        sys.exit( 1 )
    access_key = json_response["access_key"]
    server_ip = json_response["server_ip"]
    print( f"Server registered successfully with access key: {access_key} and IP: {server_ip}" )
except requests.exceptions.ConnectionError:
    print( "Failed to connect to the webserver" )
    sys.exit( 1 )
write_access_key( access_key )
try:
    key = winreg.CreateKey( winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\HammerArbiter" )
    winreg.SetValueEx( key, "IsRegistered", 0, winreg.REG_SZ, "True" )
    winreg.CloseKey( key )
except Exception as e:
    pass

time.sleep( 5 )