//This file acts as a thin wrapper so certain broader actions can be performed outside from whats defined inside the IArmDriver
//For example configuring the Arm Driver so that it knows which virtual arm driver to use (ex. ur5 vs panda), Or maybe some safety checks can be performed here as well.
//All of the definitions defined in the arm_driver.h file arm just passed through to their designated driver.

#include "robot_arm.h"
#include "factory.h"
#include "config.h"
#include "safety.h"
#include <iostream>


extern std::unique_ptr<IArmDriver> makeDriver(const std::string&, const std::string&);

RobotArm RobotArm::fromConfig(const std::string& path) {
    RobotConfig cfg = loadRobotConfig(path);
    RobotArm a;
    a.cfg_ = cfg;
    a.driver_ = makeDriver(cfg.type, cfg.ip);
    a.driver_->connect();
    validateVendorConfig(cfg, *a.driver_);
    return a;
}

IArmDriver& RobotArm::driver(){
    return *driver_;
}

void RobotArm::home() {
    driver_->home();
}

Capability RobotArm::capability() const{
    return driver_->capability();
}

void RobotArm::moveToPose(const Pose& p) {
    driver_->moveToPose(p);
}

void RobotArm::moveJoints(const std::vector<double>& q) {
    driver_->moveJoints(q);
}

void RobotArm::setGripper(bool closed) {
    driver_->setGripper(closed);
}
