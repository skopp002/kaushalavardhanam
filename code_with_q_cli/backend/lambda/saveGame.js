const AWS = require('aws-sdk');
const dynamoDB = new AWS.DynamoDB.DocumentClient();

exports.handler = async (event) => {
  try {
    const requestBody = JSON.parse(event.body);
    const { playerId, sessionToken, worldId, chunks, playerProgress } = requestBody;
    
    // Input validation
    if (!playerId || !sessionToken || !worldId) {
      return createResponse(400, { message: 'PlayerId, sessionToken, and worldId are required' });
    }
    
    // Verify session token
    const userResult = await dynamoDB.get({
      TableName: process.env.PLAYERS_TABLE,
      Key: { PlayerId: playerId }
    }).promise();
    
    if (!userResult.Item || userResult.Item.sessionToken !== sessionToken || userResult.Item.sessionExpires < Date.now()) {
      return createResponse(401, { message: 'Invalid or expired session' });
    }
    
    // Process chunks data if provided
    if (chunks && Array.isArray(chunks) && chunks.length > 0) {
      const chunkPromises = chunks.map(chunk => {
        return dynamoDB.put({
          TableName: process.env.GAME_STATE_TABLE,
          Item: {
            WorldId: worldId,
            ChunkId: chunk.chunkId,
            Data: chunk.data,
            LastModified: Date.now(),
            ModifiedBy: playerId
          }
        }).promise();
      });
      
      await Promise.all(chunkPromises);
    }
    
    // Process player progress if provided
    if (playerProgress) {
      // Get current progress first
      const currentProgressResult = await dynamoDB.get({
        TableName: process.env.PLAYER_PROGRESS_TABLE,
        Key: { PlayerId: playerId }
      }).promise();
      
      const currentProgress = currentProgressResult.Item || {
        PlayerId: playerId,
        unlockedAreas: ['starting_area'],
        learnedAstras: [],
        learnedSiddhis: [],
        hasBrahmaKavacha: false,
        level: 1,
        experience: 0
      };
      
      // Merge with new progress data
      const updatedProgress = {
        ...currentProgress,
        ...playerProgress,
        // Special handling for arrays to ensure we don't lose data
        unlockedAreas: [...new Set([...currentProgress.unlockedAreas, ...(playerProgress.unlockedAreas || [])])],
        learnedAstras: [...new Set([...currentProgress.learnedAstras, ...(playerProgress.learnedAstras || [])])],
        learnedSiddhis: [...new Set([...currentProgress.learnedSiddhis, ...(playerProgress.learnedSiddhis || [])])],
        lastUpdated: Date.now()
      };
      
      // Save updated progress
      await dynamoDB.put({
        TableName: process.env.PLAYER_PROGRESS_TABLE,
        Item: updatedProgress
      }).promise();
      
      // Check for achievements or milestones
      const achievements = checkAchievements(currentProgress, updatedProgress);
      
      // If player has learned all astras and siddhis, grant Brahma Kavacha
      if (!updatedProgress.hasBrahmaKavacha && 
          updatedProgress.learnedAstras.length >= 5 && 
          updatedProgress.learnedSiddhis.length >= 5) {
        
        // 10% chance to receive Brahma Kavacha
        if (Math.random() < 0.1) {
          await dynamoDB.update({
            TableName: process.env.PLAYER_PROGRESS_TABLE,
            Key: { PlayerId: playerId },
            UpdateExpression: 'set hasBrahmaKavacha = :true',
            ExpressionAttributeValues: {
              ':true': true
            }
          }).promise();
          
          achievements.push({
            type: 'BRAHMA_KAVACHA_GRANTED',
            message: 'You have been blessed with the Brahma Kavacha!'
          });
        }
      }
      
      return createResponse(200, {
        message: 'Game state saved successfully',
        achievements: achievements
      });
    } else {
      return createResponse(200, {
        message: 'Game state saved successfully'
      });
    }
  } catch (error) {
    console.error('Error:', error);
    return createResponse(500, { message: 'Internal server error', error: error.message });
  }
};

function checkAchievements(oldProgress, newProgress) {
  const achievements = [];
  
  // Check for newly unlocked areas
  const newAreas = newProgress.unlockedAreas.filter(area => !oldProgress.unlockedAreas.includes(area));
  if (newAreas.length > 0) {
    achievements.push({
      type: 'AREA_UNLOCKED',
      areas: newAreas,
      message: `You have unlocked ${newAreas.length} new areas!`
    });
  }
  
  // Check for newly learned astras
  const newAstras = newProgress.learnedAstras.filter(astra => !oldProgress.learnedAstras.includes(astra));
  if (newAstras.length > 0) {
    achievements.push({
      type: 'ASTRA_LEARNED',
      astras: newAstras,
      message: `You have learned ${newAstras.length} new astras!`
    });
  }
  
  // Check for newly learned siddhis
  const newSiddhis = newProgress.learnedSiddhis.filter(siddhi => !oldProgress.learnedSiddhis.includes(siddhi));
  if (newSiddhis.length > 0) {
    achievements.push({
      type: 'SIDDHI_LEARNED',
      siddhis: newSiddhis,
      message: `You have learned ${newSiddhis.length} new siddhis!`
    });
  }
  
  // Check for level up
  if (newProgress.level > oldProgress.level) {
    achievements.push({
      type: 'LEVEL_UP',
      oldLevel: oldProgress.level,
      newLevel: newProgress.level,
      message: `You have reached level ${newProgress.level}!`
    });
  }
  
  return achievements;
}

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
