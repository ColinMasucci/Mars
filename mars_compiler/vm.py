from typing import List, Tuple, Any
import importlib.util
import os
import types
import time;


Instr = Tuple[str, ...]
_UNDECLARED = object()

class VMError(Exception): pass

def _strip_unit_type(typ):
    if not isinstance(typ, str):
        return typ
    if typ.startswith(("array<", "dict<", "component:", "class:")):
        return typ
    if "::" in typ:
        return typ.split("::", 1)[0]
    return typ

class VM:
    def __init__(self, bytecode: List[Instr], class_field_info=None, component_tree=None, component_parents=None):
        self.code = bytecode
        self.stack = []
        self.pc = 0
        self.locals = {}  # current frame locals {name: (value, vartype, readonly)}
        self.globals = {} # global frame
        self._modules = {}  # module_name -> module object
        self.call_stack = []  # stack of (return_pc, locals_snapshot, local_scope_stack_snapshot)
        self.global_scope_stack = []
        self.local_scope_stack = []
        self.class_field_info = class_field_info or {}
        self.component_tree = component_tree or {"nodes": {}, "roots": []}
        self.component_parents = component_parents or {}

        self.subscriptions = {}
        # var_name -> {"topic": topic_name, "field_path": [nested, keys]}
        # example: {"pose": {"topic": "/robot/pose", "field_path": ["position", "x"]}}

        self.sensor_cache = {}   
        # topic_name -> last_value
        # example: {"/robot/pose": PoseMsg, "/lidar": LaserScanMsg}

        self.step_stack = []     
        # stores return PCs for STEP loops
        # acts like a loop stack (like call_stack, but for control flow)

        self.ros_bridge = None
        self.ros_topics_path = None
        self.ros_topics = []
        self._publish_queue = []
        self._subscription_specs = []
        self._load_config_subscriptions()

    def _load_config_subscriptions(self):
        specs = []
        seen = set()
        for path, node in self.component_tree.get("nodes", {}).items():
            for pname, sub in node.get("subscriptions", {}).items():
                topic = sub.get("topic")
                msg_type = sub.get("msg_type")
                field_path = sub.get("field_path", [])
                if not topic or not msg_type:
                    continue
                var_name = f"{path}.{pname}"
                self.subscriptions[var_name] = {"topic": topic, "field_path": field_path}
                key = (topic, msg_type)
                if key in seen:
                    continue
                seen.add(key)
                specs.append({"name": topic, "type": msg_type})
        self._subscription_specs = specs

    def attach_ros_bridge(self, bridge, topics_path: str | None = "ros_topics.txt", request_topics: bool = True):
        self.ros_bridge = bridge
        self.ros_topics_path = topics_path
        if self.ros_bridge and request_topics:
            try:
                self.ros_bridge.request_topics()
            except Exception as e:
                print(f"[ros] request_topics failed: {e}")
        if self.ros_bridge and self._subscription_specs:
            try:
                self.ros_bridge.subscribe(self._subscription_specs)
            except Exception as e:
                print(f"[ros] subscribe setup failed: {e}")

    def queue_publish(self, topic: str, msg_type: str, msg: Any):
        self._publish_queue.append((topic, msg_type, msg))

    def _wait_cooperative(self, seconds: float, tick: float = 0.01):
        if seconds <= 0:
            return
        deadline = time.monotonic() + seconds
        while True:
            now = time.monotonic()
            if now >= deadline:
                break
            # Keep message IO moving while waiting.
            self.sense()
            self.act()
            remaining = deadline - now
            time.sleep(min(tick, remaining))

    def _apply_subscriptions(self):
        for var, sub in self.subscriptions.items():
            topic = sub.get("topic")
            if topic in self.sensor_cache:
                val = self._extract_subscription_value(self.sensor_cache[topic], sub.get("field_path", []))
                if var in self.locals:
                    old = self.locals[var]
                    self._runtime_type_check(val, old[1], f"variable '{var}'")
                    self.locals[var] = (val, old[1], old[2])
                elif var in self.globals:
                    old = self.globals[var]
                    self._runtime_type_check(val, old[1], f"variable '{var}'")
                    self.globals[var] = (val, old[1], old[2])

    def _extract_subscription_value(self, payload, field_path):
        cur = payload
        for part in field_path or []:
            if not isinstance(cur, dict):
                raise VMError(f"Subscribed message field path '{'.'.join(field_path)}' is not available")
            if part not in cur:
                raise VMError(f"Subscribed message field '{part}' not found in path '{'.'.join(field_path)}'")
            cur = cur[part]
        return cur

    def _component_is_a(self, child_type, parent_type):
        if child_type == parent_type:
            return True
        cur = self.component_parents.get(child_type)
        while cur:
            if cur == parent_type:
                return True
            cur = self.component_parents.get(cur)
        return False

    def _match_component(self, start_path, target_type):
        nodes = self.component_tree.get("nodes", {})
        if start_path not in nodes:
            raise VMError(f"Unknown component '{start_path}'")

        queue = [(start_path, 0)]
        matches = []
        current_depth = 0

        while queue:
            path, depth = queue.pop(0)
            if depth > current_depth and matches:
                break
            if depth > current_depth:
                current_depth = depth
            node = nodes.get(path)
            if node is None:
                continue
            if self._component_is_a(node["type"], target_type):
                matches.append(path)
            for child in node.get("children", []):
                queue.append((child, depth + 1))

        if not matches:
            raise VMError(f"match could not find '{target_type}' under '{start_path}'")
        if len(matches) > 1:
            raise VMError(f"match found multiple '{target_type}' under '{start_path}' at depth {current_depth}")
        return matches[0]

    def _resolve_component_function(self, func_name):
        if "." not in func_name:
            return None, None
        parts = func_name.split(".")
        path = ".".join(parts[:-1])
        method = parts[-1]
        node = self.component_tree.get("nodes", {}).get(path)
        if node and method in node.get("functions", set()):
            return f"{node['type']}.{method}", path
        return None, None

    def _bind_component_locals(self, component_path):
        node = self.component_tree.get("nodes", {}).get(component_path)
        if not node:
            return
        # Bind component params into locals (readonly).
        param_types = node.get("param_types", {})
        param_values = node.get("params", {})
        for pname, ptype in param_types.items():
            if pname not in self.locals:
                self.locals[pname] = (param_values.get(pname), ptype, True)
        # Bind direct subcomponents into locals (readonly).
        for sname, spath in node.get("subcomponents", {}).items():
            if sname in self.locals:
                continue
            child = self.component_tree.get("nodes", {}).get(spath)
            stype = child.get("type") if child else None
            vtype = f"component:{stype}" if stype else "component"
            self.locals[sname] = (spath, vtype, True)

    def _normalize_runtime_type(self, typ):
        if not isinstance(typ, str):
            return typ
        if typ.endswith("[]"):
            return f"array<{self._normalize_runtime_type(typ[:-2])}>"
        return typ

    def _copy_scope_stack(self, scope_stack):
        return [scope.copy() for scope in scope_stack]

    def _active_scope_stack(self):
        return self.local_scope_stack if self.call_stack else self.global_scope_stack

    def _active_target(self):
        return self.locals if self.call_stack else self.globals

    def _enter_scope(self):
        self._active_scope_stack().append({})

    def _exit_scope(self):
        scope_stack = self._active_scope_stack()
        if not scope_stack:
            raise VMError("EXIT_SCOPE without matching ENTER_SCOPE")
        target = self._active_target()
        scope = scope_stack.pop()
        for name, previous in reversed(list(scope.items())):
            if previous is _UNDECLARED:
                target.pop(name, None)
            else:
                target[name] = previous

    def _split_top_level_types(self, s: str):
        parts = []
        depth = 0
        start = 0
        for i, ch in enumerate(s):
            if ch == "<":
                depth += 1
            elif ch == ">":
                depth -= 1
            elif ch == "," and depth == 0:
                parts.append(s[start:i].strip())
                start = i + 1
        parts.append(s[start:].strip())
        return parts

    def _is_bool(self, val):
        return type(val) is bool

    def _is_int(self, val):
        return type(val) is int and not isinstance(val, bool)

    def _is_float(self, val):
        return type(val) is float

    def _runtime_type_name(self, val):
        if isinstance(val, bool):
            return "bool"
        if isinstance(val, int) and not isinstance(val, bool):
            return "int"
        if isinstance(val, float):
            return "float"
        if isinstance(val, str):
            node = self.component_tree.get("nodes", {}).get(val)
            if node and node.get("type"):
                return f"component:{node['type']}"
            return "string"
        if isinstance(val, list):
            return "array"
        if isinstance(val, dict):
            if "__class__" in val:
                return f"class:{val.get('__class__')}"
            return "dict"
        return type(val).__name__

    def _runtime_type_check(self, val, expected_type, context="value"):
        if expected_type is None or not isinstance(expected_type, str):
            return
        expected_type = self._normalize_runtime_type(expected_type)
        if expected_type in ("dynamic", "any", "unknown", "module", "function"):
            return

        base_type = _strip_unit_type(expected_type)
        if base_type in ("dynamic", "any", "unknown", "module", "function"):
            return

        if base_type == "void":
            if val is not None:
                raise VMError(f"Type mismatch for {context}: expected void, got {self._runtime_type_name(val)}")
            return

        if base_type == "bool":
            if not self._is_bool(val):
                raise VMError(f"Type mismatch for {context}: expected bool, got {self._runtime_type_name(val)}")
            return

        if base_type == "int":
            if not self._is_int(val):
                raise VMError(f"Type mismatch for {context}: expected int, got {self._runtime_type_name(val)}")
            return

        if base_type == "float":
            if not (self._is_float(val) or self._is_int(val)):
                raise VMError(f"Type mismatch for {context}: expected float, got {self._runtime_type_name(val)}")
            return

        if base_type == "string":
            if not isinstance(val, str):
                raise VMError(f"Type mismatch for {context}: expected string, got {self._runtime_type_name(val)}")
            return

        if base_type.startswith("array<") and base_type.endswith(">"):
            if not isinstance(val, list):
                raise VMError(f"Type mismatch for {context}: expected {base_type}, got {self._runtime_type_name(val)}")
            inner = base_type[len("array<"):-1].strip()
            for i, elem in enumerate(val):
                self._runtime_type_check(elem, inner, f"{context}[{i}]")
            return

        if base_type.startswith("dict<") and base_type.endswith(">"):
            if not isinstance(val, dict):
                raise VMError(f"Type mismatch for {context}: expected {base_type}, got {self._runtime_type_name(val)}")
            inside = base_type[len("dict<"):-1].strip()
            parts = self._split_top_level_types(inside)
            if len(parts) != 2:
                raise VMError(f"Invalid dict type '{base_type}' in runtime check")
            key_t, val_t = parts[0], parts[1]
            for k, v in val.items():
                self._runtime_type_check(k, key_t, f"{context} key")
                self._runtime_type_check(v, val_t, f"{context}[{repr(k)}]")
            return

        if base_type.startswith("component:"):
            expected_comp = base_type.split(":", 1)[1]
            if not isinstance(val, str):
                raise VMError(f"Type mismatch for {context}: expected {base_type}, got {self._runtime_type_name(val)}")
            node = self.component_tree.get("nodes", {}).get(val)
            if not node or "type" not in node:
                raise VMError(f"Type mismatch for {context}: expected {base_type}, got {self._runtime_type_name(val)}")
            actual_type = node.get("type")
            if not self._component_is_a(actual_type, expected_comp):
                raise VMError(f"Type mismatch for {context}: expected {base_type}, got component:{actual_type}")
            return

        if base_type.startswith("class:") or base_type in self.class_field_info:
            expected_class = base_type.split(":", 1)[1] if base_type.startswith("class:") else base_type
            if not isinstance(val, dict) or val.get("__class__") != expected_class:
                raise VMError(f"Type mismatch for {context}: expected class:{expected_class}, got {self._runtime_type_name(val)}")
            return

        # Unknown type: skip runtime check to avoid breaking existing behavior
        return

    def _call_user_function(self, func_name, arg_values, component_path=None):
        func_pc = None
        func_begin_idx = None
        for idx, instr in enumerate(self.code):
            if instr[0] == "FUNC_BEGIN" and instr[1] == func_name:
                func_pc = idx + 1
                func_begin_idx = idx
                break
        if func_pc is None:
            resolved, resolved_path = self._resolve_component_function(func_name)
            if resolved and resolved != func_name:
                self._call_user_function(resolved, arg_values, component_path=resolved_path)
                return
            raise VMError(f"User function '{func_name}' not found")

        param_count = int(self.code[func_begin_idx][2]) if len(self.code[func_begin_idx]) > 2 else 0
        param_info = []
        for i in range(param_count):
            decl_idx = func_pc + i
            if decl_idx >= len(self.code):
                raise VMError(f"Malformed function '{func_name}': missing parameter DECLAREs")
            decl_instr = self.code[decl_idx]
            if decl_instr[0] != "DECLARE":
                raise VMError(f"Malformed function '{func_name}': expected DECLARE for parameter at bytecode index {decl_idx}, found {decl_instr[0]}")
            param_info.append((decl_instr[1], decl_instr[2] if len(decl_instr) > 2 else None))

        self.call_stack.append((self.pc + 1, self.locals.copy(), self._copy_scope_stack(self.local_scope_stack)))
        self.locals = {}
        self.local_scope_stack = []
        if component_path:
            self._bind_component_locals(component_path)
        for (name, ptype), val in zip(param_info, arg_values):
            base_type = _strip_unit_type(ptype)
            if base_type == "float" and type(val) is int:
                val = float(val)
            elif base_type == "int" and type(val) is float:
                val = int(val)
            self._runtime_type_check(val, ptype, f"parameter '{name}'")
            self.locals[name] = (val, ptype or "unknown", False)

        self.pc = func_pc + param_count #- 1


    def sense(self):
        if not self.ros_bridge:
            return

        messages = self.ros_bridge.poll()
        for msg in messages:
            op = msg.get("op")
            if op == "msg":
                topic = msg.get("topic")
                if topic:
                    self.sensor_cache[topic] = msg.get("msg")
            elif op == "topics":
                topics = msg.get("topics", [])
                self.ros_topics = topics if isinstance(topics, list) else []
            elif op == "error":
                print(f"[ros] {msg.get('message')}")

    def act(self):
        if not self.ros_bridge:
            return

        while self._publish_queue:
            topic, msg_type, payload = self._publish_queue.pop(0)
            try:
                self.ros_bridge.publish(topic, msg_type, payload)
            except Exception as e:
                print(f"[ros] publish failed for {topic}: {e}")



    #This runs the bytecode from .mars file
    def run(self, max_steps=None, debug=False):
        steps = 0 #just used for counting steps (self.pc is the pointer to the instruction being run)
        while self.pc < len(self.code):
            steps += 1
            if max_steps is not None and steps > max_steps:
                raise VMError("Exceeded maximum VM steps; possible infinite loop")

            #sense, think, act
            self.sense()
            prev_pc = self.pc
            self.execute_one(debug)#RUN ONE INSTRUCTION
            self.act()
            # Most instructions advance implicitly by falling through.
            # Control-flow ops may set self.pc directly; in that case do not auto-increment.
            if self.pc == prev_pc:
                self.pc += 1
        
        if self.stack is not None and len(self.stack) > 0:
            raise VMError("VM halted prematurely. Final stack:", self.stack, "PC:", self.pc, " Code Length:", len(self.code))



    #This runs exactly one bytecode instruction
    def execute_one(self, debug=False):
        instr = self.code[self.pc]
        op, *args = instr  # unpack opcode and any arguments
        if debug:
            print(self.pc, instr, "stack:", self.stack)
        match op:
            case "PUSH_INT":
                self.stack.append(int(args[0]))
            case "PUSH_FLOAT":
                self.stack.append(float(args[0]))
            case "PUSH_STR":
                self.stack.append(args[0])
            case "PUSH_BOOL":
                self.stack.append(bool(args[0]))

            case "PUSH_NONE":
                self.stack.append(None)

            case "ENTER_SCOPE":
                self._enter_scope()

            case "EXIT_SCOPE":
                self._exit_scope()

            case "POP":
                if not self.stack:
                    raise VMError("POP requires a value on the stack")
                self.stack.pop()

            case "DUP":
                if not self.stack:
                    raise VMError("DUP requires a value on the stack")
                self.stack.append(self.stack[-1])

            case "DUP2":
                if len(self.stack) < 2:
                    raise VMError("DUP2 requires two values on the stack")
                self.stack.extend(self.stack[-2:])

            case "SWAP":
                if len(self.stack) < 2:
                    raise VMError("SWAP requires two values on the stack")
                self.stack[-1], self.stack[-2] = self.stack[-2], self.stack[-1]

            case "CAST_INT":
                if not self.stack:
                    raise VMError("CAST_INT requires a value on the stack")
                val = self.stack.pop()
                if type(val) is float:
                    val = int(val)
                self.stack.append(val)

            case "CAST_FLOAT":
                if not self.stack:
                    raise VMError("CAST_FLOAT requires a value on the stack")
                val = self.stack.pop()
                if type(val) is int:
                    val = float(val)
                self.stack.append(val)

            case "ADD":
                b = self.stack.pop(); a = self.stack.pop()
                # String concatenation if either is str
                if isinstance(a, str) or isinstance(b, str):
                    self.stack.append(str(a) + str(b))
                else:
                    self.stack.append(a + b)

            case "SUB":
                b = self.stack.pop(); a = self.stack.pop()
                self.stack.append(a - b)

            case "MUL":
                b = self.stack.pop(); a = self.stack.pop()
                self.stack.append(a * b)

            case "DIV":
                b = self.stack.pop(); a = self.stack.pop()
                self.stack.append(a / b)

            case "MOD":
                b = self.stack.pop(); a = self.stack.pop()
                self.stack.append(a % b)

            case "POW":
                b = self.stack.pop(); a = self.stack.pop()
                self.stack.append(a ** b)
            
            case "AND":
                b = self.stack.pop(); a = self.stack.pop()
                self.stack.append(a and b)
            
            case "OR":
                b = self.stack.pop(); a = self.stack.pop()
                self.stack.append(a or b)

            case "LT":
                b = self.stack.pop(); a = self.stack.pop()
                self.stack.append(a < b)

            case "GT":
                b = self.stack.pop(); a = self.stack.pop()
                self.stack.append(a > b)

            case "LEQ":
                b = self.stack.pop(); a = self.stack.pop()
                self.stack.append(a <= b)

            case "GEQ":
                b = self.stack.pop(); a = self.stack.pop()
                self.stack.append(a >= b)

            case "EQ":
                b = self.stack.pop(); a = self.stack.pop()
                self.stack.append(a == b)

            case "NEQ":
                b = self.stack.pop(); a = self.stack.pop()
                self.stack.append(a != b)

            case "NEGATE":
                val = self.stack.pop()
                self.stack.append(-val)

            case "NOT":
                val = self.stack.pop()
                # Numbers: 0->True, nonzero->False; bools invert normally
                if isinstance(val, (int, float)):
                    self.stack.append(val == 0)
                else:
                    self.stack.append(not val)

            case "NEW_CALL":
                n_args = int(args[0])
                # stack: class_ref, args...
                arg_values = [self.stack.pop() for _ in range(n_args)][::-1]
                class_ref = self.stack.pop()
                if not isinstance(class_ref, str):
                    raise VMError("Constructor call requires class reference name")
                obj = self._new_object(class_ref)
                ctor_name = f"{class_ref}.__ctor"
                # find ctor
                func_pc = None
                func_begin_idx = None
                for idx, instr in enumerate(self.code):
                    if instr[0] == "FUNC_BEGIN" and instr[1] == ctor_name:
                        func_pc = idx + 1
                        func_begin_idx = idx
                        break
                if func_pc is None:
                    # no ctor, just push object
                    self.stack.append(obj)
                    return
                param_count = int(self.code[func_begin_idx][2]) if len(self.code[func_begin_idx]) > 2 else 0
                param_info = []
                for i in range(param_count):
                    decl_idx = func_pc + i
                    decl_instr = self.code[decl_idx]
                    if decl_instr[0] != "DECLARE":
                        raise VMError(f"Malformed constructor '{ctor_name}'")
                    param_info.append((decl_instr[1], decl_instr[2] if len(decl_instr) > 2 else None))

                # Save current frame
                self.call_stack.append((self.pc + 1, self.locals.copy(), self._copy_scope_stack(self.local_scope_stack)))
                self.locals = {}
                self.local_scope_stack = []
                self.locals["this"] = (obj, f"class:{class_ref}", False)
                for (name, ptype), val in zip(param_info[1:], arg_values):
                    base_type = _strip_unit_type(ptype)
                    if base_type == "float" and type(val) is int:
                        val = float(val)
                    elif base_type == "int" and type(val) is float:
                        val = int(val)
                    self._runtime_type_check(val, ptype, f"parameter '{name}'")
                    self.locals[name] = (val, ptype or "unknown", False)
                self.pc = func_pc + param_count #- 1
                return

            case "GET_FIELD":
                attr = args[0]
                obj = self.stack.pop()
                if isinstance(obj, str) and obj in self.component_tree.get("nodes", {}):
                    node = self.component_tree["nodes"][obj]
                    if attr in node.get("subcomponents", {}):
                        self.stack.append(node["subcomponents"][attr])
                    elif attr in node.get("params", {}):
                        self.stack.append(node["params"][attr])
                    else:
                        raise VMError(f"Component '{obj}' has no member '{attr}'")
                elif isinstance(obj, types.ModuleType):
                    if not hasattr(obj, attr):
                        raise VMError(f"Module '{obj.__name__}' has no member '{attr}'")
                    self.stack.append(getattr(obj, attr))
                else:
                    if not isinstance(obj, dict) or "__fields__" not in obj:
                        raise VMError("GET_FIELD on non-object")
                    fields = obj["__fields__"]
                    if attr not in fields:
                        raise VMError(f"Field '{attr}' not found")
                    self.stack.append(fields[attr])

            case "SET_FIELD":
                attr = args[0]
                obj = self.stack.pop()
                val = self.stack.pop()
                if isinstance(obj, str) and obj in self.component_tree.get("nodes", {}):
                    raise VMError(f"Cannot assign to component member '{attr}' on '{obj}'")
                if not isinstance(obj, dict) or "__fields__" not in obj:
                    raise VMError("SET_FIELD on non-object")
                if "__readonly__" in obj and obj["__readonly__"].get(attr):
                    raise VMError(f"Cannot assign to const field '{attr}'")
                class_name = obj.get("__class__")
                finfo = self.class_field_info.get(class_name, {}).get(attr, {})
                if isinstance(finfo, dict):
                    ftype = finfo.get("type")
                    if ftype == "float" and type(val) is int:
                        val = float(val)
                    elif ftype == "int" and type(val) is float:
                        val = int(val)
                    if ftype:
                        self._runtime_type_check(val, ftype, f"field '{class_name}.{attr}'")
                obj["__fields__"][attr] = val

            case "INC":
                name = args[0]
                target = self.locals if name in self.locals else self.globals if name in self.globals else None
                if target is None:
                    raise VMError(f"Undefined variable '{name}'")
                val, vartype, readonly = target[name]
                if type(val) is not int:
                    raise VMError(f"INC requires int, got {type(val).__name__}")
                if readonly:
                    raise VMError(f"Cannot increment readonly variable '{name}'")
                target[name] = (val + 1, vartype, readonly)
                self.stack.append(val) 

            case "DEC":
                name = args[0]
                target = self.locals if name in self.locals else self.globals if name in self.globals else None
                if target is None:
                    raise VMError(f"Undefined variable '{name}'")
                val, vartype, readonly = target[name]
                if type(val) is not int:
                    raise VMError(f"DEC requires int, got {type(val).__name__}")
                if readonly:
                    raise VMError(f"Cannot decrement readonly variable '{name}'")
                target[name] = (val - 1, vartype, readonly)
                self.stack.append(val) 

            case "DECLARE":
                name, vartype = args[0], args[1]
                readonly = False
                allow_none_init = False
                if len(args) > 2:
                    readonly = bool(args[2])
                if len(args) > 3:
                    allow_none_init = bool(args[3])
                val = self.stack.pop()
                base_type = _strip_unit_type(vartype)
                if base_type == "float" and type(val) is int:
                    val = float(val)
                elif base_type == "int" and type(val) is float:
                    val = int(val)
                if not (allow_none_init and val is None):
                    self._runtime_type_check(val, vartype, f"variable '{name}'")
                target = self._active_target()
                scope_stack = self._active_scope_stack()
                if scope_stack:
                    current_scope = scope_stack[-1]
                    if name in current_scope:
                        raise VMError(f"Variable '{name}' already declared")
                    current_scope[name] = target.get(name, _UNDECLARED)
                elif name in target:
                    raise VMError(f"Variable '{name}' already declared")
                target[name] = (val, vartype, readonly)

            case "STORE":
                name = args[0]
                val = self.stack.pop()
                target = self.locals if name in self.locals else self.globals if name in self.globals else None
                if target is None:
                    raise VMError(f"Assignment to undeclared variable '{name}'")
                old_val, vartype, readonly = target[name]
                if readonly:
                    raise VMError(f"Cannot assign to readonly variable '{name}'")
                base_type = _strip_unit_type(vartype)
                if base_type == "float" and type(val) is int:
                    val = float(val)
                elif base_type == "int" and type(val) is float:
                    val = int(val)
                self._runtime_type_check(val, vartype, f"variable '{name}'")
                target[name] = (val, vartype, readonly)

            case "LOAD":
                name = args[0]  # could be "math.PI"
                if name in self.locals:
                    val, _type, _ro = self.locals[name]
                    self.stack.append(val)
                    return
                if name in self.globals:
                    val, _type, _ro = self.globals[name]
                    self.stack.append(val)
                    return
                if name in self.component_tree.get("nodes", {}):
                    self.stack.append(name)
                    return
                if name not in self.locals:
                    raise VMError(f"Undefined variable '{name}'")
                # fallback (should not hit)
                val, _type, _ro = self.locals[name]
                self.stack.append(val)


            case "PRINT":
                n = int(args[0])  # number of arguments to print
                if n > len(self.stack):
                    raise VMError(f"PRINT expected {n} values but stack has {len(self.stack)}")

                # Pop n values (last pushed first, so reverse to print in original order)
                vals = [self.stack.pop() for _ in range(n)][::-1]
                print(*vals)

            case "PUBLISH":
                if len(self.stack) < 3:
                    raise VMError("PUBLISH requires topic, msg_type, and payload on stack")
                payload = self.stack.pop()
                msg_type = self.stack.pop()
                topic = self.stack.pop()

                if not isinstance(topic, str):
                    raise VMError(f"publish topic must be string, got {type(topic).__name__}")
                if not isinstance(msg_type, str):
                    raise VMError(f"publish msg_type must be string, got {type(msg_type).__name__}")

                self.queue_publish(topic, msg_type, payload)

            case "WAIT":
                if not self.stack:
                    raise VMError("WAIT requires seconds on stack")
                seconds = self.stack.pop()
                if not isinstance(seconds, (int, float)):
                    raise VMError(f"wait seconds must be numeric, got {type(seconds).__name__}")
                seconds = float(seconds)
                if seconds < 0:
                    raise VMError("wait seconds must be non-negative")
                self._wait_cooperative(seconds)

            case "JUMP":
                self.pc = int(args[0]) #- 1
                return

            case "JUMP_IF_FALSE":
                target = int(args[0])
                cond = self.stack.pop()
                if isinstance(cond, (int, float)):# Numbers collapse to bools
                    cond = cond != 0
                if not cond:
                    self.pc = target #- 1
                    return

            case "HALT":
                if (self.pc < len(self.code)-1):
                    raise VMError("HALT opperand unexpectedly found. Program Early Termination Issue.")
                return

            case "IMPORT":
                module_name = args[0]

                module_path = f"builtins/{module_name}.py"
                tool_path = f"tools/{module_name}.py"
                if not os.path.exists(module_path) and not os.path.exists(tool_path):
                    # Component or unknown import: skip at runtime
                    self.globals[f"{module_name}"] = (None, "module", False)
                    return
                if module_name in self._modules:
                    return  # already imported

                if not os.path.exists(module_path) and os.path.exists(tool_path):
                    module_path = tool_path

                spec = importlib.util.spec_from_file_location(module_name, module_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                self._modules[module_name] = module
                # Expose module object for member access (math.PI / math.sqrt)
                self.globals[module_name] = (module, "module", False)

                # populate locals with dotted names
                funcs_dict = getattr(module, f"{module_name.upper()}_FUNCS", {})
                for name, val in funcs_dict.items():
                    self.locals[f"{module_name}.{name}"] = (val, "function" if callable(val) else type(val).__name__, False)


            case "FUNC_BEGIN":
                # Skip function body if running normally
                # args: name, param_count
                self.pc += 1
                while self.pc < len(self.code):
                    next_op = self.code[self.pc][0]
                    if next_op == "FUNC_END":
                        break
                    self.pc += 1
                return  # skip executing function body

            case "FUNC_END":
                # Nothing: return should handle exiting
                pass

            case "CALL":
                func_name, n_args = args
                n_args = int(n_args)
                arg_values = [self.stack.pop() for _ in range(n_args)][::-1]

                # Lookup locals for user-defined functions / builtins
                func_val, typ = None, None
                if func_name in self.locals:
                    lv = self.locals[func_name]
                    if isinstance(lv, tuple) and len(lv) >= 2:
                        func_val, typ = lv[0], lv[1]
                elif func_name in self.globals:
                    lv = self.globals[func_name]
                    if isinstance(lv, tuple) and len(lv) >= 2:
                        func_val, typ = lv[0], lv[1]
                if typ == "function" and callable(func_val):
                    # Built-in Python function
                    result = func_val(*arg_values)
                    self.stack.append(result)
                else:
                    self._call_user_function(func_name, arg_values)
                    return

            case "CALL_METHOD":
                method_name, n_args = args[0], int(args[1])
                # stack: ..., obj, arg1, arg2...
                arg_values = [self.stack.pop() for _ in range(n_args)][::-1]
                obj = self.stack.pop()
                if isinstance(obj, str) and obj in self.component_tree.get("nodes", {}):
                    node = self.component_tree["nodes"][obj]
                    func_name = f"{node['type']}.{method_name}"
                    self._call_user_function(func_name, arg_values, component_path=obj)
                    return
                if isinstance(obj, types.ModuleType):
                    if not hasattr(obj, method_name):
                        raise VMError(f"Module '{obj.__name__}' has no member '{method_name}'")
                    fn = getattr(obj, method_name)
                    if not callable(fn):
                        raise VMError(f"'{obj.__name__}.{method_name}' is not callable")
                    result = fn(*arg_values)
                    self.stack.append(result)
                    return
                if not isinstance(obj, dict) or "__class__" not in obj:
                    raise VMError("Method call on non-object")
                class_name = obj["__class__"]
                func_name = f"{class_name}.{method_name}" if not method_name.startswith("__") else f"{class_name}{method_name}"

                # Find function body
                func_pc = None
                func_begin_idx = None
                for idx, instr in enumerate(self.code):
                    if instr[0] == "FUNC_BEGIN" and instr[1] == func_name:
                        func_pc = idx + 1
                        func_begin_idx = idx
                        break
                if func_pc is None:
                    raise VMError(f"Method '{func_name}' not found")

                param_count = int(self.code[func_begin_idx][2]) if len(self.code[func_begin_idx]) > 2 else 0
                param_info = []
                for i in range(param_count):
                    decl_idx = func_pc + i
                    decl_instr = self.code[decl_idx]
                    if decl_instr[0] != "DECLARE":
                        raise VMError(f"Malformed method '{func_name}'")
                    param_info.append((decl_instr[1], decl_instr[2] if len(decl_instr) > 2 else None))

                # Save current frame
                self.call_stack.append((self.pc + 1, self.locals.copy(), self._copy_scope_stack(self.local_scope_stack)))
                self.locals = {}
                self.local_scope_stack = []
                # Bind this
                self.locals["this"] = (obj, f"class:{class_name}", False)
                for (name, ptype), val in zip(param_info[1:], arg_values):
                    base_type = _strip_unit_type(ptype)
                    if base_type == "float" and type(val) is int:
                        val = float(val)
                    elif base_type == "int" and type(val) is float:
                        val = int(val)
                    self._runtime_type_check(val, ptype, f"parameter '{name}'")
                    self.locals[name] = (val, ptype or "unknown", False)
                self.pc = func_pc + param_count #- 1
                return


            case "MATCH_COMPONENT":
                target_type = self.stack.pop()
                start_path = self.stack.pop()
                if not isinstance(start_path, str) or not isinstance(target_type, str):
                    raise VMError("match expects a component reference and type name")
                match_path = self._match_component(start_path, target_type)
                self.stack.append(match_path)


            case "RETURN":
                # Optional: push return value
                ret_val = self.stack.pop() if self.stack else None

                if not self.call_stack:
                    raise VMError("Return outside function")

                self.pc, self.locals, self.local_scope_stack = self.call_stack.pop()
                self.stack.append(ret_val)
                return

            case "BUILD_ARRAY":
                # args[0] is N (may be passed as int or string)
                n = int(args[0])
                if n > len(self.stack):
                    raise VMError(f"BUILD_ARRAY expected {n} values but stack has {len(self.stack)}")
                # pop elements in reverse order, then rebuild correct left-to-right order
                elems = [self.stack.pop() for _ in range(n)][::-1]
                self.stack.append(elems)  # represent arrays as Python lists

            case "PUSH_EMPTY_ARRAY":
                self.stack.append([])
            
            case "BUILD_DICT":
                # args[0] = number of key/value pairs
                n = int(args[0])

                # We need 2*n items (key1, val1, key2, val2, ...)
                if len(self.stack) < 2 * n:
                    raise VMError(
                        f"BUILD_DICT expected {2*n} stack values but only {len(self.stack)} present"
                    )

                # Pop key/value pairs in reverse (stack is LIFO)
                # Example: stack [..., key1, val1, key2, val2]
                # Popping yields: val2, key2, val1, key1
                items = []
                for _ in range(n):
                    val = self.stack.pop()
                    key = self.stack.pop()
                    items.append((key, val))

                # Reverse the item list to restore original ordering
                items.reverse()

                # Build dictionary
                d = {}
                for key, val in items:
                    # Allow any hashable type as key (same as Python)
                    d[key] = val

                self.stack.append(d)

            case "PUSH_EMPTY_DICT":
                self.stack.append({})

            case "INDEX_GET":
                # stack: [..., container, index]
                if len(self.stack) < 2:
                    raise VMError("INDEX_GET requires container and index on stack")

                idx = self.stack.pop()
                container = self.stack.pop()

                # ---- dictionary access ----
                if isinstance(container, dict):
                    # dictionary keys can be strings, ints, bools, etc — allow anything hashable
                    if idx not in container:
                        raise VMError(f"Dictionary key not found: {idx}")
                    self.stack.append(container[idx])

                # ---- array access ----
                elif isinstance(container, list):
                    if not isinstance(idx, int):
                        raise VMError(f"Array index must be int, got {type(idx).__name__}")
                    if idx < 0 or idx >= len(container):
                        raise VMError(f"Array index out of bounds: {idx}")
                    self.stack.append(container[idx])

                # ---- unsupported type ----
                else:
                    raise VMError(f"Trying to index into unsupported type {type(container).__name__}")

            case "INDEX_SET":
                # Note: INDEX_SET returns nothing (assignment statement).
                # stack: [..., container, index, value]
                if len(self.stack) < 3:
                    raise VMError("INDEX_SET requires container, index, value on stack")

                val = self.stack.pop()
                idx = self.stack.pop()
                container = self.stack.pop()

                # ---- dictionary assignment ----
                if isinstance(container, dict):
                    container[idx] = val   # keys can be anything hashable

                # ---- array assignment ----
                elif isinstance(container, list):
                    if not isinstance(idx, int):
                        raise VMError(f"Array index must be int, got {type(idx).__name__}")
                    if idx < 0 or idx >= len(container):
                        raise VMError(f"Array index out of bounds: {idx}")
                    container[idx] = val

                # ---- unsupported type ----
                else:
                    raise VMError(f"Trying to index-assign into unsupported type {type(container).__name__}")
            
            case "UPDATE":
                self._apply_subscriptions()


            case _:
                raise VMError(f"Unknown opcode {op}")



    def _new_object(self, class_name):
        info = self.class_field_info.get(class_name, {})
        fields = {}
        readonly = {}
        for fname, finfo in info.items():
            fields[fname] = None
            readonly[fname] = finfo.get("readonly", False) if isinstance(finfo, dict) else False
        return {"__class__": class_name, "__fields__": fields, "__readonly__": readonly}
