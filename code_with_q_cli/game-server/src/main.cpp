#include <aws/gamelift/server/GameLiftServerAPI.h>
#include <aws/core/Aws.h>
#include <aws/core/utils/logging/LogLevel.h>
#include <aws/core/utils/logging/ConsoleLogSystem.h>
#include <aws/core/utils/json/JsonSerializer.h>
#include <aws/core/utils/Outcome.h>
#include <aws/core/utils/threading/Executor.h>

#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <mutex>
#include <thread>
#include <chrono>
#include <cstdlib>
#include <ctime>
#include <memory>

// Game world constants
const int WORLD_SIZE = 1000;
const int CHUNK_SIZE = 16;
const int MAX_PLAYERS = 16;
const int TICK_RATE = 20; // Ticks per second

// Forward declarations
class GameSession;
class Player;
class WorldChunk;
class GameWorld;

// Game world chunk
class WorldChunk {
public:
    WorldChunk(int x, int z) : chunkX(x), chunkZ(z), lastModified(0) {
        // Initialize chunk data
        blocks.resize(CHUNK_SIZE * CHUNK_SIZE * 256, 0);
    }

    std::string getChunkId() const {
        return std::to_string(chunkX) + ":" + std::to_string(chunkZ);
    }

    void setBlock(int x, int y, int z, int blockType) {
        if (x < 0 || x >= CHUNK_SIZE || y < 0 || y >= 256 || z < 0 || z >= CHUNK_SIZE) {
            return;
        }
        int index = (y * CHUNK_SIZE * CHUNK_SIZE) + (z * CHUNK_SIZE) + x;
        blocks[index] = blockType;
        lastModified = std::time(nullptr);
    }

    int getBlock(int x, int y, int z) const {
        if (x < 0 || x >= CHUNK_SIZE || y < 0 || y >= 256 || z < 0 || z >= CHUNK_SIZE) {
            return 0;
        }
        int index = (y * CHUNK_SIZE * CHUNK_SIZE) + (z * CHUNK_SIZE) + x;
        return blocks[index];
    }

    std::vector<int> getBlocks() const {
        return blocks;
    }

    time_t getLastModified() const {
        return lastModified;
    }

    // Serialize chunk data for network transmission
    std::string serialize() const {
        Aws::Utils::Json::JsonValue json;
        json.WithString("chunkId", getChunkId());
        
        // Compress block data using run-length encoding
        std::vector<std::pair<int, int>> compressed;
        int currentBlock = blocks[0];
        int count = 1;
        
        for (size_t i = 1; i < blocks.size(); ++i) {
            if (blocks[i] == currentBlock) {
                count++;
            } else {
                compressed.push_back({currentBlock, count});
                currentBlock = blocks[i];
                count = 1;
            }
        }
        compressed.push_back({currentBlock, count});
        
        Aws::Utils::Array<Aws::Utils::Json::JsonValue> blockData(compressed.size());
        for (size_t i = 0; i < compressed.size(); ++i) {
            Aws::Utils::Json::JsonValue entry;
            entry.WithInteger("type", compressed[i].first);
            entry.WithInteger("count", compressed[i].second);
            blockData[i] = entry;
        }
        
        json.WithArray("blocks", blockData);
        json.WithInt64("lastModified", lastModified);
        
        return json.View().WriteCompact();
    }

private:
    int chunkX;
    int chunkZ;
    std::vector<int> blocks;
    time_t lastModified;
};

// Player class
class Player {
public:
    Player(const std::string& id, const std::string& name) 
        : playerId(id), playerName(name), x(0), y(100), z(0), health(100), 
          isConnected(true), lastActivity(std::time(nullptr)) {
        // Initialize player data
    }

    std::string getPlayerId() const { return playerId; }
    std::string getPlayerName() const { return playerName; }
    
    void setPosition(float newX, float newY, float newZ) {
        x = newX;
        y = newY;
        z = newZ;
        lastActivity = std::time(nullptr);
    }
    
    void getPosition(float& outX, float& outY, float& outZ) const {
        outX = x;
        outY = y;
        outZ = z;
    }
    
    void setHealth(int newHealth) {
        health = std::max(0, std::min(100, newHealth));
    }
    
    int getHealth() const { return health; }
    
    void setConnected(bool connected) {
        isConnected = connected;
        if (connected) {
            lastActivity = std::time(nullptr);
        }
    }
    
    bool isPlayerConnected() const { return isConnected; }
    
    time_t getLastActivity() const { return lastActivity; }
    
    void updateActivity() {
        lastActivity = std::time(nullptr);
    }
    
    // Player progress
    void addUnlockedArea(const std::string& area) {
        unlockedAreas.insert(area);
    }
    
    void addLearnedAstra(const std::string& astra) {
        learnedAstras.insert(astra);
    }
    
    void addLearnedSiddhi(const std::string& siddhi) {
        learnedSiddhis.insert(siddhi);
    }
    
    void setBrahmaKavacha(bool has) {
        hasBrahmaKavacha = has;
    }
    
    void setLevel(int newLevel) {
        level = newLevel;
    }
    
    int getLevel() const { return level; }
    
    // Serialize player data for network transmission
    std::string serialize() const {
        Aws::Utils::Json::JsonValue json;
        json.WithString("playerId", playerId);
        json.WithString("playerName", playerName);
        json.WithDouble("x", x);
        json.WithDouble("y", y);
        json.WithDouble("z", z);
        json.WithInteger("health", health);
        json.WithInteger("level", level);
        json.WithBool("connected", isConnected);
        json.WithBool("hasBrahmaKavacha", hasBrahmaKavacha);
        
        // Add arrays for unlocked areas, astras, and siddhis
        Aws::Utils::Array<Aws::Utils::Json::JsonValue> areasArray(unlockedAreas.size());
        int i = 0;
        for (const auto& area : unlockedAreas) {
            areasArray[i++].AsString(area);
        }
        json.WithArray("unlockedAreas", areasArray);
        
        Aws::Utils::Array<Aws::Utils::Json::JsonValue> astrasArray(learnedAstras.size());
        i = 0;
        for (const auto& astra : learnedAstras) {
            astrasArray[i++].AsString(astra);
        }
        json.WithArray("learnedAstras", astrasArray);
        
        Aws::Utils::Array<Aws::Utils::Json::JsonValue> siddhisArray(learnedSiddhis.size());
        i = 0;
        for (const auto& siddhi : learnedSiddhis) {
            siddhisArray[i++].AsString(siddhi);
        }
        json.WithArray("learnedSiddhis", siddhisArray);
        
        return json.View().WriteCompact();
    }

private:
    std::string playerId;
    std::string playerName;
    float x, y, z;
    int health;
    int level = 1;
    bool isConnected;
    time_t lastActivity;
    std::set<std::string> unlockedAreas = {"starting_area"};
    std::set<std::string> learnedAstras;
    std::set<std::string> learnedSiddhis;
    bool hasBrahmaKavacha = false;
};

// Game world
class GameWorld {
public:
    GameWorld(const std::string& worldId) : worldId(worldId) {
        // Initialize world
        std::cout << "Creating game world: " << worldId << std::endl;
    }
    
    std::string getWorldId() const { return worldId; }
    
    WorldChunk* getChunk(int chunkX, int chunkZ) {
        std::string chunkId = std::to_string(chunkX) + ":" + std::to_string(chunkZ);
        
        std::lock_guard<std::mutex> lock(chunkMutex);
        auto it = chunks.find(chunkId);
        if (it == chunks.end()) {
            // Create new chunk if it doesn't exist
            auto newChunk = std::make_shared<WorldChunk>(chunkX, chunkZ);
            chunks[chunkId] = newChunk;
            return newChunk.get();
        }
        return it->second.get();
    }
    
    void setBlock(int x, int y, int z, int blockType) {
        // Convert world coordinates to chunk coordinates
        int chunkX = std::floor(static_cast<float>(x) / CHUNK_SIZE);
        int chunkZ = std::floor(static_cast<float>(z) / CHUNK_SIZE);
        
        // Get local coordinates within chunk
        int localX = x - (chunkX * CHUNK_SIZE);
        int localZ = z - (chunkZ * CHUNK_SIZE);
        
        // Set block in chunk
        WorldChunk* chunk = getChunk(chunkX, chunkZ);
        chunk->setBlock(localX, y, localZ, blockType);
    }
    
    int getBlock(int x, int y, int z) {
        // Convert world coordinates to chunk coordinates
        int chunkX = std::floor(static_cast<float>(x) / CHUNK_SIZE);
        int chunkZ = std::floor(static_cast<float>(z) / CHUNK_SIZE);
        
        // Get local coordinates within chunk
        int localX = x - (chunkX * CHUNK_SIZE);
        int localZ = z - (chunkZ * CHUNK_SIZE);
        
        // Get block from chunk
        WorldChunk* chunk = getChunk(chunkX, chunkZ);
        return chunk->getBlock(localX, y, localZ);
    }
    
    std::vector<std::string> getModifiedChunks(time_t since) {
        std::vector<std::string> modifiedChunks;
        std::lock_guard<std::mutex> lock(chunkMutex);
        
        for (const auto& pair : chunks) {
            if (pair.second->getLastModified() > since) {
                modifiedChunks.push_back(pair.first);
            }
        }
        
        return modifiedChunks;
    }
    
    std::string serializeChunk(const std::string& chunkId) {
        std::lock_guard<std::mutex> lock(chunkMutex);
        auto it = chunks.find(chunkId);
        if (it != chunks.end()) {
            return it->second->serialize();
        }
        return "{}";
    }

private:
    std::string worldId;
    std::map<std::string, std::shared_ptr<WorldChunk>> chunks;
    std::mutex chunkMutex;
};

// Game session
class GameSession {
public:
    GameSession(const std::string& sessionId, const std::string& gameMode) 
        : sessionId(sessionId), gameMode(gameMode), world(std::make_unique<GameWorld>(sessionId)) {
        std::cout << "Creating game session: " << sessionId << " (Mode: " << gameMode << ")" << std::endl;
        startTime = std::time(nullptr);
    }
    
    ~GameSession() {
        std::cout << "Destroying game session: " << sessionId << std::endl;
    }
    
    std::string getSessionId() const { return sessionId; }
    
    bool addPlayer(const std::string& playerId, const std::string& playerName) {
        std::lock_guard<std::mutex> lock(playersMutex);
        if (players.size() >= MAX_PLAYERS) {
            return false;
        }
        
        auto player = std::make_shared<Player>(playerId, playerName);
        players[playerId] = player;
        std::cout << "Player joined: " << playerName << " (" << playerId << ")" << std::endl;
        return true;
    }
    
    void removePlayer(const std::string& playerId) {
        std::lock_guard<std::mutex> lock(playersMutex);
        auto it = players.find(playerId);
        if (it != players.end()) {
            std::cout << "Player left: " << it->second->getPlayerName() << " (" << playerId << ")" << std::endl;
            players.erase(it);
        }
    }
    
    Player* getPlayer(const std::string& playerId) {
        std::lock_guard<std::mutex> lock(playersMutex);
        auto it = players.find(playerId);
        if (it != players.end()) {
            return it->second.get();
        }
        return nullptr;
    }
    
    size_t getPlayerCount() const {
        std::lock_guard<std::mutex> lock(playersMutex);
        return players.size();
    }
    
    std::vector<std::string> getPlayerIds() const {
        std::vector<std::string> ids;
        std::lock_guard<std::mutex> lock(playersMutex);
        for (const auto& pair : players) {
            ids.push_back(pair.first);
        }
        return ids;
    }
    
    GameWorld* getWorld() {
        return world.get();
    }
    
    void update() {
        // Check for inactive players
        std::vector<std::string> inactivePlayers;
        {
            std::lock_guard<std::mutex> lock(playersMutex);
            time_t now = std::time(nullptr);
            for (const auto& pair : players) {
                if (now - pair.second->getLastActivity() > 300) { // 5 minutes timeout
                    inactivePlayers.push_back(pair.first);
                }
            }
        }
        
        // Remove inactive players
        for (const auto& playerId : inactivePlayers) {
            removePlayer(playerId);
        }
    }
    
    std::string serializePlayerStates() {
        Aws::Utils::Json::JsonValue json;
        Aws::Utils::Array<Aws::Utils::Json::JsonValue> playersArray;
        
        {
            std::lock_guard<std::mutex> lock(playersMutex);
            playersArray = Aws::Utils::Array<Aws::Utils::Json::JsonValue>(players.size());
            
            int i = 0;
            for (const auto& pair : players) {
                Aws::Utils::Json::JsonValue playerJson = 
                    Aws::Utils::Json::JsonValue(pair.second->serialize());
                playersArray[i++] = playerJson;
            }
        }
        
        json.WithArray("players", playersArray);
        return json.View().WriteCompact();
    }

private:
    std::string sessionId;
    std::string gameMode;
    std::unique_ptr<GameWorld> world;
    std::map<std::string, std::shared_ptr<Player>> players;
    mutable std::mutex playersMutex;
    time_t startTime;
};

// Global game state
std::unique_ptr<GameSession> g_gameSession;
std::mutex g_gameSessionMutex;

// GameLift callbacks
bool onStartGameSession(Aws::GameLift::Server::Model::GameSession gameSession) {
    std::cout << "onStartGameSession called" << std::endl;
    
    // Extract game session properties
    std::string sessionId = gameSession.GetGameSessionId();
    std::string gameMode = "standard";
    
    // Check for game mode in properties
    for (const auto& prop : gameSession.GetGameProperties()) {
        if (prop.GetKey() == "gameMode") {
            gameMode = prop.GetValue();
        }
    }
    
    // Create new game session
    {
        std::lock_guard<std::mutex> lock(g_gameSessionMutex);
        g_gameSession = std::make_unique<GameSession>(sessionId, gameMode);
    }
    
    // Tell GameLift we're ready to accept players
    Aws::GameLift::Server::ActivateGameSession();
    return true;
}

bool onProcessTerminate() {
    std::cout << "onProcessTerminate called" << std::endl;
    
    // Cleanup and prepare for termination
    {
        std::lock_guard<std::mutex> lock(g_gameSessionMutex);
        g_gameSession.reset();
    }
    
    // Tell GameLift we're terminating
    Aws::GameLift::Server::ProcessEnding();
    return true;
}

bool onHealthCheck() {
    // Simple health check - return true if everything is OK
    return true;
}

// Main game loop
void gameLoop() {
    std::cout << "Game loop started" << std::endl;
    
    auto lastTick = std::chrono::steady_clock::now();
    const auto tickDuration = std::chrono::milliseconds(1000 / TICK_RATE);
    
    while (true) {
        // Wait for next tick
        auto now = std::chrono::steady_clock::now();
        auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(now - lastTick);
        if (elapsed < tickDuration) {
            std::this_thread::sleep_for(tickDuration - elapsed);
        }
        lastTick = std::chrono::steady_clock::now();
        
        // Update game state
        {
            std::lock_guard<std::mutex> lock(g_gameSessionMutex);
            if (g_gameSession) {
                g_gameSession->update();
            }
        }
    }
}

// Main function
int main(int argc, char** argv) {
    std::cout << "DharmaCraft Game Server starting..." << std::endl;
    
    // Initialize AWS SDK
    Aws::SDKOptions options;
    options.loggingOptions.logLevel = Aws::Utils::Logging::LogLevel::Info;
    Aws::InitAPI(options);
    
    // Initialize GameLift server SDK
    auto initOutcome = Aws::GameLift::Server::InitSDK();
    if (!initOutcome.IsSuccess()) {
        std::cerr << "GameLift server initialization failed: " << initOutcome.GetError().GetErrorMessage() << std::endl;
        return 1;
    }
    
    // Set up process parameters
    Aws::GameLift::Server::ProcessParameters processParams;
    processParams.OnStartGameSession = onStartGameSession;
    processParams.OnProcessTerminate = onProcessTerminate;
    processParams.OnHealthCheck = onHealthCheck;
    processParams.Port = 7777;
    processParams.LogParameters = Aws::GameLift::Server::LogParameters();
    
    // Tell GameLift we're ready to host game sessions
    auto processReadyOutcome = Aws::GameLift::Server::ProcessReady(processParams);
    if (!processReadyOutcome.IsSuccess()) {
        std::cerr << "GameLift ProcessReady failed: " << processReadyOutcome.GetError().GetErrorMessage() << std::endl;
        return 1;
    }
    
    // Start game loop in a separate thread
    std::thread gameLoopThread(gameLoop);
    
    // Wait for the game loop thread to finish (it won't unless there's an error)
    gameLoopThread.join();
    
    // Clean up
    Aws::GameLift::Server::ProcessEnding();
    Aws::ShutdownAPI(options);
    
    return 0;
}
