from core.services.base import CoreService, ServiceMode


ION_MARS_DIR = "/home/moss/Desktop/Emion/ion_mars"


class IonMarsService(CoreService):
    name = "ION_MARS"
    group = "Custom"
    directories = ["/var/ion"]
    executables = ["bash", "ionstart", "ionstop", "ionadmin", "bpadmin", "ipnadmin"]
    startup = [f"bash {ION_MARS_DIR}/ion_start.sh"]
    shutdown = ["killm"]
    validation_mode = ServiceMode.TIMER
    validation_timer = 4
