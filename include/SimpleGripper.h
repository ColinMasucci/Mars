#ifndef SIMPLEGRIPPER_H
#define SIMPLEGRIPPER_H

#include "IGripper.h"
#include <iostream>

class SimpleGripper : public IGripper {
public:
    SimpleGripper() {
        configure("configs/gripper.yaml");

        maxForce = std::stof(getConfigValue("max_force", "5.0"));
        std::string state = getConfigValue("initial_state", "open");
        isClosed = (state == "closed");
    }

    void toggle() override {
        isClosed = !isClosed;
        std::cout << "[Gripper] Toggled -> " 
                  << (isClosed ? "Closed" : "Open")
                  << " (max force: " << maxForce << ")" 
                  << std::endl;
    }

    std::string getName() const override {
        return "Simple Gripper";
    }

private:
    bool isClosed{false};
    float maxForce{5.0f};
};

#endif // SIMPLEGRIPPER_H
