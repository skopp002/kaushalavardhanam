# Deployment Guide for Dharma Craft

This document outlines the steps to deploy the Dharma Craft game infrastructure on AWS.

## Prerequisites

- AWS Account with appropriate permissions
- AWS CLI configured with credentials
- Terraform installed (v1.0.0+)
- Unity 2022.3 or later
- Node.js 18+ and npm
- C++ development environment

## Step 1: Infrastructure Deployment

1. Navigate to the infrastructure directory:
   ```
   cd infrastructure/terraform
   ```

2. Initialize Terraform:
   ```
   terraform init
   ```

3. Review the deployment plan:
   ```
   terraform plan
   ```

4. Deploy the infrastructure:
   ```
   terraform apply
   ```

5. Note the outputs for use in subsequent steps:
   - API Gateway endpoint
   - GameLift fleet ID
   - DynamoDB table names
   - S3 bucket names

## Step 2: Backend Deployment

1. Navigate to the backend directory:
   ```
   cd ../../backend
   ```

2. Install dependencies:
   ```
   npm install
   ```

3. Deploy Lambda functions:
   ```
   npm run deploy
   ```

## Step 3: Game Server Deployment

1. Navigate to the game server directory:
   ```
   cd ../game-server
   ```

2. Build the server:
   ```
   ./build.sh
   ```

3. Upload the build to GameLift:
   ```
   aws gamelift upload-build --name "DharmaCraft-Server" --build-version "1.0.0" --build-root ./build --operating-system AMAZON_LINUX_2
   ```

4. Create a fleet with the uploaded build (use the build ID from the previous step):
   ```
   aws gamelift create-fleet --name "DharmaCraftFleet" --build-id "build-xxxx" --ec2-instance-type "c5.large" --fleet-type "ON_DEMAND" --runtime-configuration "GameSessionActivationTimeoutSeconds=300,MaxConcurrentGameSessionActivations=2,ServerProcesses=[{LaunchPath=/local/game/DharmaCraftServer,Parameters=+map_rotation,ConcurrentExecutions=1}]"
   ```

## Step 4: Game Client Build

1. Open the Unity project in the game-client directory
2. Configure the client with the API Gateway endpoint and other AWS resources
3. Build the client for your target platforms (Windows, macOS, etc.)

## Step 5: Asset Deployment

1. Upload game assets to the S3 bucket:
   ```
   aws s3 sync ./assets s3://dharmacraft-assets
   ```

## Step 6: Testing

1. Launch the game client
2. Verify connectivity to the backend services
3. Test matchmaking and game session creation
4. Validate game mechanics and persistence

## Monitoring and Maintenance

- Set up CloudWatch alarms for monitoring GameLift fleet metrics
- Configure auto-scaling policies based on player demand
- Regularly backup DynamoDB tables
- Monitor costs and optimize resource usage

## Troubleshooting

- Check CloudWatch Logs for Lambda and GameLift server logs
- Verify security group settings if connection issues occur
- Ensure IAM roles have appropriate permissions
