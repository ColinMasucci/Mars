#!/usr/bin/env bash

echo "======================================="
echo "   MARS Language Installer"
echo "======================================="

# -----------------------------
# CONFIG
# -----------------------------
repoUrl="https://github.com/ColinMasucci/Mars.git"
venvDir=".venv"
repoClone="$(pwd)/Mars"
#workspaceDir="$(pwd)/MarsWorkspace"

# -----------------------------
# STEP 1: Create virtual environment
# -----------------------------
if [ ! -d "$venvDir" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$venvDir"

    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to create virtual environment."
        exit 1
    fi
else
    echo "Virtual environment already exists. Skipping..."
fi

# Resolve venv python explicitly (NO activation needed)
venvPython="$venvDir/bin/python"

if [ ! -f "$venvPython" ]; then
    echo "ERROR: Virtual environment python not found at $venvPython"
    exit 1
fi

# -----------------------------
# STEP 2: Clone repository (staging only)
# -----------------------------
if [ ! -d "$repoClone" ]; then
    echo "Cloning MARS repository..."
    git clone "$repoUrl" "$repoClone"

    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to clone MARS repository."
        exit 1
    fi
else
    echo "Repository already cloned. Skipping..."
fi

# -----------------------------
# STEP 3: Install MARS (compiler only)
# -----------------------------
echo "Installing MARS from local repository..."
"$venvPython" -m pip install "$repoClone"

if [ $? -ne 0 ]; then
    echo "ERROR: MARS installation failed."
    exit 1
fi

# -----------------------------
# STEP 4: Verify CLI installation
# -----------------------------
echo "Verifying installation..."

"$venvPython" -m mars.mars_lang.cli --help > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "MARS CLI verified successfully."
else
    echo "WARNING: MARS installed but CLI verification failed."
fi

# -----------------------------
# STEP 5: Find VS Code extension
# -----------------------------
echo "Searching for VS Code extension..."

vsixPath=$(find "$repoClone" -type f -name "*.vsix" 2>/dev/null | head -n 1)

if [ -n "$vsixPath" ]; then
    echo "Found VSIX: $vsixPath"
else
    echo "WARNING: No VSIX found. Skipping extension install."
fi

# -----------------------------
# STEP 6: Locate VS Code
# -----------------------------
codePath=""

if command -v code >/dev/null 2>&1; then
    codePath=$(command -v code)
fi

if [ -z "$codePath" ]; then
    echo "WARNING: VS Code not found. Skipping extension install."
fi

# -----------------------------
# STEP 7: Install VS Code extension
# -----------------------------
if [ -n "$codePath" ] && [ -n "$vsixPath" ]; then
    echo "Installing VS Code extension..."

    "$codePath" --install-extension "$vsixPath" --force

    if [ $? -eq 0 ]; then
        echo "VS Code extension installed successfully."
    else
        echo "WARNING: Extension installation failed."
    fi
else
    echo "Skipping VS Code extension install."
fi

# -----------------------------
# STEP 8: CLEANUP
# -----------------------------
echo "Cleaning up temporary repository..."

if [ -d "$repoClone" ]; then
    rm -rf "$repoClone"
fi

# -----------------------------
# DONE
# -----------------------------
echo ""
echo "======================================="
echo "MARS installation complete!"
echo "======================================="
echo ""
echo "Next steps:"
echo "  Activate manually (optional): source .venv/bin/activate"
echo "  Create Template Workspace: mars init MyWorkspace --seed"
echo "  Run MARS: mars run MyWorkspace/demo.mars"
echo ""