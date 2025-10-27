#ifndef DIFFERENTIALDRIVEPLUGIN_H
#define DIFFERENTIALDRIVEPLUGIN_H

#include "IDifferentialDrive.h"
#include <thread>
#include <chrono>
#include <iostream>

class DifferentialDrivePlugin {
public:
    DifferentialDrivePlugin(std::shared_ptr<IDifferentialDrive> drive)
        : drive(drive) {}

    void moveForward(float speed, int durationMs) {
        std::cout << "[Plugin] Moving forward..." << std::endl;
        drive->spinLeftMotor(speed);
        drive->spinRightMotor(speed);
        std::this_thread::sleep_for(std::chrono::milliseconds(durationMs));
        stop();
    }

    void turn(float speed, int durationMs) {
        std::cout << "[Plugin] Turning..." << std::endl;
        drive->spinLeftMotor(-speed);
        drive->spinRightMotor(speed);
        std::this_thread::sleep_for(std::chrono::milliseconds(durationMs));
        stop();
    }

    void stop() {
        drive->spinLeftMotor(0);
        drive->spinRightMotor(0);
        std::cout << "[Plugin] Stopped." << std::endl;
    }

private:
    std::shared_ptr<IDifferentialDrive> drive;
};

#endif // DIFFERENTIALDRIVEPLUGIN_H
