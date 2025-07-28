import asyncio
import os
import json
import random
import logging
from telethon import TelegramClient, events, functions, types
from telethon.sessions import StringSession
from telethon.errors import (
    UserDeactivatedBanError,
    FloodWaitError,
    ChannelPrivateError,
    ChatWriteForbiddenError,
    ChannelInvalidError,
    PeerIdInvalidError,
    SessionPasswordNeededError
)
from colorama import init, Fore
import pyfiglet
import socket
import time

# Initialize colorama
init(autoreset=True)

# Configuration
CREDENTIALS_FOLDER = 'sessions'
os.makedirs(CREDENTIALS_FOLDER, exist_ok=True)
TARGET_USER = "OgDigital"

# Timing Settings
MIN_DELAY = 15
MAX_DELAY = 30
CYCLE_DELAY = 900
INTERNET_CHECK_INTERVAL = 60  # Check internet every 60 seconds

# Set up logging
logging.basicConfig(
    filename='og_digital_bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

AUTO_REPLY_MESSAGE = "Dm @OgDigital"

def clear_screen():
    """Clear screen compatible with both Termux and PowerShell"""
    os.system('cls' if os.name == 'nt' else 'clear')

def display_banner():
    """Display the banner"""
    clear_screen()
    print(Fore.RED + pyfiglet.figlet_format("OG DIGITAL BOT"))
    print(Fore.GREEN + "By @OgDigital\n")

async def check_internet_connection():
    """Check if internet connection is available"""
    try:
        # Try connecting to Google's DNS server
        socket.create_connection(("8.8.8.8", 53), timeout=5)
        return True
    except OSError:
        return False

async def wait_for_internet():
    """Wait until internet connection is restored"""
    print(Fore.YELLOW + "Checking internet connection...")
    while not await check_internet_connection():
        print(Fore.RED + "No internet connection. Waiting...")
        await asyncio.sleep(INTERNET_CHECK_INTERVAL)
    print(Fore.GREEN + "Internet connection restored!")

def save_credentials(session_name, credentials):
    """Save session credentials"""
    path = os.path.join(CREDENTIALS_FOLDER, f"{session_name}.json")
    with open(path, "w") as f:
        json.dump(credentials, f)

def load_credentials(session_name):
    """Load session credentials"""
    path = os.path.join(CREDENTIALS_FOLDER, f"{session_name}.json")
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return None

async def generate_session():
    """Generate a new Telegram session"""
    display_banner()
    print(Fore.CYAN + "\nSession Generator (Create New Only)")
    
    session_name = f"session_{random.randint(1000, 9999)}"
    while os.path.exists(os.path.join(CREDENTIALS_FOLDER, f"{session_name}.json")):
        session_name = f"session_{random.randint(1000, 9999)}"
    
    phone_number = input(Fore.YELLOW + "Enter phone number (with country code): ")
    api_id = input(Fore.YELLOW + "Enter API ID: ")
    api_hash = input(Fore.YELLOW + "Enter API Hash: ")
    
    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()
    
    try:
        if not await client.is_user_authorized():
            print(Fore.CYAN + "\nSending code...")
            await client.send_code_request(phone_number)
            
            code = input(Fore.YELLOW + "Enter the code you received: ")
            
            try:
                await client.sign_in(phone_number, code)
                print(Fore.GREEN + "Signed in successfully!")
            except SessionPasswordNeededError:
                password = input(Fore.YELLOW + "Enter your 2FA password: ")
                await client.sign_in(password=password)
                print(Fore.GREEN + "Signed in with 2FA!")
            
        session_string = client.session.save()
        
        credentials = {
            "api_id": int(api_id),
            "api_hash": api_hash,
            "string_session": session_string,
            "phone_number": phone_number
        }
        
        save_credentials(session_name, credentials)
        
        print(Fore.GREEN + "\nSession created successfully!")
        print(Fore.CYAN + f"Session name: {session_name}")
        print(Fore.CYAN + f"Session string: {session_string}")
        
    except Exception as e:
        print(Fore.RED + f"Error during session creation: {str(e)}")
    finally:
        await client.disconnect()

async def get_last_dm_message(client, session_name):
    """Get last message from target user's DM"""
    try:
        entity = await client.get_entity(TARGET_USER)
        messages = await client.get_messages(entity, limit=10)
        
        for msg in messages:
            if not isinstance(msg, types.MessageService) and msg.message:
                return msg
                
        print(Fore.YELLOW + f"[{session_name}] No forwardable messages in DM")
        return None
        
    except PeerIdInvalidError:
        print(Fore.RED + f"[{session_name}] Not in DM with @{TARGET_USER}")
        return None
    except Exception as e:
        print(Fore.RED + f"[{session_name}] DM error: {str(e)}")
        return None

async def forward_to_group(client, group, message, session_name):
    """Reliable message forwarding with retries"""
    try:
        await client.forward_messages(group, message)
        print(Fore.GREEN + f"[{session_name}] Sent to {getattr(group, 'title', 'UNKNOWN')}")
        return True
    except FloodWaitError as e:
        wait = min(e.seconds, 30)
        print(Fore.YELLOW + f"[{session_name}] Flood wait: {wait}s")
        await asyncio.sleep(wait)
        return await forward_to_group(client, group, message, session_name)
    except (ChannelPrivateError, ChatWriteForbiddenError):
        print(Fore.YELLOW + f"[{session_name}] No access to group")
        return False
    except Exception as e:
        print(Fore.RED + f"[{session_name}] Forward error: {str(e)}")
        return False

async def process_groups(client, session_name, message):
    """Process all groups with strict timing control"""
    try:
        dialogs = await client.get_dialogs()
        groups = [d.entity for d in dialogs if d.is_group]
        
        if not groups:
            print(Fore.YELLOW + f"[{session_name}] No groups found")
            return

        print(Fore.CYAN + f"[{session_name}] Processing {len(groups)} groups")
        
        for group in groups:
            start_time = asyncio.get_event_loop().time()
            
            await forward_to_group(client, group, message, session_name)
            
            elapsed = asyncio.get_event_loop().time() - start_time
            remaining_delay = max(0, random.randint(MIN_DELAY, MAX_DELAY) - elapsed)
            
            if remaining_delay > 0:
                print(Fore.CYAN + f"[{session_name}] Waiting {remaining_delay:.1f}s")
                await asyncio.sleep(remaining_delay)
                
    except Exception as e:
        print(Fore.RED + f"[{session_name}] Group error: {str(e)}")

async def setup_auto_reply(client, session_name):
    """Efficient auto-reply setup"""
    @client.on(events.NewMessage(incoming=True))
    async def handler(event):
        if event.is_private and event.sender_id != (await client.get_me()).id:
            try:
                await event.reply(AUTO_REPLY_MESSAGE)
                print(Fore.GREEN + f"[{session_name}] Replied to DM")
            except FloodWaitError as e:
                await asyncio.sleep(min(e.seconds, 30))
                await event.reply(AUTO_REPLY_MESSAGE)
            except Exception:
                pass

async def run_session(session_name, credentials):
    """Optimized session runner with internet check"""
    client = None
    while True:
        try:
            # Check internet before starting
            await wait_for_internet()
            
            client = TelegramClient(
                StringSession(credentials["string_session"]),
                credentials["api_id"],
                credentials["api_hash"],
                device_model=f"OgDigitalBot-{random.randint(1000,9999)}",
                system_version="4.16.30-vxCustom",
                connection_retries=5,  # Increased retries
                request_retries=5
            )
            
            await client.start()
            print(Fore.GREEN + f"[{session_name}] Ready")
            
            await setup_auto_reply(client, session_name)
            
            while True:
                try:
                    message = await get_last_dm_message(client, session_name)
                    if message:
                        await process_groups(client, session_name, message)
                    
                    print(Fore.YELLOW + f"[{session_name}] Cycle complete, waiting {CYCLE_DELAY//60}min")
                    await asyncio.sleep(CYCLE_DELAY)
                    
                except Exception as e:
                    print(Fore.RED + f"[{session_name}] Error: {str(e)}")
                    await asyncio.sleep(300)
                    
        except UserDeactivatedBanError:
            print(Fore.RED + f"[{session_name}] Banned")
            break
        except Exception as e:
            print(Fore.RED + f"[{session_name}] Fatal: {str(e)}")
            await asyncio.sleep(60)  # Wait before retrying
        finally:
            if client:
                await client.disconnect()

async def main_forwarding():
    """Main forwarding function with unlimited sessions"""
    try:
        sessions = await list_sessions()
        
        if not sessions:
            print(Fore.RED + "No sessions found! Create some first.")
            return

        print(Fore.GREEN + f"\nStarting {len(sessions)} sessions")
        
        # Create tasks for all sessions
        tasks = []
        for session_name in sessions:
            credentials = load_credentials(session_name)
            if credentials:
                tasks.append(run_session(session_name, credentials))
        
        # Run all sessions concurrently
        await asyncio.gather(*tasks)
        
    except KeyboardInterrupt:
        print(Fore.YELLOW + "\nStopped by user")

# [Rest of the code remains the same as in your original file...]

if __name__ == "__main__":
    try:
        display_banner()
        asyncio.run(main_menu())
    except KeyboardInterrupt:
        print(Fore.YELLOW + "\nScript stopped")
    except Exception as e:
        print(Fore.RED + f"Unexpected error: {str(e)}")
