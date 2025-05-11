# Dharma Craft: Architecture Overview

This document outlines the architecture of the Dharma Craft game, a 3D multiplayer sandbox game set in a post-apocalyptic India.

## System Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Game Client    │────▶│  API Gateway    │────▶│  Lambda         │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                                               │
        │                                               │
        │                                               ▼
        │                                       ┌─────────────────┐
        │                                       │  DynamoDB       │
        │                                       └─────────────────┘
        │                                               │
        │                                               │
        ▼                                               ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  GameLift       │◀───▶│  Game Server    │────▶│  RDS            │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │
        │
        ▼
┌─────────────────┐     ┌─────────────────┐
│  S3 (Assets)    │────▶│  CloudFront     │
└─────────────────┘     └─────────────────┘
```

## Components

### Game Client (Unity)
- Built with Unity 2022.3+
- Handles player input, rendering, and game logic
- Communicates with backend services via REST API
- Connects to GameLift servers for real-time gameplay

### Game Server (C++)
- Runs on AWS GameLift
- Manages game state, physics, and multiplayer synchronization
- Handles player connections and disconnections
- Processes game world updates and player actions

### Backend Services (AWS Lambda)
- Authentication and user management
- Matchmaking and game session creation
- Game state persistence
- Leaderboards and player progress tracking

### Data Storage
- **DynamoDB**: Player data, game state, and player progress
- **RDS (MySQL)**: Leaderboards and analytics
- **S3**: Game assets and static content

### Networking
- **API Gateway**: RESTful API for client-server communication
- **GameLift**: Real-time game server hosting and matchmaking
- **CloudFront**: Content delivery for game assets

## Game Flow

1. **Authentication**:
   - Player logs in or registers via API Gateway/Lambda
   - Authentication data stored in DynamoDB

2. **Matchmaking**:
   - Player requests to join a game
   - Lambda function communicates with GameLift to find or create a game session
   - Player receives connection details for the game server

3. **Gameplay**:
   - Player connects directly to GameLift server
   - Game server manages real-time gameplay
   - Periodic state updates sent to backend for persistence

4. **Persistence**:
   - Game state saved to DynamoDB
   - Player progress updated
   - Achievements and milestones tracked

5. **Leaderboards**:
   - Player scores and achievements recorded in RDS
   - Leaderboards accessible via API

## Scalability and Performance

- GameLift auto-scaling based on player demand
- Serverless backend scales automatically
- DynamoDB on-demand capacity for cost optimization
- CloudFront for global asset distribution

## Security

- API Gateway authentication and authorization
- GameLift secure player sessions
- IAM roles with least privilege principle
- Encrypted data at rest and in transit

## Cost Optimization

- Serverless architecture minimizes idle resources
- GameLift Spot Instances for non-critical game sessions
- DynamoDB on-demand capacity
- CloudFront caching to reduce origin requests
- S3 lifecycle policies for asset management
