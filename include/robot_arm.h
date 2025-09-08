#pragma once
#include "types.h"
#include "config.h"
#include "arm_driver.h"
#include <memory>
#include <string>

class RobotArm {
public:
    static RobotArm fromConfig(const std::string& path);

    IArmDriver& driver();
    void connect();
    void home();
    Capability capability() const;

    void moveToPose(const Pose& p);
    void moveJoints(const std::vector<double>& q);
    void setGripper(bool closed);

private:
    RobotArm() = default;
    std::unique_ptr<IArmDriver> driver_;
    RobotConfig cfg_;
};
