import os
import sys
import unittest


THIS_DIR = os.path.dirname(__file__)
COMPILER_DIR = os.path.abspath(os.path.join(THIS_DIR, ".."))
if COMPILER_DIR not in sys.path:
    sys.path.insert(0, COMPILER_DIR)

from component_visualizer import visualize_components
from lexer import tokenize
from parser import Parser


class ComponentVisualizerTests(unittest.TestCase):
    def _parse_components(self, source):
        return Parser(tokenize(source)).parse().components

    def test_override_subcomponents_are_hidden_in_tree(self):
        components = self._parse_components(
            """
            component Motor {
                subcomponents {}
                parameters {}
                functions {}
            }

            component Sensor {
                subcomponents {}
                parameters {}
                functions {}
            }

            component BaseChassis {
                subcomponents { Motor driveMotor; }
                parameters {}
                functions {}
            }

            component ChildChassis extends BaseChassis {
                subcomponents {
                    @Override Motor driveMotor;
                    Sensor auxSensor;
                }
                parameters {}
                functions {}
            }

            component Rover extends Robot {
                subcomponents { ChildChassis chassis; }
                parameters {}
                functions {}
            }
            """
        )

        dot = visualize_components(components)
        self.assertIn("Rover.chassis.auxSensor", dot.source)
        self.assertNotIn("Rover.chassis.driveMotor", dot.source)


if __name__ == "__main__":
    unittest.main()
