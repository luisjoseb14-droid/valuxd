#include <metal_stdlib>
#include <simd/simd.h>

using namespace metal;

struct buffer_t
{
    float u_glowFromAlpha;
    int u_ca;
    float u_redOffset;
    float u_greenOffset;
    float u_blueOffset;
    int u_gamma;
    float u_gammaValue;
};

struct main0_out
{
    float4 o_fragColor [[color(0)]];
};

struct main0_in
{
    float2 v_uv [[user(locn0)]];
};

fragment main0_out main0(main0_in in [[stage_in]], constant buffer_t& buffer, texture2d<float> u_inputTex [[texture(0)]], sampler u_inputTexSmplr [[sampler(0)]])
{
    main0_out out = {};
    float4 _19 = u_inputTex.sample(u_inputTexSmplr, in.v_uv);
    float4 _t0 = _19;
    _t0 = mix(_19, float4(_t0.w), float4(buffer.u_glowFromAlpha));
    if (buffer.u_ca == 1)
    {
        float4 _t1 = u_inputTex.sample(u_inputTexSmplr, (in.v_uv + float2(-buffer.u_redOffset, buffer.u_redOffset))).yzwx;
        float _54 = _t1.w;
        float _57 = _t1.x;
        float _58 = _57 * _54;
        _t1.x = _58;
        _t1 = u_inputTex.sample(u_inputTexSmplr, (in.v_uv + float2(-buffer.u_greenOffset, buffer.u_greenOffset))).yzwx;
        float _72 = _t1.w;
        float _75 = _t1.y;
        float _76 = _75 * _72;
        _t1.y = _76;
        _t1 = u_inputTex.sample(u_inputTexSmplr, (in.v_uv + float2(-buffer.u_blueOffset, buffer.u_blueOffset))).yzwx;
        float _90 = _t1.w;
        float _93 = _t1.z;
        float _94 = _93 * _90;
        _t1.z = _94;
        _t0 = float4(_58, _76, _94, 1.0);
    }
    if (buffer.u_gamma == 1)
    {
        _t0 = pow(_t0, float4(buffer.u_gammaValue));
    }
    out.o_fragColor = _t0;
    return out;
}

