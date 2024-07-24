import os
import mss
import cv2
import time
import math
import base64
import random
import keyboard
import win32api
import win32con
import warnings

import numpy as np
import pygetwindow as gw
from pywinauto import Application

# Constants
CHECK_INTERVAL = 5
warnings.filterwarnings("ignore", category=UserWarning, module='pywinauto')

# Global Variables
global_running = False


# Function to toggle the script on and off
def toggle_script():
    global global_running
    global_running = not global_running
    if global_running:
        print("Script started.")
    else:
        print("Script stopped.")
        for clicker in auto_clickers:
            clicker.play_counter = 0


# Logger class for logging messages
class Logger:
    def __init__(self, prefix=None):
        self.prefix = prefix

    def log(self, message: str):
        if self.prefix:
            print(f"{self.prefix} {message}")
        else:
            print(message)


# Function to list windows by title keywords
def list_windows_by_title(title_keywords):
    windows = gw.getAllWindows()
    filtered_windows = []
    for window in windows:
        for keyword in title_keywords:
            if keyword.lower() in window.title.lower():
                filtered_windows.append((window.title, window._hWnd))
                break
    return filtered_windows


# AutoClicker class to manage clicking actions
class AutoClicker:
    def __init__(self, hwnd, target_colors, nearby_colors, threshold, logger, target_percentage, hit_chance,
                 min_delay, max_delay, play_count):
        self.hwnd = hwnd
        self.target_colors = target_colors
        self.nearby_colors = nearby_colors
        self.threshold = threshold
        self.logger = logger
        self.target_percentage = target_percentage
        self.hit_chance = hit_chance
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.play_count = play_count
        self.running = False
        self.clicked_points = []
        self.iteration_count = 0
        self.play_counter = 0
        self.last_check_time = time.time()
        self.last_freeze_check_time = time.time()
        self.freeze_cooldown_time = 0

    @staticmethod
    def hex_to_hsv(hex_color):
        hex_color = hex_color.lstrip('#')
        rgb = tuple(int(hex_color[i:i + 2], 16) for i in range(0, 6, 2))
        rgb_normalized = np.array([[rgb]], dtype=np.uint8)
        hsv = cv2.cvtColor(rgb_normalized, cv2.COLOR_RGB2HSV)
        return hsv[0][0]

    @staticmethod
    def click_at(x, y):
        screen_width = win32api.GetSystemMetrics(0)
        screen_height = win32api.GetSystemMetrics(1)
        if not (0 <= x < screen_width and 0 <= y < screen_height):
            raise ValueError(f"Off-screen coordinates: ({x}, {y})")
        win32api.SetCursorPos((x, y))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)

    def toggle(self):
        self.running = not self.running
        if self.running:
            self.logger.log("Script started.")
        else:
            self.logger.log("Script stopped.")
            self.play_counter = 0

    def is_near_color(self, hsv_img, center, target_hsvs, radius=8):
        x, y = center
        height, width = hsv_img.shape[:2]
        for i in range(max(0, x - radius), min(width, x + radius + 1)):
            for j in range(max(0, y - radius), min(height, y + radius + 1)):
                distance = math.sqrt((x - i) ** 2 + (y - j) ** 2)
                if distance <= radius:
                    pixel_hsv = hsv_img[j, i]
                    for target_hsv in target_hsvs:
                        if np.allclose(pixel_hsv, target_hsv, atol=[1, 50, 50]):
                            return True
        return False

    def check_and_click_play_button(self, sct, monitor):
        current_time = time.time()
        if current_time - self.last_check_time >= CHECK_INTERVAL:
            self.last_check_time = current_time

            def decode_base64_to_image(base64_string):
                image_data = base64.b64decode(base64_string)
                np_array = np.frombuffer(image_data, np.uint8)
                return cv2.imdecode(np_array, cv2.IMREAD_GRAYSCALE)

            # Placeholder strings for base64 encoded images
            button_ticket = "iVBORw0KGgoAAAANSUhEUgAAACUAAAAWCAYAAABHcFUAAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdvqGQAAAJjSURBVEhL7Za/S2phGMe/3sEmh9QEEUSCbBGKEBfFcnJxazPcDJKGpkrQwR+DOiS0CQku+j+oiCD+RBwaCxGhIvoFQWIOEe8973PPjcirV8jCoQ8cjrzv8x6+z/N8z3OUMAHMGL/E+0zxI2pSfkRNyj9FnZ+fY3V1FRKJ5O3S6XQIBALo9XoYDAbweDyw2Wy4vr4WT02PsZUym80Ih8OIRqMwmUwIBoPY398nUV85ScaKWlxcxN7eHg4PD3FycoKtrS00Gg1cXl6KEV/DVDzV7/dxfHyMtbU1KBQKOJ1OnJ6eUjXj8Ti1v1qtUuzj4yM2NzfhcDhwc3NDax8ZK6rVauHo6AixWAzb29vIZDLUUo1GI0YALy8vCIVCSKVS8Pv9yGazeHp6gtvtRqfTwfr6OtRqNYrFIsW3222qNn/OwsICrQ3BPzMfOTs7YysrK9w0b9fy8jKLRCLs7u6OPT8/s52dHbaxscG63S6r1+us2WzS3sPDAxOqRmfy+TwTBDKXy8Xsdju7v79nQpJsaWmJzoxibKWEh1HWQhwEofB6vUPZSaVSuu/u7kKlUkGpVJIP/yKTyahauVwOtVoNlUqFXhq9Xi9GDPNpT/ERwVssl8upNTyBRCIh7v7BYrFAqDwODg6odVarFfPz8+LuMFMxOufi4gJXV1fkHe6v9/AZx6vF5x+vJhfJzT+KT4vi7fH5fDAYDPTWJZNJas975ubmSBSH72m1Wvo9EnLWN1AoFJiQAEun0+LKaKbWvnG8vr6iVCrRMDYajeLqaL5F1O3tLcrlMoQRQv76Hz9/hydlBkUBvwFnxbMJbU11IgAAAABJRU5ErkJggg=="
            button_play = "iVBORw0KGgoAAAANSUhEUgAAAEMAAAAWCAIAAAAU67ZgAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAJRWlUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4gPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iQWRvYmUgWE1QIENvcmUgNi4wLWMwMDIgNzkuMTY0NDg4LCAyMDIwLzA3LzEwLTIyOjA2OjUzICAgICAgICAiPiA8cmRmOlJERiB4bWxuczpyZGY9Imh0dHA6Ly93d3cudzMub3JnLzE5OTkvMDIvMjItcmRmLXN5bnRheC1ucyMiPiA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0iIiB4bWxuczp4bXBNTT0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wL21tLyIgeG1sbnM6c3RFdnQ9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9zVHlwZS9SZXNvdXJjZUV2ZW50IyIgeG1sbnM6c3RSZWY9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9zVHlwZS9SZXNvdXJjZVJlZiMiIHhtbG5zOmRjPSJodHRwOi8vcHVybC5vcmcvZGMvZWxlbWVudHMvMS4xLyIgeG1sbnM6cGhvdG9zaG9wPSJodHRwOi8vbnMuYWRvYmUuY29tL3Bob3Rvc2hvcC8xLjAvIiB4bWxuczp0aWZmPSJodHRwOi8vbnMuYWRvYmUuY29tL3RpZmYvMS4wLyIgeG1sbnM6ZXhpZj0iaHR0cDovL25zLmFkb2JlLmNvbS9leGlmLzEuMC8iIHhtbG5zOnhtcD0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wLyIgeG1wTU06RG9jdW1lbnRJRD0iYWRvYmU6ZG9jaWQ6cGhvdG9zaG9wOjZjMDM1ZDY0LTVhZjUtOTk0ZC1hMDNhLTUxODczYWU1NjljZCIgeG1wTU06SW5zdGFuY2VJRD0ieG1wLmlpZDoxYTc4OGExOC0zYzM4LTFmNGYtYTBjNi00MzJiNTE1YTUxZmIiIHhtcE1NOk9yaWdpbmFsRG9jdW1lbnRJRD0iMUI5RjI0NjE5MzgwQjE3N0IzNzg3MzhBOEE2NDc4RDEiIGRjOmZvcm1hdD0iaW1hZ2UvcG5nIiBwaG90b3Nob3A6Q29sb3JNb2RlPSIzIiBwaG90b3Nob3A6SUNDUHJvZmlsZT0iIiB0aWZmOkltYWdlV2lkdGg9IjY3IiB0aWZmOkltYWdlTGVuZ3RoPSIyMiIgdGlmZjpQaG90b21ldHJpY0ludGVycHJldGF0aW9uPSIyIiB0aWZmOlNhbXBsZXNQZXJQaXhlbD0iMyIgdGlmZjpYUmVzb2x1dGlvbj0iOTYvMSIgdGlmZjpZUmVzb2x1dGlvbj0iOTYvMSIgdGlmZjpSZXNvbHV0aW9uVW5pdD0iMiIgZXhpZjpFeGlmVmVyc2lvbj0iMDIzMSIgZXhpZjpDb2xvclNwYWNlPSI2NTUzNSIgZXhpZjpQaXhlbFhEaW1lbnNpb249IjY3IiBleGlmOlBpeGVsWURpbWVuc2lvbj0iMjIiIHhtcDpDcmVhdGVEYXRlPSIyMDI0LTA2LTA3VDAxOjQwOjE1KzA3OjAwIiB4bXA6TW9kaWZ5RGF0ZT0iMjAyNC0wNi0wN1QwMTo0MDo0MiswNzowMCIgeG1wOk1ldGFkYXRhRGF0ZT0iMjAyNC0wNi0wN1QwMTo0MDo0MiswNzowMCI+IDx4bXBNTTpIaXN0b3J5PiA8cmRmOlNlcT4gPHJkZjpsaSBzdEV2dDphY3Rpb249InNhdmVkIiBzdEV2dDppbnN0YW5jZUlEPSJ4bXAuaWlkOjU0ZWE0MGE2LWVjOWUtZjY0ZS1hM2VhLThmMDg0MDMxM2Q2NiIgc3RFdnQ6d2hlbj0iMjAyNC0wNi0wN1QwMTo0MDo0MiswNzowMCIgc3RFdnQ6c29mdHdhcmVBZ2VudD0iQWRvYmUgUGhvdG9zaG9wIDIyLjAgKFdpbmRvd3MpIiBzdEV2dDpjaGFuZ2VkPSIvIi8+IDxyZGY6bGkgc3RFdnQ6YWN0aW9uPSJjb252ZXJ0ZWQiIHN0RXZ0OnBhcmFtZXRlcnM9ImZyb20gaW1hZ2UvanBlZyB0byBpbWFnZS9wbmciLz4gPHJkZjpsaSBzdEV2dDphY3Rpb249ImRlcml2ZWQiIHN0RXZ0OnBhcmFtZXRlcnM9ImNvbnZlcnRlZCBmcm9tIGltYWdl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"
            button_close = "iVBORw0KGgoAAAANSUhEUgAAAEIAAAAgCAIAAAApCjnuAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAJRWlUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4gPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iQWRvYmUgWE1QIENvcmUgNi4wLWMwMDIgNzkuMTY0NDg4LCAyMDIwLzA3LzEwLTIyOjA2OjUzICAgICAgICAiPiA8cmRmOlJERiB4bWxuczpyZGY9Imh0dHA6Ly93d3cudzMub3JnLzE5OTkvMDIvMjItcmRmLXN5bnRheC1ucyMiPiA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0iIiB4bWxuczp4bXBNTT0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wL21tLyIgeG1sbnM6c3RFdnQ9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9zVHlwZS9SZXNvdXJjZUV2ZW50IyIgeG1sbnM6c3RSZWY9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9zVHlwZS9SZXNvdXJjZVJlZiMiIHhtbG5zOmRjPSJodHRwOi8vcHVybC5vcmcvZGMvZWxlbWVudHMvMS4xLyIgeG1sbnM6cGhvdG9zaG9wPSJodHRwOi8vbnMuYWRvYmUuY29tL3Bob3Rvc2hvcC8xLjAvIiB4bWxuczp0aWZmPSJodHRwOi8vbnMuYWRvYmUuY29tL3RpZmYvMS4wLyIgeG1sbnM6ZXhpZj0iaHR0cDovL25zLmFkb2JlLmNvbS9leGlmLzEuMC8iIHhtbG5zOnhtcD0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wLyIgeG1wTU06RG9jdW1lbnRJRD0iYWRvYmU6ZG9jaWQ6cGhvdG9zaG9wOjY0YWIwMmE1LThlNmUtNDk0Yy1iMWRmLWRhZTUxOGZmMWQyOCIgeG1wTU06SW5zdGFuY2VJRD0ieG1wLmlpZDo0ZGM4Y2VkNy03NTY1LTU0NDAtYTlhNS0xMjYyMWM2MTc0ODIiIHhtcE1NOk9yaWdpbmFsRG9jdW1lbnRJRD0iRjU2RjM5RTJBNTExMUZERjEwODA4MDc3MUEwQTFEQTciIGRjOmZvcm1hdD0iaW1hZ2UvcG5nIiBwaG90b3Nob3A6Q29sb3JNb2RlPSIzIiBwaG90b3Nob3A6SUNDUHJvZmlsZT0iIiB0aWZmOkltYWdlV2lkdGg9IjY2IiB0aWZmOkltYWdlTGVuZ3RoPSIzMiIgdGlmZjpQaG90b21ldHJpY0ludGVycHJldGF0aW9uPSIyIiB0aWZmOlNhbXBsZXNQZXJQaXhlbD0iMyIgdGlmZjpYUmVzb2x1dGlvbj0iOTYvMSIgdGlmZjpZUmVzb2x1dGlvbj0iOTYvMSIgdGlmZjpSZXNvbHV0aW9uVW5pdD0iMiIgZXhpZjpFeGlmVmVyc2lvbj0iMDIzMSIgZXhpZjpDb2xvclNwYWNlPSI2NTUzNSIgZXhpZjpQaXhlbFhEaW1lbnNpb249IjY2IiBleGlmOlBpeGVsWURpbWVuc2lvbj0iMzIiIHhtcDpDcmVhdGVEYXRlPSIyMDI0LTA2LTA3VDAxOjU4OjAxKzA3OjAwIiB4bXA6TW9kaWZ5RGF0ZT0iMjAyNC0wNi0wN1QwMTo1OTowNiswNzowMCIgeG1wOk1ldGFkYXRhRGF0ZT0iMjAyNC0wNi0wN1QwMTo1OTowNiswNzowMCI+IDx4bXBNTTpIaXN0b3J5PiA8cmRmOlNlcT4gPHJkZjpsaSBzdEV2dDphY3Rpb249InNhdmVkIiBzdEV2dDppbnN0YW5jZUlEPSJ4bXAuaWlkOjg4MjA4ZmM0LTg2MDgtYjA0Ni1hYzJjLTM5NzNlNGRhNzg1MyIgc3RFdnQ6d2hlbj0iMjAyNC0wNi0wN1QwMTo1OTowNiswNzowMCIgc3RFdnQ6c29mdHdhcmVBZ2VudD0iQWRvYmUgUGhvdG9zaG9wIDIyLjAgKFdpbmRvd3MpIiBzdEV2dDpjaGFuZ2VkPSIvIi8+IDxyZGY6bGkgc3RFdnQ6YWN0aW9uPSJjb252ZXJ0ZWQiIHN0RXZ0OnBhcmFtZXRlcnM9ImZyb20gaW1hZ2UvanBlZyB0byBpbWFnZS9wbmciLz4gPHJkZjpsaSBzdEV2dDphY3Rpb249ImRlcml2ZWQiIHN0RXZ0OnBhcmFtZXRlcnM9ImNvbnZlcnRlZCBmcm9tIGltYWdl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"
            captcha = "iVBORw0KGgoAAAANSUhEUgAAAKoAAAAhCAIAAADGY6fOAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAJR2lUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4gPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iQWRvYmUgWE1QIENvcmUgNi4wLWMwMDIgNzkuMTY0NDg4LCAyMDIwLzA3LzEwLTIyOjA2OjUzICAgICAgICAiPiA8cmRmOlJERiB4bWxuczpyZGY9Imh0dHA6Ly93d3cudzMub3JnLzE5OTkvMDIvMjItcmRmLXN5bnRheC1ucyMiPiA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0iIiB4bWxuczp4bXBNTT0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wL21tLyIgeG1sbnM6c3RFdnQ9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9zVHlwZS9SZXNvdXJjZUV2ZW50IyIgeG1sbnM6c3RSZWY9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9zVHlwZS9SZXNvdXJjZVJlZiMiIHhtbG5zOmRjPSJodHRwOi8vcHVybC5vcmcvZGMvZWxlbWVudHMvMS4xLyIgeG1sbnM6cGhvdG9zaG9wPSJodHRwOi8vbnMuYWRvYmUuY29tL3Bob3Rvc2hvcC8xLjAvIiB4bWxuczp0aWZmPSJodHRwOi8vbnMuYWRvYmUuY29tL3RpZmYvMS4wLyIgeG1sbnM6ZXhpZj0iaHR0cDovL25zLmFkb2JlLmNvbS9leGlmLzEuMC8iIHhtbG5zOnhtcD0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wLyIgeG1wTU06RG9jdW1lbnRJRD0iYWRvYmU6ZG9jaWQ6cGhvdG9zaG9wOjNiYjgwMTg5LWQ0NDYtZDU0Ny04ZjRiLWE1OTFmZWFjMzNlNSIgeG1wTU06SW5zdGFuY2VJRD0ieG1wLmlpZDoyY2VkNDIyZC0yZjlmLWI4NDUtOTJhYS02YjZiZGFhNTVlODUiIHhtcE1NOk9yaWdpbmFsRG9jdW1lbnRJRD0iRDFDNjY4Q0M3QzkyQjExNDJERTUwQ0VENEMzODc0N0EiIGRjOmZvcm1hdD0iaW1hZ2UvcG5nIiBwaG90b3Nob3A6Q29sb3JNb2RlPSIzIiBwaG90b3Nob3A6SUNDUHJvZmlsZT0iIiB0aWZmOkltYWdlV2lkdGg9IjMyOCIgdGlmZjpJbWFnZUxlbmd0aD0iODYiIHRpZmY6UGhvdG9tZXRyaWNJbnRlcnByZXRhdGlvbj0iMiIgdGlmZjpTYW1wbGVzUGVyUGl4ZWw9IjMiIHRpZmY6WFJlc29sdXRpb249Ijk2LzEiIHRpZmY6WVJlc29sdXRpb249Ijk2LzEiIHRpZmY6UmVzb2x1dGlvblVuaXQ9IjIiIGV4aWY6RXhpZlZlcnNpb249IjAyMzEiIGV4aWY6Q29sb3JTcGFjZT0iNjU1MzUiIGV4aWY6UGl4ZWxYRGltZW5zaW9uPSIzMjgiIGV4aWY6UGl4ZWxZRGltZW5zaW9uPSI4NiIgeG1wOkNyZWF0ZURhdGU9IjIwMjQtMDYtMDdUMTY6MjM6MzQrMDc6MDAiIHhtcDpNb2RpZnlEYXRlPSIyMDI0LTA2LTA3VDE2OjMxOjUzKzA3OjAwIiB4bXA6TWV0YWRhdGFEYXRlPSIyMDI0LTA2LTA3VDE2OjMxOjUzKzA3OjAwIj4gPHhtcE1NOkhpc3Rvcnk+IDxyZGY6U2VxPiA8cmRmOmxpIHN0RXZ0OmFjdGlvbj0ic2F2ZWQiIHN0RXZ0Omluc3RhbmNlSUQ9InhtcC5paWQ6YzllNWViYjItYWY2My03MDQzLWJiODYtNDM1MjU0MDg5M2NhIiBzdEV2dDp3aGVuPSIyMDI0LTA2LTA3VDE2OjMxOjUzKzA3OjAwIiBzdEV2dDpzb2Z0d2FyZUFnZW50PSJBZG9iZSBQaG90b3Nob3AgMjIuMCAoV2luZG93cykiIHN0RXZ0OmNoYW5nZWQ9Ii8iLz4gPHJkZjpsaSBzdEV2dDphY3Rpb249ImNvbnZlcnRlZCIgc3RFdnQ6cGFyYW1ldGVycz0iZnJvbSBpbWFnZS9qcGVnIHRvIGltYWdlL3BuZyIvPiA8cmRmOmxpIHN0RXZ0OmFjdGlvbj0iZGVyaXZlZCIgc3RFdnQ6cGFyYW1ldGVycz0iY29udmVydGVkIGZyb20gaW1h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veftd7jxTcqFSk3WiHNy0Aldt1lKF+rdVi/2G1va2V6pylVTOeBOrLmTP0kSsXlHGHUNyS7V/IZset3wkyM5Jc8ajh52ZOoYd487YY87oS17p13u8FPDWGF30d/u8clhMKleS50gESxkhTpKE9SuiXr3iJkyKjoTd4SJajHwyo0cRKREQ5pUE8nAiCaDvBi4zTTR5bhWJsNlMhzoppi2JU6WskRowpLUM3GeZjHyDe2LJC7ADJn2UXJiETU3HUylYiIHKM7JoHEjUZ5A603ZYIPUpZtQp6HVCBc+YW6WtjcapZwuuEoTk2oZuWhGktckl2rjsIDx0YipiCmeBSXjGPmJpNHJcsPU2e7wzKggY03GVEwikFHiUElSYNhxAp1klFKt30v87xfGBY/ttt3f33/WWWfV63XOeaVS+dSnTlm7dq0xaGpq2rz55bf6+7fu2HHvvfdSSoMguPPOO1966aXHH398S1/fjTfe2NPTs2TJkssuu2zt2rtJqfQXV121adOm/v6tt9zyHSkRRVGhUHj66acfeeSRMRLwhS984eW+vpNOOskmHc4///ydWzdeffXVruvefvvtb299ffPmV7b3v3bvvfcqpR3HWb58+cMPPxxFkeM4ra2tPT0911xzTaFQUErZbZExdsUVV+zYseON7dt7tmy5++67C4VCHMc/+tGPenp6nn/++Xd2vH3llVcSQtatW9fX17f9nXdWrFjBOXddV2vNOfc8LwxD13WllN3d3du2/ObNt95atmyZEALAgw8++OCDD8Zx3Gg0Ojo6tm/vufrqq33ff/HFF++5557XXnutr/+tp59+urW19Zlnnnl9y5a+bX1f//rXXdet1+vNzc2bN7/Y29v71tt9a9asmTVrVhzHS5cuXb9+/aOPPvrmm2/29/U/8MADSqlCoXCQ4B+njJk5+AFADNWgmhz8KBANQ7ShRHMtiQpklixdVc8mzVk4O5miXrvssjMnteDv7o/i5iteXvvN5x7+Lx2nXjjljEvOmjLh+1deHlcqw44zsWV41UN/e9L0C26946k02ZhXW1ct7b7ok9cg7rvn9htnnD7/n1eun3vqfK5ZfeL0Kf/uix2t5f/xretVyYuZ2xLke3/18obqzj/77zc0WFLIq+vO/7Tue+2r/7TlPy9946J5nX/1b6ecPnvOGafMO+GMud++48dpEFVyxXbU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"

            templates = [
                decode_base64_to_image(button_ticket),
                decode_base64_to_image(button_play),
                decode_base64_to_image(button_close),
                decode_base64_to_image(captcha)
            ]

            for template in templates:
                if template is None:
                    continue

                template_height, template_width = template.shape

                img = np.array(sct.grab(monitor))
                img_gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)

                res = cv2.matchTemplate(img_gray, template, cv2.TM_CCOEFF_NORMED)
                loc = np.where(res >= self.threshold)

                matched_points = list(zip(*loc[::-1]))

                if matched_points:
                    pt_x, pt_y = matched_points[0]
                    cX = pt_x + template_width // 2 + monitor["left"]
                    cY = pt_y + template_height // 2 + monitor["top"]

                    if template is decode_base64_to_image(button_play):
                        delay = random.uniform(self.min_delay, self.max_delay)
                        time.sleep(delay)

                    self.click_at(cX, cY)
                    self.clicked_points.append((cX, cY))

                    if template is decode_base64_to_image(button_play):
                        self.play_counter += 1
                        if self.play_counter >= self.play_count:
                            self.logger.log("Play count reached, stopping the script.")
                            self.running = False
                            self.prompt_restart()
                            return

                    break

    def prompt_restart(self):
        response = input("Do you want to restart the script with the same parameters? (yes/no): ")
        if response.lower() == 'yes':
            self.play_counter = 0
            self.toggle()
            self.logger.log("Script restarted.")
        else:
            self.logger.log("Script ended.")

    def click_color_areas(self):
        app = None
        try:
            app = Application(backend="win32").connect(handle=self.hwnd)
        except Exception as e:
            self.logger.log(f"Failed to connect to the window: {e}")
            return

        window = app.window(handle=self.hwnd)
        window.set_focus()

        target_hsvs = [self.hex_to_hsv(color) for color in self.target_colors]
        nearby_hsvs = [self.hex_to_hsv(color) for color in self.nearby_colors]

        with mss.mss() as sct:
            while True:
                if global_running:
                    rect = window.rectangle()
                    monitor = {
                        "top": rect.top,
                        "left": rect.left,
                        "width": rect.width(),
                        "height": rect.height()
                    }

                    img = np.array(sct.grab(monitor))
                    img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)

                    screen_width = win32api.GetSystemMetrics(0)
                    screen_height = win32api.GetSystemMetrics(1)

                    for target_hsv in target_hsvs:
                        lower_bound = np.array([max(0, target_hsv[0] - 1), 30, 30])
                        upper_bound = np.array([min(179, target_hsv[0] + 1), 255, 255])
                        mask = cv2.inRange(hsv, lower_bound, upper_bound)
                        contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

                        num_contours = len(contours)
                        num_to_click = int(num_contours * self.target_percentage)
                        contours_to_click = random.sample(contours, num_to_click)

                        for contour in reversed(contours_to_click):
                            if cv2.contourArea(contour) < 6:
                                continue

                            if random.random() <= self.hit_chance:
                                M = cv2.moments(contour)
                                if M["m00"] == 0:
                                    continue
                                cX = int(M["m10"] / M["m00"]) + monitor["left"]
                                cY = int(M["m01"] / M["m00"]) + monitor["top"]

                                if not self.is_near_color(hsv, (cX - monitor["left"], cY - monitor["top"]),
                                                          nearby_hsvs):
                                    continue

                                if any(math.sqrt((cX - px) ** 2 + (cY - py) ** 2) < 35 for px, py in
                                       self.clicked_points):
                                    continue

                                if 0 <= cX < screen_width and 0 <= cY < screen_height:
                                    cY += 5
                                    self.click_at(cX, cY)
                                    self.clicked_points.append((cX, cY))

                    self.check_and_click_play_button(sct, monitor)
                    time.sleep(0.1)
                    self.iteration_count += 1
                    if self.iteration_count >= 5:
                        self.clicked_points.clear()
                        self.iteration_count = 0
                else:
                    time.sleep(0.1)


if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_dir)

    keywords = ["Blum", "Telegram"]
    windows = list_windows_by_title(keywords)

    if not windows:
        exit()

    hit_chance_input = input("Enter hit chance percentage (0-100): ")
    hit_chance = float(hit_chance_input) / 100

    min_delay = float(input("Enter minimum delay before clicking play (seconds): "))
    max_delay = float(input("Enter maximum delay before clicking play (seconds): "))
    play_count = int(input("Enter the number of times to click play: "))

    target_percentage = 0.5

    logger = Logger("[Blum]")
    target_colors = ["#c9e100", "#bae70e"]
    nearby_colors = ["#abff61", "#87ff27"]
    threshold = 0.8

    auto_clickers = []
    for hwnd in [win[1] for win in windows]:
        auto_clicker = AutoClicker(hwnd, target_colors, nearby_colors, threshold, logger, target_percentage,
                                   hit_chance, min_delay, max_delay, play_count)
        auto_clickers.append(auto_clicker)

    print("Press F2 to toggle the script on and off.")

    keyboard.add_hotkey('F2', toggle_script)

    try:
        for auto_clicker in auto_clickers:
            auto_clicker.click_color_areas()
    except Exception as e:
        logger.log(f"There is something wrong: {e}")
