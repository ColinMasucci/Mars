# Makefile

# Compiler
CXX = g++

# Compiler flags
CXXFLAGS = -Ithird-party -Iinclude -std=c++17 -Wall -Wextra

# Source files
SRCS = $(wildcard src/*.cpp)

# Output executable
TARGET = mars_demo

# Default target
all: $(TARGET)

# Build the executable
$(TARGET): $(SRCS)
	$(CXX) $(SRCS) $(CXXFLAGS) -o $(TARGET)

# Clean up build artifacts
clean:
	rm -f $(TARGET)
