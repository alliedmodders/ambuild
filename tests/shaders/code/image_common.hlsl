
struct IMAGE_VS_OUTPUT {
  float4 pos : SV_Position;
  float2 source_uv : TEXCOORD0;
  float4 image_rect : TEXCOORD1;
};
