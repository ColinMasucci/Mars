#pragma once
#include "arm_driver.h"
#include <string>
#include <vector>

class PandaDriver : public IArmDriver {
public:
    explicit PandaDriver(const std::string& ip);

    Capability capability() const override;
    void connect() override;
    void home() override;

    void moveToPose(const Pose& p) override;
    void moveJoints(const std::vector<double>& q) override;
    void setGripper(bool closed) override;

private:
    std::string ip_;
};
