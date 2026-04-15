import os
import sys
import unittest


THIS_DIR = os.path.dirname(__file__)
COMPILER_DIR = os.path.abspath(os.path.join(THIS_DIR, ".."))
if COMPILER_DIR not in sys.path:
    sys.path.insert(0, COMPILER_DIR)

from ast_nodes import ComponentDef, SubcomponentDecl, VarDecl
from component_registry import ComponentRegistry
from component_validator import ComponentValidationError, ComponentValidator
from configuration_check import build_component_tree


class ConfigRequiredParamsTests(unittest.TestCase):
    def test_subcomponent_validation_includes_inherited_required_params(self):
        base = ComponentDef(
            "BaseMotor",
            None,
            [],
            [VarDecl("int", "port", None)],
            [],
        )
        child = ComponentDef("SmartMotor", "BaseMotor", [], [], [])
        chassis = ComponentDef(
            "Chassis",
            None,
            [SubcomponentDecl("SmartMotor", "leftMotor", [])],
            [],
            [],
        )

        with self.assertRaises(ComponentValidationError) as ctx:
            ComponentValidator([base, child, chassis]).validate()

        self.assertIn("missing required parameter 'port'", str(ctx.exception))

    def test_root_robot_component_requires_inherited_params(self):
        robot = ComponentDef("Robot", None, [], [], [])
        base = ComponentDef(
            "DriveBase",
            "Robot",
            [],
            [VarDecl("float", "wheelRadius", None)],
            [],
        )
        rover = ComponentDef("Rover", "DriveBase", [], [], [])

        registry = ComponentRegistry()
        for comp in [robot, base, rover]:
            registry.register(comp)

        interfaces = ComponentValidator([robot, base, rover]).validate()

        with self.assertRaises(ComponentValidationError) as ctx:
            build_component_tree(registry, interfaces)

        self.assertIn("missing required parameter 'wheelRadius'", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
