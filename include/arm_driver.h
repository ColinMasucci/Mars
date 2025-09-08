#pragma once
#include "types.h"
#include <vector>
#include <string>

class IArmDriver {
public:
    virtual ~IArmDriver() = default;

    virtual Capability capability() const = 0;
    virtual void connect() = 0;
    virtual void home() = 0;

    virtual void moveToPose(const Pose& p) = 0;
    virtual void moveJoints(const std::vector<double>& q) = 0;

    virtual void setGripper(bool closed) = 0;
};
