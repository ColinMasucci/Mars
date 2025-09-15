#pragma once
#include "arm_driver.h"
#include "types.h"

inline Pose planSafeApproach(const Pose& target) {
    Pose p = target; p.z += 0.10; // 10 cm above
    return p;
}

inline void enforceSafetyPreconditions(const IArmDriver& drv, const Pose& p) {
    // placeholder: check workspace, speeds, joint limits (later)
    (void)drv; (void)p;
}
