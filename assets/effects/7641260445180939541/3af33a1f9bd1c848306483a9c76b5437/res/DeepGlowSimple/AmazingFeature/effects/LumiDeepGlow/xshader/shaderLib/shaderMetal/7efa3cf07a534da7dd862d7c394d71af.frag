#pragma clang diagnostic ignored "-Wmissing-prototypes"

#include <metal_stdlib>
#include <simd/simd.h>

using namespace metal;

struct buffer_t
{
    int u_blendMode;
    int u_tint;
    int u_tintMode;
    float3 u_tintColor;
    float u_tintMix;
    float u_srcOpacity;
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
float _f0(thread const float& _p0, thread const float& _p1)
{
    float _51;
    if (_p0 < 0.5)
    {
        _51 = (2.0 * _p0) * _p1;
    }
    else
    {
        _51 = 1.0 - ((2.0 * (1.0 - _p0)) * (1.0 - _p1));
    }
    return _51;
}

static inline __attribute__((always_inline))
float3 _f1(thread const float3& _p0, thread const float3& _p1)
{
    return ((float3(1.0) - (float3(2.0) * _p1)) * pow(_p0, float3(2.0))) + ((float3(2.0) * _p1) * _p0);
}

static inline __attribute__((always_inline))
float4 _f7(thread const float4& _p0)
{
    float _186 = fast::max(fast::max(_p0.x, _p0.y), _p0.z);
    if (_186 > 0.0)
    {
        return float4(_p0.xyz, _186);
    }
    else
    {
        return float4(0.0);
    }
}

static inline __attribute__((always_inline))
float _f3(thread const float& _p0, thread const float& _p1)
{
    return 1.0 - ((1.0 - _p0) * (1.0 - _p1));
}

static inline __attribute__((always_inline))
float3 _f4(thread const float3& _p0, thread const float3& _p1)
{
    float param = _p0.x;
    float param_1 = _p1.x;
    float param_2 = _p0.y;
    float param_3 = _p1.y;
    float param_4 = _p0.z;
    float param_5 = _p1.z;
    return float3(_f3(param, param_1), _f3(param_2, param_3), _f3(param_4, param_5));
}

static inline __attribute__((always_inline))
float3 _f2(thread const float3& _p0, thread const float3& _p1)
{
    return fast::min(_p0 + _p1, float3(1.0));
}

static inline __attribute__((always_inline))
float _f5(thread const float& _p0, thread const float& _p1)
{
    return (_p0 + _p1) - (_p0 * _p1);
}

static inline __attribute__((always_inline))
float4 _f6(thread const float4& _p0, thread const float4& _p1, constant int& u_blendMode)
{
    float3 _t0;
    if (u_blendMode == 0)
    {
        float3 param = _p0.xyz;
        float3 param_1 = _p1.xyz;
        _t0 = _f4(param, param_1);
    }
    else
    {
        float3 param_2 = _p0.xyz;
        float3 param_3 = _p1.xyz;
        _t0 = _f2(param_2, param_3);
    }
    float param_4 = _p0.w;
    float param_5 = _p1.w;
    return float4(_t0, _f5(param_4, param_5));
}

fragment main0_out main0(main0_in in [[stage_in]], constant buffer_t& buffer, texture2d<float> u_blurTex [[texture(0)]], texture2d<float> u_inputTex [[texture(1)]], sampler u_blurTexSmplr [[sampler(0)]], sampler u_inputTexSmplr [[sampler(1)]])
{
    main0_out out = {};
    float4 _t3 = u_blurTex.sample(u_blurTexSmplr, in.v_uv);
    float4 _219 = u_inputTex.sample(u_inputTexSmplr, in.v_uv);
    if (buffer.u_tint == 1)
    {
        float4 _t5;
        _t5.w = _t3.w;
        if (buffer.u_tintMode == 0)
        {
            float3 _247 = buffer.u_tintColor * dot(_t3.xyz, float3(0.2989999949932098388671875, 0.58700001239776611328125, 0.114000000059604644775390625));
            _t5.x = _247.x;
            _t5.y = _247.y;
            _t5.z = _247.z;
        }
        else
        {
            if (buffer.u_tintMode == 1)
            {
                float3 _262 = _t3.xyz * buffer.u_tintColor;
                _t5.x = _262.x;
                _t5.y = _262.y;
                _t5.z = _262.z;
            }
            else
            {
                if (buffer.u_tintMode == 2)
                {
                    float3 _t8 = pow(_t3.xyz, float3(1.0));
                    float3 _t9 = pow(buffer.u_tintColor, float3(1.0));
                    float param = _t8.x;
                    float param_1 = _t9.x;
                    float param_2 = _t8.y;
                    float param_3 = _t9.y;
                    float param_4 = _t8.z;
                    float param_5 = _t9.z;
                    float3 _308 = float3(_f0(param, param_1), _f0(param_2, param_3), _f0(param_4, param_5));
                    _t5.x = _308.x;
                    _t5.y = _308.y;
                    _t5.z = _308.z;
                }
                else
                {
                    float4 _316 = _t3;
                    float3 _318 = fast::min(_316.xyz, float3(1.0));
                    _t3.x = _318.x;
                    _t3.y = _318.y;
                    _t3.z = _318.z;
                    float3 param_6 = _t3.xyz;
                    float3 param_7 = buffer.u_tintColor;
                    float3 _330 = _f1(param_6, param_7);
                    _t5.x = _330.x;
                    _t5.y = _330.y;
                    _t5.z = _330.z;
                }
            }
        }
        _t3 = mix(_t3, _t5, float4(buffer.u_tintMix));
    }
    float4 param_8 = _t3;
    float4 _346 = _f7(param_8);
    _t3 = _346;
    float4 param_9 = _219;
    float4 param_10 = _346;
    float4 _353 = _t3;
    float4 _358 = mix(_353, _f6(param_9, param_10, buffer.u_blendMode), float4(buffer.u_srcOpacity));
    _t3 = _358;
    out.o_fragColor = _358;
    return out;
}

