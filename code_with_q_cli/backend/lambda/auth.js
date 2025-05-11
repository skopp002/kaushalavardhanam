const AWS = require('aws-sdk');
const crypto = require('crypto');
const dynamoDB = new AWS.DynamoDB.DocumentClient();

exports.handler = async (event) => {
  try {
    const requestBody = JSON.parse(event.body);
    const { action, username, password, playerId } = requestBody;
    
    // Input validation
    if (!action) {
      return createResponse(400, { message: 'Action is required' });
    }
    
    if (action === 'login') {
      if (!username || !password) {
        return createResponse(400, { message: 'Username and password are required' });
      }
      
      // Check if user exists
      const userResult = await dynamoDB.query({
        TableName: process.env.PLAYERS_TABLE,
        IndexName: 'UsernameIndex',
        KeyConditionExpression: 'username = :username',
        ExpressionAttributeValues: {
          ':username': username
        }
      }).promise();
      
      if (userResult.Items.length === 0) {
        return createResponse(404, { message: 'User not found' });
      }
      
      const user = userResult.Items[0];
      
      // Verify password (in production, use proper password hashing)
      const hashedPassword = crypto.createHash('sha256').update(password).digest('hex');
      if (user.passwordHash !== hashedPassword) {
        return createResponse(401, { message: 'Invalid credentials' });
      }
      
      // Generate session token
      const sessionToken = crypto.randomBytes(64).toString('hex');
      const expiresAt = Date.now() + 24 * 60 * 60 * 1000; // 24 hours
      
      // Update user with session token
      await dynamoDB.update({
        TableName: process.env.PLAYERS_TABLE,
        Key: { PlayerId: user.PlayerId },
        UpdateExpression: 'set sessionToken = :token, sessionExpires = :expires',
        ExpressionAttributeValues: {
          ':token': sessionToken,
          ':expires': expiresAt
        }
      }).promise();
      
      return createResponse(200, {
        playerId: user.PlayerId,
        username: user.username,
        sessionToken,
        expiresAt
      });
    } 
    else if (action === 'register') {
      if (!username || !password) {
        return createResponse(400, { message: 'Username and password are required' });
      }
      
      // Check if username already exists
      const existingUser = await dynamoDB.query({
        TableName: process.env.PLAYERS_TABLE,
        IndexName: 'UsernameIndex',
        KeyConditionExpression: 'username = :username',
        ExpressionAttributeValues: {
          ':username': username
        }
      }).promise();
      
      if (existingUser.Items.length > 0) {
        return createResponse(409, { message: 'Username already exists' });
      }
      
      // Create new user
      const playerId = 'player_' + crypto.randomBytes(16).toString('hex');
      const hashedPassword = crypto.createHash('sha256').update(password).digest('hex');
      
      await dynamoDB.put({
        TableName: process.env.PLAYERS_TABLE,
        Item: {
          PlayerId: playerId,
          username: username,
          passwordHash: hashedPassword,
          createdAt: Date.now(),
          lastLogin: Date.now()
        }
      }).promise();
      
      // Initialize player progress
      await dynamoDB.put({
        TableName: process.env.PLAYER_PROGRESS_TABLE,
        Item: {
          PlayerId: playerId,
          unlockedAreas: ['starting_area'],
          learnedAstras: [],
          learnedSiddhis: [],
          hasBrahmaKavacha: false,
          level: 1,
          experience: 0
        }
      }).promise();
      
      return createResponse(201, {
        playerId,
        username,
        message: 'User registered successfully'
      });
    } 
    else if (action === 'verify') {
      if (!playerId || !requestBody.sessionToken) {
        return createResponse(400, { message: 'PlayerId and sessionToken are required' });
      }
      
      // Get user
      const userResult = await dynamoDB.get({
        TableName: process.env.PLAYERS_TABLE,
        Key: { PlayerId: playerId }
      }).promise();
      
      if (!userResult.Item) {
        return createResponse(404, { message: 'User not found' });
      }
      
      const user = userResult.Item;
      
      // Verify session token
      if (user.sessionToken !== requestBody.sessionToken || user.sessionExpires < Date.now()) {
        return createResponse(401, { message: 'Invalid or expired session' });
      }
      
      return createResponse(200, {
        valid: true,
        playerId: user.PlayerId,
        username: user.username
      });
    } 
    else {
      return createResponse(400, { message: 'Invalid action' });
    }
  } catch (error) {
    console.error('Error:', error);
    return createResponse(500, { message: 'Internal server error' });
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
