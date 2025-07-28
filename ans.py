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
    SessionPasswordNeededError,
    ConnectionError
)
from colorama import init, Fore
import pyfiglet
import socket
import aiohttp

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
NETWORK_CHECK_INTERVAL = 60  # Check internet every 60 seconds

# Set up logging
logging.basicConfig(
    filename='og_digital_bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

AUTO_REPLY_MESSAGE = "Dm @OgDigital"

def clear_screen():
    """Clear the console screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def display_banner():
    """Display the banner"""
    clear_screen()
    print(Fore.RED + pyfiglet.figlet_format("OG DIGITAL BOT"))
    print(Fore.GREEN + "By @OgDigital\n")

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

async def is_internet_available():
    """Check if internet connection is available"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('http://www.google.com', timeout=5) as resp:
                return resp.status == 200
    except:
        return False

async def wait_for_internet():
    """Wait until internet connection is restored"""
    print(Fore.YELLOW + "Checking internet connection...")
    while True:
        if await is_internet_available():
            print(Fore.GREEN + "Internet connection restored!")
            return True
        print(Fore.RED + "No internet connection. Waiting...")
        await asyncio.sleep(NETWORK_CHECK_INTERVAL)

async def generate_session():
    """Generate a new Telegram session"""
    print(Fore.CYAN + "\nSession Generator (Create New Only)")
    
    session_name = f"session_{random.randint(1000, 9999)}"
    while os.path.exists(os.path.join(CREDENTIALS_FOLDER, f"{session_name}.json")):
        session_name = f"session_{random.randint(1000, 9999)}"
    
    phone_number = input(Fore.YELLOW + "Enter phone number (with country code): ")
    api_id = input(Fore.YELLOW + "Enter API ID: ")
    api_hash = input(Fore.YELLOW + "Enter API Hash: ")
    
    client = TelegramClient(StringSession(), api_id, api_hash)
    
    try:
        await client.connect()
        
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
    """Optimized session runner with network resilience"""
    client = None
    
    while True:
        try:
            # Check internet before starting
            if not await is_internet_available():
                await wait_for_internet()
            
            client = TelegramClient(
                StringSession(credentials["string_session"]),
                credentials["api_id"],
                credentials["api_hash"],
                device_model=f"OgDigitalBot-{random.randint(1000,9999)}",
                system_version="4.16.30-vxCustom",
                connection_retries=5,
                request_retries=5,
                auto_reconnect=True
            )
            
            await client.start()
            print(Fore.GREEN + f"[{session_name}] Ready")
            
            await setup_auto_reply(client, session_name)
            
            while True:
                try:
                    if not await is_internet_available():
                        await wait_for_internet()
                        # Reconnect after internet is back
                        await client.disconnect()
                        await client.connect()
                        
                    message = await get_last_dm_message(client, session_name)
                    if message:
                        await process_groups(client, session_name, message)
                    
                    print(Fore.YELLOW + f"[{session_name}] Cycle complete, waiting {CYCLE_DELAY//60}min")
                    await asyncio.sleep(CYCLE_DELAY)
                    
                except (ConnectionError, aiohttp.ClientError) as e:
                    print(Fore.RED + f"[{session_name}] Network error: {str(e)}")
                    await wait_for_internet()
                    continue
                except Exception as e:
                    print(Fore.RED + f"[{session_name}] Error: {str(e)}")
                    await asyncio.sleep(300)
                    break
                    
        except UserDeactivatedBanError:
            print(Fore.RED + f"[{session_name}] Banned")
            break
        except Exception as e:
            print(Fore.RED + f"[{session_name}] Fatal: {str(e)}")
            await asyncio.sleep(300)
        finally:
            if client and client.is_connected():
                await client.disconnect()

async def change_bio(session_name, credentials, new_bio):
    """Change account bio"""
    client = None
    try:
        if not await is_internet_available():
            await wait_for_internet()
            
        client = TelegramClient(
            StringSession(credentials["string_session"]),
            credentials["api_id"],
            credentials["api_hash"]
        )
        
        await client.start()
        await client(functions.account.UpdateProfileRequest(about=new_bio))
        print(Fore.GREEN + f"[{session_name}] Bio changed successfully")
        
    except Exception as e:
        print(Fore.RED + f"[{session_name}] Error changing bio: {str(e)}")
    finally:
        if client and client.is_connected():
            await client.disconnect()

async def change_name(session_name, credentials, first_name, last_name=""):
    """Change account name"""
    client = None
    try:
        if not await is_internet_available():
            await wait_for_internet()
            
        client = TelegramClient(
            StringSession(credentials["string_session"]),
            credentials["api_id"],
            credentials["api_hash"]
        )
        
        await client.start()
        await client(functions.account.UpdateProfileRequest(
            first_name=first_name,
            last_name=last_name
        ))
        print(Fore.GREEN + f"[{session_name}] Name changed successfully")
        
    except Exception as e:
        print(Fore.RED + f"[{session_name}] Error changing name: {str(e)}")
    finally:
        if client and client.is_connected():
            await client.disconnect()

async def list_sessions():
    """List all available sessions"""
    sessions = []
    for file in os.listdir(CREDENTIALS_FOLDER):
        if file.endswith('.json'):
            sessions.append(file[:-5])  # Remove .json extension
    return sessions

async def select_session(multiple=False):
    """Let user select session(s)"""
    sessions = await list_sessions()
    if not sessions:
        print(Fore.RED + "No sessions found!")
        return None
    
    print(Fore.CYAN + "\nAvailable sessions:")
    for i, session in enumerate(sessions, 1):
        print(Fore.CYAN + f"{i}. {session}")
    
    if multiple:
        while True:
            choice = input(Fore.YELLOW + "\nSelect session numbers (comma separated) or 'all': ")
            if choice.lower() == 'all':
                return sessions
            
            try:
                selected_indices = [int(x.strip()) for x in choice.split(',')]
                selected_sessions = [sessions[i-1] for i in selected_indices if 1 <= i <= len(sessions)]
                if selected_sessions:
                    return selected_sessions
                print(Fore.RED + "Invalid selection!")
            except ValueError:
                print(Fore.RED + "Please enter numbers separated by commas!")
    else:
        while True:
            try:
                choice = int(input(Fore.YELLOW + "\nSelect session (number): "))
                if 1 <= choice <= len(sessions):
                    return sessions[choice-1]
                print(Fore.RED + "Invalid selection!")
            except ValueError:
                print(Fore.RED + "Please enter a number!")

async def bio_changer_menu():
    """Bio changer menu with individual/all options"""
    print(Fore.CYAN + "\nBio Changer Options:")
    print(Fore.CYAN + "1. Change bio for individual session")
    print(Fore.CYAN + "2. Change bio for all sessions")
    print(Fore.CYAN + "3. Change bio for selected sessions")
    
    choice = input(Fore.YELLOW + "\nSelect option (1-3): ")
    
    if choice == "1":
        session_name = await select_session()
        if not session_name:
            return
            
        credentials = load_credentials(session_name)
        if not credentials:
            print(Fore.RED + f"Could not load credentials for {session_name}")
            return
            
        new_bio = input(Fore.YELLOW + "Enter new bio: ")
        await change_bio(session_name, credentials, new_bio)
        
    elif choice == "2":
        sessions = await list_sessions()
        if not sessions:
            print(Fore.RED + "No sessions found!")
            return
            
        new_bio = input(Fore.YELLOW + "Enter new bio for all sessions: ")
        
        for session_name in sessions:
            credentials = load_credentials(session_name)
            if credentials:
                print(Fore.CYAN + f"\nChanging bio for {session_name}...")
                await change_bio(session_name, credentials, new_bio)
            else:
                print(Fore.RED + f"Could not load credentials for {session_name}")
    
    elif choice == "3":
        session_names = await select_session(multiple=True)
        if not session_names:
            return
            
        new_bio = input(Fore.YELLOW + "Enter new bio for selected sessions: ")
        
        for session_name in session_names:
            credentials = load_credentials(session_name)
            if credentials:
                print(Fore.CYAN + f"\nChanging bio for {session_name}...")
                await change_bio(session_name, credentials, new_bio)
            else:
                print(Fore.RED + f"Could not load credentials for {session_name}")

async def name_changer_menu():
    """Name changer menu with individual/all options"""
    print(Fore.CYAN + "\nName Changer Options:")
    print(Fore.CYAN + "1. Change name for individual session")
    print(Fore.CYAN + "2. Change name for all sessions")
    print(Fore.CYAN + "3. Change name for selected sessions")
    
    choice = input(Fore.YELLOW + "\nSelect option (1-3): ")
    
    if choice == "1":
        session_name = await select_session()
        if not session_name:
            return
            
        credentials = load_credentials(session_name)
        if not credentials:
            print(Fore.RED + f"Could not load credentials for {session_name}")
            return
            
        first_name = input(Fore.YELLOW + "Enter first name: ")
        last_name = input(Fore.YELLOW + "Enter last name (optional): ")
        await change_name(session_name, credentials, first_name, last_name)
        
    elif choice == "2":
        sessions = await list_sessions()
        if not sessions:
            print(Fore.RED + "No sessions found!")
            return
            
        first_name = input(Fore.YELLOW + "Enter first name for all sessions: ")
        last_name = input(Fore.YELLOW + "Enter last name for all sessions (optional): ")
        
        for session_name in sessions:
            credentials = load_credentials(session_name)
            if credentials:
                print(Fore.CYAN + f"\nChanging name for {session_name}...")
                await change_name(session_name, credentials, first_name, last_name)
            else:
                print(Fore.RED + f"Could not load credentials for {session_name}")
    
    elif choice == "3":
        session_names = await select_session(multiple=True)
        if not session_names:
            return
            
        first_name = input(Fore.YELLOW + "Enter first name for selected sessions: ")
        last_name = input(Fore.YELLOW + "Enter last name for selected sessions (optional): ")
        
        for session_name in session_names:
            credentials = load_credentials(session_name)
            if credentials:
                print(Fore.CYAN + f"\nChanging name for {session_name}...")
                await change_name(session_name, credentials, first_name, last_name)
            else:
                print(Fore.RED + f"Could not load credentials for {session_name}")

async def collect_session_credentials(num_sessions):
    """Collect credentials for multiple sessions"""
    sessions = []
    for i in range(1, num_sessions + 1):
        print(Fore.CYAN + f"\nSession {i}/{num_sessions}")
        
        session_name = f"forward_session_{i}"
        creds = load_credentials(session_name)
        
        if creds:
            print(Fore.GREEN + f"Using existing session: {session_name}")
            sessions.append((session_name, creds))
            continue
            
        print(Fore.YELLOW + f"Enter credentials for new session: {session_name}")
        api_id = input("API ID: ")
        api_hash = input("API Hash: ")
        string_session = input("String Session: ")
        
        creds = {
            "api_id": int(api_id),
            "api_hash": api_hash,
            "string_session": string_session
        }
        
        save_credentials(session_name, creds)
        sessions.append((session_name, creds))
    
    return sessions

async def main_forwarding():
    """Main forwarding function with credential collection"""
    try:
        num_sessions = int(input(Fore.YELLOW + "Enter number of sessions to use: "))
        if num_sessions <= 0:
            raise ValueError("Number must be positive")
            
        sessions = await collect_session_credentials(num_sessions)
        
        if not sessions:
            print(Fore.RED + "No valid sessions to run!")
            return

        print(Fore.GREEN + f"\nStarting {len(sessions)} sessions")
        
        # Start all sessions without concurrency limit
        await asyncio.gather(*[run_session(name, creds) for name, creds in sessions])
        
    except ValueError as e:
        print(Fore.RED + f"Input error: {str(e)}")
    except KeyboardInterrupt:
        print(Fore.YELLOW + "\nStopped by user")

async def main_menu():
    """Main menu with options"""
    while True:
        display_banner()
        print(Fore.CYAN + "\nMain Menu:")
        print(Fore.CYAN + "1. Start DM Forwarding + Auto Reply")
        print(Fore.CYAN + "2. Bio Changer")
        print(Fore.CYAN + "3. Name Changer")
        print(Fore.CYAN + "4. Generate New Session")
        print(Fore.CYAN + "5. Exit")
        
        choice = input(Fore.YELLOW + "\nSelect option (1-5): ")
        
        if choice == "1":
            await main_forwarding()
        elif choice == "2":
            await bio_changer_menu()
        elif choice == "3":
            await name_changer_menu()
        elif choice == "4":
            await generate_session()
        elif choice == "5":
            print(Fore.YELLOW + "Exiting...")
            return
        else:
            print(Fore.RED + "Invalid choice!")

if __name__ == "__main__":
    try:
        # Configure asyncio for Windows
        if os.name == 'nt':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            
        display_banner()
        asyncio.run(main_menu())
    except KeyboardInterrupt:
        print(Fore.YELLOW + "\nScript stopped")