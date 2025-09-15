#pragma once
#include "arm_driver.h"
#include <memory>
#include <string>

// Factory function to create the correct driver implementation
std::unique_ptr<IArmDriver> makeDriver(const std::string& type, const std::string& ip);
