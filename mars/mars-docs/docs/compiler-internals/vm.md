---
id: vm
title: Virtual Machine
sidebar_label: VM
sidebar_position: 4
---

The Virtual Machine (VM) executes compiled **bytecode instructions** produced by the Mars compiler. It is a **stack-based runtime** with support for functions, objects, components, and ROS-style I/O.

---

## Overview

The VM is responsible for:

- Executing bytecode instructions sequentially
- Managing a runtime stack
- Handling variables, scopes, and functions
- Supporting objects, classes, and components
- Integrating with external systems (e.g. ROS)

---

## Execution Model

The VM uses a **stack-based architecture**:

- Values are pushed onto a stack
- Instructions pop operands and push results
- Execution is controlled by a program counter (`pc`)

Example:
```python
PUSH_INT 5
PUSH_INT 3
ADD
```

---

## Core Components

### Stack
Main evaluation stack used for expressions and calls.

### Locals / Globals
- `locals` → function scope
- `globals` → program-wide scope

### Call Stack
Stores function return states:

- return address
- local variables
- scope state

---

## Program Execution

The VM runs using:

```python
run()
```

Each cycle:

- `sense()` → read external inputs (ROS, sensors)
- `execute_one()` → run one bytecode instruction
- `act()` → publish outputs

---

## Instructions
### Data Instructions
PUSH_INT, PUSH_FLOAT, PUSH_STR, PUSH_BOOL
PUSH_NONE

### Arithmetic & Logic
`ADD`, `SUB`, `MUL`, `DIV`, `MOD`, `POW`
`AND`, `OR`
`LT`, `GT`, `LEQ`, `GEQ`, `EQ`, `NEQ`
`NEGATE`, `NOT`

### Stack Operations
`POP`
`DUP`
`DUP2`
`SWAP`

### Variables
#### Declaration
```python
DECLARE name type readonly
```

#### Assignment
```python
STORE name
LOAD name
```

### Scopes
```python
ENTER_SCOPE
EXIT_SCOPE
```
Used to manage block-level variables.

## Control Flow
### Jumps
```python
JUMP target
JUMP_IF_FALSE target
HALT
```

### Functions
```python
FUNC_BEGIN name param_count
FUNC_END name
CALL name arg_count
RETURN
```

The VM supports:

- user-defined functions
- recursion
- nested calls

### Methods & Objects
```python
CALL_METHOD method arg_count
NEW_CALL arg_count
GET_FIELD field
SET_FIELD field
```

Supports:
- classes
- objects
- method dispatch

---

## Data Structures
### Arrays
```python
BUILD_ARRAY N
INDEX_GET
INDEX_SET
PUSH_EMPTY_ARRAY
```

### Dictionaries
```python
BUILD_DICT N
INDEX_GET
INDEX_SET
PUSH_EMPTY_DICT
```

---

## Type System

The VM performs **runtime type checking** for safety.

Supported types:
- `int`
- `float`
- `bool`
- `string`
- `array<T>`
- `dict<K,V>`
- `class:X`
- `component:X`

Invalid types raise:
```python
VMError
```

---

## Components

The VM supports a **component tree system**:
- hierarchical components
- parameter binding
- subcomponents
- method calls

Special instruction:
```python
MATCH_COMPONENT
```
Used to search for matching component types in the tree.

---

## External Integration (ROS)

The VM supports real-time I/O via a ROS bridge.

### Sensor Input
```python
sense()
```
updates `sensor_cache`
syncs subscribed variables

### Publishing
```python
PUBLISH
```
Queued via:
```python
queue_publish(topic, type, msg)
```

### Waiting
```python
WAIT seconds
```
Runs a cooperative sleep loop while still processing IO.

### Update Loop
```python
UPDATE
```
Refreshes all subscribed component values.

## Memory Model
### Objects

Objects are stored as:
```python
{
  "__class__": name,
  "__fields__": {...},
  "__readonly__": {...}
}
```

### Modules

Imported dynamically and cached:
```python
IMPORT module_name
```

Modules expose:
- functions
- constants
- attributes

---

## Error Handling

All runtime errors raise:
```python
VMError
```

Includes:
- stack underflow
- invalid operations
- type mismatches
- undefined variables
- invalid memory access

Errors can optionally be mapped back to source code using `source_map`.

## Execution Safety

The VM prevents:
- infinite loops (via max_steps)
- invalid memory access
- invalid type usage
- illegal assignments (readonly fields)

## Design Notes
- Stack-based execution model
- Single instruction dispatch loop
- Strict runtime type checking
