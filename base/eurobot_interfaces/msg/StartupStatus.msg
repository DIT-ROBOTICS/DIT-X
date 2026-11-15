# Published by main/startup on the transient_local "state" QoS, so late joiners
# immediately get the latest value.

std_msgs/Header header
string[] ready_domains
string[] missing_domains
bool all_ready
