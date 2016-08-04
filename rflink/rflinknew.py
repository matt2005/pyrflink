import time
import threading
import logging
import os
import json
import select
import re
from queue import Queue
from importlib import import_module
import serial

LOGGER = logging.getLogger(__name__)

class Message:
    """Represent a message from the gateway."""

    def __init__(self, data=None):
        """Setup message."""
        self.node_id = 0
        self.message_id = 0
        self.type = 0
        self.ack = 0
        self.sub_type = 0
        self.payload = ''  # All data except payload are integers
        if data is not None:
            self.decode(data)

    def copy(self, **kwargs):
        """Copy a message, optionally replace attributes with kwargs."""
        msg = Message(self.encode())
        for key, val in kwargs.items():
            setattr(msg, key, val)
        return msg

    def decode(self, data):
        """Decode a message from command string."""
        try:
            list_data = re.split(';',data)
            if len(list_data) > 4:
                del list_data[0]
                del list_data[0]
                del list_data[-1]
                self.node_id=list_data[0]
                del list_data[0]
                self.child_id=255 #list_data[0]
                del list_data[0]
                self.type=0
                self.ack=0
                self.sub_type=0
                self.payload = list_data
                LOGGER.info('Sensor: %s',self.payload)
            elif len(list_data) == 4:
                del list_data[0]
                del list_data[0]
                del list_data[-1]
                self.node_id=255
                self.child_id=255
                self.type=3 # internal message
                self.ack=0
                self.sub_type=9
                self.payload = list_data[0] #.pop(3)
                LOGGER.info('Internal Message: %s',self.payload)
        except ValueError:
            LOGGER.warning('Error decoding message from gateway, '
                           'bad data received: %s', data)
            raise ValueError

    def encode(self):
        """Encode a command string from message."""
        try:
            return ';'.join([str(f) for f in [
                self.node_id,
                self.child_id,
                int(self.type),
                self.ack,
                int(self.sub_type),
                self.payload,
            ]]) + '\n\r'
        except ValueError:
            LOGGER.exception('Error encoding message to gateway')
            return None
