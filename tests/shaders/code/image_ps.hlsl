#include "common.hlsl"
#include "image_common.hlsl"

Texture2D tImage : register(ps, t0);
sampler sSampler : register(ps, s0);

float4 main(const IMAGE_VS_OUTPUT v) : SV_Target
{
  float2 image_offset = v.image_rect.xy;
  float2 image_size = v.image_rect.zw;
  float2 uv = image_offset + image_size * frac(v.source_uv);
  return tImage.Sample(sSampler, uv);
}
