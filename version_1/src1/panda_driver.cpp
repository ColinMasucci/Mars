#include "arm_driver.h"
#include "types.h"
#include <iostream>
#include <vector>
#include <string>
#include "panda_driver.h"


PandaDriver::PandaDriver(const std::string& ip): ip_(ip) {}

Capability PandaDriver::capability() const {
    Capability c; c.cartesian_move = true; c.joint_move = true; c.gripper = true; c.dof = 7; return c;
}

void PandaDriver::connect() { 
    std::cout << "[PandaDriver] connect to " << ip_ << "\n"; 
}

void PandaDriver::home() { 
    std::cout << "[PandaDriver] moving to home (7-joint preset)\n"; 
}

void PandaDriver::moveToPose(const Pose& p) {
    std::cout << "[PandaDriver] move to cartesian ("<<p.x<<","<<p.y<<","<<p.z<<")\n";
}

void PandaDriver::moveJoints(const std::vector<double>& q) {
    if (q.size() != 7) throw RobotError("Panda expects 7 joints");
    std::cout << "[PandaDriver] move joints (7 values)\n";
}

void PandaDriver::setGripper(bool closed) { 
    std::cout << "[PandaDriver] gripper " << (closed ? "close":"open") << "\n"; 
}


