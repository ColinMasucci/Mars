#ifndef ROBOT_H
#define ROBOT_H

#include "IComponent.h"

class Robot {
public:
    void addComponent(std::shared_ptr<IComponent> comp) {
        components.push_back(comp);
    }

    void updateAll() {
        for (auto& comp : components) {
            comp->update();
        }
    }

    void listComponents() const {
        std::cout << "Robot Components:" << std::endl;
        for (auto& comp : components) {
            std::cout << " - " << comp->getName() << std::endl;
        }
    }

private:
    std::vector<std::shared_ptr<IComponent>> components;
};

#endif // ROBOT_H
