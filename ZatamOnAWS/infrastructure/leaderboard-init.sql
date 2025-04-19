CREATE DATABASE IF NOT EXISTS ${GameName}Leaderboard;
USE ${GameName}Leaderboard;

CREATE TABLE leaderboard (
    player_id VARCHAR(255) PRIMARY KEY,
    username VARCHAR(255) NOT NULL,
    score INT NOT NULL DEFAULT 0,
    games_played INT NOT NULL DEFAULT 0,
    wins INT NOT NULL DEFAULT 0,
    last_played TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_score (score DESC),
    INDEX idx_wins (wins DESC)
);

CREATE TABLE match_history (
    match_id VARCHAR(36) PRIMARY KEY,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    map_name VARCHAR(255),
    game_mode VARCHAR(50),
    player_count INT NOT NULL DEFAULT 0,
    status VARCHAR(20) DEFAULT 'ACTIVE',
    INDEX idx_start_time (start_time DESC)
);

CREATE TABLE match_players (
    match_id VARCHAR(36),
    player_id VARCHAR(255),
    team INT,
    score INT DEFAULT 0,
    PRIMARY KEY (match_id, player_id),
    FOREIGN KEY (match_id) REFERENCES match_history(match_id),
    INDEX idx_player (player_id)
);
