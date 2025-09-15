#include "arm_driver.h"
#include "types.h"
#include <iostream>
#include <vector>
#include <string>
#include "custom_arm_driver.h"


CustomArmDriver::CustomArmDriver(const std::string& ip): ip_(ip) {}

Capability CustomArmDriver::capability() const {
    Capability c; c.cartesian_move = true; c.joint_move = true; c.gripper = true; c.dof = 7; return c;
}

void CustomArmDriver::connect() { 
    std::cout << "[CustomArmDriver] connect to " << ip_ << "\n"; 
}

void CustomArmDriver::home() { 
    std::cout << "[CustomArmDriver] moving to home (7-joint preset)\n"; 
}

void CustomArmDriver::moveToPose(const Pose& p) {
    std::cout << "[CustomArmDriver] move to cartesian ("<<p.x<<","<<p.y<<","<<p.z<<")\n";
}

void CustomArmDriver::moveJoints(const std::vector<double>& q) {
    if (q.size() != 7) throw RobotError("Panda expects 7 joints");
    std::cout << "[CustomArmDriver] move joints (7 values)\n";
}

void CustomArmDriver::setGripper(bool closed) { 
    std::cout << "[CustomArmDriver] gripper " << (closed ? "close":"open") << "\n"; 
}


