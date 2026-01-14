from microbit import *

uart.init(baudrate=115200)

# Micro:bit V2 microphone support (V1 will fall back automatically)
HAS_MIC = False
try:
    import microphone
    HAS_MIC = True
except ImportError:
    HAS_MIC = False

# ----------------------------
# PRNG + entropy mixing
# ----------------------------
_state = 0xA3C59AC3

def _u32(x):
    return x & 0xFFFFFFFF

def mix_entropy(v):
    global _state
    _state ^= _u32(v)
    _state = _u32(_state + 0x9E3779B9)
    _state ^= _u32(_state << 13)
    _state ^= _u32(_state >> 17)
    _state ^= _u32(_state << 5)

def sample_entropy():
    t = running_time()
    ax = accelerometer.get_x()
    ay = accelerometer.get_y()
    az = accelerometer.get_z()
    v = t ^ (ax << 1) ^ (ay << 2) ^ (az << 3)
    if HAS_MIC:
        v ^= (microphone.sound_level() << 8)
    mix_entropy(v)

def randbelow(n):
    sample_entropy()
    if n <= 1:
        return 0
    return _state % n

# ----------------------------
# Password generation
# ----------------------------
LOWER = "abcdefghijklmnopqrstuvwxyz"
UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
DIGIT = "0123456789"
SYMBOL = "!@#$%^&*()-_=+[]{};:,.?/"

def shuffle_list(items):
    i = len(items) - 1
    while i > 0:
        j = randbelow(i + 1)
        items[i], items[j] = items[j], items[i]
        i -= 1

def generate_password(length):
    if length < 8:
        length = 8
    chars = []
    chars.append(LOWER[randbelow(len(LOWER))])
    chars.append(UPPER[randbelow(len(UPPER))])
    chars.append(DIGIT[randbelow(len(DIGIT))])
    chars.append(SYMBOL[randbelow(len(SYMBOL))])
    allset = LOWER + UPPER + DIGIT + SYMBOL
    while len(chars) < length:
        chars.append(allset[randbelow(len(allset))])
    shuffle_list(chars)
    return "".join(chars)

def strength_label(pw):
    length = len(pw)
    has_l = False
    has_u = False
    has_d = False
    has_s = False
    for c in pw:
        if c in LOWER:
            has_l = True
        elif c in UPPER:
            has_u = True
        elif c in DIGIT:
            has_d = True
        elif c in SYMBOL:
            has_s = True
    classes = (1 if has_l else 0) + (1 if has_u else 0) + (1 if has_d else 0) + (1 if has_s else 0)
    if length >= 14 and classes == 4:
        return "STRONG"
    if length >= 12 and classes >= 3:
        return "OK"
    if length >= 10 and classes >= 2:
        return "FAIR"
    return "WEAK"

# ----------------------------
# Telemetry streaming
# Protocol:
#   S:<ms>,<ax>,<ay>,<az>,<sl>
#   EV:IDLE / EV:PRE / EV:GEN / EV:POST
#   PW:<password> / ST:<label> / LN:<len>
# ----------------------------
telemetry_on = True
telemetry_ms = 120
_last_send = 0

def send_sensor():
    global _last_send
    if not telemetry_on:
        return
    now = running_time()
    if now - _last_send < telemetry_ms:
        return
    _last_send = now

    ax = accelerometer.get_x()
    ay = accelerometer.get_y()
    az = accelerometer.get_z()
    sl = -1
    if HAS_MIC:
        sl = microphone.sound_level()
    uart.write("S:" + str(now) + "," + str(ax) + "," + str(ay) + "," + str(az) + "," + str(sl) + "\n")

pw_len = 12
last_pw = ""

display.scroll("PW", wait=False, loop=False)
sleep(250)

def show_len():
    display.scroll("L" + str(pw_len), wait=False, loop=False)

def do_generate():
    global last_pw
    uart.write("EV:PRE\n")
    for _ in range(14):
        sample_entropy()
        send_sensor()
        sleep(25)

    pw = generate_password(pw_len)
    last_pw = pw
    label = strength_label(pw)

    uart.write("EV:GEN\n")
    display.scroll(pw, wait=False, loop=False)
    sleep(250)
    display.scroll(label, wait=False, loop=False)

    uart.write("PW:" + pw + "\n")
    uart.write("ST:" + label + "\n")
    uart.write("LN:" + str(pw_len) + "\n")

    uart.write("EV:POST\n")
    for _ in range(10):
        send_sensor()
        sleep(30)

uart.write("EV:IDLE\n")
show_len()

while True:
    sample_entropy()
    send_sensor()

    if button_a.was_pressed():
        pw_len += 1
        if pw_len > 24:
            pw_len = 24
        mix_entropy(running_time() ^ 0xA55A)
        show_len()

    if button_b.was_pressed():
        pw_len -= 1
        if pw_len < 8:
            pw_len = 8
        mix_entropy(running_time() ^ 0x5AA5)
        show_len()

    if button_a.is_pressed() and button_b.is_pressed():
        do_generate()
        while button_a.is_pressed() or button_b.is_pressed():
            sleep(20)
        uart.write("EV:IDLE\n")
        show_len()

    if accelerometer.was_gesture("shake"):
        for _ in range(20):
            sample_entropy()
            send_sensor()
            sleep(10)
        display.show(Image.DIAMOND_SMALL)
        sleep(120)
        display.clear()

    if HAS_MIC:
        if microphone.sound_level() > 120:
            mix_entropy(microphone.sound_level() ^ running_time())
            display.show(Image.MUSIC_QUAVER)
            sleep(120)
            display.clear()

    if uart.any():
        try:
            cmd = uart.readline()
            if cmd:
                try:
                    cmd = cmd.decode("utf-8").strip()
                except:
                    cmd = str(cmd).strip()

                if cmd == "GEN":
                    do_generate()
                    uart.write("EV:IDLE\n")
                    show_len()

                elif cmd.startswith("LEN:"):
                    try:
                        n = int(cmd[4:])
                        if n < 8:
                            n = 8
                        if n > 24:
                            n = 24
                        pw_len = n
                        show_len()
                    except:
                        pass

                elif cmd == "LAST" and last_pw:
                    uart.write("PW:" + last_pw + "\n")

                elif cmd == "TELEM:ON":
                    telemetry_on = True
                elif cmd == "TELEM:OFF":
                    telemetry_on = False

        except:
            pass

    sleep(40)
