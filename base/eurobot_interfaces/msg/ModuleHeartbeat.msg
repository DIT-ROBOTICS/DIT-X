# Liveness + self-reported health of one module; used by the status overview.
# stamp is system time (for logs); uptime is measured with a steady clock.

uint8 OK = 0
uint8 WARN = 1
uint8 ERROR = 2

std_msgs/Header header
string domain
string module
uint8 level
float64 uptime_sec
string detail
