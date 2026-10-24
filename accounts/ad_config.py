
import os

AD_SERVER = os.getenv(
    "AD_SERVER",
    "WIN-JORTVA45BJJ.TEST.local",
)

AD_PORT = int(os.getenv("AD_PORT", "636"))

AD_BASE_DN = os.getenv(
    "AD_BASE_DN",
    "DC=TEST,DC=local",
)

AD_BIND_USER = os.getenv("AD_BIND_USER", "")
AD_BIND_PASSWORD = os.getenv("AD_BIND_PASSWORD", "")

# Active Directory user-creation settings
AD_USER_CREATE_OU = "OU=Django-Test-Users,DC=TEST,DC=local"

AD_WRITE_BIND_USER = os.getenv("AD_WRITE_BIND_USER", "")
AD_WRITE_BIND_PASSWORD = os.getenv("AD_WRITE_BIND_PASSWORD", "")
