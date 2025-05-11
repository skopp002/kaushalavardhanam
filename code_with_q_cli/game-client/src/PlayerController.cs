using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using Newtonsoft.Json.Linq;

[RequireComponent(typeof(CharacterController))]
public class PlayerController : MonoBehaviour
{
    // References
    private CharacterController characterController;
    private Camera playerCamera;
    private Transform cameraTransform;
    private Animator animator;

    // Movement settings
    [Header("Movement")]
    [SerializeField] private float walkSpeed = 5.0f;
    [SerializeField] private float runSpeed = 8.0f;
    [SerializeField] private float jumpForce = 5.0f;
    [SerializeField] private float gravity = 20.0f;
    [SerializeField] private float airControl = 0.5f;
    [SerializeField] private float rotationSpeed = 10.0f;

    // Camera settings
    [Header("Camera")]
    [SerializeField] private float lookSensitivity = 2.0f;
    [SerializeField] private float lookSmoothing = 2.0f;
    [SerializeField] private float minVerticalLookAngle = -80.0f;
    [SerializeField] private float maxVerticalLookAngle = 80.0f;

    // Interaction settings
    [Header("Interaction")]
    [SerializeField] private float interactionDistance = 5.0f;
    [SerializeField] private LayerMask interactionMask;
    [SerializeField] private Transform blockHighlight;
    [SerializeField] private float blockPlaceDelay = 0.2f;

    // Abilities
    [Header("Abilities")]
    [SerializeField] private Transform abilitySpawnPoint;
    [SerializeField] private float abilityCooldown = 1.0f;

    // UI References
    [Header("UI")]
    [SerializeField] private GameObject abilityWheelUI;
    [SerializeField] private GameObject inventoryUI;

    // Internal state
    private Vector3 moveDirection = Vector3.zero;
    private float verticalLookRotation = 0f;
    private bool isGrounded = false;
    private bool isRunning = false;
    private bool canPlaceBlock = true;
    private bool canUseAbility = true;
    private Vector3Int? highlightedBlock = null;
    private Vector3Int? adjacentBlock = null;
    private string selectedAstra = "";
    private string selectedSiddhi = "";
    private float lastPositionUpdateTime = 0f;
    private Vector3 lastReportedPosition;
    private bool uiActive = false;

    // Events
    public event Action<Vector3Int, int> OnBlockPlaced;
    public event Action<Vector3Int> OnBlockBroken;
    public event Action<string, string> OnAbilityUsed;
    public event Action<string, string> OnInteractionStarted;

    private void Awake()
    {
        // Get component references
        characterController = GetComponent<CharacterController>();
        animator = GetComponentInChildren<Animator>();
        playerCamera = GetComponentInChildren<Camera>();
        
        if (playerCamera != null)
        {
            cameraTransform = playerCamera.transform;
        }
        else
        {
            Debug.LogError("Player camera not found!");
        }
    }

    private void Start()
    {
        // Lock cursor for first-person control
        Cursor.lockState = CursorLockMode.Locked;
        Cursor.visible = false;

        // Initialize UI
        if (abilityWheelUI != null) abilityWheelUI.SetActive(false);
        if (inventoryUI != null) inventoryUI.SetActive(false);

        // Subscribe to network events
        NetworkManager.Instance.OnGameStateUpdate += OnGameStateUpdate;
        
        // Initialize position
        lastReportedPosition = transform.position;
    }

    private void OnDestroy()
    {
        // Unsubscribe from network events
        if (NetworkManager.Instance != null)
        {
            NetworkManager.Instance.OnGameStateUpdate -= OnGameStateUpdate;
        }
    }

    private void Update()
    {
        // Skip input handling if UI is active
        if (uiActive) return;

        // Handle player input
        HandleMovementInput();
        HandleMouseLook();
        HandleInteractionInput();
        HandleAbilityInput();
        HandleUIInput();

        // Update block highlighting
        UpdateBlockHighlight();

        // Send position updates to server periodically
        if (Time.time - lastPositionUpdateTime > 0.1f) // 10 updates per second
        {
            if (Vector3.Distance(transform.position, lastReportedPosition) > 0.1f)
            {
                SendPositionUpdate();
                lastReportedPosition = transform.position;
            }
            lastPositionUpdateTime = Time.time;
        }
    }

    private void HandleMovementInput()
    {
        // Check if player is grounded
        isGrounded = characterController.isGrounded;

        // Get input axes
        float horizontal = Input.GetAxis("Horizontal");
        float vertical = Input.GetAxis("Vertical");
        
        // Check if running
        isRunning = Input.GetKey(KeyCode.LeftShift);
        
        // Calculate movement direction relative to camera orientation
        Vector3 forward = cameraTransform.forward;
        Vector3 right = cameraTransform.right;
        
        // Keep movement in the horizontal plane
        forward.y = 0;
        right.y = 0;
        forward.Normalize();
        right.Normalize();
        
        // Combine movement direction
        Vector3 desiredMoveDirection = (forward * vertical) + (right * horizontal);
        
        // Apply movement speed
        float currentSpeed = isRunning ? runSpeed : walkSpeed;
        
        // Handle jumping
        if (isGrounded)
        {
            // Reset vertical velocity when grounded
            moveDirection.y = -0.5f; // Small downward force to keep grounded
            
            // Jump input
            if (Input.GetButtonDown("Jump"))
            {
                moveDirection.y = jumpForce;
                if (animator != null) animator.SetTrigger("Jump");
            }
            
            // Set horizontal movement
            moveDirection.x = desiredMoveDirection.x * currentSpeed;
            moveDirection.z = desiredMoveDirection.z * currentSpeed;
        }
        else
        {
            // Apply reduced air control when not grounded
            moveDirection.x = Mathf.Lerp(moveDirection.x, desiredMoveDirection.x * currentSpeed, airControl * Time.deltaTime);
            moveDirection.z = Mathf.Lerp(moveDirection.z, desiredMoveDirection.z * currentSpeed, airControl * Time.deltaTime);
            
            // Apply gravity
            moveDirection.y -= gravity * Time.deltaTime;
        }
        
        // Apply movement
        characterController.Move(moveDirection * Time.deltaTime);
        
        // Update animator
        if (animator != null)
        {
            animator.SetFloat("Speed", new Vector2(moveDirection.x, moveDirection.z).magnitude);
            animator.SetBool("IsRunning", isRunning && new Vector2(moveDirection.x, moveDirection.z).magnitude > 0.1f);
            animator.SetBool("IsGrounded", isGrounded);
        }
    }

    private void HandleMouseLook()
    {
        // Get mouse input
        float mouseX = Input.GetAxis("Mouse X") * lookSensitivity;
        float mouseY = Input.GetAxis("Mouse Y") * lookSensitivity;
        
        // Apply vertical rotation (pitch) to camera
        verticalLookRotation -= mouseY;
        verticalLookRotation = Mathf.Clamp(verticalLookRotation, minVerticalLookAngle, maxVerticalLookAngle);
        cameraTransform.localRotation = Quaternion.Euler(verticalLookRotation, 0f, 0f);
        
        // Apply horizontal rotation (yaw) to player
        transform.Rotate(Vector3.up * mouseX);
    }

    private void HandleInteractionInput()
    {
        // Raycast for interaction
        Ray ray = playerCamera.ViewportPointToRay(new Vector3(0.5f, 0.5f, 0));
        RaycastHit hit;
        
        if (Physics.Raycast(ray, out hit, interactionDistance, interactionMask))
        {
            // Calculate block position
            Vector3Int blockPos = Vector3Int.FloorToInt(hit.point - hit.normal * 0.1f);
            highlightedBlock = blockPos;
            
            // Calculate adjacent block position for placement
            Vector3Int adjacentPos = Vector3Int.FloorToInt(hit.point + hit.normal * 0.1f);
            adjacentBlock = adjacentPos;
            
            // Show block highlight
            if (blockHighlight != null)
            {
                blockHighlight.gameObject.SetActive(true);
                blockHighlight.position = blockPos + new Vector3(0.5f, 0.5f, 0.5f); // Center of block
            }
            
            // Break block
            if (Input.GetMouseButtonDown(0))
            {
                BreakBlock(blockPos);
            }
            
            // Place block
            if (Input.GetMouseButtonDown(1) && canPlaceBlock)
            {
                // Get selected block type from inventory (placeholder)
                int blockType = 1; // Default block type
                
                PlaceBlock(adjacentPos, blockType);
                
                // Add cooldown to prevent spam
                StartCoroutine(BlockPlaceCooldown());
            }
            
            // Interact with entity
            if (Input.GetKeyDown(KeyCode.E))
            {
                // Check if hit object is an entity
                Entity entity = hit.collider.GetComponent<Entity>();
                if (entity != null)
                {
                    InteractWithEntity(entity);
                }
            }
        }
        else
        {
            // Hide block highlight when not pointing at a block
            if (blockHighlight != null)
            {
                blockHighlight.gameObject.SetActive(false);
            }
            
            highlightedBlock = null;
            adjacentBlock = null;
        }
    }

    private void HandleAbilityInput()
    {
        // Use Astra (primary ability)
        if (Input.GetMouseButtonDown(2) && canUseAbility && !string.IsNullOrEmpty(selectedAstra))
        {
            UseAbility("astra", selectedAstra);
            StartCoroutine(AbilityCooldown());
        }
        
        // Use Siddhi (secondary ability)
        if (Input.GetKeyDown(KeyCode.Q) && canUseAbility && !string.IsNullOrEmpty(selectedSiddhi))
        {
            UseAbility("siddhi", selectedSiddhi);
            StartCoroutine(AbilityCooldown());
        }
        
        // Ability selection hotkeys (1-9)
        for (int i = 0; i < 9; i++)
        {
            if (Input.GetKeyDown(KeyCode.Alpha1 + i))
            {
                // Select ability from quick slots
                SelectAbilityFromQuickSlot(i);
            }
        }
    }

    private void HandleUIInput()
    {
        // Toggle ability wheel
        if (Input.GetKeyDown(KeyCode.Tab))
        {
            ToggleAbilityWheel();
        }
        
        // Toggle inventory
        if (Input.GetKeyDown(KeyCode.I))
        {
            ToggleInventory();
        }
        
        // Close all UI with Escape
        if (Input.GetKeyDown(KeyCode.Escape) && uiActive)
        {
            CloseAllUI();
        }
    }

    private void UpdateBlockHighlight()
    {
        // Update block highlight appearance based on action
        if (blockHighlight != null && blockHighlight.gameObject.activeInHierarchy)
        {
            // Change color based on action (break vs place)
            Renderer highlightRenderer = blockHighlight.GetComponent<Renderer>();
            if (highlightRenderer != null)
            {
                if (Input.GetMouseButton(0)) // Breaking
                {
                    highlightRenderer.material.color = new Color(1f, 0.3f, 0.3f, 0.5f);
                }
                else if (Input.GetMouseButton(1)) // Placing
                {
                    highlightRenderer.material.color = new Color(0.3f, 1f, 0.3f, 0.5f);
                }
                else // Neutral
                {
                    highlightRenderer.material.color = new Color(1f, 1f, 1f, 0.3f);
                }
            }
        }
    }

    private void BreakBlock(Vector3Int position)
    {
        // Notify listeners
        OnBlockBroken?.Invoke(position);
        
        // Send to server
        JObject data = new JObject();
        data["x"] = position.x;
        data["y"] = position.y;
        data["z"] = position.z;
        
        NetworkManager.Instance.SendMessage("breakBlock", data);
        
        // Play sound effect
        AudioManager.Instance?.PlaySoundEffect("block_break");
        
        // Play animation
        if (animator != null) animator.SetTrigger("Attack");
    }

    private void PlaceBlock(Vector3Int position, int blockType)
    {
        // Notify listeners
        OnBlockPlaced?.Invoke(position, blockType);
        
        // Send to server
        JObject data = new JObject();
        data["x"] = position.x;
        data["y"] = position.y;
        data["z"] = position.z;
        data["blockType"] = blockType;
        
        NetworkManager.Instance.SendMessage("placeBlock", data);
        
        // Play sound effect
        AudioManager.Instance?.PlaySoundEffect("block_place");
    }

    private void InteractWithEntity(Entity entity)
    {
        string entityId = entity.GetEntityId();
        string entityType = entity.GetEntityType();
        
        // Notify listeners
        OnInteractionStarted?.Invoke(entityId, entityType);
        
        // Send to server
        JObject data = new JObject();
        data["entityId"] = entityId;
        data["action"] = "interact";
        
        NetworkManager.Instance.SendMessage("entityInteraction", data);
        
        // Handle specific entity types
        if (entityType == "guru")
        {
            // Open guru dialog UI
            UIManager.Instance?.OpenGuruDialog(entity.GetEntityName());
        }
    }

    private void UseAbility(string abilityType, string abilityId)
    {
        // Create parameters based on player's current state
        JObject parameters = new JObject();
        parameters["position"] = JObject.FromObject(new { 
            x = transform.position.x, 
            y = transform.position.y, 
            z = transform.position.z 
        });
        parameters["direction"] = JObject.FromObject(new { 
            x = cameraTransform.forward.x, 
            y = cameraTransform.forward.y, 
            z = cameraTransform.forward.z 
        });
        
        // Notify listeners
        OnAbilityUsed?.Invoke(abilityType, abilityId);
        
        // Send to server
        NetworkManager.Instance.UseAbility(abilityType, abilityId, parameters);
        
        // Play effects
        PlayAbilityEffects(abilityType, abilityId);
        
        // Play animation
        if (animator != null) animator.SetTrigger("UseAbility");
    }

    private void PlayAbilityEffects(string abilityType, string abilityId)
    {
        // Play sound effect
        AudioManager.Instance?.PlaySoundEffect($"{abilityType}_{abilityId}");
        
        // Spawn visual effect
        if (abilitySpawnPoint != null)
        {
            // This would be implemented in a VisualEffectsManager
            VisualEffectsManager.Instance?.SpawnAbilityEffect(abilityType, abilityId, abilitySpawnPoint.position, cameraTransform.forward);
        }
    }

    private void SelectAbilityFromQuickSlot(int slotIndex)
    {
        // This would be implemented with an actual inventory/ability system
        // For now, just use placeholder abilities
        
        // Example astras
        string[] astras = { "vana", "agni", "vajra", "jala", "vidyut", "surya", "chandra" };
        
        // Example siddhis
        string[] siddhis = { "atma", "agni", "varuna", "vayu", "bhumi", "akasha", "kala" };
        
        // Select based on available abilities
        List<string> learnedAstras = GameManager.Instance.GetLearnedAstras();
        List<string> learnedSiddhis = GameManager.Instance.GetLearnedSiddhis();
        
        if (slotIndex < learnedAstras.Count)
        {
            selectedAstra = learnedAstras[slotIndex];
            UIManager.Instance?.UpdateSelectedAbility("astra", selectedAstra);
        }
        else if (slotIndex - learnedAstras.Count < learnedSiddhis.Count)
        {
            selectedSiddhi = learnedSiddhis[slotIndex - learnedAstras.Count];
            UIManager.Instance?.UpdateSelectedAbility("siddhi", selectedSiddhi);
        }
    }

    private void ToggleAbilityWheel()
    {
        if (abilityWheelUI != null)
        {
            bool isActive = !abilityWheelUI.activeSelf;
            abilityWheelUI.SetActive(isActive);
            
            // Update UI state
            uiActive = isActive;
            
            // Handle cursor
            Cursor.lockState = isActive ? CursorLockMode.None : CursorLockMode.Locked;
            Cursor.visible = isActive;
        }
    }

    private void ToggleInventory()
    {
        if (inventoryUI != null)
        {
            bool isActive = !inventoryUI.activeSelf;
            inventoryUI.SetActive(isActive);
            
            // Update UI state
            uiActive = isActive;
            
            // Handle cursor
            Cursor.lockState = isActive ? CursorLockMode.None : CursorLockMode.Locked;
            Cursor.visible = isActive;
        }
    }

    private void CloseAllUI()
    {
        if (abilityWheelUI != null) abilityWheelUI.SetActive(false);
        if (inventoryUI != null) inventoryUI.SetActive(false);
        
        // Update UI state
        uiActive = false;
        
        // Lock cursor again
        Cursor.lockState = CursorLockMode.Locked;
        Cursor.visible = false;
    }

    private void SendPositionUpdate()
    {
        NetworkManager.Instance.SendPlayerPosition(
            transform.position.x,
            transform.position.y,
            transform.position.z
        );
    }

    private void OnGameStateUpdate(JObject gameState)
    {
        // Handle game state updates from server
        // This could include other players' positions, world changes, etc.
    }

    // Coroutines for cooldowns
    private IEnumerator BlockPlaceCooldown()
    {
        canPlaceBlock = false;
        yield return new WaitForSeconds(blockPlaceDelay);
        canPlaceBlock = true;
    }

    private IEnumerator AbilityCooldown()
    {
        canUseAbility = false;
        yield return new WaitForSeconds(abilityCooldown);
        canUseAbility = true;
    }

    // Public methods for external control
    public void SetPosition(Vector3 position)
    {
        // Teleport player to position
        characterController.enabled = false;
        transform.position = position;
        characterController.enabled = true;
        
        // Update last reported position
        lastReportedPosition = position;
    }

    public void ApplyDamage(int amount)
    {
        // This would be implemented with a health system
        // For now, just play hit animation
        if (animator != null) animator.SetTrigger("Hit");
        
        // Play sound effect
        AudioManager.Instance?.PlaySoundEffect("player_hit");
    }

    public void LearnAbility(string abilityType, string abilityId)
    {
        // Send to server
        NetworkManager.Instance.LearnAbility(abilityType, abilityId);
        
        // Update local state
        if (abilityType == "astra")
        {
            if (string.IsNullOrEmpty(selectedAstra))
            {
                selectedAstra = abilityId;
                UIManager.Instance?.UpdateSelectedAbility("astra", selectedAstra);
            }
        }
        else if (abilityType == "siddhi")
        {
            if (string.IsNullOrEmpty(selectedSiddhi))
            {
                selectedSiddhi = abilityId;
                UIManager.Instance?.UpdateSelectedAbility("siddhi", selectedSiddhi);
            }
        }
        
        // Play effects
        AudioManager.Instance?.PlaySoundEffect("ability_learned");
        VisualEffectsManager.Instance?.PlayAbilityLearnedEffect(abilityType, abilityId);
    }
}
