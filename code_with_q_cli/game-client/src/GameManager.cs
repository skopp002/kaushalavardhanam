using System;
using System.Collections;
using System.Collections.Generic;
using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.Networking;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

public class GameManager : MonoBehaviour
{
    // Singleton instance
    public static GameManager Instance { get; private set; }

    // Configuration
    [Header("AWS Configuration")]
    [SerializeField] private string apiEndpoint = "https://your-api-gateway-url.execute-api.region.amazonaws.com/dev";
    [SerializeField] private string assetsEndpoint = "https://your-cloudfront-distribution.cloudfront.net";

    // Player data
    private string playerId;
    private string playerName;
    private string sessionToken;
    private DateTime sessionExpiry;

    // Game session data
    private string gameSessionId;
    private string playerSessionId;
    private string serverAddress;
    private int serverPort;

    // Player progress
    private List<string> unlockedAreas = new List<string>();
    private List<string> learnedAstras = new List<string>();
    private List<string> learnedSiddhis = new List<string>();
    private bool hasBrahmaKavacha = false;
    private int playerLevel = 1;
    private int playerExperience = 0;

    // Events
    public event Action OnLoginSuccess;
    public event Action<string> OnLoginFailed;
    public event Action OnMatchmakingSuccess;
    public event Action<string> OnMatchmakingFailed;
    public event Action<List<string>> OnAchievementsEarned;

    private void Awake()
    {
        // Singleton pattern
        if (Instance == null)
        {
            Instance = this;
            DontDestroyOnLoad(gameObject);
        }
        else
        {
            Destroy(gameObject);
        }
    }

    // Authentication methods
    public async Task<bool> Login(string username, string password)
    {
        try
        {
            var requestData = new Dictionary<string, string>
            {
                { "action", "login" },
                { "username", username },
                { "password", password }
            };

            var response = await SendApiRequest<LoginResponse>("/auth", requestData);

            if (response != null)
            {
                playerId = response.playerId;
                playerName = response.username;
                sessionToken = response.sessionToken;
                sessionExpiry = DateTime.Now.AddMilliseconds(response.expiresAt - DateTime.Now.Ticks);

                // Load player progress
                await LoadPlayerProgress();

                OnLoginSuccess?.Invoke();
                return true;
            }
            return false;
        }
        catch (Exception ex)
        {
            OnLoginFailed?.Invoke(ex.Message);
            return false;
        }
    }

    public async Task<bool> Register(string username, string password)
    {
        try
        {
            var requestData = new Dictionary<string, string>
            {
                { "action", "register" },
                { "username", username },
                { "password", password }
            };

            var response = await SendApiRequest<RegisterResponse>("/auth", requestData);

            if (response != null)
            {
                Debug.Log($"Registration successful: {response.message}");
                return true;
            }
            return false;
        }
        catch (Exception ex)
        {
            Debug.LogError($"Registration failed: {ex.Message}");
            return false;
        }
    }

    // Matchmaking methods
    public async Task<bool> StartMatchmaking(string gameMode = "standard")
    {
        try
        {
            var requestData = new Dictionary<string, string>
            {
                { "playerId", playerId },
                { "sessionToken", sessionToken },
                { "gameMode", gameMode }
            };

            var response = await SendApiRequest<MatchmakingResponse>("/matchmaking", requestData);

            if (response != null)
            {
                gameSessionId = response.gameSessionId;
                playerSessionId = response.playerSessionId;
                serverAddress = response.ipAddress;
                serverPort = response.port;

                Debug.Log($"Matchmaking successful: {serverAddress}:{serverPort}");
                OnMatchmakingSuccess?.Invoke();
                return true;
            }
            return false;
        }
        catch (Exception ex)
        {
            OnMatchmakingFailed?.Invoke(ex.Message);
            return false;
        }
    }

    // Game state methods
    public async Task<bool> SaveGameState(Dictionary<string, object> chunks, Dictionary<string, object> progress)
    {
        try
        {
            var requestData = new Dictionary<string, object>
            {
                { "playerId", playerId },
                { "sessionToken", sessionToken },
                { "worldId", gameSessionId },
                { "chunks", chunks },
                { "playerProgress", progress }
            };

            var response = await SendApiRequest<SaveGameResponse>("/save-game", requestData);

            if (response != null)
            {
                Debug.Log($"Game state saved: {response.message}");

                // Process achievements
                if (response.achievements != null && response.achievements.Count > 0)
                {
                    List<string> achievementMessages = new List<string>();
                    foreach (var achievement in response.achievements)
                    {
                        achievementMessages.Add(achievement.message);
                        
                        // Update local player progress based on achievements
                        if (achievement.type == "AREA_UNLOCKED" && achievement.areas != null)
                        {
                            foreach (var area in achievement.areas)
                            {
                                if (!unlockedAreas.Contains(area))
                                {
                                    unlockedAreas.Add(area);
                                }
                            }
                        }
                        else if (achievement.type == "ASTRA_LEARNED" && achievement.astras != null)
                        {
                            foreach (var astra in achievement.astras)
                            {
                                if (!learnedAstras.Contains(astra))
                                {
                                    learnedAstras.Add(astra);
                                }
                            }
                        }
                        else if (achievement.type == "SIDDHI_LEARNED" && achievement.siddhis != null)
                        {
                            foreach (var siddhi in achievement.siddhis)
                            {
                                if (!learnedSiddhis.Contains(siddhi))
                                {
                                    learnedSiddhis.Add(siddhi);
                                }
                            }
                        }
                        else if (achievement.type == "LEVEL_UP")
                        {
                            playerLevel = achievement.newLevel;
                        }
                        else if (achievement.type == "BRAHMA_KAVACHA_GRANTED")
                        {
                            hasBrahmaKavacha = true;
                        }
                    }

                    OnAchievementsEarned?.Invoke(achievementMessages);
                }

                return true;
            }
            return false;
        }
        catch (Exception ex)
        {
            Debug.LogError($"Failed to save game state: {ex.Message}");
            return false;
        }
    }

    // Leaderboard methods
    public async Task<LeaderboardResponse> GetLeaderboard(string category = "overall", int limit = 10, int offset = 0)
    {
        try
        {
            var requestData = new Dictionary<string, object>
            {
                { "action", "getLeaderboard" },
                { "category", category },
                { "limit", limit },
                { "offset", offset }
            };

            return await SendApiRequest<LeaderboardResponse>("/leaderboard", requestData);
        }
        catch (Exception ex)
        {
            Debug.LogError($"Failed to get leaderboard: {ex.Message}");
            return null;
        }
    }

    // Helper methods
    private async Task<T> SendApiRequest<T>(string endpoint, object data) where T : class
    {
        string url = apiEndpoint + endpoint;
        string jsonData = JsonConvert.SerializeObject(data);

        using (UnityWebRequest request = new UnityWebRequest(url, "POST"))
        {
            byte[] bodyRaw = System.Text.Encoding.UTF8.GetBytes(jsonData);
            request.uploadHandler = new UploadHandlerRaw(bodyRaw);
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");

            await request.SendWebRequest();

            if (request.result == UnityWebRequest.Result.ConnectionError || 
                request.result == UnityWebRequest.Result.ProtocolError)
            {
                Debug.LogError($"API Error: {request.error}");
                throw new Exception($"API Error: {request.error}");
            }

            string responseText = request.downloadHandler.text;
            Debug.Log($"API Response: {responseText}");
            return JsonConvert.DeserializeObject<T>(responseText);
        }
    }

    private async Task LoadPlayerProgress()
    {
        try
        {
            var requestData = new Dictionary<string, string>
            {
                { "playerId", playerId },
                { "sessionToken", sessionToken }
            };

            var response = await SendApiRequest<PlayerProgressResponse>("/player-progress", requestData);

            if (response != null)
            {
                unlockedAreas = response.unlockedAreas ?? new List<string> { "starting_area" };
                learnedAstras = response.learnedAstras ?? new List<string>();
                learnedSiddhis = response.learnedSiddhis ?? new List<string>();
                hasBrahmaKavacha = response.hasBrahmaKavacha;
                playerLevel = response.level;
                playerExperience = response.experience;
            }
        }
        catch (Exception ex)
        {
            Debug.LogWarning($"Failed to load player progress: {ex.Message}");
            // Use default values
            unlockedAreas = new List<string> { "starting_area" };
            learnedAstras = new List<string>();
            learnedSiddhis = new List<string>();
            hasBrahmaKavacha = false;
            playerLevel = 1;
            playerExperience = 0;
        }
    }

    // Getters for player data
    public string GetPlayerId() => playerId;
    public string GetPlayerName() => playerName;
    public List<string> GetUnlockedAreas() => unlockedAreas;
    public List<string> GetLearnedAstras() => learnedAstras;
    public List<string> GetLearnedSiddhis() => learnedSiddhis;
    public bool HasBrahmaKavacha() => hasBrahmaKavacha;
    public int GetPlayerLevel() => playerLevel;
    public int GetPlayerExperience() => playerExperience;
    public string GetServerAddress() => serverAddress;
    public int GetServerPort() => serverPort;
    public string GetPlayerSessionId() => playerSessionId;
}

// Response classes
[Serializable]
public class LoginResponse
{
    public string playerId;
    public string username;
    public string sessionToken;
    public long expiresAt;
}

[Serializable]
public class RegisterResponse
{
    public string playerId;
    public string username;
    public string message;
}

[Serializable]
public class MatchmakingResponse
{
    public string playerSessionId;
    public string gameSessionId;
    public string ipAddress;
    public int port;
    public string connectionInfo;
    public string playerSessionStatus;
}

[Serializable]
public class SaveGameResponse
{
    public string message;
    public List<Achievement> achievements;
}

[Serializable]
public class Achievement
{
    public string type;
    public string message;
    public List<string> areas;
    public List<string> astras;
    public List<string> siddhis;
    public int oldLevel;
    public int newLevel;
}

[Serializable]
public class PlayerProgressResponse
{
    public List<string> unlockedAreas;
    public List<string> learnedAstras;
    public List<string> learnedSiddhis;
    public bool hasBrahmaKavacha;
    public int level;
    public int experience;
}

[Serializable]
public class LeaderboardResponse
{
    public string category;
    public string categoryDisplayName;
    public string categoryDescription;
    public List<LeaderboardEntry> leaderboard;
    public LeaderboardPagination pagination;
}

[Serializable]
public class LeaderboardEntry
{
    public string player_id;
    public string username;
    public int score;
    public string timestamp;
    public int rank;
}

[Serializable]
public class LeaderboardPagination
{
    public int total;
    public int limit;
    public int offset;
    public bool hasMore;
}
