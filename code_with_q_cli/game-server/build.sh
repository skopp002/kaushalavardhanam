#!/bin/bash

# Exit on error
set -e

# Create build directory
mkdir -p build
cd build

# Configure with CMake
cmake ..

# Build
cmake --build . --config Release

# Create deployment package for GameLift
mkdir -p package/bin
cp DharmaCraftServer package/bin/

# Create install script for GameLift
cat > package/install.sh << 'EOL'
#!/bin/bash
# GameLift install script
# Install required dependencies
yum -y update
yum -y install aws-cli
EOL

chmod +x package/install.sh

echo "Build completed successfully. Deployment package is in build/package/"
