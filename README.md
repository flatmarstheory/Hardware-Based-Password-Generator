# Hardware-Based Password Vault & Sensor Simulation

[![Project Status](https://img.shields.io/badge/Status-Active-success)](https://github.com/YOUR_USERNAME/YOUR_REPO)
[![Hardware](https://img.shields.io/badge/Hardware-BBC_micro%3Abit_V2-orange)](https://microbit.org/)
[![Language](https://img.shields.io/badge/Language-Python_/_MicroPython-blue)](https://www.python.org/)
[![License: Unlicense](https://img.shields.io/badge/License-Unlicense-lightgrey.svg)](https://unlicense.org/)

This project transforms a BBC micro:bit into a hardware-assisted entropy source to generate cryptographically strong passwords. It features a real-time "Digital Twin" desktop application that visualizes live telemetry data from the micro:bit's sensors, providing a visual bridge between physical randomness and digital security.

## 📺 Project Demo
Click the image below to watch the full walkthrough and live demonstration on YouTube:

[![Hardware Password Generator Demo](https://img.youtube.com/vi/Vd_SRUYATmk/0.jpg)](https://www.youtube.com/watch?v=Vd_SRUYATmk)

### 📑 Video Chapters
You can jump to specific sections of the video breakdown here:
* **0:00** - Project Overview
* **0:40** - Hardware Setup (micro:bit)
* **1:20** - How Entropy is Collected
* **2:10** - MicroPython Code Explanation
* **3:10** - Python GUI and Telemetry Visualization
* **4:20** - Live Demo and Password Generation
* **5:00** - Use Cases and Project Ideas

---

## 🚀 Key Features
* **Entropy Harvesting**: Samples the accelerometer (X, Y, Z) and microphone levels to create unpredictable random seeds.
* **Digital Twin Visualization**: An animated Tkinter canvas jitters and glows in sync with physical device movement.
* **Live Telemetry**: Real-time UART streaming (115200 baud) of raw sensor data to a dedicated dashboard.
* **Cinematic Reveal**: A "slot-machine" animation cycles through characters before locking the final password.
* **Security Analysis**: Automatic assessment of password strength (Weak to Strong) based on length and character classes.

## 🛠️ Repository Structure
* **`MB.py`**: MicroPython script for the micro:bit hardware.
* **`Client.py`**: Python Tkinter desktop application for visualization.
* **`requirements.txt`**: Python dependencies (`pyserial`, `pyperclip`).

## 📥 Installation & Setup

### 1. Hardware Setup
* Connect your **BBC micro:bit** (V2 recommended for microphone support) via USB.
* Flash the `MB.py` code using the [MicroPython Editor](https://python.microbit.org/).

### 2. Software Setup
* Install the required libraries:
    ```bash
    pip install pyserial pyperclip
    ```
* Run the application:
    ```bash
    python Client.py
    ```

### 3. Usage Instructions
* **Adjust Length**: Use Button **A (+)** or **B (-)** on the micro:bit to set length between 8 and 24 characters.
* **Generate**: Press **A+B** simultaneously on the device or click **GENERATE** in the desktop app.
* **Entropy Injection**: Shake the device or make noise to increase randomness via sensor telemetry.

## 🔐 Cybersecurity Concepts
* **True Random Number Generation (TRNG)**: Using physical environmental noise instead of deterministic software algorithms.
* **Entropy Mixing**: Bitwise operations combine sensor data and timing to evolve a 32-bit random state over time.
* **Visualization of Security**: Making abstract concepts like entropy and strength assessment tangible through live data.

## 📜 License
This project is dedicated to the public domain under **The Unlicense**. You are free to copy, modify, publish, use, compile, sell, or distribute this software in source code form or as a compiled binary, for any purpose, commercial or non-commercial, and by any means.

---
*Developed by Rai Bahadur Singh.*
