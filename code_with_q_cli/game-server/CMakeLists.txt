cmake_minimum_required(VERSION 3.10)
project(DharmaCraftServer)

# Set C++ standard
set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find AWS SDK
find_package(AWSSDK REQUIRED COMPONENTS gamelift core)

# Include directories
include_directories(${AWSSDK_INCLUDE_DIRS})

# Add executable
add_executable(DharmaCraftServer src/main.cpp)

# Link libraries
target_link_libraries(DharmaCraftServer ${AWSSDK_LIBRARIES})

# Copy required DLLs for Windows
if(WIN32)
    add_custom_command(TARGET DharmaCraftServer POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
        $<TARGET_FILE:aws-cpp-sdk-gamelift>
        $<TARGET_FILE:aws-cpp-sdk-core>
        $<TARGET_FILE_DIR:DharmaCraftServer>)
endif()

# Install target
install(TARGETS DharmaCraftServer DESTINATION bin)
