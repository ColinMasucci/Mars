#pragma once
#include "arm_driver.h"
#include <string>
#include <vector>

class UR5Driver : public IArmDriver {
public:
    explicit UR5Driver(const std::string& ip);

    Capability capability() const override;
    void connect() override;
    void home() override;

    void moveToPose(const Pose& p) override;                   // match signature!
    void moveJoints(const std::vector<double>& q) override;    // must implement
    void setGripper(bool closed) override;

private:
    std::string ip_;
};
