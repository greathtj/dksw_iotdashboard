import os
import re
import json
import tempfile
import serial.tools.list_ports
import subprocess
import shutil
from typing import Any

def list_serial_ports() -> list[dict[str, str]]:
    """
    Returns a list of available serial ports.
    Each item is a tuple or object containing device name and description.
    """
    ports = serial.tools.list_ports.comports()
    # formatting as a list of dicts for easier template usage
    return [{'device': p.device, 'description': p.description} for p in ports]

import base64

def compile_sketch(source_code: str, board_fqbn: str = 'arduino:avr:uno', board_options: str = None) -> dict[str, Any]:
    """
    Compiles Arduino source code using arduino-cli.
    Returns:
       - 'success': bool
       - 'hex_content': str (if AVR)
       - 'bin_content': str (base64, if ESP32)
       - 'flash_address': int (if ESP32)
       - 'board_type': str ('avr' or 'esp32')
       - 'message': str
       - 'logs': str (compiler output)
    """
    # Determine the expected binary name (with .exe on Windows)
    cli_name = 'arduino-cli.exe' if os.name == 'nt' else 'arduino-cli'
    arduino_cli = shutil.which(cli_name)
    
    # Check for local binary in the project first to avoid snap sandbox issues
    from django.conf import settings
    local_cli = os.path.join(settings.BASE_DIR, 'development', cli_name)
    if os.path.exists(local_cli):
        arduino_cli = local_cli
    
    # If not found or if it's the snap version, try other locations
    if not arduino_cli or (os.name != 'nt' and '/snap/' in arduino_cli):
        if os.name != 'nt' and os.path.exists('/usr/local/bin/arduino-cli'):
            arduino_cli = '/usr/local/bin/arduino-cli'
        elif os.name == 'nt':
            # Check common Windows locations
            possible_paths = [
                os.path.join(os.getcwd(), 'arduino-cli.exe'),
                os.path.join(settings.BASE_DIR, 'arduino-cli.exe'),
                os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'arduino-ide', 'resources', 'app', 'node_modules', 'arduino-ide-extension', 'build', 'arduino-cli.exe'),
                os.path.join(os.environ.get('ProgramFiles', ''), 'Arduino CLI', 'arduino-cli.exe'),
                os.path.join(os.environ.get('ProgramFiles(x86)', ''), 'Arduino CLI', 'arduino-cli.exe'),
                os.path.join(os.path.expanduser('~'), 'bin', 'arduino-cli.exe'),
            ]
            for p in possible_paths:
                if os.path.exists(p):
                    arduino_cli = p
                    break
    
    if not arduino_cli or not os.path.exists(arduino_cli):
        return {'success': False, 'message': f'arduino-cli not found or inaccessible (found: {arduino_cli})'}

    # Verify execute permission
    if not os.access(arduino_cli, os.X_OK):
        whoami = subprocess.run(['whoami'], capture_output=True, text=True).stdout.strip()
        return {
            'success': False, 
            'message': f'Permission denied: arduino-cli is not executable by user "{whoami}".',
            'logs': f'Path: {arduino_cli}\nPermissions: {oct(os.stat(arduino_cli).st_mode)}\n'
                    f'Please run: chmod +x {arduino_cli}'
        }

    # Create a temporary directory for the build
    with tempfile.TemporaryDirectory() as temp_dir:
        # Sketch folder must match sketch filename
        sketch_name = "DynamicSketch"
        sketch_dir = os.path.join(temp_dir, sketch_name)
        build_dir = os.path.join(sketch_dir, "build")
        os.makedirs(sketch_dir)
        os.makedirs(build_dir)
        
        sketch_file = os.path.join(sketch_dir, f"{sketch_name}.ino")
        with open(sketch_file, 'w', encoding='utf-8') as f:
            f.write(source_code)
            
        env = os.environ.copy()
        from django.conf import settings
        
        # We explicitly set these to match the successful manual installation on the server
        from django.conf import settings
        arduino_data = getattr(settings, 'ARDUINO_DATA_DIR', '/home/greathtj/.arduino15')
        
        # Derive the home directory from the data directory to be consistent
        # e.g., if data is /home/greathtj/.arduino15, home should be /home/greathtj
        home_dir = os.path.dirname(arduino_data) if '.arduino15' in arduino_data else os.path.expanduser('~')
        
        # Diagnostic: who is running this?
        whoami = subprocess.run(['whoami'], capture_output=True, text=True).stdout.strip()

        # If we are running as www-data or another user that doesn't own home_dir, 
        # we might need a writable HOME for temporary files/locking.
        # However, we MUST keep ARDUINO_DIRECTORIES_DATA pointing to the shared cores.
        if not os.access(home_dir, os.W_OK):
            # Use temp_dir for HOME instead of the real home if it's not writable
            env['HOME'] = temp_dir 
        else:
            env['HOME'] = home_dir
            
        # Force these paths so arduino-cli uses the cores you just installed
        env['ARDUINO_DIRECTORIES_DATA'] = arduino_data
        env['ARDUINO_DATA_DIR'] = arduino_data # Some versions use this
        env['ARDUINO_DIRECTORIES_USER'] = os.path.join(home_dir, 'Arduino')
        
        # Ensure the config file is also pointed to if needed
        config_path = os.path.join(arduino_data, 'arduino-cli.yaml')

        # Header-to-library name mapping (comprehensive)
        HEADER_TO_LIB = {
            "#include <Servo.h>": ["Servo"],
            "#include <ServoAvr8xx.h>": ["Servo"],
            "#include <ArduinoJson.h>": ["ArduinoJson"],
            "#include <Adafruit_MPU6050.h>": ["Adafruit MPU6050", "Adafruit Unified Sensor", "Adafruit BusIO"],
            "#include <Adafruit_BMP085.h>": ["Adafruit BMP085 Library", "Adafruit Unified Sensor"],
            "#include <Adafruit_BME280.h>": ["Adafruit BME280", "Adafruit Unified Sensor", "Adafruit BusIO"],
            "#include <Adafruit_BME680.h>": ["Adafruit BME680", "Adafruit Unified Sensor", "Adafruit BusIO"],
            "#include <Adafruit_Sensor.h>": ["Adafruit Unified Sensor"],
            "#include <Adafruit_GFX.h>": ["Adafruit GFX Library"],
            "#include <Adafruit_ILI9341.h>": ["Adafruit ILI9341"],
            "#include <Adafruit_ST7735.h>": ["Adafruit ST7735 and ST7789 Library"],
            "#include <Adafruit_ST7789.h>": ["Adafruit ST7735 and ST7789 Library"],
            "#include <Adafruit_SH1106.h>": ["Adafruit SH1106"],
            "#include <Adafruit_NeoPixel.h>": ["Adafruit NeoPixel"],
            "#include <Adafruit_PWMServoDriver.h>": ["Adafruit PCA9685"],
            "#include <Adafruit_BusIO_Register.h>": ["Adafruit BusIO"],
            "#include <Adafruit_I2CDevice.h>": ["Adafruit BusIO"],
            "#include <Adafruit_SPIFlash.h>": ["Adafruit SPI Flash"],
            "#include <BH1750.h>": ["BH1750"],
            "#include <WiFiEsp.h>": ["WiFiEsp"],
            "#include <WiFiEspClient.h>": ["WiFiEsp"],
            "#include <WiFiEspServer.h>": ["WiFiEsp"],
            "#include <Adafruit_AHTX0.h>": ["Adafruit AHTX0", "Adafruit Unified Sensor", "Adafruit BusIO"],
            "#include <DHT.h>": ["DHT sensor library"],
            "#include <DHT_U.h>": ["DHT sensor library", "Adafruit Unified Sensor"],
            "#include <DHTsensor.h>": ["DHT sensor library"],
            "#include <SD.h>": ["SD"],
            "#include <SD_MMC.h>": ["SD_MMC"],
            "#include <SPI.h>": [],
            "#include <Wire.h>": [],
            "#include <Ethernet.h>": ["Ethernet"],
            "#include <Ethernet2.h>": ["Ethernet2"],
            "#include <Ethernet3.h>": ["Ethernet3"],
            "#include <WiFi.h>": [],
            "#include <WiFiClient.h>": [],
            "#include <WebServer.h>": ["WebServer"],
            "#include <ESPmDNS.h>": [],
            "#include <ArduinoHttpClient.h>": ["ArduinoHttpClient"],
            "#include <HTTPClient.h>": [],
            "#include <PubSubClient.h>": ["PubSubClient"],
            "#include <MiladP1.h>": ["MiladP1"],
            "#include <LiquidCrystal_I2C.h>": ["LiquidCrystal I2C"],
            "#include <LiquidCrystal.h>": [],
            "#include <OneWire.h>": ["OneWire"],
            "#include <DallasTemperature.h>": ["Dallas Temperature Controls"],
            "#include <DFRobot_Serial485.h>": ["DFRobot Serial485"],
            "#include <MicroBitMatrix.h>": ["MicroBitMatrix"],
            "#include <SPIFFS.h>": [],
            "#include <FS.h>": [],
            "#include <Update.h>": [],
            "#include <ArduinoOTA.h>": [],
            "#include <Keypad.h>": ["Keyboard"],
            "#include <MFRC522.h>": ["MFRC522"],
            "#include <RTClib.h>": ["RTClib"],
            "#include <PulseSensor_Arduino.h>": ["PulseSensor"],
            "#include <HX711.h>": ["HX711"],
            "#include <ADC121C_ESP32.h>": [],
            "#include <ESP32Servo.h>": ["ESP32Servo"],
            "#include <FastLED.h>": ["FastLED"],
            "#include <NeoPixelBus.h>": ["NeoPixelBus"],
            "#include <MAX17048FuelGauge.h>": ["MAX17048FuelGauge"],
            "#include <LowPower.h>": ["LowPower"],
            "#include <Adafruit_INA219.h>": ["Adafruit INA219"],
            "#include <Adafruit_ADS1X15.h>": ["Adafruit ADS1X15"],
            "#include <Adafruit_MCP23017.h>": ["Adafruit MCP23017"],
            "#include <Adafruit_SSD1306.h>": ["Adafruit SSD1306"],
        }

        def get_installed_libraries() -> set:
            """Get set of currently installed library names from arduino-cli."""
            try:
                result = subprocess.run(
                    [arduino_cli, "lib", "list", "--format", "json"],
                    capture_output=True, text=True, env=env, timeout=30
                )
                if result.returncode == 0 and result.stdout.strip():
                    installed = set()
                    try:
                        parsed = json.loads(result.stdout)
                        items = parsed if isinstance(parsed, list) else parsed.get('libraries', [])
                        for entry in items:
                            lib_name = entry.get("Name", "").strip()
                            if lib_name:
                                installed.add(lib_name.lower())
                                version = entry.get("Version", "").strip()
                                if version:
                                    installed.add(f"{lib_name.lower()}@{version}")
                    except json.JSONDecodeError:
                        for line in result.stdout.strip().split('\n'):
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                entry = json.loads(line)
                                if isinstance(entry, dict):
                                    lib_name = entry.get("Name", "").strip()
                                    if lib_name:
                                        installed.add(lib_name.lower())
                                        version = entry.get("Version", "").strip()
                                        if lib_name and version:
                                            installed.add(f"{lib_name.lower()}@{version}")
                            except json.JSONDecodeError:
                                continue
                    return installed
            except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                pass
            # Fallback: return empty set — we'll check per-library install below
            return set()

        def try_install_library(lib_name: str, timeout: int = 60) -> bool:
            """Try to install a library. Returns True if installed or already present."""
            try:
                print(f"Installing library: {lib_name}")
                install_cmd = [arduino_cli, "lib", "install", "--force", lib_name]
                result = subprocess.run(install_cmd, capture_output=True, text=True, env=env, timeout=timeout)
                if result.returncode == 0:
                    print(f"  -> Installed '{lib_name}' successfully")
                    return True
                # Check if it's already installed (arduino-cli returns non-zero for "already at version")
                stderr_lower = result.stderr.lower()
                stdout_lower = result.stdout.lower()
                combined = stderr_lower + stdout_lower
                if 'already' in combined or 'installed' in combined:
                    print(f"  -> '{lib_name}' already installed")
                    return True
                else:
                    print(f"  -> Install failed for '{lib_name}': {result.stderr[:200]}")
                    return False
            except subprocess.TimeoutExpired:
                print(f"  -> Timeout installing '{lib_name}'")
                return False
            except subprocess.SubprocessError as e:
                print(f"  -> Error installing '{lib_name}': {e}")
                return False

        def search_and_install_library(header_name: str, timeout: int = 60) -> bool:
            """Search arduino-cli library index for a header and install top match."""
            try:
                print(f"Searching library for header: {header_name}")

                # Generate all plausible library names from the header
                base = header_name.replace(".h", "").replace(".H", "")
                candidates_to_try = [
                    base,                                          # Adafruit_INA219
                    base.replace('_', ' '),                        # Adafruit INA219
                    base.replace('_', '-'),                        # Adafruit-INA219
                    base.lower(),                                  # adafruit_ina219
                    base.lower().replace('_', ' '),                # adafruit ina219
                    base.lower().replace('_', '-'),                # adafruit-ina219
                ]
                # Deduplicate preserving order
                seen = set()
                unique = []
                for c in candidates_to_try:
                    if c not in seen:
                        seen.add(c)
                        unique.append(c)

                # Phase 1: try direct install with each candidate name
                for lib_name in unique:
                    result = subprocess.run(
                        [arduino_cli, "lib", "install", "--force", lib_name],
                        capture_output=True, text=True, env=env, timeout=timeout
                    )
                    if result.returncode == 0:
                        print(f"  -> Installed '{lib_name}' successfully")
                        return True

                # Phase 2: search the library index with the best query
                query = base.replace('_', ' ')  # use human-readable form
                search_result = subprocess.run(
                    [arduino_cli, "lib", "search", query, "--format", "json"],
                    capture_output=True, text=True, env=env, timeout=30
                )
                if search_result.returncode == 0 and search_result.stdout.strip():
                    candidates = []
                    try:
                        parsed = json.loads(search_result.stdout)
                        if isinstance(parsed, dict):
                            for lib in parsed.get('libraries', []):
                                name = lib.get('Name', '').strip()
                                if name:
                                    candidates.append(name)
                        elif isinstance(parsed, list):
                            for lib in parsed:
                                name = lib.get('Name', '').strip() if isinstance(lib, dict) else ''
                                if name:
                                    candidates.append(name)
                    except json.JSONDecodeError:
                        for line in search_result.stdout.strip().split('\n'):
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                entry = json.loads(line)
                                if isinstance(entry, dict):
                                    name = entry.get("Name", "").strip()
                                    if name:
                                        candidates.append(name)
                            except json.JSONDecodeError:
                                continue
                    for lib_name in candidates:
                        print(f"  -> Trying search result: '{lib_name}'")
                        if try_install_library(lib_name, timeout):
                            return True

                print(f"  -> Could not find library for header '{header_name}'")
                return False
            except subprocess.TimeoutExpired:
                print(f"  -> Timeout searching for '{header_name}'")
                return False
            except subprocess.SubprocessError as e:
                print(f"  -> Error searching for '{header_name}': {e}")
                return False

        # --- Phase 1: Install mapped libraries from known includes (forced every time) ---
        for include_directive, lib_names in HEADER_TO_LIB.items():
            if include_directive in source_code:
                for lib_name in lib_names:
                    try_install_library(lib_name, timeout=90)

        # --- Phase 2: Dynamically parse all #include <...> from source ---
        dynamic_includes = set()
        for match in re.finditer(r'#include\s+<([^>]+)>', source_code):
            header = match.group(1)
            # Skip standard/stdlib includes (no .h or known core headers)
            if '.h' not in header and '.H' not in header:
                continue
            # Skip already-handled mapped headers
            include_key = f"#include <{header}>"
            if include_key in HEADER_TO_LIB:
                continue
            dynamic_includes.add(header)

        for header in dynamic_includes:
            search_and_install_library(header, timeout=90)

        # --- Phase 3: Check and install board core if missing ---
        board_core = board_fqbn.split(":")[0] + ":" + board_fqbn.split(":")[1] if ':' in board_fqbn else ""
        if board_core:
            try:
                result = subprocess.run(
                    [arduino_cli, "core", "list", "--format", "json"],
                    capture_output=True, text=True, env=env, timeout=30
                )
                core_installed = False
                if result.returncode == 0 and result.stdout.strip():
                    try:
                        parsed = json.loads(result.stdout)
                        items = parsed if isinstance(parsed, list) else []
                        for entry in items:
                            core_id = entry.get("Id", "").strip() if isinstance(entry, dict) else ''
                            if core_id == board_core:
                                core_installed = True
                                break
                    except json.JSONDecodeError:
                        for line in result.stdout.strip().split('\n'):
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                entry = json.loads(line)
                                if isinstance(entry, dict):
                                    core_id = entry.get("Id", "").strip()
                                    if core_id == board_core:
                                        core_installed = True
                                        break
                            except json.JSONDecodeError:
                                continue

                if not core_installed:
                    print(f"Board core '{board_core}' not found. Installing...")
                    install_cmd = [arduino_cli, "core", "install", board_core]
                    result = subprocess.run(install_cmd, capture_output=True, text=True, env=env, timeout=300)
                    if result.returncode == 0:
                        print(f"Board core '{board_core}' installed successfully")
                    else:
                        print(f"Failed to install board core '{board_core}': {result.stderr[:300]}")
            except subprocess.TimeoutExpired:
                print(f"Timeout checking/installing board core '{board_core}'")
            except subprocess.SubprocessError as e:
                print(f"Error checking board core: {e}")

        if not board_fqbn:
            return {
                'success': False,
                'message': 'No FQBN provided for compilation.'
            }

        print(f"Compiling sketch for {board_fqbn}...")
        cmd = [
            arduino_cli, 
            "compile", 
            "--fqbn", board_fqbn,
            "--build-path", build_dir,
        ]
        if os.path.exists(config_path):
            cmd.extend(["--config-file", config_path])
        if board_options:
            cmd.extend(["--board-options", board_options])
        cmd.append(sketch_dir)
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env, timeout=300)
            print("Compilation successful.")
            
            # Extract memory usage info from stdout
            # Example: Sketch uses 235940 bytes (17%) of program storage space. Maximum is 1310720 bytes.
            # Global variables use 15536 bytes (4%) of dynamic memory, leaving 312144 bytes for local variables. Maximum is 327680 bytes.
            memory_info = {}
            
            # Program storage
            prog_match = re.search(r"Sketch uses (\d+) bytes \(([\d%]+)\) of program storage space\. Maximum is (\d+) bytes\.", result.stdout)
            if prog_match:
                memory_info['program_bytes'] = int(prog_match.group(1))
                memory_info['program_percent'] = prog_match.group(2)
                memory_info['program_max'] = int(prog_match.group(3))
            
            # Dynamic memory
            dynamic_match = re.search(r"Global variables use (\d+) bytes \(([\d%]+)\) of dynamic memory.*Maximum is (\d+) bytes\.", result.stdout)
            if dynamic_match:
                memory_info['dynamic_bytes'] = int(dynamic_match.group(1))
                memory_info['dynamic_percent'] = dynamic_match.group(2)
                memory_info['dynamic_max'] = int(dynamic_match.group(3))

            board_type = 'esp8266' if 'esp8266' in board_fqbn.lower() else ('esp32' if 'esp32' in board_fqbn.lower() else 'avr')
            
            is_c3 = 'esp32c3' in board_fqbn.lower()
            flash_config = None
            if 'esp32' in board_fqbn.lower():
                flash_config = {'flashSize': '4MB', 'flashMode': 'dio', 'flashFreq': '80m'}
                if board_options:
                    for opt in board_options.split(','):
                        kv = opt.strip().split('=', 1)
                        if len(kv) == 2:
                            k, v = kv
                            if k == 'FlashSize':
                                flash_config['flashSize'] = v.replace('M', 'MB') if v else '4MB'
                            elif k == 'FlashMode':
                                flash_config['flashMode'] = v if v else 'dio'

            response_base = {
                'success': True,
                'board_type': board_type,
                'message': 'Compilation successful.',
                'logs': result.stdout,
                'compile_info': {
                    'memory': memory_info,
                    'fqbn': board_fqbn,
                },
            }
            if flash_config:
                response_base['flash_config'] = flash_config

            if board_type == 'avr':
                # Read the generated .hex file from build_dir
                hex_path = os.path.join(build_dir, f"{sketch_name}.ino.hex")
                if not os.path.exists(hex_path):
                    # Fallback to sketch_dir if it somehow ended up there
                    hex_path = os.path.join(sketch_dir, f"{sketch_name}.ino.hex")
                    
                if os.path.exists(hex_path):
                    with open(hex_path, 'r', encoding='utf-8') as f:
                        hex_content = f.read()
                    
                    response_base['hex_content'] = hex_content
                    return response_base
            else:
                # Read all generated component binaries for ESP32 / ESP8266
                # We return ALL files (bootloader + partitions + app) so the browser
                # can flash them at their correct addresses. This is more reliable than
                # relying on a merged binary which may not be generated by older arduino-cli.
                
                def read_binary(rel_path):
                    full = os.path.join(build_dir, rel_path)
                    if os.path.exists(full):
                        with open(full, 'rb') as f:
                            return base64.b64encode(f.read()).decode('utf-8')
                    return None

                flash_files = []
                
                if board_type == 'esp32':
                    is_c3 = 'esp32c3' in board_fqbn.lower()
                    merged = read_binary(f"{sketch_name}.ino.merged.bin")

                    if is_c3:
                        # ESP32-C3 (RISC-V): prefer merged.bin (exact layout for this board)
                        if merged:
                            flash_files.append({"data": merged, "address": 0x0, "name": "merged"})
                        else:
                            bootloader = read_binary(f"{sketch_name}.ino.bootloader.bin")
                            partitions = read_binary(f"{sketch_name}.ino.partitions.bin")
                            app = read_binary(f"{sketch_name}.ino.bin")
                            if bootloader:
                                flash_files.append({"data": bootloader, "address": 0x0000, "name": "bootloader"})
                            if partitions:
                                flash_files.append({"data": partitions, "address": 0x8000, "name": "partitions"})
                            if app:
                                flash_files.append({"data": app, "address": 0x10000, "name": "app"})
                    else:
                        # Standard ESP32 (Xtensa) — bootloader at 0x1000
                        bootloader = read_binary(f"{sketch_name}.ino.bootloader.bin")
                        partitions = read_binary(f"{sketch_name}.ino.partitions.bin")
                        app = read_binary(f"{sketch_name}.ino.bin")
                        if bootloader:
                            flash_files.append({"data": bootloader, "address": 0x1000, "name": "bootloader"})
                        if partitions:
                            flash_files.append({"data": partitions, "address": 0x8000, "name": "partitions"})
                        boot_app0 = read_binary(f"{sketch_name}.ino.boot_app0.bin")
                        if boot_app0:
                            flash_files.append({"data": boot_app0, "address": 0xE000, "name": "boot_app0"})
                        if app:
                            flash_files.append({"data": app, "address": 0x10000, "name": "app"})

                    # If no individual components found, try merged binary as fallback
                    if not flash_files:
                        if not merged:
                            merged = read_binary(f"{sketch_name}.ino.merged.bin")
                        if merged:
                            flash_files.append({"data": merged, "address": 0x0, "name": "merged"})
                
                elif board_type == 'esp8266':
                    # ESP8266: bootloader at 0x0, app at user-specified offset
                    bootloader = read_binary(f"{sketch_name}.ino.bootloader.bin")
                    app = read_binary(f"{sketch_name}.ino.bin")
                    if bootloader:
                        flash_files.append({"data": bootloader, "address": 0x0, "name": "bootloader"})
                    if app:
                        flash_files.append({"data": app, "address": 0x10000, "name": "app"})
                    
                    if not flash_files:
                        merged = read_binary(f"{sketch_name}.ino.merged.bin")
                        if merged:
                            flash_files.append({"data": merged, "address": 0x0, "name": "merged"})

                # Always try merged binary as universal fallback
                if not flash_files:
                    merged = read_binary(f"{sketch_name}.ino.merged.bin")
                    if merged:
                        flash_files.append({"data": merged, "address": 0x0, "name": "merged"})

                if flash_files:
                    # Also keep single-bin fields for backward compatibility
                    primary = flash_files[-1]  # app or merged, whichever was added last
                    response_base['flash_files'] = flash_files
                    response_base['bin_content'] = primary['data']
                    response_base['flash_address'] = primary['address']
                    response_base['message'] = f'Compilation successful. {len(flash_files)} binary file(s) generated.'
                    return response_base

            return {
                'success': False,
                'message': 'Output file was not generated.',
                'logs': result.stdout + "\n" + result.stderr
            }
                
        except subprocess.CalledProcessError as e:
            # Diagnostic: Check what cores and config the server actually sees
            diag_cmd = [arduino_cli, "core", "list"]
            diag_res = subprocess.run(diag_cmd, capture_output=True, text=True, env=env)
            config_cmd = [arduino_cli, "config", "dump"]
            config_res = subprocess.run(config_cmd, capture_output=True, text=True, env=env)
            
            error_logs = (
                f"COMMAND: {' '.join(cmd)}\n"
                f"STDOUT: {e.stdout}\nSTDERR: {e.stderr}\n"
                f"--- DIAGNOSTICS ---\n"
                f"Running as user: {whoami}\n"
                f"Cores seen by server:\n{diag_res.stdout}\n"
                f"Config dump:\n{config_res.stdout}\n"
                f"Environment ARDUINO_DIRECTORIES_DATA: {env.get('ARDUINO_DIRECTORIES_DATA')}"
            )
            return {
                'success': False,
                'message': 'Compilation failed.',
                'logs': error_logs
            }


def upload_firmware(port: str, firmware_path: str, board_type: str = 'arduino:avr:uno') -> dict[str, Any]:
    """
    [DEPRECATED / SERVER-SIDE ONLY]
    Uploads firmware to the specified port using avrdude.
    """
    
    # Check if avrdude exists
    avrdude_path = shutil.which('avrdude')
    
    if not avrdude_path:
        # Simulation mode for development enabling
        return {
            'success': False,
            'message': 'avrdude not found. Board upload is disabled.',
            'details': 'To enable uploads, please <a href="https://github.com/avrdudes/avrdude/releases" target="_blank">download AVRDUDE</a>, extract it, and add the folder to your system PATH. (Simulation: Upload would run <code>avrdude -F -V -c arduino -p ATMEGA328P -P ' + str(port) + ' -b 115200 -U flash:w:' + str(firmware_path) + '</code>)'
        }

    # Basic command for Arduino Uno (ATmega328P)
    # Adjust parameters as needed or make them dynamic based on board selection
    command = [
        avrdude_path,
        "-F", "-V",
        "-c", "arduino",
        "-p", "ATMEGA328P",
        "-P", port,
        "-b", "115200",
        "-U", f"flash:w:{firmware_path}"
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return {
            'success': True,
            'message': 'Upload successful.',
            'details': result.stdout
        }
    except subprocess.CalledProcessError as e:
        return {
            'success': False,
            'message': 'Upload failed.',
            'details': e.stderr
        }
