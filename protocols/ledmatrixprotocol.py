from protocols.byteutils import ByteUtils

class LEDMatrixProtocol():
    def __init__(self, number):
        self.connection_number = number

    def _set_discovery_group(self, hexlist, discovery_group):
        ### set discovery group ID (1 to 8?)
        if discovery_group == None:
            hexlist[2] = 0xFF
        else:
            hexlist[2] = discovery_group
        return hexlist
    
    def _set_cube_ID(self, hexlist, cube_ID):
        ### set cube ID 
        hexlist[3] = cube_ID
        return hexlist

    def _set_connection_number_motor(self, hexlist):
        ### set connection number
        hexlist[4] = self.connection_number*16 
        return hexlist

    def _generic_ledmatrix_hexlist(self, hexlist, cube_ID, discovery_group) -> list:
        """generic protocol (discovery_group, cube ID, connection number)"""
        ### set discovery group
        hexlist = self._set_discovery_group(hexlist, discovery_group)
        ### set cube ID
        hexlist = self._set_cube_ID(hexlist, cube_ID)
        ### set connection number
        hexlist = self._set_connection_number_motor(hexlist)
        return hexlist

    def ArduinoI2CLEDMatrixWritePixel_bytes(self, cube_ID, x_coordinate, y_coordinate, onoff, discovery_group=None):
        ### FF FF FF 00 00 E1 A2 00 0D 00 00 00
        hexlist = [0xFF, 0xFF, 0xFF, 0x00, 0x00, 0xE1, 0xA2, 0x00, 0x0D, 0x70, 0x01, 0x01, 0x01]
        ### generic process (discovery group & cube ID & robot number protocol)
        hexlist = self._generic_ledmatrix_hexlist(hexlist, cube_ID, discovery_group)
        ### set coordinate (0 to 7)
        hexlist[10] = x_coordinate
        hexlist[11] = y_coordinate
        ### set on/off (boolean: 0 -> on, 1 -> off)
        hexlist[12] = int(onoff)
        return bytes(hexlist)

    def ArduinoI2CLEDMatrixWritePicture_bytes(self, cube_ID, picture, discovery_group=None):
        ### FF FF FF 00 00 E2 A2 00 12 70 01 01 01 01 01 01 01 01
        hexlist = [0xFF, 0xFF, 0xFF, 0x00, 0x00, 0xE2, 0xA2, 0x00, 0x12, 0x70, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01]
        ### generic process (discovery group & cube ID & robot number protocol)
        hexlist = self._generic_ledmatrix_hexlist(hexlist, cube_ID, discovery_group)
        ### set picture (boolean list: len 8 -> xY0 to xY7)
        hexlist[10:] = list(map(int, picture))
        return bytes(hexlist)

    def ArduinoI2CLEDMatrixWriteString_bytes(self, cube_ID, strings, scroll_period, discovery_group=None):
        ### FF FF FF 00 00 E3 A2 00 00 70 01 ~
        hexlist = [0xFF, 0xFF, 0xFF, 0x00, 0x00, 0xE3, 0xA2, 0x00, 0x00, 0x70, 0x01, 0x00]
        ### generic process (discovery group & cube ID & robot number protocol)
        hexlist = self._generic_ledmatrix_hexlist(hexlist, cube_ID, discovery_group)
        ### set data size (maximum strings: 20)
        hexlist[7:9] = ByteUtils().int_to_hexlist(12+len(strings), 2) 
        ### set scroll period (1 to 200 -> 10ms to 2000ms)
        hexlist[10] = scroll_period
        ### set string (str: ascii available characters only, maximum strings: 20)
        hexlist.extend([ord(c) for c in strings])
        return bytes(hexlist)

    def ArduinoI2CLEDMatrixSetDisplay_bytes(self, cube_ID, display, discovery_group=None):
        ### FF FF FF 00 00 E4 A2 00 0A 70 01
        hexlist = [0xFF, 0xFF, 0xFF, 0x00, 0x00, 0xE4, 0xA2, 0x00, 0x0A, 0x70, 0x01]
        ### generic process (discovery group & cube ID & robot number protocol)
        hexlist = self._generic_ledmatrix_hexlist(hexlist, cube_ID, discovery_group)
        ### set display (int: 0 -> turn on device, 1 -> turn off device, 2 -> clear pixels)
        hexlist[10] = display
        return bytes(hexlist)

    def ArduinoI2CLEDMatrixSetBrightness_bytes(self, cube_ID, brightness, discovery_group=None):
        ### FF FF FF 00 00 E5 A2 00 0A 70 01
        hexlist = [0xFF, 0xFF, 0xFF, 0x00, 0x00, 0xE5, 0xA2, 0x00, 0x0A, 0x70, 0x0F]
        ### generic process (discovery group & cube ID & robot number protocol)
        hexlist = self._generic_ledmatrix_hexlist(hexlist, cube_ID, discovery_group)
        ### set brightness (int: 0 to 15)
        hexlist[10] = brightness
        return bytes(hexlist)

    def ArduinoI2CLEDMatrixSetBlinkRate_bytes(self, cube_ID, blink_rate, discovery_group=None):
        ### FF FF FF 00 00 E6 A2 00 0A 70 01
        hexlist = [0xFF, 0xFF, 0xFF, 0x00, 0x00, 0xE6, 0xA2, 0x00, 0x0A, 0x70, 0x01]
        ### generic process (discovery group & cube ID & robot number protocol)
        hexlist = self._generic_ledmatrix_hexlist(hexlist, cube_ID, discovery_group)
        ### set blink rate (int: 0 -> off, 1 -> 0.5Hz, 2 -> 1Hz, 3 -> 2Hz)
        hexlist[10] = blink_rate
        return bytes(hexlist)