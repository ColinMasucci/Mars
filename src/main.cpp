#include "Robot.h"
#include "Romi.h"
#include "DifferentialDrivePlugin.h"
#include "SimpleGripper.h"

int main() {
    Robot robot;

    // Add Romi drive
    std::shared_ptr<Romi> DiffDrive = std::make_shared<Romi>();
    robot.addComponent(DiffDrive);

    // Add a gripper to Romi as a child component
    std::shared_ptr<SimpleGripper> gripper = std::make_shared<SimpleGripper>();
    DiffDrive->addChild(gripper);

    robot.listComponents();

    // Use plugin
    DifferentialDrivePlugin drivePlugin(DiffDrive);
    drivePlugin.moveForward(0.5f, 1000);
    drivePlugin.turn(0.5f, 800);


    // Test the gripper
    gripper->toggle();
    gripper->toggle();

    return 0;
}
