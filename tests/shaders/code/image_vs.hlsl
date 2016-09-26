#include "common.hlsl"
#include "vs_common.hlsl"
#include "image_common.hlsl"

struct Image {
  float4 source_uv;
  float4 dest;
  uint tile_index;
  uint3 padding;
};

cbuffer imageBuffer : register(b4) {
  Image images[1365];
};

IMAGE_VS_OUTPUT main(const VS_INPUT input)
{
  Image image = images[input.id];

  QuadVertexInfo vi = ComputeQuadVertex(
    image.tile_index,
    image.dest,
    input.pos);

  float2 uv = (vi.clipped_pos - vi.dest_rect.xy) / vi.dest_rect.zw;

  IMAGE_VS_OUTPUT v;
  v.pos = vi.out_vertex;
  v.source_uv = uv; //TexturizeQuadVertex(image.source_uv, input.pos);
  v.image_rect = image.source_uv;
  return v;
}
