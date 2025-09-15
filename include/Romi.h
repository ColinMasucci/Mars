#ifndef ROMI_H
#define ROMI_H

#include "IDifferentialDrive.h"

class Romi : public IDifferentialDrive {
public:
    Romi() {
        configure("configs/romi.yaml");

        // Apply config
        leftMaxSpeed = std::stof(getConfigValue("left_motor_max_speed", "1.0"));
        rightMaxSpeed = std::stof(getConfigValue("right_motor_max_speed", "1.0"));
        wheelBase = std::stof(getConfigValue("wheel_base", "0.2"));
    }

    void spinLeftMotor(float speed) override {
        std::cout << "[Romi] LEFT motor speed: " << clamp(speed, leftMaxSpeed) << std::endl;
    }

    void spinRightMotor(float speed) override {
        std::cout << "[Romi] RIGHT motor speed: " << clamp(speed, rightMaxSpeed) << std::endl;
    }

    std::string getName() const override {
        return "Romi Differential Drive";
    }

private:
    float leftMaxSpeed{1.0f};
    float rightMaxSpeed{1.0f};
    float wheelBase{0.2f};

    float clamp(float input, float maxVal) {
        if (input > maxVal) return maxVal;
        if (input < -maxVal) return -maxVal;
        return input;
    }
};

#endif // ROMI_H
