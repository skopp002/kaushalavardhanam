# Dharma Craft: Post-Apocalyptic Sandbox Game

A 3D multiplayer sandbox game set in a post-apocalyptic world in India, deployed on AWS GameLift with a serverless architecture.

## Game Overview

In Dharma Craft, players explore a post-apocalyptic India, reconquering smaller areas and learning unique abilities (astras and siddhis) from gurus in each region. The ultimate goal is to defeat the final boss after collecting enough powers and potentially being blessed with the Brahma Kavacha.

## Technical Architecture

This project implements a serverless multiplayer game using:

- **AWS GameLift**: For game server hosting and matchmaking
- **DynamoDB**: For game state, player data, and world persistence
- **Amazon RDS**: For leaderboards and analytics
- **AWS Lambda**: For serverless backend functions
- **Amazon S3**: For asset storage
- **Amazon CloudFront**: For content delivery
- **API Gateway**: For REST API endpoints

## Directory Structure

```
.
├── game-server/       # C++ game server implementation
├── game-client/       # Unity game client
├── infrastructure/    # Terraform IaC for AWS deployment
├── backend/           # Lambda functions and API implementations
├── frontend/          # Web portal for account management
├── assets/            # Game assets (models, textures, sounds)
└── docs/              # Documentation
```

## Getting Started

1. Set up the infrastructure using Terraform
2. Deploy the backend services
3. Build and deploy the game server to GameLift
4. Build the game client
5. Connect and play!

## Development Requirements

- AWS Account
- Unity 2022.3 or later
- AWS CLI
- Terraform
- Node.js 18+
- C++ development environment

## Deployment

See [deployment documentation](./docs/deployment.md) for detailed instructions.
