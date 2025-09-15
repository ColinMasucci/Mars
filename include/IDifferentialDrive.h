#ifndef IDIFFERENTIALDRIVE_H
#define IDIFFERENTIALDRIVE_H

#include "IComponent.h"

class IDifferentialDrive : public IComponent {
public:
    virtual ~IDifferentialDrive() = default;

    // Core motor functions (abstract)
    virtual void spinLeftMotor(float speed) = 0;
    virtual void spinRightMotor(float speed) = 0;

    // Useful helper
    std::string getName() const override {
        return "IDifferentialDrive";
    }
};

#endif // IDIFFERENTIALDRIVE_H
