#ifndef IGRIPPER_H
#define IGRIPPER_H

#include "IComponent.h"

class IGripper : public IComponent {
public:
    virtual ~IGripper() = default;

    // Abstract function every gripper must implement
    virtual void toggle() = 0;

    std::string getName() const override {
        return "IGripper";
    }
};

#endif // IGRIPPER_H
