#pragma clang diagnostic ignored "-Wmissing-prototypes"

#include <metal_stdlib>
#include <simd/simd.h>

using namespace metal;

struct buffer_t
{
    int u_blendMode;
    float u_opacity;
    float u_gammaValue;
    int u_comp;
    float u_mult;
};

struct main0_out
{
    float4 o_fragColor [[color(0)]];
};

struct main0_in
{
    float2 v_uv [[user(locn0)]];
};

static inline __attribute__((always_inline))
float4 _f8(thread const float4& _p0, constant float& u_gammaValue)
{
    return float4(pow(_p0.xyz, float3(u_gammaValue)), _p0.w);
}

static inline __attribute__((always_inline))
float _f2(thread const float& _p0, thread const float& _p1)
{
    return 1.0 - ((1.0 - _p0) * (1.0 - _p1));
}

static inline __attribute__((always_inline))
float3 _f3(thread const float3& _p0, thread const float3& _p1)
{
    float param = _p0.x;
    float param_1 = _p1.x;
    float param_2 = _p0.y;
    float param_3 = _p1.y;
    float param_4 = _p0.z;
    float param_5 = _p1.z;
    return float3(_f2(param, param_1), _f2(param_2, param_3), _f2(param_4, param_5));
}

static inline __attribute__((always_inline))
float3 _f4(thread const float3& _p0, thread const float3& _p1, thread const float& _p2)
{
    float3 param = _p0;
    float3 param_1 = _p1;
    return (_f3(param, param_1) * _p2) + (_p0 * (1.0 - _p2));
}

static inline __attribute__((always_inline))
float3 _f0(thread const float3& _p0, thread const float3& _p1)
{
    return fast::min(_p0 + _p1, float3(1.0));
}

static inline __attribute__((always_inline))
float3 _f1(thread const float3& _p0, thread const float3& _p1, thread const float& _p2)
{
    float3 param = _p0;
    float3 param_1 = _p1;
    return (_f0(param, param_1) * _p2) + (_p0 * (1.0 - _p2));
}

static inline __attribute__((always_inline))
float _f5(thread const float& _p0, thread const float& _p1)
{
    return _p0 + (_p1 * (1.0 - _p0));
}

static inline __attribute__((always_inline))
float4 _f6(thread const float4& _p0, thread const float4& _p1, constant int& u_blendMode, constant float& u_opacity)
{
    float3 _t0;
    if (u_blendMode == 0)
    {
        float3 param = _p0.xyz / float3(fast::max(_p0.w, 0.001000000047497451305389404296875));
        float3 param_1 = _p1.xyz / float3(fast::max(_p0.w, 0.001000000047497451305389404296875));
        float param_2 = u_opacity;
        _t0 = ((_p0.xyz * (1.0 - _p1.w)) + (_p1.xyz * (1.0 - _p0.w))) + (_f4(param, param_1, param_2) * (_p0.w * _p1.w));
    }
    else
    {
        float3 param_3 = _p0.xyz / float3(fast::max(_p0.w, 0.001000000047497451305389404296875));
        float3 param_4 = _p1.xyz / float3(fast::max(_p0.w, 0.001000000047497451305389404296875));
        float param_5 = u_opacity;
        _t0 = ((_p0.xyz * (1.0 - _p1.w)) + (_p1.xyz * (1.0 - _p0.w))) + (_f1(param_3, param_4, param_5) * (_p0.w * _p1.w));
    }
    float param_6 = _p0.w;
    float param_7 = _p1.w;
    return float4(_t0, _f5(param_6, param_7));
}

static inline __attribute__((always_inline))
float4 _f7(thread const float4& _p0, constant float& u_gammaValue)
{
    return float4(pow(_p0.xyz, float3(1.0 / u_gammaValue)), _p0.w);
}

fragment main0_out main0(main0_in in [[stage_in]], constant buffer_t& buffer, texture2d<float> u_inputTex [[texture(0)]], texture2d<float> u_blurTex [[texture(1)]], sampler u_inputTexSmplr [[sampler(0)]], sampler u_blurTexSmplr [[sampler(1)]])
{
    main0_out out = {};
    float4 param = u_inputTex.sample(u_inputTexSmplr, in.v_uv);
    float4 param_1 = u_blurTex.sample(u_blurTexSmplr, in.v_uv);
    float4 _289 = _f8(param_1, buffer.u_gammaValue);
    float4 _t4;
    if (buffer.u_comp == 1)
    {
        float4 param_2 = _f8(param, buffer.u_gammaValue);
        float4 param_3 = _289;
        _t4 = _f6(param_2, param_3, buffer.u_blendMode, buffer.u_opacity);
    }
    else
    {
        _t4 = _289 * buffer.u_opacity;
    }
    float4 param_4 = _t4 * buffer.u_mult;
    float4 _315 = fast::clamp(_f7(param_4, buffer.u_gammaValue), float4(0.0), float4(1.0));
    _t4 = _315;
    out.o_fragColor = _315;
    return out;
}

