//This is where we can place custom Types that the user can use
#pragma once
#include <stdexcept>

struct Pose {
          //Position  //Orientation
    double x,y,z,     roll, pitch, yaw;
};

struct Capability {
    bool cartesian_move = false;
    bool joint_move = false;
    bool gripper = false;
    int dof = 0;
};

class RobotError : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};
