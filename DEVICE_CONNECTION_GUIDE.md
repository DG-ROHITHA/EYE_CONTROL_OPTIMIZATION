# 🔌 Device Connection & Extended Controls Guide

## 📋 Table of Contents
1. [Extended Keyboard Controls](#extended-keyboard-controls)
2. [Connecting to Arduino/Microcontrollers](#connecting-to-arduinomicrocontrollers)
3. [Smart Home Integration](#smart-home-integration)
4. [IoT Device Control](#iot-device-control)
5. [Serial Communication](#serial-communication)
6. [Network/Wi-Fi Devices](#networkwi-fi-devices)
7. [Bluetooth Devices](#bluetooth-devices)

---

## 🎮 Extended Keyboard Controls

### **Already Available Commands**

#### **Basic Navigation**
| Gaze Direction | Command | Action |
|----------------|---------|--------|
| UP | SCROLL_UP | Scroll up |
| DOWN | SCROLL_DOWN | Scroll down |
| LEFT | LEFT | Arrow left |
| RIGHT | RIGHT | Arrow right |

#### **Blink Commands**
| Blink | Command | Action |
|-------|---------|--------|
| Single blink | CLICK | Mouse click |
| Double blink | DOUBLE_CLICK | Double click |
| Long blink (3s) | EMERGENCY_ALERT | Emergency alert |
| Eyes closed (5s) | SLEEP_MODE | Sleep mode |

#### **Diagonal Controls**
| Direction | Command | Action |
|-----------|---------|--------|
| UP-LEFT | VOLUME_UP | Increase volume |
| UP-RIGHT | BRIGHTNESS_UP | Increase brightness |
| DOWN-LEFT | BACK | Browser back |
| DOWN-RIGHT | HOME | Go to home |

#### **Pattern Commands**
| Pattern | Command | Action |
|---------|---------|--------|
| L → R → L | CALL_NURSE | Call assistance |
| U → D → U | ADJUST_BED | Bed adjustment |
| L → L → R → R | EMERGENCY | Emergency protocol |

---

## 🔌 Connecting to Arduino/Microcontrollers

### **Method 1: Serial Communication (Recommended)**

#### **1. Arduino Setup**

Create this Arduino sketch:

```cpp
// Arduino Code for Eye-Tracking Control
void setup() {
  Serial.begin(9600);
  
  // Setup pins for devices
  pinMode(13, OUTPUT);  // LED/Relay 1
  pinMode(12, OUTPUT);  // LED/Relay 2
  pinMode(11, OUTPUT);  // LED/Relay 3
  pinMode(10, OUTPUT);  // LED/Relay 4
}

void loop() {
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    
    // Process commands from eye-tracking
    if (command == "LIGHT_ON") {
      digitalWrite(13, HIGH);
      Serial.println("LIGHT_ON_OK");
    }
    else if (command == "LIGHT_OFF") {
      digitalWrite(13, LOW);
      Serial.println("LIGHT_OFF_OK");
    }
    else if (command == "FAN_ON") {
      digitalWrite(12, HIGH);
      Serial.println("FAN_ON_OK");
    }
    else if (command == "FAN_OFF") {
      digitalWrite(12, LOW);
      Serial.println("FAN_OFF_OK");
    }
    else if (command == "CALL_NURSE") {
      // Activate buzzer/notification
      tone(9, 1000, 500);  // Buzzer on pin 9
      Serial.println("NURSE_CALLED");
    }
    else if (command == "EMERGENCY") {
      // Emergency alert
      for(int i=0; i<10; i++) {
        digitalWrite(13, HIGH);
        tone(9, 1000, 100);
        delay(100);
        digitalWrite(13, LOW);
        delay(100);
      }
      Serial.println("EMERGENCY_ACTIVATED");
    }
  }
}
```

#### **2. Python Integration**

Add this to your eye-tracking code:

```python
import serial
import time

class ArduinoController:
    """Control Arduino devices via serial"""
    def __init__(self, port='COM3', baud_rate=9600):
        try:
            self.serial = serial.Serial(port, baud_rate, timeout=1)
            time.sleep(2)  # Wait for Arduino to initialize
            print(f"✓ Connected to Arduino on {port}")
        except Exception as e:
            print(f"✗ Could not connect to Arduino: {e}")
            self.serial = None
    
    def send_command(self, command):
        """Send command to Arduino"""
        if self.serial:
            try:
                self.serial.write(f"{command}\n".encode())
                response = self.serial.readline().decode().strip()
                print(f"Arduino response: {response}")
                return response
            except Exception as e:
                print(f"Error sending command: {e}")
                return None
    
    def light_on(self):
        return self.send_command("LIGHT_ON")
    
    def light_off(self):
        return self.send_command("LIGHT_OFF")
    
    def fan_on(self):
        return self.send_command("FAN_ON")
    
    def fan_off(self):
        return self.send_command("FAN_OFF")
    
    def call_nurse(self):
        return self.send_command("CALL_NURSE")
    
    def emergency(self):
        return self.send_command("EMERGENCY")
    
    def close(self):
        if self.serial:
            self.serial.close()

# Initialize Arduino controller
arduino = ArduinoController('COM3')  # Change COM3 to your port

# In your command executor, add:
def _execute_real(self, command):
    # ... existing code ...
    
    # Arduino controls
    elif command == "LIGHT_ON":
        arduino.light_on()
    elif command == "LIGHT_OFF":
        arduino.light_off()
    elif command == "FAN_ON":
        arduino.fan_on()
    elif command == "FAN_OFF":
        arduino.fan_off()
    elif command == "CALL_NURSE":
        arduino.call_nurse()
    elif command == "EMERGENCY":
        arduino.emergency()
```

#### **3. Finding Your Arduino Port**

**Windows:**
```python
# List available ports
import serial.tools.list_ports
ports = serial.tools.list_ports.comports()
for port in ports:
    print(f"{port.device} - {port.description}")
```

**Common ports:**
- Windows: COM3, COM4, COM5
- Linux: /dev/ttyUSB0, /dev/ttyACM0
- Mac: /dev/cu.usbmodem1421

#### **4. Install PySerial**
```bash
pip install pyserial
```

---

## 🏠 Smart Home Integration

### **Method 1: Home Assistant Integration**

```python
import requests

class HomeAssistantController:
    """Control Home Assistant devices"""
    def __init__(self, base_url, access_token):
        self.base_url = base_url.rstrip('/')
        self.headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
    
    def turn_on(self, entity_id):
        """Turn on a device"""
        url = f"{self.base_url}/api/services/homeassistant/turn_on"
        data = {'entity_id': entity_id}
        response = requests.post(url, headers=self.headers, json=data)
        return response.status_code == 200
    
    def turn_off(self, entity_id):
        """Turn off a device"""
        url = f"{self.base_url}/api/services/homeassistant/turn_off"
        data = {'entity_id': entity_id}
        response = requests.post(url, headers=self.headers, json=data)
        return response.status_code == 200
    
    def set_brightness(self, entity_id, brightness):
        """Set light brightness (0-255)"""
        url = f"{self.base_url}/api/services/light/turn_on"
        data = {
            'entity_id': entity_id,
            'brightness': brightness
        }
        response = requests.post(url, headers=self.headers, json=data)
        return response.status_code == 200

# Usage
ha = HomeAssistantController(
    'http://192.168.1.100:8123',
    'your_long_lived_access_token'
)

# Control devices
ha.turn_on('light.bedroom')
ha.turn_off('light.bedroom')
ha.set_brightness('light.bedroom', 128)
```

### **Method 2: Direct Smart Device APIs**

#### **Philips Hue**
```python
from phue import Bridge

class HueController:
    def __init__(self, bridge_ip):
        self.bridge = Bridge(bridge_ip)
        self.bridge.connect()
    
    def light_on(self, light_id):
        self.bridge.set_light(light_id, 'on', True)
    
    def light_off(self, light_id):
        self.bridge.set_light(light_id, 'on', False)
    
    def set_brightness(self, light_id, brightness):
        self.bridge.set_light(light_id, 'bri', brightness)

# Install: pip install phue
hue = HueController('192.168.1.2')
hue.light_on(1)
```

#### **TP-Link Smart Plugs**
```python
from kasa import SmartPlug

class TPLinkController:
    def __init__(self, device_ip):
        self.plug = SmartPlug(device_ip)
    
    async def turn_on(self):
        await self.plug.update()
        await self.plug.turn_on()
    
    async def turn_off(self):
        await self.plug.update()
        await self.plug.turn_off()

# Install: pip install python-kasa
```

---

## 📡 IoT Device Control (MQTT)

### **MQTT Integration (For Most IoT Devices)**

```python
import paho.mqtt.client as mqtt

class MQTTController:
    """Control IoT devices via MQTT"""
    def __init__(self, broker, port=1883, username=None, password=None):
        self.client = mqtt.Client()
        
        if username and password:
            self.client.username_pw_set(username, password)
        
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
        self.client.connect(broker, port, 60)
        self.client.loop_start()
    
    def on_connect(self, client, userdata, flags, rc):
        print(f"Connected to MQTT broker with result code {rc}")
    
    def on_message(self, client, userdata, msg):
        print(f"Received: {msg.topic} - {msg.payload.decode()}")
    
    def publish(self, topic, message):
        """Send command to device"""
        self.client.publish(topic, message)
    
    def subscribe(self, topic):
        """Subscribe to device status"""
        self.client.subscribe(topic)
    
    # Device-specific commands
    def light_on(self, device_id):
        self.publish(f"home/{device_id}/light", "ON")
    
    def light_off(self, device_id):
        self.publish(f"home/{device_id}/light", "OFF")
    
    def call_nurse(self):
        self.publish("hospital/nurse/call", "EMERGENCY")

# Install: pip install paho-mqtt

# Usage
mqtt_ctrl = MQTTController('192.168.1.100')
mqtt_ctrl.light_on('bedroom')
```

---

## 🔗 Network/Wi-Fi Devices (HTTP/REST API)

```python
import requests

class NetworkDeviceController:
    """Control network devices via HTTP"""
    
    def __init__(self, base_url):
        self.base_url = base_url
    
    def send_get(self, endpoint):
        """Send GET request"""
        try:
            response = requests.get(f"{self.base_url}{endpoint}")
            return response.json() if response.ok else None
        except Exception as e:
            print(f"Error: {e}")
            return None
    
    def send_post(self, endpoint, data):
        """Send POST request"""
        try:
            response = requests.post(f"{self.base_url}{endpoint}", json=data)
            return response.json() if response.ok else None
        except Exception as e:
            print(f"Error: {e}")
            return None
    
    # Example: ESP8266/ESP32 control
    def light_on(self):
        return self.send_get('/light/on')
    
    def light_off(self):
        return self.send_get('/light/off')
    
    def set_brightness(self, value):
        return self.send_post('/light/brightness', {'value': value})

# Usage
device = NetworkDeviceController('http://192.168.1.50')
device.light_on()
```

---

## 📱 Bluetooth Devices

```python
import bluetooth

class BluetoothController:
    """Control Bluetooth devices"""
    
    def __init__(self, device_address):
        self.address = device_address
        self.socket = None
    
    def connect(self):
        """Connect to Bluetooth device"""
        try:
            self.socket = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            self.socket.connect((self.address, 1))
            print(f"✓ Connected to {self.address}")
            return True
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            return False
    
    def send(self, message):
        """Send message to device"""
        if self.socket:
            try:
                self.socket.send(message.encode())
                return True
            except Exception as e:
                print(f"Error sending: {e}")
                return False
    
    def disconnect(self):
        """Disconnect from device"""
        if self.socket:
            self.socket.close()
    
    @staticmethod
    def discover_devices():
        """Find nearby Bluetooth devices"""
        print("Searching for devices...")
        devices = bluetooth.discover_devices(lookup_names=True)
        for addr, name in devices:
            print(f"  {name} - {addr}")
        return devices

# Install: pip install pybluez

# Usage
bt = BluetoothController('XX:XX:XX:XX:XX:XX')
if bt.connect():
    bt.send('LIGHT_ON')
    bt.disconnect()
```

---

## 🎯 Complete Integration Example

Here's how to integrate everything into your eye-tracking system:

```python
# Add to eye_control_optimized.py

# Import controllers
from device_controllers import (
    ArduinoController,
    HomeAssistantController,
    MQTTController,
    NetworkDeviceController,
    BluetoothController
)

# Initialize all controllers
class DeviceManager:
    def __init__(self):
        # Arduino for physical devices
        self.arduino = ArduinoController('COM3')
        
        # MQTT for IoT devices
        self.mqtt = MQTTController('192.168.1.100')
        
        # Home Assistant for smart home
        self.home_assistant = HomeAssistantController(
            'http://192.168.1.100:8123',
            'your_token'
        )
        
        # Network devices
        self.network_device = NetworkDeviceController('http://192.168.1.50')
    
    def execute_command(self, command):
        """Route commands to appropriate devices"""
        
        if command == "LIGHT_ON":
            self.arduino.light_on()
            self.mqtt.light_on('bedroom')
            self.home_assistant.turn_on('light.bedroom')
        
        elif command == "LIGHT_OFF":
            self.arduino.light_off()
            self.mqtt.light_off('bedroom')
            self.home_assistant.turn_off('light.bedroom')
        
        elif command == "CALL_NURSE":
            self.arduino.call_nurse()
            self.mqtt.publish('hospital/nurse/call', 'PATIENT_1')
        
        elif command == "EMERGENCY_ALERT":
            self.arduino.emergency()
            self.mqtt.publish('hospital/emergency', 'CRITICAL')
            # Send SMS, email, etc.
        
        elif command == "FAN_ON":
            self.arduino.fan_on()
            self.network_device.send_get('/fan/on')
        
        # Add more commands...

# Usage in main code
device_manager = DeviceManager()

# In command execution:
def execute(self, command):
    # ... existing pyautogui commands ...
    
    # Device commands
    device_manager.execute_command(command)
```

---

## 🔧 Installation Requirements

```bash
# For Arduino
pip install pyserial

# For MQTT
pip install paho-mqtt

# For Home Assistant / HTTP devices
pip install requests

# For Bluetooth
pip install pybluez

# For TP-Link
pip install python-kasa

# For Philips Hue
pip install phue
```

---

## 📡 Connection Summary Table

| Device Type | Protocol | Python Library | Difficulty |
|-------------|----------|----------------|------------|
| Arduino | Serial (USB) | pyserial | ⭐ Easy |
| ESP8266/ESP32 | Wi-Fi (HTTP) | requests | ⭐ Easy |
| MQTT Devices | Wi-Fi (MQTT) | paho-mqtt | ⭐⭐ Medium |
| Smart Plugs | Wi-Fi (API) | python-kasa | ⭐⭐ Medium |
| Philips Hue | Wi-Fi (API) | phue | ⭐⭐ Medium |
| Home Assistant | Wi-Fi (REST) | requests | ⭐⭐⭐ Advanced |
| Bluetooth | Bluetooth | pybluez | ⭐⭐⭐ Advanced |

---

## 🎮 Adding Custom Commands

To add your own commands, follow this pattern:

1. **Add pattern to SequenceDetector:**
```python
self.patterns = {
    'YOUR_COMMAND': ['UP', 'UP', 'DOWN']  # Your sequence
}
```

2. **Add to CommandExecutor:**
```python
elif command == "YOUR_COMMAND":
    # Your action here
    device_manager.your_function()
```

3. **Test in simulation mode first!**

---

## 💡 Tips for Device Integration

1. **Start Simple:** Begin with Arduino serial communication
2. **Test Separately:** Test device control separately before integrating
3. **Use Simulation Mode:** Always test new commands in simulation
4. **Error Handling:** Add try-except blocks for all device communications
5. **Timeouts:** Set reasonable timeouts for network operations
6. **Feedback:** Provide audio/visual feedback for command execution
7. **Emergency Stop:** Always have a way to stop all devices quickly

---

## 🚨 Safety Considerations

1. **Test Mode:** Always test with simulation mode first
2. **Confirmations:** Require confirmation for critical commands
3. **Timeouts:** Implement command timeouts
4. **Manual Override:** Keep manual controls as backup
5. **Error Recovery:** Handle connection losses gracefully
6. **Emergency Stop:** Physical emergency stop button recommended

---

## 📞 Need Help?

For specific device integration:
1. Check device documentation
2. Look for REST API or serial protocol
3. Find Python library for the device
4. Follow examples in this guide

**Happy controlling! 🎯🔌**
