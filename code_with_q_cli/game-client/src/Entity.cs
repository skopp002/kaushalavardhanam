using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using Newtonsoft.Json.Linq;

public class Entity : MonoBehaviour
{
    // Entity identification
    [SerializeField] private string entityId;
    [SerializeField] private string entityType;
    [SerializeField] private string entityName;
    
    // Entity properties
    [SerializeField] private int health = 100;
    [SerializeField] private int maxHealth = 100;
    [SerializeField] private bool isInteractable = true;
    [SerializeField] private float interactionDistance = 3.0f;
    [SerializeField] private string interactionPrompt = "Press E to interact";
    
    // Visual elements
    [SerializeField] private GameObject interactionIndicator;
    [SerializeField] private GameObject healthBar;
    
    // For NPCs and enemies
    [SerializeField] private bool isNPC = false;
    [SerializeField] private bool isEnemy = false;
    [SerializeField] private float moveSpeed = 3.0f;
    [SerializeField] private float detectionRange = 10.0f;
    [SerializeField] private float attackRange = 2.0f;
    [SerializeField] private int attackDamage = 10;
    [SerializeField] private float attackCooldown = 1.5f;
    
    // For gurus
    [SerializeField] private bool isGuru = false;
    [SerializeField] private string[] teachableAstras;
    [SerializeField] private string[] teachableSiddhis;
    [SerializeField] private string[] dialogueLines;
    
    // Internal state
    private bool isPlayerInRange = false;
    private bool canAttack = true;
    private Animator animator;
    private Transform playerTransform;
    private Vector3 startPosition;
    private Quaternion startRotation;
    private bool isDead = false;
    
    // Events
    public event Action<int> OnHealthChanged;
    public event Action OnDeath;
    public event Action<string> OnInteractionStarted;
    
    private void Awake()
    {
        // Generate a unique ID if not set
        if (string.IsNullOrEmpty(entityId))
        {
            entityId = Guid.NewGuid().ToString();
        }
        
        // Get components
        animator = GetComponentInChildren<Animator>();
        
        // Store initial position and rotation
        startPosition = transform.position;
        startRotation = transform.rotation;
    }
    
    private void Start()
    {
        // Hide interaction indicator initially
        if (interactionIndicator != null)
        {
            interactionIndicator.SetActive(false);
        }
        
        // Update health bar
        UpdateHealthBar();
        
        // Find player
        GameObject playerObject = GameObject.FindGameObjectWithTag("Player");
        if (playerObject != null)
        {
            playerTransform = playerObject.transform;
        }
    }
    
    private void Update()
    {
        // Check if player is in range for interaction
        if (isInteractable && playerTransform != null)
        {
            float distanceToPlayer = Vector3.Distance(transform.position, playerTransform.position);
            bool playerInRange = distanceToPlayer <= interactionDistance;
            
            // Show/hide interaction indicator
            if (playerInRange != isPlayerInRange)
            {
                isPlayerInRange = playerInRange;
                if (interactionIndicator != null)
                {
                    interactionIndicator.SetActive(isPlayerInRange);
                }
                
                // Show interaction prompt
                if (isPlayerInRange)
                {
                    UIManager.Instance?.ShowInteractionPrompt(interactionPrompt);
                }
                else
                {
                    UIManager.Instance?.HideInteractionPrompt();
                }
            }
        }
        
        // Handle NPC behavior
        if (isNPC && !isDead)
        {
            HandleNPCBehavior();
        }
    }
    
    private void HandleNPCBehavior()
    {
        if (playerTransform == null) return;
        
        float distanceToPlayer = Vector3.Distance(transform.position, playerTransform.position);
        
        // Enemy behavior
        if (isEnemy)
        {
            // Check if player is in detection range
            if (distanceToPlayer <= detectionRange)
            {
                // Look at player
                Vector3 directionToPlayer = playerTransform.position - transform.position;
                directionToPlayer.y = 0; // Keep on same vertical plane
                Quaternion targetRotation = Quaternion.LookRotation(directionToPlayer);
                transform.rotation = Quaternion.Slerp(transform.rotation, targetRotation, Time.deltaTime * 5f);
                
                // Move towards player if not in attack range
                if (distanceToPlayer > attackRange)
                {
                    // Move towards player
                    transform.position += transform.forward * moveSpeed * Time.deltaTime;
                    
                    // Play walking animation
                    if (animator != null)
                    {
                        animator.SetBool("IsWalking", true);
                        animator.SetBool("IsAttacking", false);
                    }
                }
                else
                {
                    // Attack player if in range and cooldown is ready
                    if (canAttack)
                    {
                        Attack();
                    }
                    
                    // Stop moving
                    if (animator != null)
                    {
                        animator.SetBool("IsWalking", false);
                    }
                }
            }
            else
            {
                // Return to start position if player is out of range
                if (Vector3.Distance(transform.position, startPosition) > 0.5f)
                {
                    // Move back to start position
                    Vector3 directionToStart = startPosition - transform.position;
                    directionToStart.y = 0;
                    Quaternion targetRotation = Quaternion.LookRotation(directionToStart);
                    transform.rotation = Quaternion.Slerp(transform.rotation, targetRotation, Time.deltaTime * 3f);
                    
                    transform.position += transform.forward * moveSpeed * 0.5f * Time.deltaTime;
                    
                    // Play walking animation
                    if (animator != null)
                    {
                        animator.SetBool("IsWalking", true);
                        animator.SetBool("IsAttacking", false);
                    }
                }
                else
                {
                    // At start position, return to original rotation
                    transform.rotation = Quaternion.Slerp(transform.rotation, startRotation, Time.deltaTime * 2f);
                    
                    // Idle animation
                    if (animator != null)
                    {
                        animator.SetBool("IsWalking", false);
                        animator.SetBool("IsAttacking", false);
                    }
                }
            }
        }
        // Guru behavior
        else if (isGuru)
        {
            // Gurus don't move, they just turn to face the player when in range
            if (distanceToPlayer <= detectionRange)
            {
                // Look at player
                Vector3 directionToPlayer = playerTransform.position - transform.position;
                directionToPlayer.y = 0; // Keep on same vertical plane
                Quaternion targetRotation = Quaternion.LookRotation(directionToPlayer);
                transform.rotation = Quaternion.Slerp(transform.rotation, targetRotation, Time.deltaTime * 2f);
                
                // Play idle animation with awareness
                if (animator != null)
                {
                    animator.SetBool("IsAwareOfPlayer", true);
                }
            }
            else
            {
                // Return to original rotation
                transform.rotation = Quaternion.Slerp(transform.rotation, startRotation, Time.deltaTime * 1f);
                
                // Play standard idle animation
                if (animator != null)
                {
                    animator.SetBool("IsAwareOfPlayer", false);
                }
            }
        }
        // Generic NPC behavior
        else
        {
            // Simple wandering behavior
            // Implementation would depend on the specific NPC type
        }
    }
    
    private void Attack()
    {
        // Play attack animation
        if (animator != null)
        {
            animator.SetBool("IsAttacking", true);
            animator.SetTrigger("Attack");
        }
        
        // Deal damage to player
        PlayerHealth playerHealth = playerTransform.GetComponent<PlayerHealth>();
        if (playerHealth != null)
        {
            playerHealth.TakeDamage(attackDamage);
        }
        
        // Start attack cooldown
        StartCoroutine(AttackCooldown());
    }
    
    private IEnumerator AttackCooldown()
    {
        canAttack = false;
        yield return new WaitForSeconds(attackCooldown);
        canAttack = true;
    }
    
    public void TakeDamage(int damage)
    {
        if (isDead) return;
        
        health -= damage;
        health = Mathf.Clamp(health, 0, maxHealth);
        
        // Notify listeners
        OnHealthChanged?.Invoke(health);
        
        // Update health bar
        UpdateHealthBar();
        
        // Play hit animation
        if (animator != null)
        {
            animator.SetTrigger("Hit");
        }
        
        // Check for death
        if (health <= 0)
        {
            Die();
        }
    }
    
    private void Die()
    {
        isDead = true;
        
        // Play death animation
        if (animator != null)
        {
            animator.SetTrigger("Die");
        }
        
        // Disable interaction
        isInteractable = false;
        if (interactionIndicator != null)
        {
            interactionIndicator.SetActive(false);
        }
        
        // Hide health bar
        if (healthBar != null)
        {
            healthBar.SetActive(false);
        }
        
        // Notify listeners
        OnDeath?.Invoke();
        
        // Disable collider after a delay
        StartCoroutine(DisableColliderAfterDelay());
    }
    
    private IEnumerator DisableColliderAfterDelay()
    {
        yield return new WaitForSeconds(2.0f);
        
        // Disable collider
        Collider entityCollider = GetComponent<Collider>();
        if (entityCollider != null)
        {
            entityCollider.enabled = false;
        }
    }
    
    private void UpdateHealthBar()
    {
        if (healthBar != null)
        {
            // Update health bar scale or fill amount
            Transform fill = healthBar.transform.Find("Fill");
            if (fill != null)
            {
                float healthPercent = (float)health / maxHealth;
                fill.localScale = new Vector3(healthPercent, 1, 1);
            }
        }
    }
    
    public void Interact()
    {
        if (!isInteractable || isDead) return;
        
        // Notify listeners
        OnInteractionStarted?.Invoke(entityId);
        
        // Handle specific entity types
        if (isGuru)
        {
            // Open guru dialog
            UIManager.Instance?.OpenGuruDialog(entityName, dialogueLines, teachableAstras, teachableSiddhis);
        }
        else if (isNPC)
        {
            // Open NPC dialog
            UIManager.Instance?.OpenNPCDialog(entityName, dialogueLines);
        }
        
        // Play interaction animation
        if (animator != null)
        {
            animator.SetTrigger("Interact");
        }
    }
    
    // Getters
    public string GetEntityId() => entityId;
    public string GetEntityType() => entityType;
    public string GetEntityName() => entityName;
    public bool IsGuru() => isGuru;
    public bool IsEnemy() => isEnemy;
    public string[] GetTeachableAstras() => teachableAstras;
    public string[] GetTeachableSiddhis() => teachableSiddhis;
    
    // Network synchronization
    public void UpdateFromServer(JObject data)
    {
        // Update entity state from server data
        if (data["health"] != null)
        {
            health = data["health"].Value<int>();
            UpdateHealthBar();
        }
        
        if (data["position"] != null)
        {
            float x = data["position"]["x"].Value<float>();
            float y = data["position"]["y"].Value<float>();
            float z = data["position"]["z"].Value<float>();
            transform.position = new Vector3(x, y, z);
        }
        
        if (data["rotation"] != null)
        {
            float yaw = data["rotation"].Value<float>();
            transform.rotation = Quaternion.Euler(0, yaw, 0);
        }
        
        if (data["isDead"] != null && data["isDead"].Value<bool>())
        {
            if (!isDead)
            {
                Die();
            }
        }
    }
}
