using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using Newtonsoft.Json.Linq;

public class WorldManager : MonoBehaviour
{
    // Singleton instance
    public static WorldManager Instance { get; private set; }

    // World settings
    [Header("World Settings")]
    [SerializeField] private int viewDistance = 8; // Chunks
    [SerializeField] private int chunkSize = 16; // Blocks
    [SerializeField] private int worldHeight = 256;
    [SerializeField] private Transform worldOrigin;

    // Block prefabs
    [Header("Block Prefabs")]
    [SerializeField] private GameObject[] blockPrefabs;
    [SerializeField] private Material[] blockMaterials;

    // Entity prefabs
    [Header("Entity Prefabs")]
    [SerializeField] private GameObject playerPrefab;
    [SerializeField] private GameObject enemyPrefab;
    [SerializeField] private GameObject guruPrefab;
    [SerializeField] private GameObject npcPrefab;

    // Optimization
    [Header("Optimization")]
    [SerializeField] private bool useInstancing = true;
    [SerializeField] private bool useLOD = true;
    [SerializeField] private float chunkUpdateInterval = 0.2f;

    // Internal state
    private Dictionary<string, Chunk> loadedChunks = new Dictionary<string, Chunk>();
    private Dictionary<string, Entity> loadedEntities = new Dictionary<string, Entity>();
    private Dictionary<string, GameObject> otherPlayers = new Dictionary<string, GameObject>();
    private Vector3Int lastPlayerChunk = new Vector3Int(int.MaxValue, 0, int.MaxValue);
    private Queue<Vector3Int> chunkLoadQueue = new Queue<Vector3Int>();
    private HashSet<string> requestedChunks = new HashSet<string>();
    private Transform playerTransform;
    private bool isWorldLoaded = false;

    // Events
    public event Action<Vector3Int> OnChunkLoaded;
    public event Action<Vector3Int> OnChunkUnloaded;
    public event Action<string, Entity> OnEntitySpawned;
    public event Action<string> OnEntityDespawned;
    public event Action OnWorldLoaded;

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

    private void Start()
    {
        // Subscribe to network events
        NetworkManager.Instance.OnChunkData += OnChunkDataReceived;
        NetworkManager.Instance.OnGameStateUpdate += OnGameStateUpdate;
        
        // Start chunk loading coroutine
        StartCoroutine(ProcessChunkQueue());
    }

    private void OnDestroy()
    {
        // Unsubscribe from network events
        if (NetworkManager.Instance != null)
        {
            NetworkManager.Instance.OnChunkData -= OnChunkDataReceived;
            NetworkManager.Instance.OnGameStateUpdate -= OnGameStateUpdate;
        }
    }

    private void Update()
    {
        // Find player if not already set
        if (playerTransform == null)
        {
            GameObject player = GameObject.FindGameObjectWithTag("Player");
            if (player != null)
            {
                playerTransform = player.transform;
            }
        }

        // Update chunks based on player position
        if (playerTransform != null)
        {
            Vector3Int currentChunk = WorldToChunkCoordinates(playerTransform.position);
            
            // Check if player moved to a new chunk
            if (currentChunk != lastPlayerChunk)
            {
                UpdateLoadedChunks(currentChunk);
                lastPlayerChunk = currentChunk;
            }
        }
    }

    private void UpdateLoadedChunks(Vector3Int centerChunk)
    {
        // Determine which chunks should be loaded
        HashSet<Vector3Int> chunksToLoad = new HashSet<Vector3Int>();
        
        // Add chunks within view distance
        for (int x = -viewDistance; x <= viewDistance; x++)
        {
            for (int z = -viewDistance; z <= viewDistance; z++)
            {
                Vector3Int chunkPos = new Vector3Int(centerChunk.x + x, 0, centerChunk.z + z);
                chunksToLoad.Add(chunkPos);
                
                // Request chunk data from server if not already loaded or requested
                string chunkKey = GetChunkKey(chunkPos);
                if (!loadedChunks.ContainsKey(chunkKey) && !requestedChunks.Contains(chunkKey))
                {
                    RequestChunkData(chunkPos);
                    requestedChunks.Add(chunkKey);
                }
            }
        }
        
        // Unload chunks that are out of range
        List<string> chunksToUnload = new List<string>();
        foreach (var kvp in loadedChunks)
        {
            Vector3Int chunkPos = ChunkKeyToCoordinates(kvp.Key);
            if (!chunksToLoad.Contains(chunkPos))
            {
                chunksToUnload.Add(kvp.Key);
            }
        }
        
        // Unload chunks
        foreach (string chunkKey in chunksToUnload)
        {
            UnloadChunk(chunkKey);
        }
    }

    private void RequestChunkData(Vector3Int chunkPos)
    {
        // Queue chunk for loading
        chunkLoadQueue.Enqueue(chunkPos);
        
        // Request chunk data from server
        JObject data = new JObject();
        data["chunkX"] = chunkPos.x;
        data["chunkZ"] = chunkPos.z;
        
        NetworkManager.Instance.SendMessage("requestChunk", data);
    }

    private IEnumerator ProcessChunkQueue()
    {
        while (true)
        {
            // Process chunks in queue
            if (chunkLoadQueue.Count > 0)
            {
                Vector3Int chunkPos = chunkLoadQueue.Dequeue();
                
                // Check if chunk is still needed (player might have moved away)
                if (playerTransform != null)
                {
                    Vector3Int playerChunk = WorldToChunkCoordinates(playerTransform.position);
                    int distance = Mathf.Max(Mathf.Abs(chunkPos.x - playerChunk.x), Mathf.Abs(chunkPos.z - playerChunk.z));
                    
                    if (distance <= viewDistance)
                    {
                        // Create empty chunk while waiting for server data
                        CreateEmptyChunk(chunkPos);
                    }
                    else
                    {
                        // Remove from requested chunks if no longer needed
                        string chunkKey = GetChunkKey(chunkPos);
                        requestedChunks.Remove(chunkKey);
                    }
                }
                
                // Wait before processing next chunk
                yield return new WaitForSeconds(chunkUpdateInterval);
            }
            else
            {
                // No chunks to process, wait a bit
                yield return new WaitForSeconds(0.5f);
                
                // Check if world is loaded
                if (!isWorldLoaded && loadedChunks.Count > 0)
                {
                    isWorldLoaded = true;
                    OnWorldLoaded?.Invoke();
                }
            }
        }
    }

    private void CreateEmptyChunk(Vector3Int chunkPos)
    {
        string chunkKey = GetChunkKey(chunkPos);
        
        // Skip if chunk already exists
        if (loadedChunks.ContainsKey(chunkKey))
        {
            return;
        }
        
        // Create chunk game object
        GameObject chunkObject = new GameObject($"Chunk_{chunkPos.x}_{chunkPos.z}");
        chunkObject.transform.parent = worldOrigin;
        chunkObject.transform.position = ChunkToWorldPosition(chunkPos);
        
        // Add chunk component
        Chunk chunk = chunkObject.AddComponent<Chunk>();
        chunk.Initialize(chunkPos, chunkSize, worldHeight);
        
        // Add to loaded chunks
        loadedChunks[chunkKey] = chunk;
        
        // Notify listeners
        OnChunkLoaded?.Invoke(chunkPos);
    }

    private void UnloadChunk(string chunkKey)
    {
        if (loadedChunks.TryGetValue(chunkKey, out Chunk chunk))
        {
            Vector3Int chunkPos = ChunkKeyToCoordinates(chunkKey);
            
            // Destroy chunk game object
            Destroy(chunk.gameObject);
            
            // Remove from loaded chunks
            loadedChunks.Remove(chunkKey);
            requestedChunks.Remove(chunkKey);
            
            // Notify listeners
            OnChunkUnloaded?.Invoke(chunkPos);
        }
    }

    private void OnChunkDataReceived(JObject chunkData)
    {
        try
        {
            // Extract chunk coordinates
            int chunkX = chunkData["chunkX"].Value<int>();
            int chunkZ = chunkData["chunkZ"].Value<int>();
            Vector3Int chunkPos = new Vector3Int(chunkX, 0, chunkZ);
            string chunkKey = GetChunkKey(chunkPos);
            
            // Get or create chunk
            Chunk chunk;
            if (!loadedChunks.TryGetValue(chunkKey, out chunk))
            {
                // Create chunk game object
                GameObject chunkObject = new GameObject($"Chunk_{chunkX}_{chunkZ}");
                chunkObject.transform.parent = worldOrigin;
                chunkObject.transform.position = ChunkToWorldPosition(chunkPos);
                
                // Add chunk component
                chunk = chunkObject.AddComponent<Chunk>();
                chunk.Initialize(chunkPos, chunkSize, worldHeight);
                
                // Add to loaded chunks
                loadedChunks[chunkKey] = chunk;
                
                // Notify listeners
                OnChunkLoaded?.Invoke(chunkPos);
            }
            
            // Update chunk with data from server
            JArray blocksData = chunkData["blocks"] as JArray;
            if (blocksData != null)
            {
                // Process block data
                // This could be RLE compressed or other format depending on server implementation
                List<int> blocks = new List<int>();
                
                foreach (JObject blockData in blocksData)
                {
                    int blockType = blockData["type"].Value<int>();
                    int count = blockData["count"].Value<int>();
                    
                    for (int i = 0; i < count; i++)
                    {
                        blocks.Add(blockType);
                    }
                }
                
                // Update chunk with block data
                chunk.UpdateBlocks(blocks.ToArray());
            }
            
            // Remove from requested chunks
            requestedChunks.Remove(chunkKey);
        }
        catch (Exception ex)
        {
            Debug.LogError($"Error processing chunk data: {ex.Message}");
        }
    }

    private void OnGameStateUpdate(JObject gameState)
    {
        try
        {
            // Process entities
            JArray entitiesData = gameState["entities"] as JArray;
            if (entitiesData != null)
            {
                // Track which entities we've seen in this update
                HashSet<string> updatedEntities = new HashSet<string>();
                
                foreach (JObject entityData in entitiesData)
                {
                    string entityId = entityData["entityId"].Value<string>();
                    string entityType = entityData["entityType"].Value<string>();
                    
                    updatedEntities.Add(entityId);
                    
                    // Update or create entity
                    if (loadedEntities.TryGetValue(entityId, out Entity entity))
                    {
                        // Update existing entity
                        entity.UpdateFromServer(entityData);
                    }
                    else
                    {
                        // Create new entity
                        SpawnEntity(entityId, entityType, entityData);
                    }
                }
                
                // Remove entities that weren't in the update
                List<string> entitiesToRemove = new List<string>();
                foreach (string entityId in loadedEntities.Keys)
                {
                    if (!updatedEntities.Contains(entityId))
                    {
                        entitiesToRemove.Add(entityId);
                    }
                }
                
                foreach (string entityId in entitiesToRemove)
                {
                    DespawnEntity(entityId);
                }
            }
            
            // Process other players
            JArray playersData = gameState["players"] as JArray;
            if (playersData != null)
            {
                // Track which players we've seen in this update
                HashSet<string> updatedPlayers = new HashSet<string>();
                
                foreach (JObject playerData in playersData)
                {
                    string playerId = playerData["playerId"].Value<string>();
                    
                    // Skip local player
                    if (playerId == GameManager.Instance.GetPlayerId())
                    {
                        continue;
                    }
                    
                    updatedPlayers.Add(playerId);
                    
                    // Update or create player
                    if (otherPlayers.TryGetValue(playerId, out GameObject playerObject))
                    {
                        // Update existing player
                        UpdateOtherPlayer(playerObject, playerData);
                    }
                    else
                    {
                        // Create new player
                        SpawnOtherPlayer(playerId, playerData);
                    }
                }
                
                // Remove players that weren't in the update
                List<string> playersToRemove = new List<string>();
                foreach (string playerId in otherPlayers.Keys)
                {
                    if (!updatedPlayers.Contains(playerId))
                    {
                        playersToRemove.Add(playerId);
                    }
                }
                
                foreach (string playerId in playersToRemove)
                {
                    DespawnOtherPlayer(playerId);
                }
            }
        }
        catch (Exception ex)
        {
            Debug.LogError($"Error processing game state: {ex.Message}");
        }
    }

    private void SpawnEntity(string entityId, string entityType, JObject entityData)
    {
        try
        {
            // Get entity position
            float x = entityData["position"]["x"].Value<float>();
            float y = entityData["position"]["y"].Value<float>();
            float z = entityData["position"]["z"].Value<float>();
            Vector3 position = new Vector3(x, y, z);
            
            // Get entity rotation
            float yaw = entityData["rotation"]?.Value<float>() ?? 0f;
            Quaternion rotation = Quaternion.Euler(0, yaw, 0);
            
            // Create entity based on type
            GameObject entityPrefab = null;
            
            switch (entityType)
            {
                case "enemy":
                    entityPrefab = enemyPrefab;
                    break;
                case "guru":
                    entityPrefab = guruPrefab;
                    break;
                case "npc":
                    entityPrefab = npcPrefab;
                    break;
                default:
                    Debug.LogWarning($"Unknown entity type: {entityType}");
                    return;
            }
            
            if (entityPrefab == null)
            {
                Debug.LogError($"Missing prefab for entity type: {entityType}");
                return;
            }
            
            // Instantiate entity
            GameObject entityObject = Instantiate(entityPrefab, position, rotation);
            entityObject.name = $"{entityType}_{entityId}";
            
            // Get entity component
            Entity entity = entityObject.GetComponent<Entity>();
            if (entity == null)
            {
                entity = entityObject.AddComponent<Entity>();
            }
            
            // Initialize entity with data
            entity.UpdateFromServer(entityData);
            
            // Add to loaded entities
            loadedEntities[entityId] = entity;
            
            // Notify listeners
            OnEntitySpawned?.Invoke(entityId, entity);
        }
        catch (Exception ex)
        {
            Debug.LogError($"Error spawning entity: {ex.Message}");
        }
    }

    private void DespawnEntity(string entityId)
    {
        if (loadedEntities.TryGetValue(entityId, out Entity entity))
        {
            // Destroy entity game object
            Destroy(entity.gameObject);
            
            // Remove from loaded entities
            loadedEntities.Remove(entityId);
            
            // Notify listeners
            OnEntityDespawned?.Invoke(entityId);
        }
    }

    private void SpawnOtherPlayer(string playerId, JObject playerData)
    {
        try
        {
            // Get player position
            float x = playerData["x"].Value<float>();
            float y = playerData["y"].Value<float>();
            float z = playerData["z"].Value<float>();
            Vector3 position = new Vector3(x, y, z);
            
            // Get player rotation
            float yaw = playerData["rotation"]?.Value<float>() ?? 0f;
            Quaternion rotation = Quaternion.Euler(0, yaw, 0);
            
            // Instantiate player
            GameObject playerObject = Instantiate(playerPrefab, position, rotation);
            playerObject.name = $"Player_{playerId}";
            
            // Set player name
            string playerName = playerData["playerName"]?.Value<string>() ?? $"Player {playerId}";
            TextMesh nameText = playerObject.GetComponentInChildren<TextMesh>();
            if (nameText != null)
            {
                nameText.text = playerName;
            }
            
            // Add to other players
            otherPlayers[playerId] = playerObject;
        }
        catch (Exception ex)
        {
            Debug.LogError($"Error spawning other player: {ex.Message}");
        }
    }

    private void UpdateOtherPlayer(GameObject playerObject, JObject playerData)
    {
        try
        {
            // Get player position
            float x = playerData["x"].Value<float>();
            float y = playerData["y"].Value<float>();
            float z = playerData["z"].Value<float>();
            Vector3 position = new Vector3(x, y, z);
            
            // Get player rotation
            float yaw = playerData["rotation"]?.Value<float>() ?? playerObject.transform.eulerAngles.y;
            Quaternion rotation = Quaternion.Euler(0, yaw, 0);
            
            // Update position and rotation smoothly
            OtherPlayerController controller = playerObject.GetComponent<OtherPlayerController>();
            if (controller != null)
            {
                controller.SetTargetPositionAndRotation(position, rotation);
            }
            else
            {
                // Fallback to direct update
                playerObject.transform.position = position;
                playerObject.transform.rotation = rotation;
            }
            
            // Update animation state if available
            Animator animator = playerObject.GetComponentInChildren<Animator>();
            if (animator != null)
            {
                bool isMoving = playerData["isMoving"]?.Value<bool>() ?? false;
                bool isRunning = playerData["isRunning"]?.Value<bool>() ?? false;
                
                animator.SetBool("IsMoving", isMoving);
                animator.SetBool("IsRunning", isRunning);
            }
        }
        catch (Exception ex)
        {
            Debug.LogError($"Error updating other player: {ex.Message}");
        }
    }

    private void DespawnOtherPlayer(string playerId)
    {
        if (otherPlayers.TryGetValue(playerId, out GameObject playerObject))
        {
            // Destroy player game object
            Destroy(playerObject);
            
            // Remove from other players
            otherPlayers.Remove(playerId);
        }
    }

    // Helper methods for block manipulation
    public void SetBlock(Vector3Int worldPosition, int blockType)
    {
        // Convert world position to chunk coordinates
        Vector3Int chunkPos = WorldToChunkCoordinates(worldPosition);
        string chunkKey = GetChunkKey(chunkPos);
        
        // Check if chunk is loaded
        if (loadedChunks.TryGetValue(chunkKey, out Chunk chunk))
        {
            // Convert world position to local chunk position
            Vector3Int localPos = WorldToLocalCoordinates(worldPosition, chunkPos);
            
            // Set block in chunk
            chunk.SetBlock(localPos.x, localPos.y, localPos.z, blockType);
        }
    }

    public int GetBlock(Vector3Int worldPosition)
    {
        // Convert world position to chunk coordinates
        Vector3Int chunkPos = WorldToChunkCoordinates(worldPosition);
        string chunkKey = GetChunkKey(chunkPos);
        
        // Check if chunk is loaded
        if (loadedChunks.TryGetValue(chunkKey, out Chunk chunk))
        {
            // Convert world position to local chunk position
            Vector3Int localPos = WorldToLocalCoordinates(worldPosition, chunkPos);
            
            // Get block from chunk
            return chunk.GetBlock(localPos.x, localPos.y, localPos.z);
        }
        
        return 0; // Air or empty
    }

    // Coordinate conversion methods
    public Vector3Int WorldToChunkCoordinates(Vector3 worldPosition)
    {
        int chunkX = Mathf.FloorToInt(worldPosition.x / chunkSize);
        int chunkZ = Mathf.FloorToInt(worldPosition.z / chunkSize);
        return new Vector3Int(chunkX, 0, chunkZ);
    }

    public Vector3Int WorldToLocalCoordinates(Vector3Int worldPosition, Vector3Int chunkPos)
    {
        int localX = worldPosition.x - (chunkPos.x * chunkSize);
        int localZ = worldPosition.z - (chunkPos.z * chunkSize);
        return new Vector3Int(localX, worldPosition.y, localZ);
    }

    public Vector3 ChunkToWorldPosition(Vector3Int chunkPos)
    {
        return new Vector3(chunkPos.x * chunkSize, 0, chunkPos.z * chunkSize);
    }

    public string GetChunkKey(Vector3Int chunkPos)
    {
        return $"{chunkPos.x}:{chunkPos.z}";
    }

    public Vector3Int ChunkKeyToCoordinates(string chunkKey)
    {
        string[] parts = chunkKey.Split(':');
        int x = int.Parse(parts[0]);
        int z = int.Parse(parts[1]);
        return new Vector3Int(x, 0, z);
    }

    // Public methods for external use
    public GameObject GetBlockPrefab(int blockType)
    {
        if (blockType >= 0 && blockType < blockPrefabs.Length)
        {
            return blockPrefabs[blockType];
        }
        return null;
    }

    public Material GetBlockMaterial(int blockType)
    {
        if (blockType >= 0 && blockType < blockMaterials.Length)
        {
            return blockMaterials[blockType];
        }
        return null;
    }

    public bool IsChunkLoaded(Vector3Int chunkPos)
    {
        string chunkKey = GetChunkKey(chunkPos);
        return loadedChunks.ContainsKey(chunkKey);
    }

    public Entity GetEntityById(string entityId)
    {
        if (loadedEntities.TryGetValue(entityId, out Entity entity))
        {
            return entity;
        }
        return null;
    }

    public List<Entity> GetEntitiesInRange(Vector3 position, float range)
    {
        List<Entity> entitiesInRange = new List<Entity>();
        
        foreach (Entity entity in loadedEntities.Values)
        {
            float distance = Vector3.Distance(position, entity.transform.position);
            if (distance <= range)
            {
                entitiesInRange.Add(entity);
            }
        }
        
        return entitiesInRange;
    }
}
