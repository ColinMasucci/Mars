#pragma once
#include <string>

struct RobotConfig {
    std::string type;
    std::string vendor_config;
    std::string ip;
    std::string tool;
};

RobotConfig loadRobotConfig(const std::string& path);
void validateVendorConfig(const RobotConfig& cfg, const class IArmDriver& drv);
