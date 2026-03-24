# Requirements

Requirements let classes declare what component capabilities they need. They are validated against the component configuration built from `.marsc` files.

## Where Requirements Live
Requirements appear inside class definitions:
```mars
class Example {
    requirements {
        Motor(functions=spin());
        optional Sensor(parameters=[range > 10]);
    }
}
```

## Syntax Overview
A requirement item is a requirement expression, terminated by a semicolon:
```mars
requirements {
    Chassis(parameters=[trackWidth > 0]);
    Arm(functions=[lift(), extend()]);
    Drive && Sensors;
    !DebugComponent;
    optional Encoder;
}
```

The building blocks:
- Requirement spec: `TypeName(...)`
- Logical operators: `&&`, `||`, `!`
- Parentheses for grouping
- `optional` modifier

## Requirement Spec
The core form is `TypeName(...)` where `TypeName` is a component type. Inside the parentheses, you can add any of these keys:
- `parameters=...`
- `functions=...`
- `subcomponents=...`

Example:
```mars
Chassis(
    parameters=[trackWidth > 0, scrubFactor >= 0],
    functions=[drive(), getVelocities()]
);
```

### Parameters
`parameters` is a list of boolean expressions evaluated against a component instance’s parameters.

Example:
```mars
Motor(parameters=[maxRPM >= 10]);
```

Rules and behavior:
- Parameter names refer to the target component’s parameters.
- Expressions must be evaluatable from literals and simple operators.
- If a required parameter is missing or cannot be evaluated, the requirement fails.
- Unit tags are supported in expressions.

### Functions
`functions` is a list of required function names (with empty parentheses).

Example:
```mars
Chassis(functions=[drive(), getVelocities()]);
```

Only function presence is checked, not parameter types.

### Subcomponents
`subcomponents` is a list of nested requirement expressions that must be satisfied somewhere under the target component’s subtree.

Example:
```mars
RobotBase(subcomponents=[Motor(functions=spin())]);
```

Subcomponent requirements can use `&&`, `||`, and `!` just like top-level requirements.

## Optional Requirements
`optional` can be applied in three places:
- Before a requirement item: `optional Sensor;`
- Before a spec in a list: `subcomponents=[optional Sensor]`
- Before a parameter or function requirement: `parameters=[optional range > 10]`, `functions=[optional spin()]`

Optional requirements do not fail the build. They are reported as flags.

## How Requirements Are Evaluated
Requirements are checked against the component tree built from `.marsc` config:
- Only Robot-family roots are considered.
- A requirement spec matches any component instance of that type or any derived type in the subtree.
- If any matching instance satisfies all constraints, the requirement passes.
- If only optional constraints fail, the requirement passes with a flag.
- If no match satisfies the constraints, the requirement fails.

Logical operators:
- `A && B` requires both to pass.
- `A || B` passes if either passes.
- `!A` passes only if `A` does not pass.

`optional` turns a hard failure into a flag at the point it appears.

## Interaction With Configuration
Requirements use data from the configuration:
- Parameter values come from defaults and bindings in `.marsc`.
- Missing required parameters in config are configuration errors, not requirement errors.
- Function presence is derived from component definitions and inheritance.

Inheritance matters:
- A requirement for `Chassis` also matches `DifferentialChassis` or any derived component.

## When Requirements Run
There are two validation passes:
- Config pass: requirements are checked against all Robot-family roots based purely on `.marsc`.
- Instantiated pass: requirements are checked against actual component arguments passed to class constructors.

The instantiated pass resolves component paths through:
- Direct component variables
- Member access (`robot.chassis`)
- `match()` expressions

If a class has requirements but no component argument can be resolved, validation fails.

## Outputs
Hard failures abort execution with a detailed message.
Optional failures are printed as flags (prefixed with `[requirements]`).
