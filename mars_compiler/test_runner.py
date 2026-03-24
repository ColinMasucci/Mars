import json
import os
import sys
from interpreter import interpret_code_from_string

###How to run tests:
#For a specific test file:
#     python test_runner.py <test_filename.json>
#To run all test files:
#     python test_runner.py


TEST_DIR = "tests"

def run_test_case(case):
    print("────────────────────────────────────────────")

    # Skip disabled test (if "code_disabled" exists but "code" does not)
    if "code" not in case and "code_disabled" in case:
        print(f"⏭ Skipping disabled test: {case['name']}")
        return True, True  # (passed, disabled)
    
    name = case["name"]
    code = case["code"]
    expected_output = case.get("expect")
    expected_error = case.get("error")

    print(f"Running test: {name}")

    try:
        output = interpret_code_from_string(code)

        if expected_error:
            print(f"❌ Expected error '{expected_error}' but code ran successfully")
            return False, False
        
        if expected_output is not None:
            if output.strip() == expected_output.strip():
                print("✔ Passed")
                return True, False
            else:
                print(f"❌ Wrong output. Expected '{expected_output}', got '{output}'")
                return False, False

        print("✔ Passed (no expected output)")
        return True, False

    except Exception as e:
        if expected_error:
            if expected_error.lower() in str(e).lower():
                print("✔ Passed (caught expected error)")
                return True, False
            else:
                print(f"❌ Wrong error. Expected '{expected_error}', got '{e}'")
                return False, False
        else:
            print(f"❌ Unexpected error: {e}")
            return False, False

def run_test_file(filepath):
    print("\n============================================================")
    print(f"Running test file: {os.path.basename(filepath)}")
    
    with open(filepath) as f:
        data = json.load(f)
    
    passed_count = 0
    disabled_count = 0

    for case in data["tests"]:
        passed, disabled = run_test_case(case)
        if passed:
            passed_count += 1
        if disabled:
            disabled_count += 1
        print()

    total = len(data["tests"])
    print(f"Finished {os.path.basename(filepath)}: {passed_count}/{total} tests passed")
    if disabled_count > 0:
        print(f"🔸 Disabled tests in this file: {disabled_count}\n")

    return passed_count, total, disabled_count




def main():
    # Run a specific file
    if len(sys.argv) == 2:
        filename = sys.argv[1]
        path = os.path.join(TEST_DIR, filename)
        passed, total, disabled = run_test_file(path)

        print(f"GLOBAL SUCCESS RATE: {passed}/{total} = {passed/total*100:.2f}%")
        print(f"TOTAL DISABLED TESTS: {disabled}")
        return
    
    # Run all files
    files = [f for f in os.listdir(TEST_DIR) if f.endswith(".json")]
    print("Running all test suites...\n")
    
    total_passed = 0
    total_tests = 0
    total_disabled = 0

    for f in files:
        passed, total, disabled = run_test_file(os.path.join(TEST_DIR, f))
        total_passed += passed
        total_tests += total
        total_disabled += disabled

    print("============================================================")
    print(f"GLOBAL SUCCESS RATE: {total_passed}/{total_tests} = {total_passed/total_tests*100:.2f}%")
    print(f"TOTAL DISABLED TESTS ACROSS ALL FILES: {total_disabled}")
    print("============================================================")

    if total_passed == total_tests:
        print("✔✔✔ All tests passed ✔✔✔")
    else:
        print("❌ Some tests failed")



if __name__ == "__main__":
    main()
