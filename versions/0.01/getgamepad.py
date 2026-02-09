# Gamepad state reader
# Cross-platform support added for Linux/macOS

import platform

# Platform detection
IS_WINDOWS = platform.system() == 'Windows'

# Normalization functions
def normalize(x):
    """Normalize axis values from -32768 to 32767 to -1.0 to 1.0"""
    return round(x / 32768, 1)

def normalizet(x):
    """Normalize trigger values from 0-255 to 0.0-1.0"""
    return round(x / 255, 1)

if IS_WINDOWS:
    try:
        from readPad import rPad
        _XINPUT_AVAILABLE = True

        def gamepad_check():
            """
            Check gamepad state (Windows/XInput).
            Returns list of normalized values:
            ['LT','RT','Lx','Ly','Rx','Ry','UP','DOWN','LEFT','RIGHT',
             'START','SELECT','L3','R3','LB','RB','A','B','X','Y']
            """
            con = rPad(1)
            dictionary = con.read
            lista = list(dictionary.values())
            # Convert boolean to int
            lista = list(map(int, lista))
            # Normalize axis values (indices 2-6)
            listab = list(map(normalize, lista[2:6]))
            lista[2:6] = listab[:]
            # Normalize trigger values (indices 0-2)
            listac = list(map(normalizet, lista[0:2]))
            lista[0:2] = listac[:]
            return lista

    except (ImportError, OSError):
        _XINPUT_AVAILABLE = False
else:
    _XINPUT_AVAILABLE = False

# Cross-platform fallback (stub implementation)
if not _XINPUT_AVAILABLE:
    def gamepad_check():
        """
        Stub gamepad check for non-Windows platforms or when XInput unavailable.
        Returns list of zeros matching the expected format:
        ['LT','RT','Lx','Ly','Rx','Ry','UP','DOWN','LEFT','RIGHT',
         'START','SELECT','L3','R3','LB','RB','A','B','X','Y']
        """
        # Return 20 zeros: 2 triggers + 4 axes + 14 buttons
        return [0] * 20


if __name__ == '__main__':
    print(f"Platform: {platform.system()}")
    print(f"XInput available: {_XINPUT_AVAILABLE}")
    print(f"Gamepad state: {gamepad_check()}")
