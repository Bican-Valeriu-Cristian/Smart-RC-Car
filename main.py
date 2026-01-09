# from time import sleep
# from controller import start_ble_background, STATE

# def main():
#     start_ble_background()   # BLE starts in the background

#     while True:
#         if STATE.connected:
#             print("Joystick:", STATE.joyX, STATE.joyY, "Buttons:", STATE.buttons, "Connected" if STATE.connected else "Disconnected")

#         sleep(0.5)

# if __name__ == "__main__":
#     main()

import asyncio
from bleak import BleakClient, BleakScanner

DEVICE_NAME = "Esp32-BLE-Controller" 
CHAR_UUID = "87654321-4321-4321-4321-ba0987654321"  # full characteristic UUID

async def main():
    print("Scanning...")
    devices = await BleakScanner.discover()

    for d in devices:
        print(d)

    # Find your ESP32 by name
    target = next((d for d in devices if d.name and DEVICE_NAME in d.name), None)
    if not target:
        print("Device not found.")
        return

    print("Connecting to:", target.address)
    try:
        async with BleakClient(target.address) as client:
            print("Connected.")
            val = await client.read_gatt_char(CHAR_UUID)
            print("Characteristic value:", val.decode())
    except Exception as e:
        print("Failed to connect or read characteristic:", e)

asyncio.run(main())

