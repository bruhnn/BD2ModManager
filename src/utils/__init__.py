from ctypes import windll

def is_running_as_admin():
    return windll.shell32.IsUserAnAdmin() == 1
