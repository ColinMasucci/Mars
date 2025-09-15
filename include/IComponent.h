#ifndef ICOMPONENT_H
#define ICOMPONENT_H

#include <string>
#include <vector>
#include <memory>
#include <iostream>
#include <fstream>
#include <sstream>
#include <unordered_map>

class IComponent {
public:
    float x{0.0f};
    float y{0.0f};
    float orientation{0.0f};

    virtual ~IComponent() = default;

    // Common YAML-style config loader
    virtual void configure(const std::string& configFile) {
        std::ifstream file(configFile);
        if (!file.is_open()) {
            std::cerr << "Failed to open config file: " << configFile << std::endl;
            return;
        }

        std::string line;
        while (std::getline(file, line)) {
            if (line.empty() || line[0] == '#') continue;

            std::istringstream iss(line);
            std::string key, value;
            if (std::getline(iss, key, ':')) {
                if (std::getline(iss, value)) {
                    // trim spaces
                    key.erase(0, key.find_first_not_of(" \t"));
                    key.erase(key.find_last_not_of(" \t") + 1);
                    value.erase(0, value.find_first_not_of(" \t"));
                    value.erase(value.find_last_not_of(" \t") + 1);
                    config[key] = value;
                }
            }
        }
        file.close();
    }

    std::string getConfigValue(const std::string& key, const std::string& def = "") const {
        auto it = config.find(key);
        return (it != config.end()) ? it->second : def;
    }

    void addChild(std::shared_ptr<IComponent> child) {
        children.push_back(child);
    }

    const std::vector<std::shared_ptr<IComponent>>& getChildren() const {
        return children;
    }

    // Every component should have a name/type
    virtual std::string getName() const = 0;

    // Optional: initialize/loop hook
    virtual void update() {
        // Default: no-op
    }

protected:
    std::vector<std::shared_ptr<IComponent>> children;
    std::unordered_map<std::string, std::string> config;
};

#endif // ICOMPONENT_H
