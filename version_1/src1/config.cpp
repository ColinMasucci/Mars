#include "config.h"
#include "arm_driver.h"
#include "types.h"
#include "../third-party/json.hpp"   // third_party/json.hpp
#include <fstream>
#include <iostream>

using json = nlohmann::json;

RobotConfig loadRobotConfig(const std::string& path) {
    std::ifstream f(path);
    if (!f) throw std::runtime_error("Cannot open config: " + path);
    json j; f >> j;
    RobotConfig cfg;
    cfg.type = j["robot"]["type"].get<std::string>();
    cfg.vendor_config = j["robot"]["vendor_config"].get<std::string>();
    cfg.ip = j["robot"]["ip"].get<std::string>();
    if (j["robot"].contains("tool")) cfg.tool = j["robot"]["tool"].get<std::string>();
    return cfg;
}

void validateVendorConfig(const RobotConfig& cfg, const IArmDriver& drv) {
    std::ifstream f(cfg.vendor_config);
    if (!f) throw std::runtime_error("Cannot open vendor config: " + cfg.vendor_config);
    json j; f >> j;
    int vendor_dof = j["dof"].get<int>();
    Capability c = drv.capability();
    if (vendor_dof != c.dof) {
        std::cerr << "Warning: vendor DOF ("<<vendor_dof<<") != driver DOF ("<<c.dof<<")\n";
    }
    // more checks can be added: joint names present, required capabilities, etc.
}
