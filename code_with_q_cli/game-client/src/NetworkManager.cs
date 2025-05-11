using System;
using System.Collections;
using System.Collections.Generic;
using System.Net;
using System.Net.Sockets;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

public class NetworkManager : MonoBehaviour
{
    // Singleton instance
    public static NetworkManager Instance { get; private set; }

    // Network configuration
    private string serverAddress;
    private int serverPort;
    private string playerSessionId;
    private TcpClient tcpClient;
    private NetworkStream networkStream;
    private Thread receiveThread;
    private bool isConnected = false;
    private Queue<string> messageQueue = new Queue<string>();
    private object queueLock = new object();

    // Events
    public event Action OnConnected;
    public event Action<string> OnConnectionFailed;
    public event Action OnDisconnected;
    public event Action<JObject> OnGameStateUpdate;
    public event Action<JObject> OnPlayerUpdate;
    public event Action<JObject> OnChunkData;
    public event Action<string, JObject> OnCustomMessage;

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

    private void Update()
    {
        // Process received messages on the main thread
        if (messageQueue.Count > 0)
        {
            string message;
            lock (queueLock)
            {
                message = messageQueue.Dequeue();
            }
            ProcessMessage(message);
        }
    }

    private void OnDestroy()
    {
        Disconnect();
    }

    public async Task<bool> Connect(string address, int port, string sessionId)
    {
        try
        {
            // Store connection info
            serverAddress = address;
            serverPort = port;
            playerSessionId = sessionId;

            // Create TCP client
            tcpClient = new TcpClient();
            
            // Connect to server
            await tcpClient.ConnectAsync(serverAddress, serverPort);
            
            if (!tcpClient.Connected)
            {
                Debug.LogError("Failed to connect to server");
                OnConnectionFailed?.Invoke("Failed to connect to server");
                return false;
            }
            
            // Get network stream
            networkStream = tcpClient.GetStream();
            
            // Send player session ID to authenticate
            JObject authMessage = new JObject();
            authMessage["type"] = "auth";
            authMessage["playerSessionId"] = playerSessionId;
            
            byte[] authData = System.Text.Encoding.UTF8.GetBytes(authMessage.ToString());
            await networkStream.WriteAsync(authData, 0, authData.Length);
            
            // Start receive thread
            isConnected = true;
            receiveThread = new Thread(ReceiveLoop);
            receiveThread.IsBackground = true;
            receiveThread.Start();
            
            Debug.Log("Connected to game server");
            OnConnected?.Invoke();
            
            return true;
        }
        catch (Exception ex)
        {
            Debug.LogError($"Connection error: {ex.Message}");
            OnConnectionFailed?.Invoke(ex.Message);
            return false;
        }
    }

    public void Disconnect()
    {
        if (!isConnected) return;
        
        isConnected = false;
        
        // Clean up network resources
        if (networkStream != null)
        {
            networkStream.Close();
            networkStream = null;
        }
        
        if (tcpClient != null)
        {
            tcpClient.Close();
            tcpClient = null;
        }
        
        // Wait for receive thread to terminate
        if (receiveThread != null && receiveThread.IsAlive)
        {
            receiveThread.Join(1000);
            receiveThread = null;
        }
        
        Debug.Log("Disconnected from game server");
        OnDisconnected?.Invoke();
    }

    public async Task<bool> SendMessage(string type, JObject data)
    {
        if (!isConnected || networkStream == null)
        {
            Debug.LogError("Cannot send message: Not connected to server");
            return false;
        }
        
        try
        {
            // Create message
            JObject message = new JObject();
            message["type"] = type;
            message["data"] = data;
            
            // Send message
            string messageJson = message.ToString(Formatting.None);
            byte[] messageData = System.Text.Encoding.UTF8.GetBytes(messageJson);
            
            await networkStream.WriteAsync(messageData, 0, messageData.Length);
            return true;
        }
        catch (Exception ex)
        {
            Debug.LogError($"Error sending message: {ex.Message}");
            return false;
        }
    }

    private void ReceiveLoop()
    {
        byte[] buffer = new byte[8192];
        
        while (isConnected)
        {
            try
            {
                if (networkStream.CanRead)
                {
                    StringBuilder messageBuilder = new StringBuilder();
                    int bytesRead;
                    
                    // Read data from network stream
                    while ((bytesRead = networkStream.Read(buffer, 0, buffer.Length)) > 0)
                    {
                        string chunk = System.Text.Encoding.UTF8.GetString(buffer, 0, bytesRead);
                        messageBuilder.Append(chunk);
                        
                        // Check if we have a complete message
                        if (chunk.EndsWith("}"))
                        {
                            string message = messageBuilder.ToString();
                            
                            // Add message to queue for processing on main thread
                            lock (queueLock)
                            {
                                messageQueue.Enqueue(message);
                            }
                            
                            messageBuilder.Clear();
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                if (isConnected)
                {
                    Debug.LogError($"Error in receive loop: {ex.Message}");
                    Disconnect();
                }
                break;
            }
        }
    }

    private void ProcessMessage(string messageJson)
    {
        try
        {
            JObject message = JObject.Parse(messageJson);
            string type = message["type"]?.ToString();
            
            switch (type)
            {
                case "gameState":
                    OnGameStateUpdate?.Invoke(message["data"] as JObject);
                    break;
                
                case "playerUpdate":
                    OnPlayerUpdate?.Invoke(message["data"] as JObject);
                    break;
                
                case "chunkData":
                    OnChunkData?.Invoke(message["data"] as JObject);
                    break;
                
                default:
                    // Custom message type
                    OnCustomMessage?.Invoke(type, message["data"] as JObject);
                    break;
            }
        }
        catch (Exception ex)
        {
            Debug.LogError($"Error processing message: {ex.Message}");
        }
    }

    // Helper methods for common game actions
    public async Task<bool> SendPlayerPosition(float x, float y, float z)
    {
        JObject data = new JObject();
        data["x"] = x;
        data["y"] = y;
        data["z"] = z;
        
        return await SendMessage("playerPosition", data);
    }

    public async Task<bool> RequestChunkData(int chunkX, int chunkZ)
    {
        JObject data = new JObject();
        data["chunkX"] = chunkX;
        data["chunkZ"] = chunkZ;
        
        return await SendMessage("requestChunk", data);
    }

    public async Task<bool> PlaceBlock(int x, int y, int z, int blockType)
    {
        JObject data = new JObject();
        data["x"] = x;
        data["y"] = y;
        data["z"] = z;
        data["blockType"] = blockType;
        
        return await SendMessage("placeBlock", data);
    }

    public async Task<bool> BreakBlock(int x, int y, int z)
    {
        JObject data = new JObject();
        data["x"] = x;
        data["y"] = y;
        data["z"] = z;
        
        return await SendMessage("breakBlock", data);
    }

    public async Task<bool> InteractWithEntity(string entityId, string action)
    {
        JObject data = new JObject();
        data["entityId"] = entityId;
        data["action"] = action;
        
        return await SendMessage("entityInteraction", data);
    }

    public async Task<bool> LearnAbility(string abilityType, string abilityId)
    {
        JObject data = new JObject();
        data["abilityType"] = abilityType; // "astra" or "siddhi"
        data["abilityId"] = abilityId;
        
        return await SendMessage("learnAbility", data);
    }

    public async Task<bool> UseAbility(string abilityType, string abilityId, JObject parameters)
    {
        JObject data = new JObject();
        data["abilityType"] = abilityType;
        data["abilityId"] = abilityId;
        data["parameters"] = parameters;
        
        return await SendMessage("useAbility", data);
    }
}
