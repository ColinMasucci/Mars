//This is the main file that the user will create. Or more accurately the .cpp file that will be generated when the user finishes creating their .mars file and then compiles that.


//We can auto include any headers that are required so that the user does not have to memorize that sort of thing.
#include "robot_arm.h"
#include "safety.h"
#include <iostream>



void pick(const Pose& p, RobotArm& arm) { 
    //added some placeholder safety functions that can be called before had maybe. Or maybe they should be called automatically in the RobotArm.cpp whenever a movement function is called. Where the safety functions are called is up for debate. Currently there is a universal placeholder located in the safety.h file
    Pose approach = planSafeApproach(p); 
    enforceSafetyPreconditions(arm.driver(), approach); 
    arm.moveToPose(approach); 
    arm.moveToPose(p); 
    arm.setGripper(true); 
    arm.moveToPose(approach); 
} 

void place(const Pose& p, RobotArm& arm) { 
    Pose approach = planSafeApproach(p); 
    enforceSafetyPreconditions(arm.driver(), approach); 
    arm.moveToPose(approach); 
    arm.moveToPose(p); 
    arm.setGripper(false); 
    arm.moveToPose(approach); 
}

int main() {
    try {
        // Swap this file between robot_config_ur5.json and robot_config_panda.json
        //GOAL: THIS SHOULD BE THE ONLY LINE YOU NEED TO CHANGE!!!!!
        RobotArm arm = RobotArm::fromConfig("configs/robot_config_ur5.json");
        arm.home();

        Pose pickPose{0.4, 0.0, 0.20, 0, 0, 0};
        Pose placePose{0.6, 0.0, 0.20, 0, 0, 0};

        //METHOD 01 (User creates there own functions)
        printf("Method 01 (user created functions)");
        pick(pickPose, arm);
        place(placePose, arm);


        //METHOD 02 (Process is done manually line by line)
        printf("Method 02 (manual instructions)");
        //pickup logic
        arm.moveToPose(pickPose);
        arm.setGripper(true); 
        arm.home(); 

        //placedown logic
        arm.moveToPose(placePose);
        arm.setGripper(false); 
        arm.home(); 

    } catch (const std::exception& e) {
        std::cerr << "Fatal: " << e.what() << "\n";
    }
    return 0;
}
