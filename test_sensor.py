import sensor, time
while True:
    d = sensor.get_distance_cm()
    print(f"{d:.1f} cm")
    time.sleep(0.3)