class GlobalSerialManager {
    constructor() {
        this.port = null;
        this.reader = null;
        this.writer = null;
        this.currentBaud = null;
        this.isBusy = false;
        this.globalError = null;
    }

    async getPort(requestedPort = null) {
        if (requestedPort) {
            this.port = requestedPort;
        } else {
            this.port = await navigator.serial.requestPort();
        }
        return this.port;
    }

    async open(baudRate, retryCount = 0) {
        if (!this.port) throw new Error("No port selected.");

        if (this.port.readable) {
            if (retryCount === 0) {
                console.log("GlobalSerialManager: Port already open, closing and retrying...");
                try { await this.port.close(); } catch (e) {}
                await new Promise(r => setTimeout(r, 1000));
                return this.open(baudRate, retryCount + 1);
            }
            throw new Error("시리얼 포트가 이미 다른 탭에서 사용 중입니다. 다른 탭을 닫고 다시 시도하세요.");
        }

        console.log(`GlobalSerialManager: Opening port at ${baudRate} baud...`);
        try {
            await this.port.open({ baudRate: baudRate });
        } catch (err) {
            if (err.message.includes('already open') && retryCount < 8) {
                console.log(`GlobalSerialManager: Port conflict, retrying (attempt ${retryCount + 1})...`);
                try { await this.port.close(); } catch (e) {}
                await new Promise(r => setTimeout(r, 2000));
                return this.open(baudRate, retryCount + 1);
            }
            throw err;
        }
        this.currentBaud = baudRate;
        await new Promise(r => setTimeout(r, 100));
        return this.port;
    }

    async close() {
        console.log("GlobalSerialManager: Closing port and releasing locks...");
        if (this.reader) {
            try {
                await this.reader.cancel();
                this.reader.releaseLock();
            } catch (e) {
                console.warn("GlobalSerialManager: Reader release error:", e);
            }
            this.reader = null;
        }
        if (this.writer) {
            try {
                this.writer.releaseLock();
            } catch (e) {
                console.warn("GlobalSerialManager: Writer release error:", e);
            }
            this.writer = null;
        }
        let hadPort = false;
        if (this.port) {
            hadPort = true;
            try {
                if (this.port.readable) {
                    console.log("GlobalSerialManager: Closing serial port...");
                    await this.port.close();
                    console.log("GlobalSerialManager: Port closed successfully.");
                }
            } catch (e) { 
                console.error("GlobalSerialManager: Port close failed:", e);
            }
            this.port = null;
        }
        this.currentBaud = null;
        this.isBusy = false;
        if (hadPort) {
            await new Promise(r => setTimeout(r, 1000));
        }
    }

    async nukeAllPorts() {
        console.log("GlobalSerialManager: Nuking all authorized ports...");
        try {
            const ports = await navigator.serial.getPorts();
            for (const port of ports) {
                try {
                    if (port.readable) {
                        console.log("GlobalSerialManager: Force-closing a port...", port.getInfo());
                        await port.close();
                    }
                } catch (e) {
                    console.warn("GlobalSerialManager: Failed to nuke a port:", e);
                }
            }
        } catch (e) {
            console.error("GlobalSerialManager: Nuke failed:", e);
        }
        this.port = null;
        this.reader = null;
        this.writer = null;
        await new Promise(r => setTimeout(r, 500));
    }
}

window.arduinoSerialManager = new GlobalSerialManager();

class ArduinoUploader {
    constructor(statusCallback, options = {}) {
        this.statusCallback = statusCallback || console.log;
        this.buffer = [];
        this.readLoopActive = false;
        this.readLoopPromise = null;
        this.messages = {
            connected: "Connected at {baud} baud.",
            connection_failed: "Connection failed: {error}",
            read_loop_error: "Read loop error: {error}",
            write_error: "Write error: {error}",
            parsing_hex: "Parsing hex file...",
            firmware_size: "Firmware size: {size} bytes",
            resetting: "Resetting board (DTR/RTS pulse)...",
            synchronizing: "Synchronizing...",
            sync_attempt: "Sync attempt {attempt}/40...",
            sync_failed: "Failed to sync with bootloader. Ensure correct board/baud and try manual reset.",
            entering_prog: "Entering programming mode...",
            writing_page: "Writing page at 0x{address}...",
            failed_set_address: "Failed to set address.",
            failed_prog_page: "Failed to program page.",
            upload_complete: "Upload complete!",
            no_port_esp32: "No port connected for ESP32 upload.",
            preparing_esp32: "Preparing ESP32 upload process...",
            binary_size: "Binary size: {size} bytes",
            target_address: "Target Address: 0x{address}",
            connecting_esp32: "Connecting to ESP32 bootloader...",
            boot_button_hint: "Please hold the BOOT button if it fails to connect.",
            handshaking: "Handshaking...",
            handshake_success: "Handshake successful. Starting flash...",
            flashing_esp32: "0x{address} 주소에 펌웨어 플래싱 중...",
            flash_complete: "Flash complete!",
            esp32_failed: "ESP32 Upload failed: {error}",
            esp32_hint: "Hint: Try holding the BOOT button on the ESP32 during the 'Connecting...' phase.",
            no_port_esp8266: "No port connected for ESP8266 upload.",
            preparing_esp8266: "Preparing ESP8266 upload process...",
            connecting_esp8266: "Connecting to ESP8266 bootloader...",
            flashing_esp8266: "0x{address} 주소에 펌웨어 플래싱 중...",
            esp8266_failed: "ESP8266 Upload failed: {error}",
            monitor_connected: "Connected to Serial Monitor at {baud} baud.",
            monitor_failed: "Serial Monitor connection failed: {error}",
            monitor_disconnected: "Serial Monitor Disconnected.",
            ...(options.messages || {})
        };
    }

    t(key, params = {}) {
        let msg = this.messages[key] || key;
        for (const [p, val] of Object.entries(params)) {
            msg = msg.replace(`{${p}}`, val);
        }
        return msg;
    }

    log(msg, type = 'info') {
        this.statusCallback(msg, type);
    }

    async connect(baudRate = 115200) {
        try {
            await window.arduinoSerialManager.close();
            const port = await window.arduinoSerialManager.getPort();
            if (port.readable) {
                console.log("ArduinoUploader: Got already-open port, closing it...");
                await window.arduinoSerialManager.close();
                if (port.readable) {
                    throw new Error("다른 탭에서 이미 시리얼 포트를 사용 중입니다. 다른 탭을 닫고 다시 시도하세요.");
                }
            }
            await window.arduinoSerialManager.open(baudRate);
            window.arduinoSerialManager.writer = port.writable.getWriter();
            window.arduinoSerialManager.reader = port.readable.getReader();
            this.log(this.t('connected', { baud: baudRate }));
            this.readLoopActive = true;
            this.readLoopPromise = this.startReadLoop();
            return true;
        } catch (err) {
            let msg = err.message;
            if (msg.includes('Failed to open serial port')) {
                msg = '시리얼 포트를 열 수 없습니다. 1) 아두이노 IDE, PuTTY 등 다른 프로그램이 포트를 사용 중인지 확인하세요. 2) USB 케이블이 제대로 연결되어 있는지 확인하세요. 3) 장치의 드라이버가 올바르게 설치되었는지 확인하세요.';
            }
            this.log(this.t('connection_failed', { error: msg }), "error");
            await window.arduinoSerialManager.close();
            return false;
        }
    }

    async startReadLoop() {
        const reader = window.arduinoSerialManager.reader;
        try {
            while (this.readLoopActive && reader) {
                const { value, done } = await reader.read();
                if (done) break;
                if (value) {
                    for (let b of value) this.buffer.push(b);
                }
            }
        } catch (e) {
            if (this.readLoopActive) console.warn("ArduinoUploader: Read loop stopped:", e.message);
        }
    }

    async disconnect() {
        this.readLoopActive = false;
        await window.arduinoSerialManager.close();
        if (this.readLoopPromise) {
            await Promise.race([this.readLoopPromise, new Promise(r => setTimeout(r, 200))]);
            this.readLoopPromise = null;
        }
    }

    async sendCommand(cmd, timeout = 1000) {
        const writer = window.arduinoSerialManager.writer;
        if (!writer) return [];
        this.buffer = [];
        try {
            await writer.write(new Uint8Array(cmd));
        } catch (e) {
            this.log(this.t('write_error', { error: e.message }), "error");
            return [];
        }
        const start = Date.now();
        while (Date.now() - start < timeout) {
            if (this.buffer.length >= 2) {
                const syncIdx = this.buffer.indexOf(0x14);
                const endIdx = this.buffer.indexOf(0x10, syncIdx + 1);
                if (syncIdx !== -1 && endIdx !== -1) {
                    const res = this.buffer.slice(syncIdx, endIdx + 1);
                    this.buffer = this.buffer.slice(endIdx + 1);
                    return res;
                }
            }
            await new Promise(r => setTimeout(r, 10));
        }
        return [];
    }

    parseHex(hexString) {
        const lines = hexString.split(/\r?\n/);
        const data = new Uint8Array(32768);
        let maxAddr = 0;
        for (let line of lines) {
            line = line.trim();
            if (line[0] !== ':') continue;
            const byteCount = parseInt(line.substring(1, 3), 16);
            const addr = parseInt(line.substring(3, 7), 16);
            const recordType = parseInt(line.substring(7, 9), 16);
            if (recordType === 0) {
                for (let i = 0; i < byteCount; i++) {
                    const start = 9 + (i * 2);
                    data[addr + i] = parseInt(line.substring(start, start + 2), 16);
                }
                maxAddr = Math.max(maxAddr, addr + byteCount);
            }
        }
        return data.slice(0, maxAddr);
    }

    async upload(hexString) {
        try {
            this.log(this.t('parsing_hex'));
            const firmware = this.parseHex(hexString);
            this.log(this.t('firmware_size', { size: firmware.length }));
            const port = window.arduinoSerialManager.port;
            this.log(this.t('resetting'));
            await port.setSignals({ dataTerminalReady: false, requestToSend: false });
            await new Promise(r => setTimeout(r, 200));
            await port.setSignals({ dataTerminalReady: true, requestToSend: true });
            await new Promise(r => setTimeout(r, 200));
            await port.setSignals({ dataTerminalReady: false, requestToSend: false });
            await new Promise(r => setTimeout(r, 500));
            this.buffer = [];
            this.log(this.t('synchronizing'));
            let synced = false;
            for (let i = 0; i < 40; i++) {
                const res = await this.sendCommand([0x30, 0x20], 100);
                if (res.length >= 2) { synced = true; break; }
                if (i % 5 === 0) this.log(this.t('sync_attempt', { attempt: i }), 'debug');
                await new Promise(r => setTimeout(r, 20));
            }
            if (!synced) { this.log(this.t('sync_failed'), "error"); return false; }
            this.log(this.t('entering_prog'));
            await this.sendCommand([0x50, 0x20]);
            const pageSize = 128;
            for (let addr = 0; addr < firmware.length; addr += pageSize) {
                this.log(this.t('writing_page', { address: addr.toString(16) }));
                const wordAddr = addr >> 1;
                const resAddr = await this.sendCommand([0x55, wordAddr & 0xff, (wordAddr >> 8) & 0xff, 0x20]);
                if (resAddr.length < 2) { this.log(this.t('failed_set_address'), "error"); return false; }
                const pageData = new Uint8Array(pageSize).fill(0xFF);
                const chunk = firmware.slice(addr, addr + pageSize);
                pageData.set(chunk);
                const cmd = [0x64, 0x00, pageSize, 0x46, ...pageData, 0x20];
                const resProg = await this.sendCommand(cmd, 2000);
                if (resProg.length < 2) { this.log(this.t('failed_prog_page'), "error"); return false; }
            }
            await this.sendCommand([0x51, 0x20]);
            this.log(this.t('upload_complete'), "success");
            return true;
        } catch (err) {
            this.log("Upload error: " + err.message, "error");
            return false;
        } finally {
            await this.disconnect();
        }
    }

    async uploadEsp8266(base64Bin, flashAddress = 0x0, baudRate = 460800) {
        try {
            this.log(this.t('preparing_esp8266'));
            this.readLoopActive = false;
            if (window.arduinoSerialManager.reader) {
                try {
                    await window.arduinoSerialManager.reader.cancel();
                    window.arduinoSerialManager.reader.releaseLock();
                } catch (e) {
                    console.warn("ArduinoUploader: Error releasing reader lock:", e);
                }
                window.arduinoSerialManager.reader = null;
            }
            if (window.arduinoSerialManager.writer) {
                try {
                    window.arduinoSerialManager.writer.releaseLock();
                } catch (e) {
                    console.warn("ArduinoUploader: Error releasing writer lock:", e);
                }
                window.arduinoSerialManager.writer = null;
            }
            const port = window.arduinoSerialManager.port;
            if (port && port.readable) {
                console.log("ArduinoUploader: Closing port for ESP8266 handover...");
                try {
                    await port.close();
                    await new Promise(r => setTimeout(r, 1000));
                    console.log("ArduinoUploader: Port closed status:", port.readable);
                } catch (e) {
                    console.warn("ArduinoUploader: Minor error closing port before ESP8266 flash:", e);
                }
            }
            if (port && port.readable) {
                throw new Error("시리얼 포트가 정상적으로 닫히지 않았습니다. 잠시 후 다시 시도하거나 페이지를 새로고침하세요.");
            }
            const binaryString = atob(base64Bin);
            const binData = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
                binData[i] = binaryString.charCodeAt(i);
            }
            const esploader = new esptooljs.ESPLoader({
                port: port,
                baudrate: baudRate,
                terminal: {
                    clean: () => { },
                    writeLine: (data) => this.log(data),
                    write: (data) => console.log(data)
                }
            });
            this.log(this.t('connecting_esp8266'));
            await esploader.main();
            this.log(this.t('handshake_success'), "success");
            this.log("Erasing all flash (this may take a minute)...");
            await esploader.eraseFlash();
            this.log(this.t('flashing_esp8266', { address: flashAddress.toString(16) }));
            await esploader.writeFlash({
                fileArray: [{ data: binaryString, address: flashAddress }],
                flashSize: '4MB', 
                flashMode: 'dio', 
                flashFreq: '80m',
                eraseAll: false, 
                compress: true
            });
            this.log(this.t('flash_complete'), "success");
            await esploader.after();
            return true;
        } catch (err) {
            this.log(this.t('esp8266_failed', { error: err.message }), "error");
            return false;
        } finally {
            await this.disconnect();
        }
    }

    async releaseSerialForEsptool() {
        this.readLoopActive = false;
        if (window.arduinoSerialManager.reader) {
            try {
                await window.arduinoSerialManager.reader.cancel();
                window.arduinoSerialManager.reader.releaseLock();
            } catch (e) { }
            window.arduinoSerialManager.reader = null;
        }
        if (window.arduinoSerialManager.writer) {
            try {
                window.arduinoSerialManager.writer.releaseLock();
            } catch (e) { }
            window.arduinoSerialManager.writer = null;
        }
        const port = window.arduinoSerialManager.port;
        if (port && port.readable) {
            console.log("ArduinoUploader: Closing port for ESP32 handover...");
            try {
                await port.close();
                await new Promise(r => setTimeout(r, 1000));
            } catch (e) { }
        }
        if (port && port.readable) {
            throw new Error("시리얼 포트가 정상적으로 닫히지 않았습니다. 잠시 후 다시 시도하거나 페이지를 새로고침하세요.");
        }
        return port;
    }

    async createEsptoolConnection(port, baudRate) {
        const esploader = new esptooljs.ESPLoader({
            port: port,
            baudrate: baudRate,
            terminal: {
                clean: () => { },
                writeLine: (data) => this.log(data),
                write: (data) => console.log(data)
            }
        });
        this.log(this.t('connecting_esp32'));
        await esploader.main();
        this.log(this.t('handshake_success'), "success");
        return esploader;
    }

    async uploadEsp32Multi(flashFiles, baudRate = 460800, flashConfig = null) {
        try {
            this.log(this.t('preparing_esp32'));
            const port = await this.releaseSerialForEsptool();
            if (!port) throw new Error("No serial port available.");
            const fileArray = flashFiles.map(f => ({
                data: atob(f.data),
                address: f.address
            }));
            const totalBytes = fileArray.reduce((sum, f) => sum + f.data.length, 0);
            this.log(`총 ${flashFiles.length}개 파일, ${totalBytes.toLocaleString()} 바이트 준비 완료`);
            flashFiles.forEach(f => {
                this.log(`  - ${f.name}: 0x${f.address.toString(16)} (${atob(f.data).length.toLocaleString()} bytes)`);
            });
            const esploader = await this.createEsptoolConnection(port, baudRate);
            this.log("전체 플래시 메모리 쓰기 시작 (부트로더 + 파티션 + 앱)...");
            const fc = flashConfig || {};
            await esploader.writeFlash({
                fileArray: fileArray,
                flashSize: fc.flashSize || '4MB',
                flashMode: fc.flashMode || 'dio',
                flashFreq: fc.flashFreq || '80m',
                eraseAll: true,
                compress: true
            });
            this.log(this.t('flash_complete'), "success");
            await esploader.after();
            return true;
        } catch (err) {
            this.log(this.t('esp32_failed', { error: err.message }), "error");
            return false;
        } finally {
            await this.disconnect();
        }
    }

    async uploadEsp32(base64Bin, flashAddress = 0x10000, baudRate = 460800, flashConfig = null) {
        return this.uploadEsp32Multi([
            { data: base64Bin, address: flashAddress, name: 'app' }
        ], baudRate, flashConfig);
    }
}

class SerialMonitor {
    constructor(outputCallback, options = {}) {
        this.outputCallback = outputCallback || console.log;
        this.keepReading = false;
        this.readLoopPromise = null;
        this.messages = {
            connected: "Connected to Serial Monitor at {baud} baud.",
            failed: "Serial Monitor connection failed: {error}",
            disconnected: "Serial Monitor Disconnected.",
            ...(options.messages || {})
        };
    }

    t(key, params = {}) {
        let msg = this.messages[key] || key;
        for (const [p, val] of Object.entries(params)) {
            msg = msg.replace(`{${p}}`, val);
        }
        return msg;
    }

    async getAuthorizedPorts() {
        return await navigator.serial.getPorts();
    }

    async connect(baudRate = 115200, portInstance = null) {
        try {
            await window.arduinoSerialManager.close();
            const port = await window.arduinoSerialManager.getPort(portInstance);
            if (port.readable) {
                console.log("SerialMonitor: Got already-open port, closing it...");
                await window.arduinoSerialManager.close();
                if (port.readable) {
                    throw new Error("다른 탭에서 이미 시리얼 포트를 사용 중입니다. 다른 탭을 닫고 다시 시도하세요.");
                }
            }
            await window.arduinoSerialManager.open(baudRate);
            this.outputCallback(this.t('connected', { baud: baudRate }), "success");
            this.keepReading = true;
            this.readLoopPromise = this.readLoop();
            return true;
        } catch (err) {
            let msg = err.message;
            if (msg.includes('Failed to open serial port')) {
                msg = '시리얼 포트를 열 수 없습니다. 1) 아두이노 IDE, PuTTY 등 다른 프로그램이 포트를 사용 중인지 확인하세요. 2) USB 케이블이 제대로 연결되어 있는지 확인하세요. 3) 장치의 드라이버가 올바르게 설치되었는지 확인하세요.';
            }
            this.outputCallback(this.t('failed', { error: msg }), "error");
            await window.arduinoSerialManager.close();
            return false;
        }
    }

    async readLoop() {
        const port = window.arduinoSerialManager.port;
        if (!port || !port.readable) return;
        window.arduinoSerialManager.reader = port.readable.getReader();
        const decoder = new TextDecoder();
        try {
            while (this.keepReading && window.arduinoSerialManager.reader) {
                const { value, done } = await window.arduinoSerialManager.reader.read();
                if (done) break;
                if (value) {
                    const text = decoder.decode(value);
                    this.outputCallback(text, "data");
                }
            }
        } catch (error) {
            if (this.keepReading) this.outputCallback("Read error: " + error.message, "error");
        } finally {
            if (window.arduinoSerialManager.reader) {
                window.arduinoSerialManager.reader.releaseLock();
                window.arduinoSerialManager.reader = null;
            }
        }
    }

    async disconnect() {
        this.keepReading = false;
        await window.arduinoSerialManager.close();
        if (this.readLoopPromise) {
            await Promise.race([this.readLoopPromise, new Promise(r => setTimeout(r, 200))]);
            this.readLoopPromise = null;
        }
        this.outputCallback(this.t('disconnected'), "info");
    }
}
