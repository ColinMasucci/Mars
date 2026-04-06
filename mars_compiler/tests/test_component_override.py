import os
import sys
import unittest


THIS_DIR = os.path.dirname(__file__)
COMPILER_DIR = os.path.abspath(os.path.join(THIS_DIR, ".."))
if COMPILER_DIR not in sys.path:
    sys.path.insert(0, COMPILER_DIR)

from component_validator import ComponentValidationError, ComponentValidator
from lexer import tokenize
from parser import Parser


class ComponentOverrideTests(unittest.TestCase):
    def parse_components(self, source):
        program = Parser(tokenize(source)).parse()
        return program.components

    def test_parser_accepts_override_for_parameters_and_subcomponents(self):
        components = self.parse_components(
            """
            component Motor {
                subcomponents {}
                parameters { int port; }
                functions {}
            }

            component Base {
                subcomponents { Motor left; }
                parameters { int speed = 1; }
                functions {}
            }

            component Child extends Base {
                subcomponents { @override Motor left(port = 1); }
                parameters { @override int speed = 2; }
                functions {}
            }
            """
        )

        child = next(comp for comp in components if comp.name == "Child")
        self.assertTrue(child.subcomponents[0].is_override)
        self.assertTrue(child.parameters[0].is_override)

    def test_lowercase_override_token_is_accepted(self):
        components = self.parse_components(
            """
            component Motor {
                subcomponents {}
                parameters {}
                functions {}
            }

            component Base {
                subcomponents { Motor left; }
                parameters { int speed = 1; }
                functions {}
            }

            component Child extends Base {
                subcomponents { @override Motor left; }
                parameters { @override int speed = 2; }
                functions {}
            }
            """
        )

        child = next(comp for comp in components if comp.name == "Child")
        self.assertTrue(child.subcomponents[0].is_override)
        self.assertTrue(child.parameters[0].is_override)

    def test_override_param_requires_inherited_param(self):
        components = self.parse_components(
            """
            component Base {
                subcomponents {}
                parameters {}
                functions {}
            }

            component Child extends Base {
                subcomponents {}
                parameters { @Override int speed = 2; }
                functions {}
            }
            """
        )

        with self.assertRaises(ComponentValidationError) as ctx:
            ComponentValidator(components).validate()

        self.assertIn("no inherited parameter exists", str(ctx.exception))

    def test_override_subcomponent_requires_inherited_subcomponent(self):
        components = self.parse_components(
            """
            component Motor {
                subcomponents {}
                parameters {}
                functions {}
            }

            component Base {
                subcomponents {}
                parameters {}
                functions {}
            }

            component Child extends Base {
                subcomponents { @Override Motor left; }
                parameters {}
                functions {}
            }
            """
        )

        with self.assertRaises(ComponentValidationError) as ctx:
            ComponentValidator(components).validate()

        self.assertIn("no inherited subcomponent exists", str(ctx.exception))

    def test_override_subcomponent_must_keep_same_type(self):
        components = self.parse_components(
            """
            component Motor {
                subcomponents {}
                parameters {}
                functions {}
            }

            component SmartMotor {
                subcomponents {}
                parameters {}
                functions {}
            }

            component Base {
                subcomponents { Motor left; }
                parameters {}
                functions {}
            }

            component Child extends Base {
                subcomponents { @Override SmartMotor left; }
                parameters {}
                functions {}
            }
            """
        )

        with self.assertRaises(ComponentValidationError) as ctx:
            ComponentValidator(components).validate()

        self.assertIn("must match inherited type", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
