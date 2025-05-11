const AWS = require('aws-sdk');
const gameLift = new AWS.GameLift();
const dynamoDB = new AWS.DynamoDB.DocumentClient();

exports.handler = async (event) => {
  try {
    const requestBody = JSON.parse(event.body);
    const { playerId, sessionToken, region, gameMode } = requestBody;
    
    // Input validation
    if (!playerId || !sessionToken) {
      return createResponse(400, { message: 'PlayerId and sessionToken are required' });
    }
    
    // Verify session token
    const userResult = await dynamoDB.get({
      TableName: process.env.PLAYERS_TABLE,
      Key: { PlayerId: playerId }
    }).promise();
    
    if (!userResult.Item || userResult.Item.sessionToken !== sessionToken || userResult.Item.sessionExpires < Date.now()) {
      return createResponse(401, { message: 'Invalid or expired session' });
    }
    
    // Get player progress to determine matchmaking parameters
    const progressResult = await dynamoDB.get({
      TableName: process.env.PLAYER_PROGRESS_TABLE,
      Key: { PlayerId: playerId }
    }).promise();
    
    const playerProgress = progressResult.Item || {
      level: 1,
      unlockedAreas: ['starting_area']
    };
    
    // Determine matchmaking parameters based on player progress
    const matchmakingParams = {
      level: playerProgress.level,
      unlockedAreas: playerProgress.unlockedAreas,
      gameMode: gameMode || 'standard'
    };
    
    // Check for existing game sessions that match criteria
    const existingSessionsResult = await gameLift.searchGameSessions({
      FleetId: process.env.GAMELIFT_FLEET_ID,
      FilterExpression: 'gameMode = :gameMode AND hasOpenPlayerSlots = true',
      SortExpression: 'creationTime DESC',
      Limit: 10,
      ExpressionAttributeValues: {
        ':gameMode': { S: matchmakingParams.gameMode }
      }
    }).promise();
    
    let gameSessionId;
    let ipAddress;
    let port;
    
    // Join existing session or create new one
    if (existingSessionsResult.GameSessions && existingSessionsResult.GameSessions.length > 0) {
      // Join existing session
      const session = existingSessionsResult.GameSessions[0];
      gameSessionId = session.GameSessionId;
      ipAddress = session.IpAddress;
      port = session.Port;
    } else {
      // Create new game session
      const newSessionResult = await gameLift.createGameSession({
        FleetId: process.env.GAMELIFT_FLEET_ID,
        MaximumPlayerSessionCount: 16,
        GameProperties: [
          { Key: 'gameMode', Value: matchmakingParams.gameMode },
          { Key: 'level', Value: matchmakingParams.level.toString() }
        ],
        Name: `DharmaCraft-${matchmakingParams.gameMode}-${Date.now()}`
      }).promise();
      
      // Wait for game session to activate
      let activationStatus = 'ACTIVATING';
      let retries = 0;
      const maxRetries = 10;
      
      while (activationStatus === 'ACTIVATING' && retries < maxRetries) {
        await new Promise(resolve => setTimeout(resolve, 2000)); // Wait 2 seconds
        
        const sessionStatusResult = await gameLift.describeGameSessions({
          GameSessionId: newSessionResult.GameSession.GameSessionId
        }).promise();
        
        if (sessionStatusResult.GameSessions && sessionStatusResult.GameSessions.length > 0) {
          activationStatus = sessionStatusResult.GameSessions[0].Status;
          if (activationStatus === 'ACTIVE') {
            gameSessionId = sessionStatusResult.GameSessions[0].GameSessionId;
            ipAddress = sessionStatusResult.GameSessions[0].IpAddress;
            port = sessionStatusResult.GameSessions[0].Port;
            break;
          }
        }
        
        retries++;
      }
      
      if (activationStatus !== 'ACTIVE') {
        return createResponse(500, { message: 'Failed to create game session' });
      }
    }
    
    // Create player session
    const playerSessionResult = await gameLift.createPlayerSession({
      GameSessionId: gameSessionId,
      PlayerId: playerId,
      PlayerData: JSON.stringify({
        username: userResult.Item.username,
        level: playerProgress.level,
        unlockedAreas: playerProgress.unlockedAreas,
        learnedAstras: playerProgress.learnedAstras || [],
        learnedSiddhis: playerProgress.learnedSiddhis || [],
        hasBrahmaKavacha: playerProgress.hasBrahmaKavacha || false
      })
    }).promise();
    
    return createResponse(200, {
      playerSessionId: playerSessionResult.PlayerSession.PlayerSessionId,
      gameSessionId: gameSessionId,
      ipAddress: ipAddress,
      port: port,
      connectionInfo: `${ipAddress}:${port}`,
      playerSessionStatus: playerSessionResult.PlayerSession.Status
    });
  } catch (error) {
    console.error('Error:', error);
    return createResponse(500, { message: 'Internal server error', error: error.message });
  }
};

function createResponse(statusCode, body) {
  return {
    statusCode,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Credentials': true
    },
    body: JSON.stringify(body)
  };
}
