#include <metal_stdlib>
#include <simd/simd.h>

using namespace metal;

struct buffer_t
{
    float offsetY_0;
    float2 textExpandRatio;
    float shakeX;
    float shakeScale;
    float shakeY;
    float scale;
    float back_alpha;
    float mix_with_black;
};

struct main0_out
{
    float4 o_fragColor [[color(0)]];
};

struct main0_in
{
    float2 v_uv [[user(locn0)]];
};

fragment main0_out main0(main0_in in [[stage_in]], constant buffer_t& buffer, texture2d<float> mainTex [[texture(0)]], sampler mainTexSmplr [[sampler(0)]])
{
    main0_out out = {};
    float2 _t1 = in.v_uv;
    _t1.y -= (buffer.offsetY_0 / buffer.textExpandRatio.y);
    _t1.x -= ((buffer.shakeX * buffer.shakeScale) / buffer.textExpandRatio.x);
    _t1.y -= ((buffer.shakeY * buffer.shakeScale) / buffer.textExpandRatio.y);
    float4 _63 = mainTex.sample(mainTexSmplr, _t1);
    float4 _t2 = _63;
    float4 _81 = mainTex.sample(mainTexSmplr, (((in.v_uv - float2(0.5)) * buffer.scale) + float2(0.5))) * buffer.back_alpha;
    float4 _t4 = _81;
    out.o_fragColor = (mix(_81, float4(0.0, 0.0, 0.0, _t4.w), float4(buffer.mix_with_black)) * (1.0 - _t2.w)) + _63;
    return out;
}

