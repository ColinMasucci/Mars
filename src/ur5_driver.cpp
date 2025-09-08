#include "arm_driver.h"
#include "types.h"
#include <iostream>
#include <vector>
#include <string>
#include "ur5_driver.h"


UR5Driver::UR5Driver(const std::string& ip): ip_(ip) {}

Capability UR5Driver::capability() const {
    Capability c; c.cartesian_move = true; c.joint_move = true; c.gripper = true; c.dof = 6; return c;
}

void UR5Driver::connect() { 
    std::cout << "[UR5Driver] connect to " << ip_ << "\n"; 
}

void UR5Driver::home() { 
    std::cout << "[UR5Driver] moving to home (6-joint preset)\n"; 
}

void UR5Driver::moveToPose(const Pose& p)  {
    std::cout << "[UR5Driver] move to cartesian ("<<p.x<<","<<p.y<<","<<p.z<<")\n";
}

void UR5Driver::moveJoints(const std::vector<double>& q)  {
    if (q.size() != 6) throw RobotError("UR5 expects 6 joints");
    std::cout << "[UR5Driver] move joints (6 values)\n";
}

void UR5Driver::setGripper(bool closed) { 
    std::cout << "[UR5Driver] gripper " << (closed ? "close":"open") << "\n"; 
}


