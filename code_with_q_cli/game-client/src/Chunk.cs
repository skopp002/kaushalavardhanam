using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class Chunk : MonoBehaviour
{
    // Chunk properties
    private Vector3Int chunkPosition;
    private int chunkSize;
    private int worldHeight;
    private int[,,] blocks;
    
    // Mesh data
    private List<Vector3> vertices = new List<Vector3>();
    private List<int> triangles = new List<int>();
    private List<Vector2> uvs = new List<Vector2>();
    
    // Components
    private MeshFilter meshFilter;
    private MeshRenderer meshRenderer;
    private MeshCollider meshCollider;
    
    // Optimization
    private bool isDirty = true;
    private bool isInitialized = false;
    
    // Block face directions
    private static readonly Vector3Int[] faceDirections = new Vector3Int[]
    {
        new Vector3Int(0, 0, 1),  // Front
        new Vector3Int(0, 0, -1), // Back
        new Vector3Int(1, 0, 0),  // Right
        new Vector3Int(-1, 0, 0), // Left
        new Vector3Int(0, 1, 0),  // Top
        new Vector3Int(0, -1, 0)  // Bottom
    };
    
    // UV coordinates for each face (assuming 16x16 texture atlas)
    private static readonly Vector2[] faceUVs = new Vector2[]
    {
        new Vector2(0, 0),
        new Vector2(0, 1),
        new Vector2(1, 1),
        new Vector2(1, 0)
    };
    
    public void Initialize(Vector3Int position, int size, int height)
    {
        chunkPosition = position;
        chunkSize = size;
        worldHeight = height;
        
        // Initialize block array
        blocks = new int[chunkSize, worldHeight, chunkSize];
        
        // Get or add required components
        meshFilter = GetComponent<MeshFilter>();
        if (meshFilter == null)
        {
            meshFilter = gameObject.AddComponent<MeshFilter>();
        }
        
        meshRenderer = GetComponent<MeshRenderer>();
        if (meshRenderer == null)
        {
            meshRenderer = gameObject.AddComponent<MeshRenderer>();
        }
        
        meshCollider = GetComponent<MeshCollider>();
        if (meshCollider == null)
        {
            meshCollider = gameObject.AddComponent<MeshCollider>();
        }
        
        // Set material
        meshRenderer.material = WorldManager.Instance.GetBlockMaterial(1); // Default material
        
        isInitialized = true;
        isDirty = true;
    }
    
    private void Update()
    {
        // Rebuild mesh if dirty
        if (isDirty && isInitialized)
        {
            RebuildMesh();
            isDirty = false;
        }
    }
    
    public void UpdateBlocks(int[] blockData)
    {
        if (!isInitialized) return;
        
        // Ensure block data is the right size
        if (blockData.Length != chunkSize * worldHeight * chunkSize)
        {
            Debug.LogError($"Block data size mismatch: {blockData.Length} vs {chunkSize * worldHeight * chunkSize}");
            return;
        }
        
        // Update block array
        int index = 0;
        for (int y = 0; y < worldHeight; y++)
        {
            for (int z = 0; z < chunkSize; z++)
            {
                for (int x = 0; x < chunkSize; x++)
                {
                    blocks[x, y, z] = blockData[index++];
                }
            }
        }
        
        // Mark chunk as dirty to rebuild mesh
        isDirty = true;
    }
    
    public int GetBlock(int x, int y, int z)
    {
        // Check bounds
        if (x < 0 || x >= chunkSize || y < 0 || y >= worldHeight || z < 0 || z >= chunkSize)
        {
            return 0; // Air or empty
        }
        
        return blocks[x, y, z];
    }
    
    public void SetBlock(int x, int y, int z, int blockType)
    {
        // Check bounds
        if (x < 0 || x >= chunkSize || y < 0 || y >= worldHeight || z < 0 || z >= chunkSize)
        {
            return;
        }
        
        // Update block
        blocks[x, y, z] = blockType;
        
        // Mark chunk as dirty
        isDirty = true;
    }
    
    private void RebuildMesh()
    {
        // Clear mesh data
        vertices.Clear();
        triangles.Clear();
        uvs.Clear();
        
        // Generate mesh data
        for (int x = 0; x < chunkSize; x++)
        {
            for (int y = 0; y < worldHeight; y++)
            {
                for (int z = 0; z < chunkSize; z++)
                {
                    int blockType = blocks[x, y, z];
                    
                    // Skip air blocks
                    if (blockType == 0)
                    {
                        continue;
                    }
                    
                    // Add faces for this block
                    AddBlockFaces(new Vector3Int(x, y, z), blockType);
                }
            }
        }
        
        // Create or update mesh
        Mesh mesh = new Mesh();
        mesh.vertices = vertices.ToArray();
        mesh.triangles = triangles.ToArray();
        mesh.uv = uvs.ToArray();
        
        // Recalculate normals and bounds
        mesh.RecalculateNormals();
        mesh.RecalculateBounds();
        
        // Assign mesh to components
        meshFilter.mesh = mesh;
        meshCollider.sharedMesh = mesh;
    }
    
    private void AddBlockFaces(Vector3Int blockPos, int blockType)
    {
        // Check each face direction
        for (int i = 0; i < 6; i++)
        {
            Vector3Int neighborPos = blockPos + faceDirections[i];
            
            // Check if face should be visible
            bool isVisible = false;
            
            // If neighbor is outside chunk, check with world manager
            if (neighborPos.x < 0 || neighborPos.x >= chunkSize || 
                neighborPos.z < 0 || neighborPos.z >= chunkSize)
            {
                // Convert to world coordinates
                Vector3Int worldPos = new Vector3Int(
                    chunkPosition.x * chunkSize + neighborPos.x,
                    neighborPos.y,
                    chunkPosition.z * chunkSize + neighborPos.z
                );
                
                // Check with world manager
                int neighborBlockType = WorldManager.Instance.GetBlock(worldPos);
                isVisible = IsBlockTransparent(neighborBlockType);
            }
            // If neighbor is outside height range, it's visible if facing up or down
            else if (neighborPos.y < 0 || neighborPos.y >= worldHeight)
            {
                isVisible = true;
            }
            // Otherwise check local blocks
            else
            {
                int neighborBlockType = blocks[neighborPos.x, neighborPos.y, neighborPos.z];
                isVisible = IsBlockTransparent(neighborBlockType);
            }
            
            // Add face if visible
            if (isVisible)
            {
                AddFace(blockPos, i, blockType);
            }
        }
    }
    
    private void AddFace(Vector3Int blockPos, int faceIndex, int blockType)
    {
        // Get current vertex count
        int vertexIndex = vertices.Count;
        
        // Get block texture coordinates
        Vector2 textureOffset = GetTextureOffset(blockType, faceIndex);
        
        // Add vertices for this face
        switch (faceIndex)
        {
            case 0: // Front (Z+)
                vertices.Add(new Vector3(blockPos.x, blockPos.y, blockPos.z + 1));
                vertices.Add(new Vector3(blockPos.x, blockPos.y + 1, blockPos.z + 1));
                vertices.Add(new Vector3(blockPos.x + 1, blockPos.y + 1, blockPos.z + 1));
                vertices.Add(new Vector3(blockPos.x + 1, blockPos.y, blockPos.z + 1));
                break;
            case 1: // Back (Z-)
                vertices.Add(new Vector3(blockPos.x + 1, blockPos.y, blockPos.z));
                vertices.Add(new Vector3(blockPos.x + 1, blockPos.y + 1, blockPos.z));
                vertices.Add(new Vector3(blockPos.x, blockPos.y + 1, blockPos.z));
                vertices.Add(new Vector3(blockPos.x, blockPos.y, blockPos.z));
                break;
            case 2: // Right (X+)
                vertices.Add(new Vector3(blockPos.x + 1, blockPos.y, blockPos.z + 1));
                vertices.Add(new Vector3(blockPos.x + 1, blockPos.y + 1, blockPos.z + 1));
                vertices.Add(new Vector3(blockPos.x + 1, blockPos.y + 1, blockPos.z));
                vertices.Add(new Vector3(blockPos.x + 1, blockPos.y, blockPos.z));
                break;
            case 3: // Left (X-)
                vertices.Add(new Vector3(blockPos.x, blockPos.y, blockPos.z));
                vertices.Add(new Vector3(blockPos.x, blockPos.y + 1, blockPos.z));
                vertices.Add(new Vector3(blockPos.x, blockPos.y + 1, blockPos.z + 1));
                vertices.Add(new Vector3(blockPos.x, blockPos.y, blockPos.z + 1));
                break;
            case 4: // Top (Y+)
                vertices.Add(new Vector3(blockPos.x, blockPos.y + 1, blockPos.z + 1));
                vertices.Add(new Vector3(blockPos.x, blockPos.y + 1, blockPos.z));
                vertices.Add(new Vector3(blockPos.x + 1, blockPos.y + 1, blockPos.z));
                vertices.Add(new Vector3(blockPos.x + 1, blockPos.y + 1, blockPos.z + 1));
                break;
            case 5: // Bottom (Y-)
                vertices.Add(new Vector3(blockPos.x, blockPos.y, blockPos.z));
                vertices.Add(new Vector3(blockPos.x, blockPos.y, blockPos.z + 1));
                vertices.Add(new Vector3(blockPos.x + 1, blockPos.y, blockPos.z + 1));
                vertices.Add(new Vector3(blockPos.x + 1, blockPos.y, blockPos.z));
                break;
        }
        
        // Add triangles
        triangles.Add(vertexIndex);
        triangles.Add(vertexIndex + 1);
        triangles.Add(vertexIndex + 2);
        triangles.Add(vertexIndex);
        triangles.Add(vertexIndex + 2);
        triangles.Add(vertexIndex + 3);
        
        // Add UVs
        for (int i = 0; i < 4; i++)
        {
            Vector2 uv = faceUVs[i];
            uv.x = (uv.x / 16) + (textureOffset.x / 16);
            uv.y = (uv.y / 16) + (textureOffset.y / 16);
            uvs.Add(uv);
        }
    }
    
    private Vector2 GetTextureOffset(int blockType, int faceIndex)
    {
        // This would be implemented based on your texture atlas layout
        // For now, just use a simple mapping
        
        // Example: Each block type has a row in the texture atlas
        int row = blockType - 1; // Subtract 1 because block type 0 is air
        
        // Different faces might have different textures
        int column = 0;
        
        // For example, top and bottom faces might have different textures
        if (faceIndex == 4) // Top
        {
            column = 1;
        }
        else if (faceIndex == 5) // Bottom
        {
            column = 2;
        }
        
        return new Vector2(column, row);
    }
    
    private bool IsBlockTransparent(int blockType)
    {
        // Block type 0 is air (transparent)
        // Add other transparent block types as needed
        return blockType == 0;
    }
}
