const { exec } = require('child_process');
const fs = require('fs');
const path = require('path');

// Configuration
const region = process.env.AWS_REGION || 'us-west-2';
const environment = process.env.ENVIRONMENT || 'dev';

// Lambda functions to deploy
const functions = [
  {
    name: 'auth',
    handler: 'auth.handler',
    timeout: 10,
    memory: 128,
    environment: {
      PLAYERS_TABLE: `DharmaCraft-Players-${environment}`
    }
  },
  {
    name: 'matchmaking',
    handler: 'matchmaking.handler',
    timeout: 15,
    memory: 128,
    environment: {
      GAMELIFT_FLEET_ID: process.env.GAMELIFT_FLEET_ID || ''
    }
  },
  {
    name: 'saveGame',
    handler: 'saveGame.handler',
    timeout: 15,
    memory: 256,
    environment: {
      GAME_STATE_TABLE: `DharmaCraft-GameState-${environment}`,
      PLAYER_PROGRESS_TABLE: `DharmaCraft-PlayerProgress-${environment}`
    }
  },
  {
    name: 'leaderboard',
    handler: 'leaderboard.handler',
    timeout: 10,
    memory: 128,
    environment: {
      DB_HOST: process.env.DB_HOST || '',
      DB_PORT: process.env.DB_PORT || '3306',
      DB_NAME: 'leaderboard',
      DB_USERNAME: process.env.DB_USERNAME || 'admin',
      DB_PASSWORD: process.env.DB_PASSWORD || ''
    }
  }
];

// Check if build directory exists
const buildDir = path.join(__dirname, 'build');
if (!fs.existsSync(buildDir)) {
  console.error('Build directory not found. Run "npm run build" first.');
  process.exit(1);
}

// Deploy each function
functions.forEach(func => {
  const zipFile = path.join(buildDir, `${func.name}.zip`);
  
  if (!fs.existsSync(zipFile)) {
    console.error(`${func.name}.zip not found. Run "npm run build" first.`);
    return;
  }
  
  console.log(`Deploying ${func.name}...`);
  
  // Prepare environment variables
  const envVars = Object.entries(func.environment)
    .map(([key, value]) => `${key}=${value}`)
    .join(',');
  
  // AWS CLI command to update function
  const updateCommand = `aws lambda update-function-code \
    --region ${region} \
    --function-name dharmacraft-${func.name} \
    --zip-file fileb://${zipFile}`;
  
  // Execute update command
  exec(updateCommand, (error, stdout, stderr) => {
    if (error) {
      console.error(`Error updating ${func.name}: ${error.message}`);
      
      // Function might not exist, try to create it
      console.log(`Attempting to create function ${func.name}...`);
      
      const createCommand = `aws lambda create-function \
        --region ${region} \
        --function-name dharmacraft-${func.name} \
        --runtime nodejs18.x \
        --role arn:aws:iam::${process.env.AWS_ACCOUNT_ID}:role/dharmacraft-lambda-role \
        --handler ${func.handler} \
        --timeout ${func.timeout} \
        --memory-size ${func.memory} \
        --environment "Variables={${envVars}}" \
        --zip-file fileb://${zipFile}`;
      
      exec(createCommand, (createError, createStdout, createStderr) => {
        if (createError) {
          console.error(`Error creating ${func.name}: ${createError.message}`);
          return;
        }
        console.log(`Successfully created ${func.name}`);
      });
      
      return;
    }
    
    console.log(`Successfully updated ${func.name}`);
    
    // Update function configuration
    const configCommand = `aws lambda update-function-configuration \
      --region ${region} \
      --function-name dharmacraft-${func.name} \
      --timeout ${func.timeout} \
      --memory-size ${func.memory} \
      --environment "Variables={${envVars}}"`;
    
    exec(configCommand, (configError, configStdout, configStderr) => {
      if (configError) {
        console.error(`Error updating ${func.name} configuration: ${configError.message}`);
        return;
      }
      console.log(`Successfully updated ${func.name} configuration`);
    });
  });
});

console.log('Deployment process started. Check AWS Console for status.');
