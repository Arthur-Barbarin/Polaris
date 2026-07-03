# Build the libpolaris_ft shared library.
# `make` produces ../build/libpolaris_ft.{so|dylib} depending on platform.

UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Darwin)
  EXT := dylib
  LDFLAGS := -dynamiclib
else
  EXT := so
  LDFLAGS := -shared
endif

CXX      ?= g++
CXXFLAGS ?= -O2 -std=c++17 -fPIC -Wall -Wextra -Wno-unused-parameter

BUILD_DIR := ../build
TARGET    := $(BUILD_DIR)/libpolaris_ft.$(EXT)

SRCS := flight_core.cpp c_api.cpp
OBJS := $(SRCS:%.cpp=$(BUILD_DIR)/%.o)

.PHONY: all clean

all: $(TARGET)

$(BUILD_DIR)/%.o: %.cpp | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) -c $< -o $@

$(TARGET): $(OBJS)
	$(CXX) $(LDFLAGS) -o $@ $^

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

clean:
	rm -rf $(BUILD_DIR)
