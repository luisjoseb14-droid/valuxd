#pragma clang diagnostic ignored "-Wmissing-prototypes"

#include <metal_stdlib>
#include <simd/simd.h>

using namespace metal;

// Implementation of the GLSL radians() function
template<typename T>
inline T radians(T d)
{
    return d * T(0.01745329251);
}

struct buffer_t
{
    float u_gammaValue;
    float u_stepsInt;
    float u_angle;
    float2 u_aspect;
    float u_rotate;
    float u_steps;
    float u_stride;
    float u_sigma;
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
float2 _f4(thread const float2& _p0, thread const float& _p1)
{
    float _186 = sin(_p1);
    float _189 = cos(_p1);
    return float2x2(float2(_189, -_186), float2(_186, _189)) * _p0;
}

static inline __attribute__((always_inline))
float _f2(thread const float& _p0, thread const float& _p1)
{
    return exp((-(_p0 * _p0)) / ((2.0 * _p1) * _p1)) / (2.5066282749176025390625 * _p1);
}

static inline __attribute__((always_inline))
float3 _f0(thread const float3& _p0, constant float& u_gammaValue)
{
    return float3(pow(_p0, float3(u_gammaValue)));
}

static inline __attribute__((always_inline))
float3 _f3(thread const float& _p0, thread const float2& _p1, thread const float& _p2, thread const float& _p3, constant float& u_gammaValue, texture2d<float> u_inputTex, sampler u_inputTexSmplr, thread float2& v_uv, constant float& u_stepsInt)
{
    float param = 0.0;
    float param_1 = _p3;
    float _t0 = _f2(param, param_1);
    float3 param_2 = u_inputTex.sample(u_inputTexSmplr, v_uv).xyz;
    float _97 = _t0;
    float3 _t2 = float3(0.0);
    int _105 = int(_p0);
    for (int _t4 = 1; _t4 < 32; _t4 += int(u_stepsInt))
    {
        if (_t4 >= _105)
        {
            break;
        }
        float _125 = float(_t4);
        float param_3 = (_125 / _p0) * 15.0;
        float param_4 = _p3;
        float _135 = _f2(param_3, param_4);
        float2 _141 = (_p1 * _125) * _p2;
        float3 param_5 = u_inputTex.sample(u_inputTexSmplr, (v_uv + _141)).xyz;
        float3 param_6 = u_inputTex.sample(u_inputTexSmplr, (v_uv - _141)).xyz;
        _t2 += ((_f0(param_5, u_gammaValue) + _f0(param_6, u_gammaValue)) * _135);
        _t0 += (_135 * 2.0);
    }
    return (_t2 + (_f0(param_2, u_gammaValue) * _97)) / float3(_t0);
}

static inline __attribute__((always_inline))
float3 _f1(thread const float3& _p0, constant float& u_gammaValue)
{
    return float3(pow(_p0, float3(1.0 / u_gammaValue)));
}

fragment main0_out main0(main0_in in [[stage_in]], constant buffer_t& buffer, texture2d<float> u_inputTex [[texture(0)]], sampler u_inputTexSmplr [[sampler(0)]])
{
    main0_out out = {};
    float _212 = (buffer.u_angle / 180.0) * 3.141592502593994140625;
    float2 param = float2(cos(_212), sin(_212)) / buffer.u_aspect;
    float param_1 = radians(buffer.u_rotate);
    float param_2 = buffer.u_steps;
    float2 param_3 = _f4(param, param_1);
    float param_4 = buffer.u_stride;
    float param_5 = buffer.u_sigma;
    float3 param_6 = _f3(param_2, param_3, param_4, param_5, buffer.u_gammaValue, u_inputTex, u_inputTexSmplr, in.v_uv, buffer.u_stepsInt);
    out.o_fragColor = float4(_f1(param_6, buffer.u_gammaValue), 1.0);
    return out;
}

