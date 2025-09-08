#include "factory.h"
#include "ur5_driver.h"
#include "panda_driver.h"
#include <stdexcept>

std::unique_ptr<IArmDriver> makeDriver(const std::string& type, const std::string& ip) {
    if (type == "ur5") {
        return std::make_unique<UR5Driver>(ip);
    }
    if (type == "panda") {
        return std::make_unique<PandaDriver>(ip);
    }
    throw std::runtime_error("Unknown driver type: " + type);
}
