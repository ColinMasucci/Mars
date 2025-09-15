#include "robot_arm.h"
#include <iostream>
int main() {
    // unsupported: # tiny MARS example
    RobotArm arm = RobotArm::fromConfig("configs/robot_config_panda.json");
    // unsupported: new Arm = arm
    // unsupported: arm.home
    // unsupported: arm.moveToPose 0.40 0.00 0.20
    // unsupported: arm.setGripper true
    // unsupported: arm.moveToPose 0.60 0.00 0.20
    return 0;
}