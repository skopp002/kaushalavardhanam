const mysql = require('mysql2/promise');
const AWS = require('aws-sdk');
const dynamoDB = new AWS.DynamoDB.DocumentClient();

// Database connection configuration
const dbConfig = {
  host: process.env.DB_HOST,
  port: process.env.DB_PORT,
  database: process.env.DB_NAME,
  user: process.env.DB_USERNAME,
  password: process.env.DB_PASSWORD
};

// Create connection pool
let pool;

exports.handler = async (event) => {
  try {
    // Initialize connection pool if not already done
    if (!pool) {
      pool = await mysql.createPool(dbConfig);
      
      // Check if tables exist, create if they don't
      await initializeDatabase();
    }
    
    const requestBody = JSON.parse(event.body);
    const { action, playerId, sessionToken, category, limit, offset } = requestBody;
    
    // Input validation
    if (!action) {
      return createResponse(400, { message: 'Action is required' });
    }
    
    // For actions that require authentication
    if (['submit', 'getPlayerRank'].includes(action)) {
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
    }
    
    // Handle different actions
    switch (action) {
      case 'getLeaderboard':
        return await getLeaderboard(category, limit, offset);
      
      case 'submit':
        return await submitScore(playerId, requestBody.score, requestBody.category);
      
      case 'getPlayerRank':
        return await getPlayerRank(playerId, requestBody.category);
      
      default:
        return createResponse(400, { message: 'Invalid action' });
    }
  } catch (error) {
    console.error('Error:', error);
    return createResponse(500, { message: 'Internal server error', error: error.message });
  }
};

async function initializeDatabase() {
  const connection = await pool.getConnection();
  try {
    // Create leaderboard table if it doesn't exist
    await connection.query(`
      CREATE TABLE IF NOT EXISTS leaderboard (
        id INT AUTO_INCREMENT PRIMARY KEY,
        player_id VARCHAR(255) NOT NULL,
        username VARCHAR(255) NOT NULL,
        score INT NOT NULL,
        category VARCHAR(50) NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX (player_id),
        INDEX (category),
        INDEX (score)
      )
    `);
    
    // Create categories table if it doesn't exist
    await connection.query(`
      CREATE TABLE IF NOT EXISTS categories (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(50) UNIQUE NOT NULL,
        display_name VARCHAR(100) NOT NULL,
        description TEXT
      )
    `);
    
    // Insert default categories if they don't exist
    await connection.query(`
      INSERT IGNORE INTO categories (name, display_name, description)
      VALUES 
        ('overall', 'Overall Score', 'Combined player score across all activities'),
        ('areas_conquered', 'Areas Conquered', 'Number of areas reconquered'),
        ('astras_learned', 'Astras Learned', 'Number of astras learned from gurus'),
        ('siddhis_mastered', 'Siddhis Mastered', 'Number of siddhis mastered'),
        ('boss_defeats', 'Boss Defeats', 'Number of boss defeats')
    `);
  } finally {
    connection.release();
  }
}

async function getLeaderboard(category = 'overall', limit = 10, offset = 0) {
  // Validate and sanitize inputs
  const validatedCategory = category.replace(/[^a-z_]/g, '');
  const validatedLimit = Math.min(Math.max(parseInt(limit) || 10, 1), 100);
  const validatedOffset = Math.max(parseInt(offset) || 0, 0);
  
  const [rows] = await pool.query(`
    SELECT l.player_id, l.username, l.score, l.timestamp, 
           (SELECT COUNT(*) + 1 FROM leaderboard WHERE category = ? AND score > l.score) as rank
    FROM leaderboard l
    WHERE l.category = ?
    ORDER BY l.score DESC
    LIMIT ? OFFSET ?
  `, [validatedCategory, validatedCategory, validatedLimit, validatedOffset]);
  
  // Get total count for pagination
  const [countResult] = await pool.query(`
    SELECT COUNT(*) as total FROM leaderboard WHERE category = ?
  `, [validatedCategory]);
  
  // Get category info
  const [categoryInfo] = await pool.query(`
    SELECT display_name, description FROM categories WHERE name = ?
  `, [validatedCategory]);
  
  return createResponse(200, {
    category: validatedCategory,
    categoryDisplayName: categoryInfo[0]?.display_name || validatedCategory,
    categoryDescription: categoryInfo[0]?.description || '',
    leaderboard: rows,
    pagination: {
      total: countResult[0].total,
      limit: validatedLimit,
      offset: validatedOffset,
      hasMore: (validatedOffset + validatedLimit) < countResult[0].total
    }
  });
}

async function submitScore(playerId, score, category = 'overall') {
  // Validate inputs
  if (score === undefined || score === null) {
    return createResponse(400, { message: 'Score is required' });
  }
  
  const validatedCategory = category.replace(/[^a-z_]/g, '');
  const validatedScore = parseInt(score);
  
  // Get player info
  const userResult = await dynamoDB.get({
    TableName: process.env.PLAYERS_TABLE,
    Key: { PlayerId: playerId }
  }).promise();
  
  if (!userResult.Item) {
    return createResponse(404, { message: 'Player not found' });
  }
  
  const username = userResult.Item.username;
  
  // Check if player already has a score in this category
  const [existingScore] = await pool.query(`
    SELECT id, score FROM leaderboard 
    WHERE player_id = ? AND category = ?
  `, [playerId, validatedCategory]);
  
  if (existingScore.length > 0) {
    // Only update if new score is higher
    if (validatedScore > existingScore[0].score) {
      await pool.query(`
        UPDATE leaderboard 
        SET score = ?, timestamp = NOW() 
        WHERE id = ?
      `, [validatedScore, existingScore[0].id]);
      
      return createResponse(200, {
        message: 'Score updated successfully',
        oldScore: existingScore[0].score,
        newScore: validatedScore
      });
    } else {
      return createResponse(200, {
        message: 'Existing score is higher',
        existingScore: existingScore[0].score,
        submittedScore: validatedScore
      });
    }
  } else {
    // Insert new score
    await pool.query(`
      INSERT INTO leaderboard (player_id, username, score, category)
      VALUES (?, ?, ?, ?)
    `, [playerId, username, validatedScore, validatedCategory]);
    
    return createResponse(201, {
      message: 'Score submitted successfully',
      score: validatedScore
    });
  }
}

async function getPlayerRank(playerId, category = 'overall') {
  const validatedCategory = category.replace(/[^a-z_]/g, '');
  
  // Get player's score and rank
  const [playerScore] = await pool.query(`
    SELECT score, 
           (SELECT COUNT(*) + 1 FROM leaderboard WHERE category = ? AND score > l.score) as rank
    FROM leaderboard l
    WHERE player_id = ? AND category = ?
  `, [validatedCategory, playerId, validatedCategory]);
  
  if (playerScore.length === 0) {
    return createResponse(404, {
      message: 'No score found for this player in the specified category'
    });
  }
  
  // Get nearby players (5 above and 5 below)
  const [nearbyPlayers] = await pool.query(`
    (SELECT player_id, username, score, 
            (SELECT COUNT(*) + 1 FROM leaderboard WHERE category = ? AND score > l.score) as rank
     FROM leaderboard l
     WHERE category = ? AND score >= ?
     ORDER BY score ASC
     LIMIT 5)
    UNION
    (SELECT player_id, username, score,
            (SELECT COUNT(*) + 1 FROM leaderboard WHERE category = ? AND score > l.score) as rank
     FROM leaderboard l
     WHERE category = ? AND player_id = ?)
    UNION
    (SELECT player_id, username, score,
            (SELECT COUNT(*) + 1 FROM leaderboard WHERE category = ? AND score > l.score) as rank
     FROM leaderboard l
     WHERE category = ? AND score <= ?
     ORDER BY score DESC
     LIMIT 5)
    ORDER BY score DESC
  `, [
    validatedCategory, validatedCategory, playerScore[0].score,
    validatedCategory, validatedCategory, playerId,
    validatedCategory, validatedCategory, playerScore[0].score
  ]);
  
  return createResponse(200, {
    playerRank: playerScore[0].rank,
    playerScore: playerScore[0].score,
    nearbyPlayers: nearbyPlayers
  });
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
