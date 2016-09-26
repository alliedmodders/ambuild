
// Group #1: Updates on Window size changes.
cbuffer worldBuffer : register(b0) {
  float4x4 kProjection;
};

struct Tile {
  float4 screenRect;
};

// Group #2: Updated on tile buffer changes.
cbuffer tileBuffer : register(b1) {
  Tile tiles[4096];
};

struct VS_INPUT {
  float2 pos : POSITION;
  uint id : SV_InstanceID;
};

struct QuadVertexInfo {
  // The vertex to pass to the pixel shader.
  float4 out_vertex;
  // Destination rect, in screen space.
  float4 dest_rect;
  // Destination vertex, clipped to tile bounds.
  float2 clipped_pos;
};

QuadVertexInfo ComputeQuadVertex(uint tile_index, float4 dest_rect, float2 vertex)
{
  float4 tile_screen_rect = tiles[tile_index].screenRect;

  // Convert the vertex to screen space.
#if 0
  float2 screen_vertex = lerp(
    dest_rect.xy, // Top-left vertex.
    dest_rect.zw, // Bottom-right vertex.
    vertex);
#else
  float2 screen_vertex = float2(
    dest_rect.x + vertex.x * dest_rect.z,
    dest_rect.y + vertex.y * dest_rect.w);
#endif

  // Clamp the vertex to inside the tile.
#if 1
  screen_vertex = clamp(
    screen_vertex,
    tile_screen_rect.xy,
    tile_screen_rect.xy + tile_screen_rect.zw);
#endif

  QuadVertexInfo info;
  info.out_vertex = mul(kProjection, float4(screen_vertex, 0, 1));
  info.dest_rect = dest_rect;
  info.clipped_pos = screen_vertex;

  return info;
}

float2 TexturizeQuadVertex(float4 uv_rect, float2 pos)
{
  return float2(
    uv_rect.x + pos.x * uv_rect.z,
    uv_rect.y + pos.y * uv_rect.w);
}
