"""Example for using pyrflink."""
import rflink.rflink as rflink
import time

def event(update_type, nid):
    """Callback for rflink updates."""
    print(update_type + " " + str(nid))

# To create a serial gateway.
GATEWAY = rflink.SerialGateway('/dev/ttyACM0', event, True)

GATEWAY.debug = True
GATEWAY.start()
time.sleep(20)
# To set sensor 1, child 1, sub-type V_LIGHT (= 2), with value 1.
#GATEWAY.set_child_value(1, 1, 2, 1)
GATEWAY.stop()
